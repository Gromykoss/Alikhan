"""Alikhan EVO v5 — Evolution API + QA parser + survey + fill EJO"""
import time, requests, json, sys, os
from datetime import datetime
import re

EVO = "http://127.0.0.1:8080"
KEY = "SuperSecretKey_Grok2026_!@#"
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)
print("Alikhan EVO v5 — sandbox", flush=True)

def send_msg(chat_id, text):
    requests.post(f"{EVO}/message/sendText/alikhan",
        json={"number": chat_id, "text": text[:3800]},
        headers={"apikey": KEY, "Content-Type": "application/json"}, timeout=10)

def _is_qa(text):
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    # Also detect VOR code format: "2.1.5 = 100м3"
    import re
    if re.search(r'\d\.\d\.\d+\s*=', text):
        return True
    return False

def _parse_qa(gid, text):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from handlers import ask_grok
        from db import get_conn
        
        prompt = f"""Извлеки факты из ответа прораба. Формат: building | category | fact_text
building: АБК/Общежитие/общая
category: персонал/техника/инцидент/бетонирование/монтаж/земляные работы/документация

{text[:3000]}

Только строки фактов, без пояснений."""
        result = ask_grok(prompt, max_tokens=500)
        conn = get_conn()
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for line in result.split("\n"):
            # First check for VOR code format: "2.1.5 = 100м3"
            vor_match = re.match(r'(\d\.\d\.\d+)\s*=\s*(\d+(?:\.\d+)?)\s*(\S*)', line.strip())
            if vor_match:
                code, vol, unit = vor_match.groups()
                cur.execute("INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                    (gid, today, 'общая', 'объём', f'{code} = {vol}{unit}'))
                count += 1
                continue
            # Then Grok format
            parts = [p.strip() for p in line.strip().split("|", 2)]
            if len(parts) >= 3 and len(line) > 10:
                cur.execute("INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                    (gid, today, parts[0], parts[1], parts[2]))
                count += 1
        conn.commit()
        cur.close(); conn.close()
        if count > 0:
            send_msg(gid, f"✅ Принято: {count} фактов")
        print(f"[QA] {count} facts saved from '{text[:60]}'", flush=True)
    except Exception as e:
        print(f"[QA ERR] {e}", flush=True)

# Main loop
seen = set()
try:
    r = requests.post(f"{EVO}/chat/findMessages/alikhan",
        json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 10},
        headers={"apikey": KEY}, timeout=15)
    for m in r.json().get("messages", {}).get("records", []):
        seen.add(m["key"]["id"])
    print(f"Seeded {len(seen)} IDs", flush=True)
except Exception as e:
    print(f"Seed error: {e}", flush=True)

print(f"Watching: {SANDBOX}", flush=True)

while True:
    try:
        r = requests.post(f"{EVO}/chat/findMessages/alikhan",
            json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 1},
            headers={"apikey": KEY}, timeout=15)
        msgs = r.json().get("messages", {}).get("records", [])

        for m in msgs:
            mid = m["key"]["id"]
            if mid in seen or m["key"].get("fromMe"):
                continue
            seen.add(mid)

            msg = m.get("message", {})
            text = msg.get("conversation", "") or msg.get("extendedTextMessage", {}).get("text", "")
            
            # Photo/image message handling
            img_msg = msg.get("imageMessage")
            if img_msg:
                caption = img_msg.get("caption", "")
                # Detect building from caption
                building = None
                for tag in ["АБК", "Общежитие", "Галерея", "Общий план"]:
                    if tag.lower() in caption.lower():
                        building = tag
                        break
                # Save to DB
                try:
                    import json as _json
                    from db import get_conn as _getconn
                    conn = _getconn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (SANDBOX, "user", "user", "image", mid,  # store WhatsApp msg ID as content
                          _json.dumps({"building": building or "без тега", "msg_id": mid}), datetime.now()))
                    conn.commit()
                    cur.close(); conn.close()
                    print(f"[PHOTO] Saved: {building or 'без тега'} — {caption[:40]}", flush=True)
                except Exception as e:
                    print(f"[PHOTO ERR] {e}", flush=True)
                continue
            
            if not text.strip():
                continue

            # QA parser (runs on ALL messages, even without "алихан")
            if _is_qa(text):
                _parse_qa(SANDBOX, text)
                continue

            # Only respond to "алихан"
            if "алихан" not in text.lower():
                continue

            # Survey trigger
            if any(w in text.lower() for w in ["опрос", "опросник"]):
                import subprocess as sp
                sp.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX],
                    cwd="/home/hermes-workspace/Alikhan-migration/bot")
                continue

            # Fill EJO trigger
            if any(w in text.lower() for w in ["заполни ежо", "сформируй ежо"]):
                import subprocess as sp, base64
                # First check completeness
                check = sp.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX, "--check-only"],
                    capture_output=True, text=True, cwd="/home/hermes-workspace/Alikhan-migration/bot")
                if "missing" in check.stdout.lower() or "не хватает" in check.stdout.lower():
                    send_msg(SANDBOX, "❌ Не все данные собраны. Сначала дособерите опросник.")
                    continue
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                sp.run(["python3", "fill_ejo.py", today_str],
                    cwd="/home/hermes-workspace/Alikhan-migration/bot")
                # Find latest version
                import glob
                files = sorted(glob.glob(f"/tmp/ЕЖО_{today_str}_v*.xlsx"))
                if files:
                    path = files[-1]
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    requests.post(f"{EVO}/message/sendMedia/alikhan",
                        json={"number": SANDBOX, "mediatype": "document", "media": b64,
                              "fileName": f"ЕЖО_{today_str}_v{len(files)}.xlsx"},
                        headers={"apikey": KEY}, timeout=30)
                    send_msg(SANDBOX, f"📊 ЕЖО v{len(files)} отправлен")
                continue

            sender = m.get("key",{}).get("remoteJid","?").split("@")[0] if "@" in m.get("key",{}).get("remoteJid","") else "?"
            print(f"[{sender}] {text[:60]}", flush=True)
            try:
                from handlers import ask_grok
                reply = ask_grok(f"Ответь коротко на русском: {text[:2000]}", max_tokens=200)
                send_msg(SANDBOX, reply)
            except Exception as e:
                print(f"[AI ERR] {e}", flush=True)

        time.sleep(3)
    except Exception as e:
        print(f"[LOOP ERR] {e}", flush=True)
        time.sleep(5)
