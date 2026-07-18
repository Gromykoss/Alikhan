# Real Photo Sourcing via Evolution API

When `bot_memory_messages` contains wrong/outdated WA message IDs (after SIM_DATE flood or seen-clearing), use Evolution API to find the real photos.

## API: findMessages

```
POST http://127.0.0.1:8080/chat/findMessages/alikhan
Headers: apikey, Content-Type: application/json
Body: {"where": {"key": {"remoteJid": "SANDBOX_ID"}}, "limit": 50, "page": 1}
```

Response: `{"messages": {"total": N, "pages": M, "currentPage": P, "records": [...]}}`

## Filtering

```python
records = data['messages']['records']
for msg in records:
    if not isinstance(msg, dict): continue
    msg_data = msg.get('message') or {}
    if 'imageMessage' not in msg_data: continue
    
    k = msg.get('key', {}) or {}
    mid = k.get('id', '')
    fromMe = k.get('fromMe', False)
    ts = msg.get('messageTimestamp', 0)
    caption = msg_data['imageMessage'].get('caption', '')
    
    # Filter: user-sent, today's timestamp range, matching caption
    if not fromMe and ts > TODAY_MIN_TS:
        real_photos.append({'id': mid, 'ts': ts, 'caption': caption})
```

## Updating DB + ЕЖО

```python
# 1. Delete old entries
DELETE FROM bot_memory_messages WHERE message_type='image' AND DATE(created_at)='YYYY-MM-DD';

# 2. Insert real ones
for mid in real_ids:
    INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
    VALUES (SANDBOX, 'user', 'user', 'image', mid, 
            json_build_object('building', 'Общежитие', 'msg_id', mid), 
            'YYYY-MM-DD HH:MM:SS+00');

# 3. Download photos from Evolution API
GET /chat/getBase64FromMediaMessage/alikhan
Body: {"message": {"key": {"id": "WA_MSG_ID"}}}

# 4. Insert into ЕЖО via openpyxl
from openpyxl.drawing.image import Image as XI
img = XI(io.BytesIO(base64.b64decode(b64_data)))
img.width = 355; img.height = 267
ws.add_image(img, f"A{row}")
```

## Pitfall: content column not UNIQUE

`bot_memory_messages.content` can't have a UNIQUE constraint (some values exceed 8KB — full file paths). Use SELECT-then-INSERT pattern instead.

## Timestamp filtering

Photos from different days have different `messageTimestamp` ranges. Today's photos will cluster in a tight timestamp range (~1782882928-1782883022 for 2026-07-01 session). Use `min(ts)` + `max(ts)` from the first few results to establish the window.
