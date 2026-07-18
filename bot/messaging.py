"""
messaging.py — Unified message sending module for Alikhan WhatsApp bot.
Single implementation for send_msg, send_voice, send_document.
Replaces duplicates in main_waha.py, handlers.py, and poll.py.

Usage:
    from messaging import send_msg, send_voice, send_document
"""
import requests
import json
import os
import base64
import subprocess
import urllib.request
from bridge_wrapper import EVO, KEY

# ── Text ──

def send_msg(chat_id, text):
    """Send text message via Evolution API. Truncates at 3800 chars."""
    try:
        body = json.dumps({"number": chat_id, "text": str(text or "")[:3800]}).encode()
        req = urllib.request.Request(f"{EVO}/message/sendText/alikhan", data=body, method='POST')
        req.add_header('apikey', KEY)
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[SEND] {str(text)[:100]}", flush=True)
            return resp.status in (200, 201)
    except Exception as e:
        print(f"[SEND ERR] {e}", flush=True)
        return False

# ── Voice (TTS) ──

def send_voice(chat_id, text):
    """Generate TTS audio via edge-tts and send. Falls back to text on failure."""
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
        print(f"[TTS] Sent voice to {chat_id[:20]}...", flush=True)
        return True
    except Exception as e:
        print(f"[TTS ERR] {e}", flush=True)
        return send_msg(chat_id, text)

# ── Document ──

def send_document(chat_id, filepath, filename=None):
    """Send a document via Evolution API with error checking. Returns True if sent."""
    try:
        with open(filepath, "rb") as f:
            b64_enc = base64.b64encode(f.read()).decode()
        r = requests.post(f"{EVO}/message/sendMedia/alikhan",
            json={"number": chat_id, "mediatype": "document", "media": b64_enc,
                  "fileName": filename or os.path.basename(filepath)},
            headers={"apikey": KEY}, timeout=30)
        if r.status_code in (200, 201):
            print(f"[SEND OK] {filename or filepath} → {chat_id[:20]}...", flush=True)
            return True
        else:
            print(f"[SEND FAIL] {filename or filepath}: HTTP {r.status_code} — {r.text[:200]}", flush=True)
            return False
    except Exception as e:
        print(f"[SEND ERR] {filename or filepath}: {e}", flush=True)
        return False
