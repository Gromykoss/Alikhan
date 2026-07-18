# Redis + sendMedia Fix (2026-07-13)

## Problem
Evolution API documents (.xlsx) not arriving in WhatsApp despite HTTP 201 responses. Text and images work fine.

## Root Cause
Two issues compounded:

### 1. No response checking in sendMedia calls
`main_waha.py` used bare `requests.post(sendMedia)` without checking response. Bot always said "отправлен" regardless of actual delivery.

**Fix:** `_send_document(chat_id, filepath, filename)` helper in `main_waha.py`:
```python
def _send_document(chat_id, filepath, filename=None):
    with open(filepath, "rb") as f:
        b64_enc = base64.b64encode(f.read()).decode()
    r = requests.post(f"{EVO}/message/sendMedia/alikhan",
        json={"number": chat_id, "mediatype": "document", "media": b64_enc,
              "fileName": filename or os.path.basename(filepath)},
        headers={"apikey": KEY}, timeout=30)
    if r.status_code in (200, 201):
        print(f"[SEND OK] {filename}")
        return True
    else:
        print(f"[SEND FAIL] {filename}: HTTP {r.status_code} — {r.text[:200]}")
        return False
```

### 2. Redis in slave read-only mode
Evolution API container had Redis configured as slave of external server `175.24.232.83:26619`. Master was down, Redis stuck in read-only. Evolution couldn't write media session state.

**Diagnostic:**
```bash
docker exec evolution-redis redis-cli INFO replication | grep role
# Expected: role:master
# Got: role:slave
```

**Fix:**
```bash
docker exec evolution-redis redis-cli SLAVEOF NO ONE
```

**Verification:**
```bash
docker exec evolution-redis redis-cli INFO replication | grep role
# Should now show: role:master
```

### Verification
After both fixes:
1. Bot properly logs send failures
2. Documents arrive in WhatsApp
3. Redis shows master role
