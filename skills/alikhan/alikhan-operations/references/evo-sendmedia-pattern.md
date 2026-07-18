# Evolution API sendMedia — working pattern

**Date:** 2026-07-14
**Bug:** Evolution API `/message/sendMedia` returns 500 "Unexpected field" on multipart form data. HTTP 201 accept но file не доходит или 500 на неправильный формат.

## Working: JSON + base64

```python
import httpx, asyncio, base64

async def send_document(filepath, filename, group_id="120363179621030401@g.us"):
    with open(filepath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()

    url = "http://127.0.0.1:8080/message/sendMedia/alikhan"
    headers = {"apikey": "SuperSecretKey_Grok2026_!@#", "Content-Type": "application/json"}
    payload = {
        "number": group_id,
        "mediatype": "document",
        "fileName": filename,
        "media": b64
    }
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        # HTTP 201 = accepted, HTTP 500 = wrong format
        return r.status_code, r.json()
```

## NOT working

- `curl -F "media=@file"` — multipart form → 500 "Unexpected field"
- `curl -d '{"media": "BASE64"}'` — base64 too large for shell → "Argument list too long"
- `httpx files={"media": (...)}` — multipart form → 500

## Key: base64 inside JSON body

Evolution API expects `media` field as base64-encoded string INSIDE the JSON payload, not as a multipart file attachment.
