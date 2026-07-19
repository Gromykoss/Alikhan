import time
import json
import os
import sys
import urllib.request
import urllib.error
from flask import Flask, jsonify, request
import threading

sys.stdout.reconfigure(line_buffering=True)
print("Алихан v5 (Evolution polling) starting...", flush=True)

from router import route, extract_text
from handlers import HANDLERS, ask_grok
from secret_config import get_evo_key, get_secret
import db

# Evolution API config
EVO_BASE = "http://127.0.0.1:8080"
EVO_INSTANCE = "alikhan"
GROUPS = [os.environ.get("WHATSAPP_SANDBOX", ""), os.environ.get("WHATSAPP_PRODUCTION", "")]
ALLOWED_GROUPS = set(GROUPS)

EVO_KEY = get_evo_key(required=True)
HEADERS = {"apikey": EVO_KEY, "Content-Type": "application/json"}

COOLDOWN = {}
SEEN = set()

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "instance": EVO_INSTANCE, "mode": "polling"})

import base64
import os
os.makedirs("/tmp/alikhan_docs", exist_ok=True)

# Update DB config dynamically if needed (db.py uses hardcoded, but we note EVO_DB_PASS)
EVO_DB_PASS = get_secret("EVO_DB_PASS", "DB_PASS")

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        payload = request.get_json(force=True)
    except:
        return jsonify({"error": "invalid json"}), 400

    if payload.get("event") != "MESSAGES_UPSERT":
        return jsonify({"ok": True})

    data = payload.get("data", {})
    key = data.get("key", {})
    if key.get("fromMe"):
        return jsonify({"ok": True})

    remote_jid = key.get("remoteJid", "")
    if remote_jid not in ALLOWED_GROUPS:
        return jsonify({"ok": True})

    mid = key.get("id", "")
    if mid in SEEN:
        return jsonify({"ok": True})

    sender = data.get("pushName", "unknown")
    msg = data.get("message", {})
    doc = msg.get("documentMessage")
    img = msg.get("imageMessage")

    now = time.time()
    if sender in COOLDOWN and now - COOLDOWN[sender] < 3:
        SEEN.add(mid)
        return jsonify({"ok": True})
    COOLDOWN[sender] = now

    extracted = ""
    file_name = None
    message_type = "text"

    if doc and doc.get("base64"):
        message_type = "document"
        file_name = doc.get("fileName", "doc.pdf")
        b64 = doc["base64"]
        fpath = f"/tmp/alikhan_docs/{mid}_{file_name}"
        try:
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(b64))
            # extract text
            import pdfplumber
            with pdfplumber.open(fpath) as pdf:
                extracted = "\n".join([p.extract_text() or "" for p in pdf.pages])
        except Exception as e:
            print(f"PDF extract ERR: {e}", flush=True)
            extracted = f"[document: {file_name}]"
        try:
            db.save_message(remote_jid, sender, "user", extracted, message_type="document", file_name=file_name)
        except Exception as e:
            print(f"DB save ERR: {e}", flush=True)
        print(f"[WEBHOOK DOC {sender}] {file_name}", flush=True)

    elif img and img.get("base64"):
        message_type = "image"
        b64 = img["base64"]
        fpath = f"/tmp/alikhan_docs/{mid}_image.jpg"
        try:
            with open(fpath, "wb") as f:
                f.write(base64.b64decode(b64))
            desc = ask_grok("Опиши изображение кратко", image_base64=b64, mimetype=img.get("mimetype", "image/jpeg"))
            extracted = desc
        except Exception as e:
            print(f"IMG ERR: {e}", flush=True)
            extracted = "[image]"
        try:
            db.save_message(remote_jid, sender, "user", extracted, message_type="image")
        except:
            pass
        print(f"[WEBHOOK IMG {sender}]", flush=True)

    else:
        text = extract_text(data)  # reuse from router
        if "алихан" not in text.lower():
            SEEN.add(mid)
            return jsonify({"ok": True})
        extracted = text
        try:
            db.save_message(remote_jid, sender, "user", extracted)
        except:
            pass
        print(f"[WEBHOOK {sender}] {extracted[:60]}", flush=True)

    SEEN.add(mid)

    # route and handle same as polling
    try:
        ctx = route(data, remote_jid, sender, mid)
        cmd = ctx.get("command", "ai")
        handler = HANDLERS.get(cmd, HANDLERS.get("ai"))
        if handler:
            handler(remote_jid, sender, ctx)
            print(f"  → {cmd} (webhook)", flush=True)
    except Exception as e:
        print(f"Webhook route ERR: {e}", flush=True)

    return jsonify({"ok": True})

