#!/usr/bin/env python3
"""
watchdog_bridge.py - cron health monitor for Hermes WhatsApp Bridge (:3000).

The WhatsApp bridge is a Node.js subprocess spawned by Hermes gateway. This
watchdog must not restart services. It only detects incidents and sends alerts.

Usage:
    python3 watchdog_bridge.py
    python3 watchdog_bridge.py --daemon
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import fcntl
from datetime import datetime, timezone


BRIDGE_HEALTH_URL = "http://127.0.0.1:3000/health"
BRIDGE_BASE_URL = "http://127.0.0.1:3000"
CHECK_INTERVAL = 300
FAIL_THRESHOLD = 3
MAX_ALERT_ATTEMPTS = 5
HEALTH_TIMEOUT = 15
ALERT_TIMEOUT = 10

LOG_PATH = "/tmp/alikhan_watchdog.log"
STATE_PATH = "/tmp/alikhan_watchdog_state.json"
LOCK_PATH = f"{STATE_PATH}.lock"
SECRETS_PATH = "~/.hermes/secrets.env"
PROFILE_ENV_PATH = "~/.hermes/profiles/alikhan/.env"

BRIDGE_DOWN = "BRIDGE_DOWN"
BRIDGE_DOWNGRADED = "BRIDGE_DOWNGRADED"
NOT_CONNECTED = "NOT_CONNECTED"
FAILURE_TYPES = (BRIDGE_DOWN, BRIDGE_DOWNGRADED, NOT_CONNECTED)

ACTION_BY_TYPE = {
    BRIDGE_DOWN: "рестарт gateway (Hermes)",
    BRIDGE_DOWNGRADED: "пересобрать кастомный bridge.js",
    NOT_CONNECTED: "проверить WhatsApp-сессию",
}

DISCORD_WEBHOOK_URL = ""
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stdout_is_log_file() -> bool:
    try:
        return os.path.samefile("/proc/self/fd/1", LOG_PATH)
    except OSError:
        return False


def _log(msg: str) -> None:
    """Write a timestamped watchdog line to /tmp log and stdout when useful."""
    line = f"[{_utc_now()}] {msg}"
    if not _stdout_is_log_file():
        print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _empty_failure_state() -> dict:
    return {
        failure_type: {
            "count": 0,
            "last_failure_at": None,
            "alert_sent": False,
            "alert_attempted": False,
            "alert_attempts": 0,
        }
        for failure_type in FAILURE_TYPES
    }


def _new_state() -> dict:
    return {
        "active_failure_type": None,
        "incident_alert_sent": False,
        "failures": _empty_failure_state(),
        "last_recovered_at": None,
        "recovery_pending": False,
        "recovery_attempts": 0,
    }


def _normalize_state(raw: object) -> dict:
    if not isinstance(raw, dict):
        return _new_state()

    state = _new_state()
    active_failure_type = raw.get("active_failure_type")
    if active_failure_type in FAILURE_TYPES:
        state["active_failure_type"] = active_failure_type
    state["incident_alert_sent"] = bool(raw.get("incident_alert_sent"))

    raw_failures = raw.get("failures")
    if isinstance(raw_failures, dict):
        for failure_type in FAILURE_TYPES:
            item = raw_failures.get(failure_type)
            if not isinstance(item, dict):
                continue
            state["failures"][failure_type]["count"] = max(0, int(item.get("count") or 0))
            state["failures"][failure_type]["last_failure_at"] = item.get("last_failure_at")
            state["failures"][failure_type]["alert_sent"] = bool(item.get("alert_sent"))
            state["failures"][failure_type]["alert_attempted"] = bool(item.get("alert_attempted"))
            state["failures"][failure_type]["alert_attempts"] = max(
                0,
                int(item.get("alert_attempts") or bool(item.get("alert_attempted"))),
            )

    state["last_recovered_at"] = raw.get("last_recovered_at")
    state["recovery_pending"] = bool(raw.get("recovery_pending"))
    state["recovery_attempts"] = max(0, int(raw.get("recovery_attempts") or 0))
    return state


def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return _normalize_state(json.load(f))
    except FileNotFoundError:
        return _new_state()
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
        _log(f"State corrupt/unreadable, starting clean: {e}")
        return _new_state()


def _save_state(state: dict) -> None:
    tmp_path = f"{STATE_PATH}.{os.getpid()}.tmp"
    data = json.dumps(_normalize_state(state), ensure_ascii=False, indent=2, sort_keys=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(data)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, STATE_PATH)


def _read_env_file(path: str) -> dict:
    values = {}
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    except OSError as e:
        _log(f"Env file unreadable {path}: {e}")
    return values


def _load_secrets() -> None:
    """Load alert credentials from secrets.env, then profile .env fallback."""
    global DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
    TELEGRAM_BOT_TOKEN = os.environ.get("ALERT_TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("ALERT_TELEGRAM_CHAT_ID", "")

    secrets = _read_env_file(SECRETS_PATH)
    if secrets.get("DISCORD_WEBHOOK_URL"):
        DISCORD_WEBHOOK_URL = secrets["DISCORD_WEBHOOK_URL"]
    if secrets.get("ALERT_TELEGRAM_TOKEN"):
        TELEGRAM_BOT_TOKEN = secrets["ALERT_TELEGRAM_TOKEN"]
    if secrets.get("ALERT_TELEGRAM_CHAT_ID"):
        TELEGRAM_CHAT_ID = secrets["ALERT_TELEGRAM_CHAT_ID"]

    profile = _read_env_file(PROFILE_ENV_PATH)
    if not TELEGRAM_BOT_TOKEN and profile.get("TELEGRAM_BOT_TOKEN"):
        TELEGRAM_BOT_TOKEN = profile["TELEGRAM_BOT_TOKEN"]
    if not TELEGRAM_CHAT_ID and profile.get("TELEGRAM_HOME_CHANNEL"):
        TELEGRAM_CHAT_ID = profile["TELEGRAM_HOME_CHANNEL"]


def _get_health() -> tuple:
    """Return (http_ok, data, error_text) for /health."""
    try:
        req = urllib.request.Request(BRIDGE_HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            if resp.status != 200:
                return False, None, f"HTTP {resp.status}"
            try:
                return True, json.loads(body), None
            except json.JSONDecodeError as e:
                return False, None, f"invalid JSON: {e}"
    except urllib.error.HTTPError as e:
        return False, None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, None, str(e.reason)
    except TimeoutError as e:
        return False, None, f"timeout: {e}"
    except OSError as e:
        return False, None, str(e)


def _endpoint_status(url: str, method: str = "GET", payload: object = None) -> tuple:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as resp:
            resp.read()
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except urllib.error.URLError as e:
        return None, str(e.reason)
    except TimeoutError as e:
        return None, f"timeout: {e}"
    except OSError as e:
        return None, str(e)


def _a_plus_contract_detail() -> tuple:
    ack_status, ack_error = _endpoint_status(
        f"{BRIDGE_BASE_URL}/messages-ack",
        method="POST",
        payload={"messageIds": []},
    )
    if ack_status == 404:
        return False, "/messages-ack HTTP 404"
    if ack_status is None:
        return True, f"A+ contract not confirmed: /messages-ack unavailable: {ack_error}"

    return True, f"A+ contract OK: /messages-ack HTTP {ack_status}"


def _classify_health(http_ok: bool, data: object, error_text: str = None) -> tuple:
    """Return (failure_type, detail). failure_type is None when bridge is healthy."""
    if not http_ok:
        return BRIDGE_DOWN, error_text or "/health unavailable"
    if not isinstance(data, dict):
        return BRIDGE_DOWN, "/health JSON is not an object"
    status = data.get("status")
    if status != "connected":
        return NOT_CONNECTED, f"status={status!r}"
    contract_ok, contract_detail = _a_plus_contract_detail()
    if not contract_ok:
        return BRIDGE_DOWNGRADED, contract_detail
    return None, f"healthy: {contract_detail}"


def _send_telegram_alert(title: str, message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"{title}\n{message}",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=ALERT_TIMEOUT) as resp:
            ok = resp.status == 200
            if ok:
                _log("Telegram alert sent")
            else:
                _log(f"Telegram alert failed: HTTP {resp.status}")
            return ok
    except Exception as e:
        _log(f"Telegram alert failed: {e}")
        return False


def _send_discord_alert(title: str, message: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False

    payload = json.dumps({
        "content": f"{title}\n{message}",
    }).encode("utf-8")
    req = urllib.request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=ALERT_TIMEOUT) as resp:
            ok = resp.status in (200, 204)
            if ok:
                _log("Discord alert sent")
            else:
                _log(f"Discord alert failed: HTTP {resp.status}")
            return ok
    except Exception as e:
        _log(f"Discord alert failed: {e}")
        return False


def _send_alert(title: str, message: str) -> bool:
    """Send Telegram first, then Discord fallback."""
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        if _send_telegram_alert(title, message):
            return True
    elif DISCORD_WEBHOOK_URL:
        if _send_discord_alert(title, message):
            return True
    else:
        _log("[ALERT DISABLED] нет канала")
        return False

    if DISCORD_WEBHOOK_URL:
        return _send_discord_alert(title, message)

    _log("[ALERT DISABLED] нет канала")
    return False


def _any_alert_sent(state: dict) -> bool:
    return bool(state.get("incident_alert_sent")) or any(
        state["failures"][failure_type]["alert_sent"] for failure_type in FAILURE_TYPES
    )


def _record_failure(state: dict, failure_type: str, detail: str) -> tuple:
    if state.get("active_failure_type") != failure_type:
        state["failures"] = _empty_failure_state()
        state["active_failure_type"] = failure_type

    failure = state["failures"][failure_type]
    failure["count"] += 1
    failure["last_failure_at"] = _utc_now()
    state["last_recovered_at"] = None
    state["recovery_pending"] = False
    state["recovery_attempts"] = 0

    _log(f"{failure_type}: failure #{failure['count']} - {detail}")

    if failure["count"] < FAIL_THRESHOLD or failure["alert_sent"]:
        return state, None

    if failure["alert_attempts"] >= MAX_ALERT_ATTEMPTS:
        _log(f"{failure_type}: alert was not delivered, attempts exhausted")
        return state, None

    failure["alert_attempted"] = True
    failure["alert_attempts"] += 1
    title = f"Alikhan watchdog: {failure_type}"
    message = (
        f"Тип сбоя: {failure_type}\n"
        f"Детали: {detail}\n"
        f"Последовательных отказов: {failure['count']}\n"
        f"Что делать: {ACTION_BY_TYPE[failure_type]}"
    )
    return state, (title, message, failure_type)


def _record_recovery(state: dict) -> tuple:
    should_alert = _any_alert_sent(state)
    recovered_at = _utc_now()

    if state.get("active_failure_type") or any(
        state["failures"][failure_type]["count"] for failure_type in FAILURE_TYPES
    ):
        _log("recovered: bridge healthy, A+ contract OK, status connected")
        if should_alert:
            state["recovery_pending"] = True

    state["last_recovered_at"] = recovered_at

    if not state.get("recovery_pending"):
        return _new_state(), None

    state["recovery_attempts"] += 1
    return state, (
        "Alikhan watchdog: RECOVERED",
        "WhatsApp bridge восстановился: /health OK, контракт A+ OK, status=connected.",
        None,
    )


def run_once() -> int:
    """Single health check for cron. Returns 0 if healthy, 1 if failed."""
    with open(LOCK_PATH, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        state = _load_state()
        http_ok, data, error_text = _get_health()
        failure_type, detail = _classify_health(http_ok, data, error_text)

        if failure_type is None:
            state, alert = _record_recovery(state)
            try:
                _save_state(state)
            except OSError as e:
                _log(f"State save failed, recovery alert skipped: {e}")
                return 0
            if alert:
                title, message, _ = alert
                if _send_alert(title, message):
                    clean_state = _new_state()
                    clean_state["last_recovered_at"] = state.get("last_recovered_at")
                    try:
                        _save_state(clean_state)
                    except OSError as e:
                        _log(f"State save failed after recovery alert: {e}")
                else:
                    _log("RECOVERED: alert was not delivered")
            return 0

        state, alert = _record_failure(state, failure_type, detail)
        try:
            _save_state(state)
        except OSError as e:
            _log(f"State save failed, incident alert skipped: {e}")
            return 1

        if alert:
            title, message, alert_failure_type = alert
            if _send_alert(title, message):
                state["failures"][alert_failure_type]["alert_sent"] = True
                state["incident_alert_sent"] = True
                try:
                    _save_state(state)
                except OSError as e:
                    _log(f"State save failed after incident alert: {e}")
            else:
                _log(f"{alert_failure_type}: alert was not delivered")
        return 1


def daemon_loop() -> None:
    _log("Watchdog daemon started - checking every 5 minutes")
    while True:
        try:
            run_once()
        except Exception as e:
            _log(f"Unexpected error in watchdog loop: {e}")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    _load_secrets()
    if "--daemon" in sys.argv:
        daemon_loop()
    else:
        sys.exit(run_once())
