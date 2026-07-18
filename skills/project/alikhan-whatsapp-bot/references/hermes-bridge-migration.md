# Hermes Bridge Migration — Evolution API → Native Bridge

Date: 15.07.2026

## Why migrate

| | Evolution API | Hermes Bridge |
|---|---|---|
| Containers | 3 Docker (api, redis, postgres) | 0 — built into gateway |
| Failure points | Docker + API + Python = 3 | Bridge → Python = 2 |
| Maintenance | Separate updates, DB collation, Redis replica | Auto with `hermes update` |
| Message recording | age gate bugs, save_message after filter | `_record_group_message_sync` — unconditional JSONL |

## Single-line patch (bridge.js)

**File:** `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js`  
**Line:** 637

```diff
- if (WHATSAPP_DM_POLICY !== 'pairing' && !matchesAllowedUser(senderId, ALLOWED_USERS, SESSION_DIR)) {
+ if (!isGroup && WHATSAPP_DM_POLICY !== 'pairing' && !matchesAllowedUser(senderId, ALLOWED_USERS, SESSION_DIR)) {
```

**Effect:** Bridge forwards messages from ALL group members, not just whitelisted users.  
**Why safe:** Python adapter already handles group-level policy (`_is_group_allowed`) — bridge.js sender filtering is redundant for groups.

## Pairing procedure

1. **Unlink from Evolution API** (if same number): WhatsApp → Settings → Linked Devices → tap device → Log Out
2. **Start bridge in pair-json mode:**
   ```bash
   cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge
   WHATSAPP_MODE=bot node bridge.js --session ~/.hermes/sessions/whatsapp --pair-json
   ```
3. **Extract QR string from JSON output:**
   ```python
   import re, json
   with open('/tmp/bridge-output.txt', 'rb') as f:
       raw = f.read()
   match = re.search(rb'\{"ts":\d+,"event":"qr","qr":"([^"]+)"\}', raw)
   qr_str = match.group(1).decode()
   ```
4. **Generate QR PNG:**
   ```python
   import qrcode
   img = qrcode.make(qr_str)
   img.save('/tmp/whatsapp-qr.png')
   ```
5. **Scan QR** with WhatsApp on phone (Linked Devices)
6. **Verify:** `curl http://127.0.0.1:3000/health` → `{"status":"connected"}`

## Bridge REST API

Base: `http://127.0.0.1:3000`

| Method | Endpoint | Description | Payload |
|--------|----------|-------------|---------|
| GET | `/health` | Connection status | — |
| GET | `/messages` | Poll new messages | — |
| POST | `/send` | Send text | `{chatId, message}` |
| POST | `/send-media` | Send file | `{chatId, filePath, mediaType, caption?}` |
| GET | `/chat/:id` | Chat/group info | — |

## Evolution API → Bridge mapping for Alikhan

| Operation | Evolution API | Bridge API |
|-----------|--------------|------------|
| Poll messages | `POST /chat/findMessages/alikhan` (paginated) | `GET /messages` (queue drain) |
| Send text | `POST /message/sendText/alikhan` | `POST /send` |
| Send document | `POST /message/sendMedia/alikhan` (base64) | `POST /send-media` (filePath) |
| Health | `GET /` | `GET /health` |
| Delete message | `DELETE /chat/deleteMessageForEveryone/alikhan` | Not available |

## Pitfalls

1. **Bridge restart blocked inside Hermes.** `hermes gateway restart` from SSH, not from agent terminal.
2. **`hermes gateway pair` doesn't exist** in this Hermes version. Use `--pair-json` mode directly.
3. **WhatsApp: one number = one session.** Evolution API and Hermes bridge can't share the same number simultaneously.
4. **Migration order matters:** patch bridge.js → pair WhatsApp → migrate main_waha.py → stop Evolution API. Don't stop Evolution API before code migration is ready.
