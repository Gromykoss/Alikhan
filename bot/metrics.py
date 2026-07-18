"""
metrics.py — Prometheus-compatible metrics for Alikhan bot (AUDIT-016).
Exposes counters and gauges via HTTP on :9090 for Grafana dashboards.

Usage:
    from metrics import metrics
    metrics.inc('messages_total', labels={'chat': 'sandbox'})
    metrics.inc('errors_total')
    metrics.set('bridge_queue_size', 15)
    metrics.observe('ejo_generation_seconds', 2.3)

Exposes: GET http://0.0.0.0:9090/metrics
"""
import threading
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Metric registry ──

class MetricsRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}    # name → value
        self._gauges = {}      # name → value
        self._histograms = {}  # name → list of values

    # ── Counter ──
    def inc(self, name, value=1, labels=None):
        with self._lock:
            key = self._key(name, labels)
            self._counters[key] = self._counters.get(key, 0) + value

    # ── Gauge ──
    def set(self, name, value, labels=None):
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] = value

    def inc_gauge(self, name, value=1, labels=None):
        with self._lock:
            key = self._key(name, labels)
            self._gauges[key] = self._gauges.get(key, 0) + value

    # ── Histogram ──
    def observe(self, name, value, labels=None):
        with self._lock:
            key = self._key(name, labels)
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            # Keep last 1000 observations
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-500:]

    def _key(self, name, labels=None):
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def render(self):
        """Render Prometheus text format."""
        lines = []
        with self._lock:
            for key, val in sorted(self._counters.items()):
                lines.append(f"# TYPE {key.split('{')[0]} counter")
                lines.append(f"{key} {val}")
            for key, val in sorted(self._gauges.items()):
                lines.append(f"# TYPE {key.split('{')[0]} gauge")
                lines.append(f"{key} {val}")
            for key, vals in sorted(self._histograms.items()):
                base = key.split('{')[0]
                lines.append(f"# TYPE {base} histogram")
                if vals:
                    lines.append(f"{base}_count {len(vals)}")
                    lines.append(f"{base}_sum {sum(vals)}")
                    lines.append(f"{base}_avg {sum(vals)/len(vals):.3f}")
        return "\n".join(lines) + "\n"


# ── HTTP handler ──

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.render().encode())
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress HTTP access logs


# ── Global instance ──
metrics = MetricsRegistry()

# ── Server starter ──

def start_metrics_server(port=9090):
    """Start Prometheus metrics HTTP server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="metrics-server")
    thread.start()
    print(f"[METRICS] Server started on :{port}", flush=True)
    return server
