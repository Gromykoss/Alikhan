import time, requests, sys, json

with open('/tmp/evo_key.txt') as f:
    EVO_KEY = f.read().strip()

sys.stdout.reconfigure(line_buffering=True)
print("Алихан v3 starting...", flush=True)

from router import route, extract_text
from handlers import HANDLERS
import db

EVO_URL = "http://127.0.0.1:8080"
GROUPS = ["120363179621030401@g.us", "120363400682390076@g.us"]
HEADERS = {"apikey": EVO_KEY, "Content-Type": "application/json"}
seen = set()
COOLDOWN = {}

ALLOWED_GROUPS = set(GROUPS)

print(f"Watching: {GROUPS}", flush=True)

while True:
    try:
        for group in GROUPS:
            resp = requests.post(f"{EVO_URL}/chat/findMessages/alikhan",
                headers=HEADERS,
                json={"where": {"key": {"remoteJid": group}}, "page": 1, "limit": 3}, timeout=10)
            
            if resp.status_code != 200:
                continue
                
            for msg in resp.json().get('messages', {}).get('records', []):
                mid = msg.get('id', '')
                key = msg.get('key', {})
                if mid in seen or key.get('fromMe'):
                    continue
                seen.add(mid)
                
                sender = msg.get('pushName', 'unknown')
                chat_id = str(key.get('remoteJid', group)).strip()
                
                # Guard: allowed groups
                if chat_id not in ALLOWED_GROUPS:
                    continue
                
                text = extract_text({"message": msg.get('message', {}), "key": key})
                
                # Guard: "алихан" keyword
                if 'алихан' not in text.lower():
                    continue
                
                # Cooldown
                now = time.time()
                if sender in COOLDOWN and now - COOLDOWN[sender] < 3:
                    continue
                COOLDOWN[sender] = now
                
                print(f"[{sender}] {text[:60]}", flush=True)
                
                # Save to memory
                try:
                    db.save_message(chat_id, sender, "user", text)
                except: pass
                
                # Route
                ctx = route(msg, chat_id, sender, key.get('id', ''))
                cmd = ctx['command']
                handler = HANDLERS.get(cmd, HANDLERS.get('ai'))
                
                if handler:
                    try:
                        handler(chat_id, sender, ctx)
                        print(f"  → {cmd}", flush=True)
                    except Exception as e:
                        print(f"  ERR [{cmd}]: {e}", flush=True)
                    
    except Exception as e:
        print(f"Poll ERR: {e}", flush=True)
    
    time.sleep(2)
