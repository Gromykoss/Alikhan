# WAHA API Reference — Discovered 2026-06-23

## Container

```bash
docker run -d --name waha --network evolution_api_default -p 3000:3000 \
  --restart unless-stopped --dns 8.8.8.8 \
  -e WHATSAPP_DEFAULT_ENGINE=NOWEB \
  -e WAHA_API_KEY=*** \
  devlikeapro/waha:latest
```

## Session Lifecycle

### Create (with NOWEB store enabled)
```bash
curl -s -X POST http://127.0.0.1:3000/api/sessions \
  -H "X-Api-Key: waha123" -H "Content-Type: application/json" \
  -d '{"name":"alikhan","config":{"engine":"NOWEB","noweb":{"store":{"enabled":true,"fullSync":true}}}}'
```
Store MUST be enabled at CREATE time. Start-time config is ignored.

### Start session
```bash
curl -s -X POST http://127.0.0.1:3000/api/sessions/alikhan/start \
  -H "X-Api-Key: waha123" -H "Content-Type: application/json"
```

### Stop session
```bash
curl -s -X POST http://127.0.0.1:3000/api/sessions/alikhan/stop \
  -H "X-Api-Key: waha123"
```

### Get session status
```bash
curl -s http://127.0.0.1:3000/api/sessions/alikhan -H "X-Api-Key: waha123"
# Returns: {"name":"alikhan","status":"WORKING","me":{"id":"79958974452@c.us","pushName":"Алихан"},"engine":{"engine":"NOWEB"}}
```

## Pairing Codes (when QR fails)

```bash
# Request pairing code
curl -s -X POST http://127.0.0.1:3000/api/alikhan/auth/request-code \
  -H "X-Api-Key: waha123" -H "Content-Type: application/json" \
  -d '{"phoneNumber":"79958974452"}'
# Returns: {"code":"XXXX-XXXX"}
```

Only works when session status is `SCAN_QR_CODE`. Session must be freshly created and started.

## Message Operations

### Send text (CRITICAL: must include "session" field)
```bash
curl -s -X POST http://127.0.0.1:3000/api/sendText \
  -H "X-Api-Key: waha123" -H "Content-Type: application/json" \
  -d '{"session":"alikhan","chatId":"120363179621030401@g.us","text":"hello"}'
```
Returns 201 with message key. Silent failure (401) if `session` field missing.

### Get messages (requires NOWEB store)
```bash
curl -s http://127.0.0.1:3000/api/alikhan/chats/120363179621030401@g.us/messages?limit=3 \
  -H "X-Api-Key: waha123"
```
Returns `[]` (empty) if store not enabled. Returns `[{id,body,fromMe,from,timestamp}]` when store is enabled.

### Message object format
```json
{
  "id": "false_120363179621030401@g.us_XXXX",
  "body": "text",
  "fromMe": false,
  "from": "120363179621030401@g.us",
  "timestamp": 1782186832,
  "_data": {...}
}
```

## Known Issues

1. **Store config only works at CREATE**: Recreating session requires new pairing code
2. **401 silent failure**: Wrong API key returns 401 with no error in bot logs
3. **DNS**: Always use `--dns 8.8.8.8` — systemd-resolved breaks Docker DNS
4. **Port 3000**: Only port reliably accessible from external devices on this VPS
