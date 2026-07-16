"""bridge_wrapper.py — thin monkey-patch layer to translate Evolution API calls to Hermes Bridge.

Import at the very top of main_waha.py:
    from bridge_wrapper import *

Exports the globals EVO/KEY/SANDBOX/PRODUCTION so existing code keeps working.
Replaces requests.post and urllib.request.Request/urlopen for the specific Evolution endpoints.

v2 — Message buffer: /messages is destructive (splice), so we cache all messages
locally and return only the ones matching remoteJid filter. Prevents PROD thread
from consuming sandbox messages and vice versa.
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

# ── Message buffer (bridge /messages is destructive — we cache) ──────────
_BUFFER = []  # holds all messages across JIDs

def _fetch_and_buffer():
    """Fetch all messages from bridge and add to buffer. Called on every poll."""
    global _BUFFER
    try:
        br = requests.get(f"{BRIDGE}/messages", timeout=10)
        new_msgs = br.json() if br.ok else []
        _BUFFER.extend(new_msgs)
        # Keep last 200 messages max
        if len(_BUFFER) > 200:
            _BUFFER = _BUFFER[-200:]
    except Exception:
        pass

def _drain_buffer(remote_jid):
    """Return messages matching remote_jid from buffer, removing them."""
    global _BUFFER
    if not remote_jid:
        # No filter — return all
        msgs = _BUFFER[:]
        _BUFFER = []
        return msgs
    matched = [m for m in _BUFFER if remote_jid in m.get("chatId", "")]
    _BUFFER = [m for m in _BUFFER if remote_jid not in m.get("chatId", "")]
    return matched

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
        # Fetch from bridge (destructive), buffer locally, drain by remoteJid
        _fetch_and_buffer()
        body = json or {}
        remote_jid = body.get("where", {}).get("key", {}).get("remoteJid", "")
        bridge_msgs = _drain_buffer(remote_jid)

        records = []
        for m in bridge_msgs:
            rec = {
                "key": {"id": str(m.get("messageId", int(time.time()*1000))),
                        "remoteJid": m.get("chatId", "")},
                "message": {"conversation": m.get("body", "")},
                "messageTimestamp": m.get("timestamp", int(time.time()*1000)),
                "pushName": m.get("senderName", ""),
                "from": m.get("senderId", ""),
            }
            # Attach media metadata if present
            if m.get("hasMedia"):
                media = {
                    "mediaType": m.get("mediaType", ""),
                    "mimetype": m.get("mime", ""),
                    "fileName": m.get("fileName", ""),
                    "mediaUrls": m.get("mediaUrls", []),
                }
                rec["message"]["_media"] = media
            records.append(rec)

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

    if "/message/sendMedia/" in url:
        # send document/image/audio via bridge
        try:
            body = json or {}
            chat_id = body.get("number") or body.get("chatId")
            media_b64 = body.get("media", "")
            media_type = body.get("mediatype", "document")
            fname = body.get("fileName", "file")
            caption = body.get("caption", "")
            if chat_id and media_b64:
                import base64 as _b64, tempfile, os
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{fname}")
                tmp.write(_b64.b64decode(media_b64))
                tmp.close()
                requests.post(f"{BRIDGE}/send-media", json={
                    "chatId": chat_id,
                    "filePath": tmp.name,
                    "mediaType": media_type,
                    "caption": caption,
                    "fileName": fname
                }, timeout=60)
                os.unlink(tmp.name)
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
            requests.post(f"{BRIDGE}/send-media", json={
                "chatId": chat_id,
                "filePath": "/tmp/tts_output.mp3",
                "mediaType": payload.get("mediatype", "audio"),
                "caption": payload.get("caption", ""),
                "fileName": payload.get("fileName", "")
            }, timeout=30)
            return _evo_response({"status": "ok"})
        except Exception as e:
            return _evo_response({"status": "error", "message": str(e)})

    if getattr(req, "_is_media_download", False):
        return _evo_response({"base64": ""})

    return _orig_urlopen(req, **kwargs)

urllib.request.urlopen = _patched_urlopen

print("[bridge_wrapper] Evolution → Hermes Bridge monkey-patch active (v2, buffered)", flush=True)
