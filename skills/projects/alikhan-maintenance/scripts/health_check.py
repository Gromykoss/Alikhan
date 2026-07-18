#!/usr/bin/env python3
"""Alikhan health check — comprehensive, not superficial.
Exit 0 = all OK. Exit 1 = problems found. Exit 2 = fatal.
Output: one line per check, problems prefixed with 'FAIL:', warnings with 'WARN:'.
"""

import subprocess, sys, os, urllib.request, json, re
from datetime import datetime, timedelta

PROBLEMS = []

def check(name, ok, detail=""):
    if ok:
        print(f"OK: {name}")
    else:
        PROBLEMS.append(f"{name}: {detail}")
        print(f"FAIL: {name}: {detail}")

def warn(name, detail=""):
    print(f"WARN: {name}: {detail}")

# 1. Single process running
try:
    result = subprocess.run(["pgrep", "-af", "main_waha.py"], capture_output=True, text=True, timeout=5)
    procs = [l for l in result.stdout.strip().split('\n') if l and 'grep' not in l]
    n = len(procs)
    if n == 0:
        check("bot process", False, "not running")
    elif n == 1:
        check("bot process", True, "1 instance")
    else:
        check("bot process", False, f"{n} instances (zombie!)")
except Exception as e:
    check("bot process", False, str(e))

# 2. psycopg2 importable
try:
    result = subprocess.run(
        ["/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3", "-c", "import psycopg2; print('ok')"],
        capture_output=True, text=True, timeout=5)
    check("psycopg2 module", result.stdout.strip() == 'ok', result.stderr.strip())
except Exception as e:
    check("psycopg2 module", False, str(e))

# 3. DB connection
try:
    from psycopg2 import connect
    host = subprocess.run(
        ["docker", "inspect", "evolution-postgres", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
        capture_output=True, text=True, timeout=5).stdout.strip()
    conn = connect(host=host, port=5432, dbname='evolution_db', user='evolution', password='pass123', connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT 1")
    cur.close(); conn.close()
    check("DB connection", True)
except Exception as e:
    check("DB connection", False, str(e)[:100])

# 4. Document extractor service
try:
    req = urllib.request.Request("http://127.0.0.1:8099/health")
    resp = urllib.request.urlopen(req, timeout=5)
    check("document extractor :8099", resp.status == 200, f"status={resp.status}")
except Exception as e:
    check("document extractor :8099", False, str(e)[:80])

# 5. Evolution API reachable
try:
    req = urllib.request.Request("http://127.0.0.1:8080/")
    resp = urllib.request.urlopen(req, timeout=5)
    check("Evolution API :8080", resp.status in (200, 404, 405), f"status={resp.status}")
except Exception as e:
    check("Evolution API :8080", False, str(e)[:80])

# 6. Recent REJECT errors in log
try:
    log_path = "/tmp/alikhan.log"
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()
        recent = lines[-200:]
        reject_count = sum(1 for l in recent if 'REJECT' in l)
        if reject_count > 0:
            warn("REJECT in logs", f"{reject_count} recent REJECT(s)")
        else:
            check("no REJECT errors", True)
except Exception as e:
    warn("log check failed", str(e)[:80])

# 7. Last processed message timestamp
try:
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()
        last_activity = None
        for line in reversed(lines):
            if '[MSG]' in line or '[REPLY]' in line or '[LOOP ERR]' in line:
                last_activity = line
                break
        if last_activity:
            if '[LOOP ERR]' in last_activity:
                warn("bot loop errors", last_activity.strip()[:100])
            else:
                check("recent activity", True)
except:
    pass

# 8. Collation warnings spam
try:
    if os.path.exists(log_path):
        with open(log_path) as f:
            lines = f.readlines()
        collation_warns = sum(1 for l in lines[-500:] if 'collation version' in l)
        if collation_warns > 50:
            warn("collation warnings", f"{collation_warns} in last 500 lines — DB needs REINDEX")
except:
    pass

print()
if PROBLEMS:
    print(f"\u274c {len(PROBLEMS)} problem(s) found:")
    for p in PROBLEMS:
        print(f"  \u2022 {p}")
    sys.exit(1)
else:
    print("\u2705 All checks passed")
    sys.exit(0)
