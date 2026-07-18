# Bridge → Wrapper → Bot Media Flow (v3 — 17.07.2026)

## Flow

```
WhatsApp → Baileys → bridge.js → extractBridgeEvent() → /messages → 
  bridge_wrapper::_fetch_and_buffer() → _patched_requests_post → 
  main_waha.py poll loop
```

## Key detail: media metadata

**bridge.js** `extractBridgeEvent()` (bridge_helpers.js:358):
```js
if (messageContent.imageMessage) {
    body = item.caption || '';       // EMPTY for captionless images
    hasMedia = true;
    mediaType = 'image';
    // downloads to IMAGE_CACHE_DIR (/tmp/hermes-media-cache/)
}
```

**bridge_wrapper.py** `_patched_requests_post` (line 83-96):
```python
rec = {
    "message": {"conversation": m.get("body", "")},  # may be ""
}
if m.get("hasMedia"):  # True for images
    rec["message"]["_media"] = {
        "mediaType": m.get("mediaType", ""),  # "image"
        "fileName": m.get("fileName", ""),    # caption from WhatsApp
        "mediaUrls": m.get("mediaUrls", []),  # local cache paths
    }
```

## What broke (17.07.2026)

**main_waha.py** photo handler checked `msg.get("imageMessage")` — Evolution API format that NEVER matched bridge messages. Fix: check `msg.get("_media")` with `mediaType == "image"`.

**Sandbox** (line 526 → fixed): `_media` with type "image" → save to DB
**Production** (line 390 → fixed): `_media` with type "image" → save to DB

**Documents in prod** (line 416, NOT changed): still uses `documentMessage` + `getBase64FromMediaMessage`. Bridge returns `body: ""` for documents. The patched `_patched_urlopen` returns empty base64. Production document saving doesn't work but user said "все работает кроме фото" — not touched.

## Debugging Pitfalls

### 5-minute age gate (main_waha.py:502-507)
```python
if now_ts - msg_ts > 300:
    seen.add(mid); continue
```
Messages >5 min old are skipped. If bot restart + production first-run backfill takes >5 min, incoming sandbox photos may be discarded before the poll loop reaches them. Symptom: photos arrive (bridge cache has files) but no `[PHOTO]` in log.

### E2E testing before user test
After any media pipeline change, test end-to-end programmatically:
```python
# Simulate bridge event → wrapper → bot handler
bridge_msg = {
    "hasMedia": True, "mediaType": "image",
    "fileName": "test.jpg", "body": "",
    "chatId": "120363179621030401@g.us"
}
rec = build_wrapper_record(bridge_msg)  # re-create wrapper logic
media_meta = rec["message"].get("_media")
assert media_meta and media_meta["mediaType"] == "image"
```
Do NOT ask user to test raw code. Fix → programmatic verify → THEN user test.

## Verification

After bot restart, photo should appear as `[PHOTO] Saved: ...` in sandbox log, `[PROD PHOTO] Saved: ...` in production log. NOT `[PROD TEXT] Saved: [image received]`.
