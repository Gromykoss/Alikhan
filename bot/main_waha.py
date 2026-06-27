"""Alikhan EVO v5 — Evolution API + QA parser + survey + fill EJO + STT/TTS"""
import time, requests, json, sys, os, base64, tempfile, subprocess
from datetime import datetime
import re
import urllib.request

EVO = "http://127.0.0.1:8080"
KEY = "SuperSecretKey_Grok2026_!@#"
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)
print("Alikhan EVO v5 — sandbox", flush=True)

def send_msg(chat_id, text):
    print(f"[REPLY] {text[:100]}", flush=True)
    requests.post(f"{EVO}/message/sendText/alikhan",
        json={"number": chat_id, "text": text[:3800]},
        headers={"apikey": KEY, "Content-Type": "application/json"}, timeout=10)

def transcribe_audio(b64_audio):
    """STT via faster-whisper + Grok post-correction"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
            f.write(base64.b64decode(b64_audio))
            ogg_path = f.name
        wav_path = ogg_path.replace(".ogg", ".wav")
        subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
                       capture_output=True, check=True)
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(wav_path, language="ru")
        raw = " ".join(s.text for s in segments).strip()
        os.unlink(ogg_path); os.unlink(wav_path)
        if not raw:
            return ""
        # Post-correct via Grok
        from handlers import ask_grok
        corrected = ask_grok(
            f"Исправь опечатки и ошибки распознавания в тексте. "
            f"Скорее всего там имя «Алихан» (голосовой ассистент). "
            f"Также исправь искажённые вопросные слова: такая→какая, такой→какой, че→что, скока→сколько. "
            f"Верни ТОЛЬКО исправленный текст, без пояснений:\n\n{raw}",
            max_tokens=200
        ).strip()
        print(f"[STT] raw={raw[:80]} => corrected={corrected[:80]}", flush=True)
        return corrected if corrected else raw
    except Exception as e:
        print(f"[STT ERR] {e}", flush=True)
        return ""

def send_voice(chat_id, text):
    """TTS via edge-tts + sendMedia"""
    try:
        mp3_path = "/tmp/tts_output.mp3"
        subprocess.run(["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", text, "--write-media", mp3_path],
                       check=True, capture_output=True)
        with open(mp3_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        req = urllib.request.Request(
            f"{EVO}/message/sendMedia/alikhan",
            data=json.dumps({"number": chat_id, "mediatype": "audio", "mimetype": "audio/mpeg", "media": b64}).encode(),
            headers={"apikey": KEY, "Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=30)
        print(f"[TTS] Sent voice to {chat_id}", flush=True)
    except Exception as e:
        print(f"[TTS ERR] {e}", flush=True)
        send_msg(chat_id, text)  # fallback to text

def _is_qa(text):
    # Skip if it's a question (QA is for data submissions, not questions)
    if "?" in text or any(w in text.lower() for w in ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что", "как"]):
        return False
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
        
        prompt = f"""Извлеки ВСЕ факты из ответа прораба. Каждый факт — отдельной строкой.
Формат: building | category | fact_text
building: АБК/Общежитие/общая
category: персонал/техника/инцидент/бетонирование/монтаж/земляные работы/документация
ВАЖНО: ИТР и рабочие — это РАЗНЫЕ факты. Если сказано «5 рабочих ИТР 2», извлеки ДВЕ строки:
общая | персонал | 5 рабочих
общая | персонал | ИТР 2 человека

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
            return True
        else:
            print(f"[QA] 0 facts from '{text[:60]}'", flush=True)
            return False
    except Exception as e:
        print(f"[QA ERR] {e}", flush=True)

# Main loop
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_ids.json")
seen = set()
if os.path.exists(SEEN_FILE):
    try:
        with open(SEEN_FILE) as f:
            seen = set(json.load(f))
        print(f"Loaded {len(seen)} seen IDs from disk", flush=True)
    except:
        pass
try:
    # Seed from first page (newest messages)
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

