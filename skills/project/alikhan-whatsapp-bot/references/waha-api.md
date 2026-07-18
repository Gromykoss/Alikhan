# WAHA WhatsApp HTTP API — Quick Reference

## Deploy (Docker)
```bash
docker run -d --name waha -p 3000:3000 --restart unless-stopped \
  -e WHATSAPP_DEFAULT_ENGINE=NOWEB \
  -e WAHA_API_KEY=*** \
  devlikeapro/waha:latest
```

## API Endpoints (with X-Api-Key header)

### Session management
- `POST /api/sessions` — create session `{"name":"alikhan"}`
- `POST /api/sessions/:name/start` — start session
- `POST /api/sessions/:name/stop` — stop session
- `GET /api/sessions/:name` — get session status
- `DELETE /api/sessions/:name` — delete session

### Authentication / QR Code
- `GET /api/:session/auth/qr` — QR as JSON `{"qr":"base64..."}`
- `GET /api/:session/auth/qr?format=image` — QR as PNG image
- `GET /api/:session/auth/qr?format=raw` — QR as raw base64 string
- `POST /api/:session/auth/request-code` — request pairing code (phone number required)

### Messaging
- `POST /api/sendText` — send text `{"chatId":"120363...@g.us","text":"hello"}`
- `POST /api/sendImage` — send image (base64 or URL)
- `POST /api/sendFile` — send document

### Webhooks
Configure per-session to POST incoming messages to your bot's endpoint.

### Status codes
- `STARTING` — session is initializing
- `WORKING` — connected, ready
- `STOPPED` — not running
- `FAILED` — error

## Engine: NOWEB
- No browser/Puppeteer needed
- WebSocket-based (similar to Baileys)
- Supports multi-device
- ~200MB RAM

## Known issues
- QR code regenerates every ~30 seconds (WAHA uses short-lived QR)
- Session persists across container restarts (data in /app/data)
- Profile name loads 5-10 seconds after connection
