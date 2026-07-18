# Document Extractor Service — Setup & Troubleshooting

**Service:** `document_extract_server.py` on port 8099
**Location:** `/root/doc_import/scripts/`
**Env file:** `/root/doc_import/document_extract.env`

## Architecture

```
POST :8099/extract-document {"base64": "...", "fileName": "...", "mimetype": "..."}
  → saves base64 to FILES_DIR/{messageId}_{filename}
  → subprocess: extract_document_text.py {filepath}
  → reads stdout → returns {"ok": true, "text": "...", "pages": N}
```

## Startup (correct)

```python
import subprocess, os
env = os.environ.copy()
with open('/root/doc_import/document_extract.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            env[k] = v.strip('"').strip("'")
env['PYTHONDONTWRITEBYTECODE'] = '1'
subprocess.Popen(
    ['/root/doc_import/venv/bin/python', '/tmp/extract_server.py'],
    env=env
)
```

## Critical Pitfalls

### 1. XAI_KEY not in environment
Without XAI_API_KEY, the extractor silently fails when processing scan PDFs (500 error). The key MUST be passed via environment, not just in the env file — the server inherits env but the subprocess.run() inside the server does NOT automatically inherit from the server's parent. Use explicit env passthrough in the startup.

### 2. FILES_DIR permission
Default: `/root/doc_import/files/` — owned by root, hermes-user cannot write → 500.
**Fix:** Patch `FILES_DIR = Path("/tmp/doc_import/files")` in server script.

### 3. Port already in use
Previous `python3 -m http.server 8099` blocker — always kill old processes first:
```bash
fuser -vk 8099/tcp
```

### 4. extract_document_text.py call
Server calls: `subprocess.run([PYTHON, EXTRACT_SCRIPT, str(saved_path)])` — ONE argument, reads stdout. The script writes JSON to stdout, NOT to an output file.

## Health Check

```bash
curl http://127.0.0.1:8099/health
# → {"ok": true}
```

## Test end-to-end

```python
# 1. Get document message from Evolution API
body = json.dumps({"where": {"key": {"remoteJid": GROUP}}, "page": 1, "limit": 5}).encode()
req = urllib.request.Request('http://127.0.0.1:8080/chat/findMessages/alikhan', data=body, method='POST')
req.add_header('apikey', evo_key)
# Find message with documentMessage...

# 2. Get base64
body2 = json.dumps({"message": full_message}).encode()
req2 = urllib.request.Request('http://127.0.0.1:8080/chat/getBase64FromMediaMessage/alikhan', data=body2, method='POST')
req2.add_header('apikey', evo_key)
# Returns {"base64": "...", "fileName": "...", "mimetype": "..."}

# 3. Extract text
body3 = json.dumps({"base64": b64, "fileName": fname, "mimetype": mime}).encode()
req3 = urllib.request.Request('http://127.0.0.1:8099/extract-document', data=body3, method='POST')
# Returns {"ok": true, "text": "...", "pages": N}
```
