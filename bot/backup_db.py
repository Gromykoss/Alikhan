#!/usr/bin/env python3
"""
backup_db.py — Daily PostgreSQL backup script for Alikhan (AUDIT-018).
Creates pg_dump backups in /backups/ with 30-day rotation.

Usage:
    python3 backup_db.py               # run once (for cron)
    python3 backup_db.py --restore <file>   # restore from backup
"""
import os
import sys
import subprocess
import glob
from datetime import datetime, timedelta

BACKUP_DIR = "/backups"
RETENTION_DAYS = 30
DB_HOST = None  # auto-detected
DB_NAME = "evolution_db"
DB_USER = "evolution"


def _get_db_host():
    """Resolve PostgreSQL container IP."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "evolution-postgres",
             "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"],
            capture_output=True, text=True, timeout=10
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass
    return "172.18.0.4"  # fallback


def backup():
    """Create a compressed SQL backup."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    host = _get_db_host()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_path = os.path.join(BACKUP_DIR, f"alikhan_db_{ts}.sql.gz")

    # Use pg_dump via docker exec
    cmd = [
        "docker", "exec", "evolution-postgres",
        "pg_dump", "-U", DB_USER, "-d", DB_NAME,
        "--no-owner", "--no-acl"
    ]

    try:
        with open(dump_path, "wb") as f:
            pg_dump = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gzip = subprocess.Popen(["gzip"], stdin=pg_dump.stdout, stdout=f)
            pg_dump.stdout.close()
            gzip.communicate()

        size = os.path.getsize(dump_path)
        print(f"[BACKUP] Created: {dump_path} ({size} bytes)", flush=True)
        _rotate()
        return dump_path
    except Exception as e:
        print(f"[BACKUP ERR] {e}", flush=True)
        return None


def _rotate():
    """Remove backups older than RETENTION_DAYS."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    for f in glob.glob(os.path.join(BACKUP_DIR, "alikhan_db_*.sql.gz")):
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime < cutoff:
                os.unlink(f)
                print(f"[BACKUP] Rotated out: {os.path.basename(f)}", flush=True)
        except OSError:
            pass


def restore(backup_path):
    """Restore from a compressed SQL backup."""
    if not os.path.exists(backup_path):
        print(f"[RESTORE ERR] File not found: {backup_path}", flush=True)
        return False
    try:
        with open(backup_path, "rb") as f:
            gunzip = subprocess.Popen(["gunzip", "-c"], stdin=f, stdout=subprocess.PIPE)
            psql = subprocess.Popen(
                ["docker", "exec", "-i", "evolution-postgres",
                 "psql", "-U", DB_USER, "-d", DB_NAME],
                stdin=gunzip.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            gunzip.stdout.close()
            _, stderr = psql.communicate()
            if psql.returncode == 0:
                print(f"[RESTORE] Successfully restored from {backup_path}", flush=True)
                return True
            else:
                print(f"[RESTORE ERR] {stderr.decode()[:500]}", flush=True)
                return False
    except Exception as e:
        print(f"[RESTORE ERR] {e}", flush=True)
        return False


if __name__ == "__main__":
    if "--restore" in sys.argv:
        idx = sys.argv.index("--restore")
        if idx + 1 < len(sys.argv):
            restore(sys.argv[idx + 1])
        else:
            print("Usage: python3 backup_db.py --restore <path>")
    else:
        backup()
