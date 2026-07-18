# Live Bridge Media Trace (17.07.2026)

## Purpose
When images arrive via Hermes Bridge but `[PHOTO]` never appears in main_waha.py logs (even after the `_media` fix), trace one message end-to-end with minimal invasive prints.

## Allowed files ONLY
- `bridge_wrapper.py`
- `main_waha.py`

**Never touch** `bridge.js`, `bridge_helpers.js`, or any JS.

## Minimal debug prints to insert

### bridge_wrapper.py (in _patched_requests_post, inside the bridge_msgs loop)
```python
print(f"[BRIDGE DEBUG] hasMedia={m.get('hasMedia')}, mediaType={m.get('mediaType')}, body={str(m.get('body',''))[:60]}", flush=True)
...
if m.get("hasMedia"):
    ...
    rec["message"]["_media"] = media
print(f"[WRAPPER DEBUG] _media present: {'_media' in rec.get('message', {})} for id {rec['key']['id'][:12]}", flush=True)
```

### main_waha.py (sandbox poll loop, right after the existing [MSG] line)
```python
print(f"[MSG] {mid[:12]}...", flush=True)
has_media = bool(msg.get("_media") and msg.get("_media").get("mediaType") == "image")
print(f"[MAIN DEBUG] media_meta matched: {has_media} for {mid[:12]}", flush=True)
```

(Use a temp variable for the bool expression to avoid f-string backslash syntax error.)

## Execution sequence
1. Add the three prints above (use `sed` or targeted patch — keep changes <5 lines total).
2. `pkill -f main_waha.py || true`
3. `cd /home/hermes-workspace/Alikhan-migration/bot && nohup python3 main_waha.py > /tmp/bot.log 2>&1 &`
4. Trigger via bridge:
   ```bash
   curl -X POST http://127.0.0.1:3000/send \
     -H "Content-Type: application/json" \
     -d '{"chatId":"120363179621030401@g.us","message":"DEBUG test"}'
   ```
5. `sleep 10 && tail -80 /tmp/bot.log`
6. Look for message IDs starting with `3EB0*` — these are the ones that went through the full pipeline.

## Expected trace (healthy run)
```
[BRIDGE DEBUG] hasMedia=True, mediaType=image, body=...
[WRAPPER DEBUG] _media present: True for id 3EB0F2FB62...
[MSG] 3EB0F2FB62...
[MAIN DEBUG] media_meta matched: True for 3EB0F2FB62...
[PROD PHOTO] Saved: ...
```

## Post-run cleanup
Remove the three temporary prints immediately after the trace succeeds. Commit the clean state.

## Why this pattern
- E2E unit test passes but live bot fails → the difference is almost always in the live bridge event shape or the prod listener vs sandbox poll path.
- The prints are the minimal set that covers: raw bridge event → wrapper construction → main_waha decision point.
- Using `/tmp/bot.log` + nohup keeps the live session clean while capturing the trace.