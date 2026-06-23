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
                if "алихан" not in text.lower():
                    continue
                print(f"[{sender}] {text[:60]}", flush=True)
                result = route(text)
                handler_name = result.get("command", "chat")
                query = result.get("query", text)
                print(f"  -> {handler_name}", flush=True)
                handler = HANDLERS.get(handler_name, HANDLERS["ai"])
                handler(gid, sender, payload)
        time.sleep(3)
    except Exception as e:
        print(f"ERR: {e}", flush=True)
        time.sleep(5)