def download_quoted_media(m, mid):
    ctx_info = m.get("contextInfo", {}) or {}
    quoted = ctx_info.get("quotedMessage", {})
    doc = quoted.get("documentMessage") or quoted.get("imageMessage")
    if not doc:
        return None
    try:
        key = m.get("key", {})
        url = f"{EVO_BASE}/chat/downloadMedia/{EVO_INSTANCE}"
        payload = {"key": key}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            # assume result has base64 or mediaUrl; Evolution typically returns base64
            b64 = result.get("base64") or result.get("media")
            if b64:
                import base64
                ext = ".pdf" if "pdf" in doc.get("mimetype", "") else ".jpg"
                fname = doc.get("fileName") or f"media{ext}"
                fpath = f"/tmp/alikhan_docs/{mid}_{fname}"
                with open(fpath, "wb") as f:
                    f.write(base64.b64decode(b64))
                return {"path": fpath, "filename": fname, "caption": doc.get("caption", ""), "mimetype": doc.get("mimetype", "")}
    except Exception as e:
        print(f"Download media ERR: {e}", flush=True)
        # Return metadata even if download fails — handler can still use filename/caption
        fname = doc.get("fileName") or "unknown"
        return {"path": None, "filename": fname, "caption": doc.get("caption", ""), "mimetype": doc.get("mimetype", "")}
    return None

def poll_messages():
    url = f"{EVO_BASE}/chat/findMessages/{EVO_INSTANCE}"
    while True:
        for group in GROUPS:
            payload = {
                "where": {"key": {"remoteJid": group}},
                "page": 1,
                "limit": 5
            }
            try:
                data = json.dumps(payload).encode()
                req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    msgs = json.loads(resp.read())
                    for m in msgs.get("messages", {}).get("records", []):
                        key = m.get("key", {})
                        mid = key.get("id", "")
                        if mid in SEEN or key.get("fromMe"):
                            continue
                        remote_jid = key.get("remoteJid", "")
                        if remote_jid not in ALLOWED_GROUPS:
                            continue
                        sender = m.get("pushName", "unknown")
                        text = extract_text(m)
                        if "алихан" not in text.lower():
                            SEEN.add(mid)
                            continue

                        now = time.time()
                        if sender in COOLDOWN and now - COOLDOWN[sender] < 3:
                            SEEN.add(mid)
                            continue
                        COOLDOWN[sender] = now

                        print(f"[{sender}] {text[:60]}", flush=True)
                        try:
                            db.save_message(remote_jid, sender, "user", text)
                        except:
                            pass

                        ctx = route(m, remote_jid, sender, mid)
                        media = download_quoted_media(m, mid)
                        if media:
                            ctx["document"] = media
                            ctx["image_path"] = media["path"] if "image" in media.get("mimetype","") else None
                        cmd = ctx["command"]
                        handler = HANDLERS.get(cmd, HANDLERS.get("ai"))
                        if handler:
                            try:
                                handler(remote_jid, sender, ctx)
                                print(f"  → {cmd}", flush=True)
                            except Exception as e:
                                print(f"  ERR [{cmd}]: {e}", flush=True)
                        SEEN.add(mid)
            except Exception as e:
                print(f"Poll ERR {group}: {e}", flush=True)
        time.sleep(3)

def send_text(number, text):
    url = f"{EVO_BASE}/message/sendText/{EVO_INSTANCE}"
    payload = {"number": number, "text": text}
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 201
    except:
        return False

import handlers
handlers.send_text = send_text

if __name__ == "__main__":
    print("Starting polling thread...", flush=True)
    t = threading.Thread(target=poll_messages, daemon=True)
    t.start()
    print("Starting health server on :5555", flush=True)
    app.run(host="0.0.0.0", port=5555, threaded=True)