while True:
    try:
        # Get total pages first
        r = requests.post(f"{EVO}/chat/findMessages/alikhan",
            json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 1},
            headers={"apikey": KEY}, timeout=15)
        total_pages = r.json().get("messages", {}).get("pages", 1)
        # Fetch first 1 page (newest messages — Evolution API page 1 = newest)
        msgs = []
        r = requests.post(f"{EVO}/chat/findMessages/alikhan",
            json={"where": {"key": {"remoteJid": SANDBOX}}, "page": 1, "limit": 5},
            headers={"apikey": KEY}, timeout=15)
        msgs.extend(r.json().get("messages", {}).get("records", []))

        # Deduplicate by ID (same message can appear across pages)
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
            # Save seen IDs immediately
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen), f)
            print(f"[MSG] {mid[:12]}... {int(now_ts - msg_ts)}s ago", flush=True)

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
                          _json.dumps({"building": building or "без тег", "msg_id": mid}), datetime.now()))
                    conn.commit()
                    cur.close(); conn.close()
                    print(f"[PHOTO] Saved: {building or 'без тег'} — {caption[:40]}", flush=True)
                except Exception as e:
                    print(f"[PHOTO ERR] {e}", flush=True)
                continue
            
            # STT: audioMessage / ptvMessage
            audio_msg = msg.get("audioMessage") or msg.get("ptvMessage")
            if audio_msg:
                try:
                    # Get base64 via Evolution API
                    payload = {"message": m}
                    req = urllib.request.Request(
                        f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
                        data=json.dumps(payload).encode(),
                        headers={"apikey": KEY, "Content-Type": "application/json"}
                    )
                    resp = urllib.request.urlopen(req, timeout=30)
                    b64_audio = json.loads(resp.read().decode()).get("base64", "")
                    if b64_audio:
                        transcribed = transcribe_audio(b64_audio)
                        if transcribed:
                            text = transcribed
                            print(f"[STT] Transcribed: {text[:80]}", flush=True)
                            # Save ALL transcriptions to DB (like photos)
                            try:
                                import json as _json
                                from db import get_conn as _getconn
                                conn = _getconn()
                                cur = conn.cursor()
                                cur.execute("""
                                    INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (SANDBOX, "user", "user", "voice", text,
                                      _json.dumps({"msg_id": mid, "source": "stt"}), datetime.now()))
                                conn.commit()
                                cur.close(); conn.close()
                                print(f"[STT] Saved to DB: {text[:60]}", flush=True)
                            except Exception as e:
                                print(f"[STT DB ERR] {e}", flush=True)
                except Exception as e:
                    print(f"[STT FETCH ERR] {e}", flush=True)
                    continue
            
            if not text.strip():
                continue

            # QA parser (runs on ALL messages, even without "алихан")
            if _is_qa(text):
                if _parse_qa(SANDBOX, text):
                    continue

            # Only respond to "алихан" (with fuzzy matching for STT errors)
            ali_match = re.search(r'[ао]л[еи][хгк]', text.lower())
            if not ali_match:
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

            # Voice reply trigger
            voice_reply = any(w in text.lower() for w in ["голосом", "озвучь", "голос"])
            sender = m.get("key",{}).get("remoteJid","?").split("@")[0] if "@" in m.get("key",{}).get("remoteJid","") else "?"
            print(f"[{sender}] {text[:60]}", flush=True)
            # Try DB fact lookup before Grok
            db_reply = None
            try:
                from db_memory import fact_lookup
                today_str = datetime.now().strftime("%Y-%m-%d")
                # Filter by category if question is specific
                cat_filter = None
                if any(w in text.lower() for w in ["рабочих", "персонал", "сколько человек", "итр", "инженер"]):
                    cat_filter = "персонал"
                elif any(w in text.lower() for w in ["техник", "оборудован", "машин"]):
                    cat_filter = "техника"
                facts = fact_lookup(SANDBOX, start_date=today_str, limit=10, category=cat_filter)
                if facts:
                    lines = [f"{f['category']}: {f['fact']} ({f['building']})" for f in facts]
                    db_reply = "📋 Сегодня:\n" + "\n".join(lines)
            except Exception as e:
                print(f"[DB LOOKUP ERR] {e}", flush=True)

            # Weather API lookup
            weather_reply = None
            if any(w in text.lower() for w in ["погод", "температур", "ветер", "давлени", "осадк"]):
                try:
                    import urllib.request as _ur
                    wreq = _ur.Request(
                        "https://api.open-meteo.com/v1/forecast?latitude=42.284&longitude=72.765"
                        "&current=temperature_2m,wind_speed_10m,relative_humidity_2m,pressure_msl,weather_code"
                        "&timezone=Asia/Bishkek&forecast_days=1"
                    )
                    wdata = json.loads(_ur.urlopen(wreq, timeout=10).read())
                    c = wdata.get("current", {})
                    wmo = {0:"Ясно",1:"Ясно",2:"Переменная облачность",3:"Пасмурно",45:"Туман",48:"Иней",
                           51:"Морось",53:"Морось",55:"Морось",61:"Дождь",63:"Дождь",65:"Ливень",
                           71:"Снег",73:"Снег",75:"Снег",80:"Ливень",95:"Гроза",96:"Гроза с градом",99:"Гроза с градом"}
                    weather_reply = (
                        f"🌤 Джеруй: {wmo.get(c.get('weather_code',0),'?')}, "
                        f"{c.get('temperature_2m','?')}°C, "
                        f"ветер {c.get('wind_speed_10m','?')} м/с, "
                        f"{c.get('relative_humidity_2m','?')}%, "
                        f"{round(c.get('pressure_msl',0)*0.75006)} мм рт.ст."
                    )
                except Exception as e:
                    print(f"[WEATHER ERR] {e}", flush=True)

            try:
                from handlers import ask_grok
                if weather_reply:
                    reply = weather_reply
                elif db_reply and any(w in text.lower() for w in ["рабочих", "техник", "статус", "что сегодня", "происшестви", "итог", "подведи", "сделано", "персонал"]):
                    # Send DB facts to Grok for summarization
                    reply = ask_grok(
                        f"Ты — строительный инспектор на площадке ТЗРК Джеруй (один объект). "
                        f"Строятся: АБК, Общежитие, Галерея. "
                        f"ПРОСУММИРУЙ все числа из фактов ниже. "
                        f"Дай точную итоговую цифру. "
                        f"Вот факты из базы за сегодня:\n{db_reply}\n\n"
                        f"Ответь на вопрос прораба коротко и по делу (1-2 предложения):\n{text[:500]}",
                        max_tokens=200
                    ).strip()
                else:
                    reply = ask_grok(
                    f"Ты — строительный инспектор на площадке ТЗРК Джеруй (Кыргызстан, горы, ~2700м). "
                    f"Строятся: АБК (2 этажа), Общежитие (3 этажа), Галерея. "
                    f"Сегодня {datetime.now().strftime('%d.%m.%Y, %A')}. "
                    f"Если вопрос про факты (техника, рабочие, происшествия) — скажи что нужно уточнить в БД. "
                    f"Отвечай как прораб: коротко, по делу, без воды.\n\n"
                    f"Вопрос: {text[:1800]}", max_tokens=200)
                if voice_reply:
                    send_voice(SANDBOX, reply)
                send_msg(SANDBOX, reply)
            except Exception as e:
                print(f"[AI ERR] {e}", flush=True)

        time.sleep(3)
    except Exception as e:
        print(f"[LOOP ERR] {e}", flush=True)
        time.sleep(5)
