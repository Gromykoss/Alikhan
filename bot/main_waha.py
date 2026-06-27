"""Alikhan EVO v5 — thin orchestrator (modules: stt, qa, router, db_lookup)"""
import time, requests, json, sys, os, base64, tempfile, subprocess, urllib.request
from datetime import datetime
import re

EVO = "http://127.0.0.1:8080"
KEY = "SuperSecretKey_Grok2026_!@#"
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)
print("Alikhan EVO v5 — sandbox", flush=True)

# ── Send message ──
def send_msg(chat_id, text):
    print(f"[REPLY] {text[:100]}", flush=True)
    requests.post(f"{EVO}/message/sendText/alikhan",
        json={"number": chat_id, "text": text[:3800]},
        headers={"apikey": KEY, "Content-Type": "application/json"}, timeout=10)

def send_voice(chat_id, text):
    try:
        mp3_path = "/tmp/tts_output.mp3"
        subprocess.run(["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", text,
                        "--write-media", mp3_path], check=True, capture_output=True)
        with open(mp3_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        req = urllib.request.Request(
            f"{EVO}/message/sendMedia/alikhan",
            data=json.dumps({"number": chat_id, "mediatype": "audio", "mimetype": "audio/mpeg", "media": b64}).encode(),
            headers={"apikey": KEY, "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30)
        print(f"[TTS] Sent voice to {chat_id}", flush=True)
    except Exception as e:
        print(f"[TTS ERR] {e}", flush=True)
        send_msg(chat_id, text)

# ── Modules ──
from stt import transcribe_audio
from router import route

# ── Persistence ──
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_ids.json")
seen = set()
if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE) as f:
            seen = set(json.load(f))
        print(f"Loaded {len(seen)} seen IDs from disk", flush=True)
    except:
        pass

# ── Seed ──
try:
    r = requests.post(f"{EVO}/chat/findMessages/alikhan",
        json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 10},
        headers={"apikey": KEY}, timeout=15)
    for m in r.json().get("messages", {}).get("records", []):
        seen.add(m["key"]["id"])
    print(f"Seeded {len(seen)} IDs", flush=True)
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)
except Exception as e:
    print(f"Seed error: {e}", flush=True)

print(f"Watching: {SANDBOX}", flush=True)

# ── Main loop ──
while True:
    try:
        # Get page 1 (newest) for metadata, then fetch page 1
        r = requests.post(f"{EVO}/chat/findMessages/alikhan",
            json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 5},
            headers={"apikey": KEY}, timeout=15)
        msgs = r.json().get("messages", {}).get("records", [])

        # Deduplicate
        seen_ids = set()
        unique_msgs = []
        for m in msgs:
            mid = m["key"]["id"]
            if mid not in seen_ids and not m["key"].get("fromMe"):
                seen_ids.add(mid)
                unique_msgs.append(m)
        msgs = unique_msgs

        for m in msgs:
            mid = m["key"]["id"]
            if mid in seen:
                continue
            # Skip messages older than 10 minutes
            msg_ts = m.get("messageTimestamp", 0)
            now_ts = int(time.time())
            if now_ts - msg_ts > 600:
                seen.add(mid)
                continue
            seen.add(mid)
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen), f)
            print(f"[MSG] {mid[:12]}... {int(now_ts - msg_ts)}s ago", flush=True)

            msg = m.get("message", {})
            text = msg.get("conversation", "") or msg.get("extendedTextMessage", {}).get("text", "")

            # Photo
            img_msg = msg.get("imageMessage")
            if img_msg:
                caption = img_msg.get("caption", "")
                building = None
                for tag in ["АБК", "Общежитие", "Галерея", "Общий план"]:
                    if tag.lower() in caption.lower():
                        building = tag
                        break
                try:
                    import json as _json
                    from db import get_conn as _getconn
                    conn = _getconn()
                    cur = conn.cursor()
                    cur.execute("""INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (SANDBOX, "user", "user", "image", mid,
                         _json.dumps({"building": building or "без тег", "msg_id": mid}), datetime.now()))
                    conn.commit(); cur.close(); conn.close()
                    print(f"[PHOTO] Saved: {building or 'без тег'} — {caption[:40]}", flush=True)
                except Exception as e:
                    print(f"[PHOTO ERR] {e}", flush=True)
                continue

            # Audio / voice
            audio_msg = msg.get("audioMessage") or msg.get("ptvMessage")
            if audio_msg:
                try:
                    payload = {"message": m}
                    req = urllib.request.Request(f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
                        data=json.dumps(payload).encode(),
                        headers={"apikey": KEY, "Content-Type": "application/json"})
                    resp = urllib.request.urlopen(req, timeout=30)
                    b64_audio = json.loads(resp.read().decode()).get("base64", "")
                    if b64_audio:
                        transcribed = transcribe_audio(b64_audio)
                        if transcribed:
                            text = transcribed
                            # Save to DB
                            try:
                                import json as _json
                                from db import get_conn as _getconn
                                conn = _getconn(); cur = conn.cursor()
                                cur.execute("""INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                                    (SANDBOX, "user", "user", "voice", text,
                                     _json.dumps({"msg_id": mid, "source": "stt"}), datetime.now()))
                                conn.commit(); cur.close(); conn.close()
                                print(f"[STT] Saved to DB: {text[:60]}", flush=True)
                            except Exception as e:
                                print(f"[STT DB ERR] {e}", flush=True)
                except Exception as e:
                    print(f"[STT FETCH ERR] {e}", flush=True)
                    continue

            if not text.strip():
                continue

            # Survey trigger
            if any(w in text.lower() for w in ["опрос", "опросник"]):
                subprocess.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX],
                    cwd=os.path.dirname(os.path.abspath(__file__)))
                continue

            # Fill EJO trigger
            if any(w in text.lower() for w in ["заполни ежо", "сформируй ежо"]):
                import glob as _glob
                check = subprocess.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX, "--check-only"],
                    capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
                if "missing" in check.stdout.lower() or "не хватает" in check.stdout.lower():
                    send_msg(SANDBOX, "❌ Не все данные собраны. Сначала дособерите опросник.")
                    continue
                today_str = datetime.now().strftime("%Y-%m-%d")
                subprocess.run(["python3", "fill_ejo.py", today_str],
                    cwd=os.path.dirname(os.path.abspath(__file__)))
                files = sorted(_glob.glob(f"/tmp/ЕЖО_{today_str}_v*.xlsx"))
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

            # Route
            sender = m.get("key",{}).get("remoteJid","?").split("@")[0] if "@" in m.get("key",{}).get("remoteJid","") else "?"
            print(f"[{sender}] {text[:60]}", flush=True)
            action, reply, voice = route(text, SANDBOX, sender)
            if action == "IGNORE":
                continue
            if voice:
                send_voice(SANDBOX, reply)
            send_msg(SANDBOX, reply)

        time.sleep(3)
    except Exception as e:
        print(f"[LOOP ERR] {e}", flush=True)
        time.sleep(5)
