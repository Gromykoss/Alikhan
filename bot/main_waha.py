"""Alikhan EVO v5 — thin orchestrator (modules: stt, qa, router, db_lookup)"""
import time, requests, json, sys, os, base64, tempfile, subprocess, urllib.request
from datetime import datetime
import re
from secret_config import get_evo_key

EVO = "http://127.0.0.1:8080"
KEY = get_evo_key(required=True)
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)
print("Alikhan EVO v5 — sandbox", flush=True)

# Simulation date (set to None for production)
SIM_DATE = "2026-06-28"

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

def _update_template_from_correction(b64_data, fname):
    """When user sends a corrected ЕЖО .xlsx, use it as new template."""
    import glob as _glob, base64 as _b64
    from openpyxl import load_workbook
    TEMPLATE = "/home/hermes-workspace/Alikhan-migration/bot/templates/ЕЖО_шаблон.xlsx"

    # Save corrected file
    corrected_path = f"/tmp/corrected_{fname}"
    with open(corrected_path, "wb") as f:
        f.write(_b64.b64decode(b64_data))
    print(f"[TEMPLATE] Received corrected: {fname} ({os.path.getsize(corrected_path)} bytes)", flush=True)

    # Find latest auto-generated ЕЖО (by modification time)
    auto_files = sorted(_glob.glob("/tmp/ЕЖО_20*_v*.xlsx"), key=os.path.getmtime, reverse=True)
    if not auto_files:
        # No auto-generated yet — use as initial template
        import shutil
        shutil.copy(corrected_path, TEMPLATE)
        print(f"[TEMPLATE] Set as initial template: {TEMPLATE}", flush=True)
        return

    auto_path = auto_files[0]
    print(f"[TEMPLATE] Comparing with auto: {os.path.basename(auto_path)}", flush=True)

    # Compare cumulative volumes between corrected and auto — by code, not row
    wb_corr = load_workbook(corrected_path, data_only=True)
    wb_auto = load_workbook(auto_path, data_only=True)
    ws_c = wb_corr['Ежедневный отчет']
    ws_a = wb_auto['Ежедневный отчет']

    # Build code→(row, values) maps
    def build_code_map(ws):
        cmap = {}
        for r in range(24, ws.max_row + 1):
            code = ws.cell(r, 3).value
            if not code: continue
            code = str(code).strip()
            cmap[code] = {
                'row': r,
                16: ws.cell(r, 16).value,   # мес.факт
                19: ws.cell(r, 19).value,   # общ.факт
                21: ws.cell(r, 21).value,   # остаток
            }
        return cmap

    cmap_c = build_code_map(ws_c)
    cmap_a = build_code_map(ws_a)

    diffs = []
    all_codes = set(cmap_c.keys()) | set(cmap_a.keys())
    for code in sorted(all_codes):
        vc = cmap_c.get(code, {})
        va = cmap_a.get(code, {})
        for col, name in [(16, 'мес.факт'), (19, 'общ.факт'), (21, 'остаток')]:
            try:
                vc_f = float(vc.get(col, 0)) if vc.get(col) is not None else 0
                va_f = float(va.get(col, 0)) if va.get(col) is not None else 0
            except:
                continue
            if abs(vc_f - va_f) > 0.01:
                diffs.append(f"  {code} {name}: авто={va_f} → правка={vc_f}")

    wb_corr.close(); wb_auto.close()

    if diffs:
        print(f"[TEMPLATE] Found {len(diffs)} differences:", flush=True)
        for d in diffs[:10]:
            print(d, flush=True)
        if len(diffs) > 10:
            print(f"  ... and {len(diffs)-10} more", flush=True)

    # Replace template with corrected version
    import shutil, re as _re
    shutil.copy(corrected_path, TEMPLATE)
    # Extract date from filename (e.g., "27.06.2026") or fall back to today
    m = _re.search(r'(\d{2})\.(\d{2})\.(\d{4})', fname)
    if m:
        date_str = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
    dated_path = f"/tmp/ЕЖО_template_{date_str}.xlsx"
    shutil.copy(corrected_path, dated_path)
    # Save as dated ЕЖО so yesterday_cum() finds correct cumulative values (overwrite)
    ejo_path = f"/tmp/ЕЖО_{date_str}_v1.xlsx"
    shutil.copy(corrected_path, ejo_path)

    summary = f"📎 Правки приняты ({len(diffs)} отличий). Шаблон обновлён."
    if diffs:
        summary += "\nОсновные изменения:\n" + "\n".join(diffs[:5])
    send_msg(SANDBOX, summary)

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
                         _json.dumps({"building": building or "без тег", "msg_id": mid}), datetime.now() if not SIM_DATE else datetime.strptime(SIM_DATE, "%Y-%m-%d")))
                    conn.commit(); cur.close(); conn.close()
                    print(f"[PHOTO] Saved: {building or 'без тег'} — {caption[:40]}", flush=True)
                except Exception as e:
                    print(f"[PHOTO ERR] {e}", flush=True)
                continue

            # Document (табель, Excel, PDF)
            doc_msg = msg.get("documentMessage") or msg.get("documentWithCaptionMessage", {}).get("message", {}).get("documentMessage")
            if doc_msg:
                try:
                    payload = {"message": m}
                    req = urllib.request.Request(f"{EVO}/chat/getBase64FromMediaMessage/alikhan",
                        data=json.dumps(payload).encode(),
                        headers={"apikey": KEY, "Content-Type": "application/json"})
                    resp = urllib.request.urlopen(req, timeout=60)
                    result = json.loads(resp.read().decode())
                    b64 = result.get("base64", "")
                    fname = result.get("fileName", doc_msg.get("fileName", "document"))
                    if b64:
                        # Save to DB
                        import json as _json
                        from db import get_conn as _getconn
                        conn = _getconn(); cur = conn.cursor()
                        cur.execute("""INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, tags, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                            (SANDBOX, "user", "user", "document", fname,
                             _json.dumps({"msg_id": mid, "file_name": fname}),
                             datetime.now() if not SIM_DATE else datetime.strptime(SIM_DATE, "%Y-%m-%d")))
                        conn.commit(); cur.close(); conn.close()
                        print(f"[DOC] Saved: {fname}", flush=True)
                        # Extract text via document extractor for future AI analysis
                        try:
                            ext_req = urllib.request.Request("http://localhost:8099/extract-document",
                                data=json.dumps({"base64": b64, "file_name": fname}).encode(),
                                headers={"Content-Type": "application/json"})
                            ext_resp = urllib.request.urlopen(ext_req, timeout=60)
                            ext_data = json.loads(ext_resp.read().decode())
                            ext_text = ext_data.get("content") or ext_data.get("text", "")
                            if ext_text:
                                print(f"[DOC] Extracted {len(ext_text)} chars from {fname}", flush=True)
                        except Exception as ex:
                            print(f"[DOC EXTRACT ERR] {ex}", flush=True)
                        # If this is a corrected ЕЖО, update template
                        if fname and 'ЕЖО' in fname and fname.endswith('.xlsx'):
                            try:
                                _update_template_from_correction(b64, fname)
                            except Exception as ex:
                                print(f"[TEMPLATE UPDATE ERR] {ex}", flush=True)
                except Exception as e:
                    print(f"[DOC ERR] {e}", flush=True)
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
                                     _json.dumps({"msg_id": mid, "source": "stt"}), datetime.now() if not SIM_DATE else datetime.strptime(SIM_DATE, "%Y-%m-%d")))
                                conn.commit(); cur.close(); conn.close()
                                print(f"[STT] Saved to DB: {text[:60]}", flush=True)
                            except Exception as e:
                                print(f"[STT DB ERR] {e}", flush=True)
                except Exception as e:
                    print(f"[STT FETCH ERR] {e}", flush=True)
                    continue

            if not text.strip():
                continue

            # Close survey + force EJO (MUST be before survey trigger)
            if any(w in text.lower() for w in ["закрыть опрос", "завершить опрос", "закончить опрос", "стоп опрос", "опрос стоп", "опрос закрыть", "опрос завершить", "опрос закончить", "готово", "хватит"]):
                import glob as _glob
                # Auto-fill missing data
                import psycopg2
                from db import get_conn as _gc3
                conn3 = _gc3(); cur3 = conn3.cursor()
                today_str = SIM_DATE or datetime.now().strftime("%Y-%m-%d")
                cats = {'бетонирование': 'Бетонирование не выполнялось',
                        'монтаж': 'Монтаж не выполнялся',
                        'земляные работы': 'Земляные работы не выполнялись'}
                for cat, fact_text in cats.items():
                    cur3.execute("SELECT count(*) FROM bot_memory_facts WHERE fact_date=%s AND category=%s", (today_str, cat))
                    if cur3.fetchone()[0] == 0:
                        cur3.execute("INSERT INTO bot_memory_facts (chat_id, fact_date, building, category, fact, source) VALUES (%s,%s,'общая',%s,%s,'auto')",
                                     (SANDBOX, today_str, cat, fact_text))
                conn3.commit(); cur3.close(); conn3.close()
                send_msg(SANDBOX, "✅ Опрос закрыт. Формирую ЕЖО...")
                # Immediately trigger EJO
                subprocess.run(["python3", "fill_ejo.py", today_str],
                    cwd=os.path.dirname(os.path.abspath(__file__)))
                files = sorted(_glob.glob(f"/tmp/ЕЖО_{today_str}_v*.xlsx"))
                if files:
                    path = files[-1]
                    b64 = base64.b64encode(open(path, "rb").read()).decode()
                    payload = json.dumps({"number": SANDBOX, "mediatype": "document", "media": b64,
                                          "fileName": f"ЕЖО_{today_str}_v{len(files)}.xlsx"})
                    req = urllib.request.Request(f"{EVO}/message/sendMedia/alikhan", data=payload.encode(),
                        headers={"apikey": KEY, "Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=20)
                    send_msg(SANDBOX, f"📄 ЕЖО за {today_str}")
                continue

            # Survey trigger
            if any(w in text.lower() for w in ["начать опрос", "запустить опрос"]):
                subprocess.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX],
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    env={**os.environ, "EJO_DATE": SIM_DATE} if SIM_DATE else None)
                continue

            # Fill EJO trigger
            if any(w in text.lower() for w in ["заполни ежо", "сформируй ежо", "формируй ежо", "сделай ежо"]):
                import glob as _glob
                check = subprocess.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX, "--check-only"],
                    capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)),
                    env={**os.environ, "EJO_DATE": SIM_DATE} if SIM_DATE else None)
                if "missing" in check.stdout.lower() or "не хватает" in check.stdout.lower():
                    send_msg(SANDBOX, "📋 Не все данные собраны. Запускаю опрос...")
                    subprocess.run(["python3", "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX],
                        cwd=os.path.dirname(os.path.abspath(__file__)),
                        env={**os.environ, "EJO_DATE": SIM_DATE} if SIM_DATE else None)
                    continue
                today_str = SIM_DATE or datetime.now().strftime("%Y-%m-%d")
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
