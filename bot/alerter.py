"""
alerter.py — Telegram alert notifications for Alikhan bot (AUDIT-017).
Sends alerts when: bot crashed, no messages > 10min, error rate > threshold, Grok API down.

Usage:
    from alerter import send_alert
    send_alert("Bot down", "main_waha.py process not found")
    send_alert("No messages", "No WhatsApp messages for 15 minutes")
"""
import os
import json
import urllib.request
from datetime import datetime

# ── Config ──
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None
ALERT_ENABLED = False


def _load_alert_config():
    """Load Telegram credentials from secrets."""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALERT_ENABLED
    try:
        with open(os.path.expanduser("~/.hermes/secrets.env")) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    if k == 'ALERT_TELEGRAM_TOKEN':
                        TELEGRAM_BOT_TOKEN = v
                    elif k == 'ALERT_TELEGRAM_CHAT_ID':
                        TELEGRAM_CHAT_ID = v
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            ALERT_ENABLED = True
            print("[ALERTER] Telegram alerts configured", flush=True)
        else:
            print("[ALERTER] Telegram alerts NOT configured — set ALERT_TELEGRAM_TOKEN + ALERT_TELEGRAM_CHAT_ID in secrets.env", flush=True)
    except Exception as e:
        print(f"[ALERTER] Config error: {e}", flush=True)


def send_alert(title, message, level="WARNING"):
    """Send alert to Telegram. No-op if not configured."""
    if not ALERT_ENABLED:
        print(f"[ALERT: {level}] {title}: {message}", flush=True)
        return False

    emoji = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(level, "⚪")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"{emoji} **{level} | {title}**\n{ts}\n\n{message}\n\n_Alikhan Bot_"

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        body = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }).encode()
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print(f"[ALERT SENT] {title}", flush=True)
                return True
    except Exception as e:
        print(f"[ALERT FAIL] {title}: {e}", flush=True)
    return False


# Load config on import
_load_alert_config()
