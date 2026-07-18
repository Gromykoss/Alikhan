#!/usr/bin/env python3
"""
watchdog_bridge.py — Health monitor for Hermes WhatsApp Bridge (:3000).

Checks bridge health every 5 minutes. If the bridge is down:
  1. Auto-restart via systemd (systemctl --user restart hermes-whatsapp-bridge)
  2. Send alert to Discord webhook (if configured)
  3. Log incident to /tmp/alikhan_watchdog.log

Usage:
    # Run once (for cron / systemd timer)
    python3 watchdog_bridge.py

    # Run as daemon with 5-minute loop
    python3 watchdog_bridge.py --daemon

Environment (secrets.env or direct):
    DISCORD_WEBHOOK_URL — Discord webhook for alerts (optional)
    ALERT_TELEGRAM_TOKEN / ALERT_TELEGRAM_CHAT_ID — Telegram fallback (optional)

Cron (preferred):
    */5 * * * * python3 /home/hermes-workspace/Alikhan-migration/bot/watchdog_bridge.py
"""

import os
import sys
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────
BRIDGE_HEALTH_URL = "http://127.0.0.1:3000/health"
BRIDGE_SERVICE = "hermes-whatsapp-bridge"
CHECK_INTERVAL = 300  # seconds (5 minutes)
LOG_PATH = "/tmp/alikhan_watchdog.log"
FAIL_THRESHOLD = 3    # consecutive failures before restart

# Alert endpoints (loaded from secrets)
DISCORD_WEBHOOK_URL = None
TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None

_failure_count = 0


def _log(msg: str) -> None:
    """Append timestamped line to watchdog log."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _load_secrets() -> None:
    """Load alert webhook URLs from secrets.env."""
    global DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    secrets_path = os.path.expanduser("~/.hermes/secrets.env")
    try:
        with open(secrets_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k == "DISCORD_WEBHOOK_URL":
                        DISCORD_WEBHOOK_URL = v.strip('"').strip("'")
                    elif k == "ALERT_TELEGRAM_TOKEN":
                        TELEGRAM_BOT_TOKEN = v.strip('"').strip("'")
                    elif k == "ALERT_TELEGRAM_CHAT_ID":
                        TELEGRAM_CHAT_ID = v.strip('"').strip("'")
    except FileNotFoundError:
        pass


def _check_bridge_health() -> bool:
    """Return True if bridge :3000/health responds with 200."""
    try:
        req = urllib.request.Request(BRIDGE_HEALTH_URL)
        resp = urllib.request.urlopen(req, timeout=15)
        if resp.status == 200:
            body = resp.read().decode()
            data = json.loads(body) if body else {}
            status = data.get("status", "unknown")
            return status == "connected"
        return False
    except Exception as e:
        _log(f"Health check failed: {e}")
        return False


def _restart_bridge() -> bool:
    """Restart Hermes WhatsApp Bridge via systemd --user."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "restart", BRIDGE_SERVICE],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            _log(f"Bridge restarted successfully")
            return True
        _log(f"Restart failed (rc={result.returncode}): {result.stderr.strip()}")
        return False
    except Exception as e:
        _log(f"Restart command failed: {e}")
        return False


def _send_discord_alert(title: str, message: str) -> bool:
    """Send alert to Discord via webhook. Returns True on success."""
    if not DISCORD_WEBHOOK_URL:
        _log(f"[ALERT-DISCORD DISABLED] {title}: {message}")
        return False

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = json.dumps({
        "embeds": [{
            "title": f"🔴 {title}",
            "description": message,
            "color": 0xFF0000,  # Red
            "footer": {"text": f"Alikhan Watchdog · {ts}"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }).encode()

    try:
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                _log("Discord alert sent")
                return True
    except Exception as e:
        _log(f"Discord alert failed: {e}")
    return False


def _send_telegram_alert(title: str, message: str) -> bool:
    """Send alert to Telegram as fallback."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        text = f"🔴 **{title}**\n{message}"
        body = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }).encode()
        req = urllib.request.Request(url, data=body,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _send_alert(title: str, message: str) -> None:
    """Send alert to all configured channels."""
    discord_ok = _send_discord_alert(title, message)
    if not discord_ok:
        _send_telegram_alert(title, message)


def run_once() -> int:
    """Single health check. Returns 0 if healthy, 1 otherwise."""
    global _failure_count

    healthy = _check_bridge_health()
    if healthy:
        if _failure_count > 0:
            _log(f"Bridge recovered after {_failure_count} failures")
        _failure_count = 0
        return 0

    _failure_count += 1
    _log(f"Bridge DOWN (failure #{_failure_count})")

    if _failure_count >= FAIL_THRESHOLD:
        _log(f"Threshold reached — restarting bridge")
        _send_alert(
            "Hermes Bridge DOWN",
            f"Bridge failed {_failure_count} consecutive health checks.\n"
            f"Auto-restart triggered.\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        if _restart_bridge():
            # Wait for bridge to stabilize
            time.sleep(15)
            if _check_bridge_health():
                _log("Bridge recovered after restart")
                _send_alert(
                    "Hermes Bridge RECOVERED",
                    f"Bridge was down for ~{_failure_count * 5} minutes. "
                    f"Auto-restart successful."
                )
                _failure_count = 0
                return 0
            else:
                _log("Bridge still DOWN after restart")
                _send_alert(
                    "Hermes Bridge STILL DOWN",
                    f"Auto-restart failed. Manual intervention required.\n"
                    f"Check: `systemctl --user status hermes-whatsapp-bridge`"
                )

    return 1


def daemon_loop() -> None:
    """Infinite loop — check every 5 minutes."""
    _log("Watchdog daemon started — checking every 5 minutes")
    while True:
        try:
            run_once()
        except Exception as e:
            _log(f"Unexpected error in watchdog loop: {e}")
        time.sleep(CHECK_INTERVAL)


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _load_secrets()

    if "--daemon" in sys.argv:
        daemon_loop()
    else:
        # Single-shot mode (for cron)
        result = run_once()
        sys.exit(result)
