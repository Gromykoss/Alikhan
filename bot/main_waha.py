import time, requests, sys, os

WAHA = "http://127.0.0.1:3000"
KEY = "waha123"
HEADERS = {"X-Api-Key": KEY, "Content-Type": "application/json"}
GROUPS = ["120363179621030401@g.us"]  # sandbox only

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from router import route
from handlers import HANDLERS

sys.stdout.reconfigure(line_buffering=True)
print("Alikhan WAHA v2 — sandbox only", flush=True)

def send_msg(chat_id, text):
    try:
        r = requests.post(f"{WAHA}/api/sendText", json={
            "session": "alikhan", "chatId": chat_id, "text": text[:1000]
        }, headers=HEADERS, timeout=10)
        return r.status_code == 200
    except:
        return False

seen = set()
print(f"Watching: {GROUPS}", flush=True)

while True:
    try:
        for gid in GROUPS:
            r = requests.get(f"{WAHA}/api/alikhan/chats/{gid}/messages?limit=3",
                           headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            msgs = r.json()
            data = msgs if isinstance(msgs, list) else msgs.get("data", [])
            for m in data:
                mid = m.get("id", "")
                if mid in seen or m.get("fromMe"):
                    continue
                seen.add(mid)
                text = m.get("body", "") or m.get("text", "")
                sender = m.get("from", "?")
                has_media = m.get("hasMedia", False)
                
                # Detect media type for document/photo messages
                if has_media:
                    media_obj = m.get("media", {})
                    msg_data = m.get("_data", {}).get("message", {})
                    # Check for document or photo
                    has_doc = "document" in str(msg_data.keys()).lower()
                    has_img = "image" in str(msg_data.keys()).lower()
                    
                    if has_doc or media_obj.get("mimetype","").startswith("application/"):
                        result = route(text, gid, sender, mid)
                        result["command"] = "document"
                        result["fileName"] = media_obj.get("filename", "document")
                        result["messageId"] = mid
                        result["mimetype"] = media_obj.get("mimetype", "")
                        print(f"[{sender}] 📄 {media_obj.get('filename','doc')[:40]}", flush=True)
                        handler = HANDLERS.get("document")
                        if handler:
                            handler(gid, sender, result)
                        continue
                    elif has_img or media_obj.get("mimetype","").startswith("image/"):
                        result = route(text, gid, sender, mid)
                        result["command"] = "photo"
                        result["messageId"] = mid
                        result["mimetype"] = media_obj.get("mimetype", "image/jpeg")
                        print(f"[{sender}] 📷 photo", flush=True)
                        handler = HANDLERS.get("photo")
                        if handler:
                            handler(gid, sender, result)
                        continue
                
                if "алихан" not in text.lower():
                    continue
                print(f"[{sender}] {text[:60]}", flush=True)
                result = route(text)
                handler_name = result.get("command", "chat")
                query = result.get("query", text)
                print(f"  -> {handler_name}", flush=True)
                handler = HANDLERS.get(handler_name, HANDLERS["ai"])
                handler(gid, sender, result)
        time.sleep(3)
    except Exception as e:
        print(f"ERR: {e}", flush=True)
        time.sleep(5)
