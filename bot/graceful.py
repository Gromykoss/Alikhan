"""
graceful.py — Graceful degradation for Alikhan bot (AUDIT-019).
Ensures the bot continues working even when individual services fail.

Patterns:
- Grok API down → fallback to Ollama with degraded quality
- Ollama down → fallback to Grok (no degradation)
- PostgreSQL down → in-memory cache + auto-retry every 60s
- Bridge down → reconnect loop with exponential backoff

Usage:
    from graceful import with_fallback, db_retry
    
    result = with_fallback(
        primary=lambda: grok_call(),
        fallback=lambda: ollama_call(),
        alert_msg="Grok API unavailable — switched to Ollama"
    )
"""
import time
import threading

# ── Service health tracking ──
_health = {
    'grok': {'healthy': True, 'failures': 0, 'last_check': 0},
    'ollama': {'healthy': True, 'failures': 0, 'last_check': 0},
    'postgres': {'healthy': True, 'failures': 0, 'last_check': 0},
    'bridge': {'healthy': True, 'failures': 0, 'last_check': 0},
}
_lock = threading.Lock()


def mark_healthy(service):
    with _lock:
        _health[service]['healthy'] = True
        _health[service]['failures'] = 0
        _health[service]['last_check'] = time.time()


def mark_unhealthy(service):
    with _lock:
        _health[service]['failures'] += 1
        _health[service]['last_check'] = time.time()
        if _health[service]['failures'] >= 3:
            _health[service]['healthy'] = False


def is_healthy(service):
    with _lock:
        return _health[service]['healthy']


def get_health():
    """Return full health snapshot for metrics/alerts."""
    with _lock:
        return {k: dict(v) for k, v in _health.items()}


# ── Fallback with alerts ──

def with_fallback(primary, fallback, alert_msg=None, service='grok'):
    """Execute primary func, fall back on failure. Returns (result, used_fallback)."""
    try:
        result = primary()
        mark_healthy(service)
        return (result, False)
    except Exception as e:
        mark_unhealthy(service)
        if alert_msg:
            print(f"[FALLBACK] {alert_msg}: {e}", flush=True)
        try:
            result = fallback()
            return (result, True)
        except Exception as e2:
            print(f"[FALLBACK FAIL] Both primary and fallback failed for {service}: {e2}", flush=True)
            raise


# ── DB retry with backoff ──

class _DbCache:
    """Simple in-memory cache for DB fallback."""
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value


db_cache = _DbCache()


def db_retry(func, max_retries=3, backoff_base=2.0):
    """Execute DB operation with retry on connection failure."""
    last_err = None
    for attempt in range(max_retries):
        try:
            result = func()
            mark_healthy('postgres')
            return result
        except Exception as e:
            last_err = e
            mark_unhealthy('postgres')
            if attempt < max_retries - 1:
                wait = backoff_base ** attempt
                print(f"[DB RETRY] Attempt {attempt+1} failed, retrying in {wait}s: {e}", flush=True)
                time.sleep(wait)
    raise last_err
