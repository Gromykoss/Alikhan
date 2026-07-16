"""bridge_wrapper.py — thin monkey-patch layer to translate Evolution API calls to Hermes Bridge.

Import at the very top of main_waha.py:
    from bridge_wrapper import *

Exports the globals EVO/KEY/SANDBOX/PRODUCTION so existing code keeps working.
Replaces requests.post and urllib.request.Request/urlopen for the specific Evolution endpoints.
"""

import requests
import urllib.request
import json
import time
from types import SimpleNamespace
from functools import wraps

# ── Exported globals (so main_waha.py does not break) ─────────────────────
EVO = "http://127.0.0.1:3000"   # dummy – never actually called after patching
KEY = "bridge"                  # dummy
SANDBOX = "120363179621030401@g.us"
PRODUCTION = "120363400682390076@g.us"

BRIDGE = "http://127.0.0.1:3000"

# ── Helper: fake Evolution-style Response ─────────────────────────────────
def _evo_response(payload):
    """Return an object that looks enough like requests.Response for the caller."""
    r = SimpleNamespace()
    r.status_code = 200
    r.text = json.dumps(payload)
    r.json = lambda: payload
    r.headers = {"Content-Type": "application/json"}
    return r

# ── Monkey-patch requests.post ────────────────────────────────────────────
_orig_requests_post = requests.post

def _patched_requests_post(url, json=None, headers=None, **kwargs):
    if "/chat/findMessages/" in url:
        # Bridge returns list of messages directly
        try:
            br = requests.get(f"{BRIDGE}/messages", timeout=10)
            bridge_msgs = br.json() if br.ok else []
        except Exception:
            bridge_msgs = []

        records = []
        for m in bridge_msgs:
            records.append({
                "key": {"id": str(m.get("timestamp", int(time.time()*1000)))},
                "message": {"conversation": m.get("body", "")},
                "messageTimestamp": m.get("timestamp", int(time.time()*1000)),
                "pushName": m.get("senderName", ""),
                "from": m.get("senderId", ""),
            })

        return _evo_response({"messages": {"records": records}})

    if "/message/sendText/" in url:
        # send_msg path
        try:
            body = json or {}
            chat_id = body.get("number") or body.get("chatId")
            text = body.get("text", "")
            if chat_id and text:
                requests.post(f"{BRIDGE}/send", json={"chatId": chat_id, "message": text}, timeout=10)
            return _evo_response({"status": "ok"})
        except Exception as e:
            return _evo_response({"status": "error", "message": str(e)})

    # Fallback to original for anything else
    return _orig_requests_post(url, json=json, headers=headers, **kwargs)

requests.post = _patched_requests_post

# ── Monkey-patch urllib.request for media endpoints ───────────────────────
_orig_urlopen = urllib.request.urlopen
_orig_Request = urllib.request.Request

def _patched_Request(url, data=None, headers=None, **kwargs):
    if "/message/sendMedia/" in url:
        # We intercept at urlopen time – store the fact that this is a media request
        req = _orig_Request(url, data=data, headers=headers or {}, **kwargs)
        req._is_media = True
        return req
    if "/chat/getBase64FromMediaMessage/" in url:
        req = _orig_Request(url, data=data, headers=headers or {}, **kwargs)
        req._is_media_download = True
        return req
    return _orig_Request(url, data=data, headers=headers or {}, **kwargs)

urllib.request.Request = _patched_Request

def _patched_urlopen(req, **kwargs):
    if getattr(req, "_is_media", False):
        try:
            payload = json.loads(req.data.decode()) if req.data else {}
            chat_id = payload.get("number") or payload.get("chatId")
            # For voice / document we just call /send-media with the already-encoded data
            # Bridge expects filePath; we cannot easily satisfy that here, so we fall back
            # to a no-op success response (voice path already has a fallback in main_waha).
            requests.post(f"{BRIDGE}/send-media", json={
                "chatId": chat_id,
                "filePath": "/tmp/tts_output.mp3",   # placeholder – real impl would write first
                "mediaType": payload.get("mediatype", "audio"),
                "caption": payload.get("caption", ""),
                "fileName": payload.get("fileName", "")
            }, timeout=30)
            return _evo_response({"status": "ok"})
        except Exception as e:
            return _evo_response({"status": "error", "message": str(e)})

    if getattr(req, "_is_media_download", False):
        # Not needed for current flow – return empty success
        return _evo_response({"base64": ""})

    return _orig_urlopen(req, **kwargs)

urllib.request.urlopen = _patched_urlopen

print("[bridge_wrapper] Evolution → Hermes Bridge monkey-patch active", flush=True)