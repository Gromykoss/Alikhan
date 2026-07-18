# Production Group Listener — Code Pattern

Complete code for adding a passive WhatsApp group listener to `main_waha.py`.
Pattern applied 2026-07-08 for the Alikhan WhatsApp bot (ТЗРК Джеруй).

## Full implementation

Insert after the calendar reminder thread (line 192) and before the main loop:

```python
PRODUCTION = "120363400682390076@g.us"

# ── Production group listener (photos, documents, text — no replies) ──
def production_listener_loop():
    """Background thread: poll production group, save media, never reply."""
    print(f"[PROD] Listener started for {PRODUCTION}", flush=True)
    prod_seen = set()
    while True:
        try:
            r = requests.post(f"{EVO}/chat/findMessages/alikhan",
                json={"where": {"key": {"remoteJid": PRODUCTION}}, "page": 1, "limit": 5},
                headers={"apikey": KEY}, timeout=15)
            msgs = r.json().get("messages", {}).get("records", [])
            for m in msgs:
                mid = m["key"]["id"]
                if mid in prod_seen or m["key"].get("fromMe"):
                    continue
                msg_ts = m.get("messageTimestamp", 0)
                if int(time.time()) - msg_ts > 600:
                    prod_seen.add(mid)
                    continue
                prod_seen.add(mid)
                msg = m.get("message", {})
                caption = msg.get("imageMessage", {}).get("caption", "") or \
                          msg.get("documentMessage", {}).get("fileName", "") or ""
                
                # Photo
                img_msg = msg.get("imageMessage")
                if img_msg:
                    cap = img_msg.get("caption", "")
                    building = None
                    for tag in ["АБК", "Общежитие", "Галерея", "Общий план"]:
                        if tag.lower() in cap.lower():
                            building = tag
                            break
                    # Save to DB (dedup by msg_id)
                    from db import get_conn
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("SELECT 1 FROM bot_memory_messages WHERE content = %s", (mid,))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (PRODUCTION, "user", "user", "image", mid,
                             json.dumps({"building": building or "без тег", "msg_id": mid}),
                             datetime.now()))
                        conn.commit()
                    conn.close()
                    continue

                # Document
                doc_msg = msg.get("documentMessage") or \
                          msg.get("documentWithCaptionMessage", {}).get("message", {}).get("documentMessage")
                if doc_msg:
                    payload = {"message": m}
                    req = urllib.request.Request(f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
                        data=json.dumps(payload).encode(),
                        headers={"apikey": KEY, "Content-Type": "application/json"})
                    resp = urllib.request.urlopen(req, timeout=60)
                    result = json.loads(resp.read().decode())
                    b64 = result.get("base64", "")
                    fname = result.get("fileName", doc_msg.get("fileName", "document"))
                    if b64:
                        from db import get_conn
                        conn = get_conn(); cur = conn.cursor()
                        cur.execute("SELECT 1 FROM bot_memory_messages WHERE content = %s", (mid,))
                        if not cur.fetchone():
                            cur.execute(
                                "INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                (PRODUCTION, "user", "user", "document", fname,
                                 json.dumps({"msg_id": mid, "file_name": fname}),
                                 datetime.now()))
                            conn.commit()
                        conn.close()
                    continue

                # Text — save + QA parse
                text = msg.get("conversation", "") or \
                       msg.get("extendedTextMessage", {}).get("text", "")
                if text:
                    from db import get_conn
                    conn = get_conn(); cur = conn.cursor()
                    cur.execute("SELECT 1 FROM bot_memory_messages WHERE content = %s", (mid,))
                    if not cur.fetchone():
                        cur.execute(
                            "INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (PRODUCTION, "user", "user", "text", text,
                             json.dumps({"msg_id": mid}),
                             datetime.now()))
                        conn.commit()
                        # Run QA parser
                        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                        from qa import parse_qa
                        parse_qa(PRODUCTION, text)
                    conn.close()
                    continue
        except Exception as e:
            print(f"[PROD LISTENER ERR] {e}", flush=True)
        time.sleep(10)

threading.Thread(target=production_listener_loop, daemon=True).start()
```

## Verification

```bash
# After restart, log should show:
tail -5 /tmp/alikhan.log
# [PROD] Listener started for 120363400682390076@g.us

# Check production messages in DB (after new messages arrive):
docker exec evolution-postgres psql -U evolution -d evolution_db -c \
  "SELECT message_type, LEFT(content,40), created_at FROM bot_memory_messages WHERE chat_id='120363400682390076@g.us' ORDER BY created_at DESC LIMIT 10"
```

## Pitfalls

- **Production group ID must match** `120363400682390076@g.us` — wrong ID = silent failure (no error, just empty results)
- **Separate `prod_seen` set is critical** — sharing `seen` with sandbox would cause sandbox to re-process production messages
- **`parse_qa(PRODUCTION, text)` not `SANDBOX`** — facts must be tagged with correct chat_id
- **Thread does NOT import `send_msg`** — no reply mechanism exists, by design
