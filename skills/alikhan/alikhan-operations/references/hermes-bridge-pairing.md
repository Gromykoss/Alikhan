# Hermes WhatsApp Bridge Pairing — 15.07.2026

## What this is

Procedure for pairing WhatsApp with the native Hermes bridge (Baileys-based), replacing Evolution API transport.

## When to use

- First-time Hermes → WhatsApp pairing
- After `docker restart evolution-api` breaks the session (pitfall #19)
- After unlinking WhatsApp from a previous session

## Step-by-step pairing

### 1. Unlink previous session (if any)

Phone: WhatsApp → Settings → Linked Devices → tap device → **Log Out**

Or: delete session files:
```bash
rm -rf ~/.hermes/sessions/whatsapp/
```

### 2. Apply bridge patches

**Patch A (mandatory):** Allow non-whitelisted group members:
```bash
# bridge.js line 637 — add !isGroup && before the allowlist check
```
```diff
- if (WHATSAPP_DM_POLICY !== 'pairing' && !matchesAllowedUser(...)) {
+ if (!isGroup && WHATSAPP_DM_POLICY !== 'pairing' && !matchesAllowedUser(...)) {
```

**Patch B (optional):** Save QR string for PNG generation:
```diff
+ const fs = require('fs');
+ try { fs.writeFileSync('/tmp/whatsapp-qr.txt', qr, 'utf8'); } catch(e) {}
```

### 3. Start the bridge

```bash
cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge
WHATSAPP_MODE=bot node bridge.js --session ~/.hermes/sessions/whatsapp
```

QR code appears as ASCII art in terminal. Scan with phone within 20 seconds.

### 4. If QR won't scan (ASCII not scannable from screenshot)

Use `--pair-json` mode to get raw QR string, then generate PNG:
```bash
cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge
WHATSAPP_MODE=bot node bridge.js --session ~/.hermes/sessions/whatsapp --pair-json
```

Extract QR string from JSON output:
```python
import json, qrcode, re

with open('/tmp/bridge-output.txt') as f:
    raw = f.read()

match = re.search(r'"qr":"([^"]+)"', raw)
if match:
    qr_str = match.group(1)
    img = qrcode.make(qr_str)
    img.save('/tmp/whatsapp-qr.png')
```

**Deliver QR to Telegram:** Use `vision_analyze` — the image is attached to the conversation and visible to the user. Data URLs and MEDIA: prefix do NOT work for Telegram delivery.

### 5. Verify connection

```bash
curl -s http://127.0.0.1:3000/health
# {"status":"connected","queueLength":0,...}
```

## Bridge API endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/messages` | Poll new messages (returns array, empties queue) |
| POST | `/send` | Send text `{chatId, message}` |
| POST | `/send-media` | Send file `{chatId, filePath, mediaType, caption, fileName}` |
| GET | `/chat/:id` | Chat info |
| GET | `/health` | Connection status |

## Pitfalls

1. **QR expires in ~20 seconds.** Generate fresh QR immediately before scanning.
2. **Cannot restart Hermes gateway from inside Hermes.** The `hermes gateway restart` command kills the agent process. Run it from a separate SSH terminal.
3. **Port 3000 conflict.** Only one bridge instance at a time. Use `fuser -k 3000/tcp` to free the port.
4. **WhatsApp mode must be 'bot'.** `WHATSAPP_MODE=bot` — self-chat mode rejects group messages.
5. **ASCII QR is NOT scannable from screenshots.** Use `--pair-json` + Python qrcode to generate a real PNG.
6. **Evolution API uses the SAME WhatsApp number.** You can't have both Hermes bridge and Evolution API connected to the same number. Stop Evolution API first.
7. **Patches reset on `hermes update`.** Re-apply after update. See `references/hermes-bridge-migration.md` for the auto-reapply hook.
