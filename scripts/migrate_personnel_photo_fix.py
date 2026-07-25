#!/usr/bin/env python3
"""
Миграция исторических данных для исправления двух багов:

БАГ 1: Персонал — end_date не закрывается
  - Закрыть end_date для всех записей ojr_section1_personnel,
    кроме последней записи каждой организации+должности.

БАГ 2: Фото — local_path не сохраняется в tags
  - Для существующих изображений попытаться восстановить local_path
    из _media метаданных (если файл ещё в кеше).

Безопасный режим: dry_run=True — только отчёт, без изменений.
Для выполнения: dry_run=False.
"""

import os
import sys
import json

# DB config — mirrors db.py
DB_PASS = os.environ.get("DB_PASS", "")
try:
    with open('/home/hermes-workspace/.hermes/secrets.env') as f:
        for line in f:
            if line.startswith('EVO_DB_PASS=') or line.startswith('DB_PASS='):
                DB_PASS = line.strip().split('=', 1)[1]
except Exception:
    pass

import psycopg2
import psycopg2.extras
import subprocess
import ipaddress


def _valid_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _docker_container_ip(container_name="evolution-postgres"):
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
             container_name],
            capture_output=True, text=True, timeout=2,
        )
    except Exception:
        return None
    ip = result.stdout.strip()
    return ip if _valid_ip(ip) else None


def resolve_db_host():
    env_host = os.environ.get("DB_HOST") or os.environ.get("EVO_DB_HOST")
    if env_host:
        return env_host
    return _docker_container_ip() or "172.22.0.4"


DB_CONFIG = {
    "host": resolve_db_host(),
    "port": 5432,
    "user": "evolution",
    "password": DB_PASS,
    "dbname": "evolution_db",
}


def get_conn():
    DB_CONFIG["host"] = resolve_db_host()
    return psycopg2.connect(**DB_CONFIG)


def migrate_personnel(dry_run=True):
    """БАГ 1: Закрыть end_date для всех записей кроме последней (per org+position)."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Показать текущее состояние (дубликаты)
    cur.execute("""
        SELECT organization_name, position, COUNT(*) as cnt,
               bool_or(end_date IS NULL) as has_open
        FROM ojr_section1_personnel
        WHERE is_active = TRUE
        GROUP BY organization_name, position
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
    """)
    dupes = cur.fetchall()
    print(f"\n{'='*60}")
    print(f"[PERSONNEL] Организации с дублирующимися записями: {len(dupes)}")
    print(f"{'='*60}")
    for d in dupes:
        print(f"  {d['organization_name']} / {d['position']}: {d['cnt']} записей (has_open={d['has_open']})")

    if not dupes:
        print("[PERSONNEL] Дубликатов нет — миграция не требуется.")
        cur.close()
        conn.close()
        return

    # SQL для закрытия end_date: для каждой записи, у которой есть более поздняя
    # запись с той же org+position, ставим end_date = день до следующей start_date
    sql = """
        UPDATE ojr_section1_personnel p1
        SET end_date = (
            SELECT MIN(p2.start_date) - INTERVAL '1 day'
            FROM ojr_section1_personnel p2
            WHERE p2.organization_name = p1.organization_name
            AND p2.position = p1.position
            AND p2.start_date > p1.start_date
            AND p2.is_active = TRUE
        ),
        updated_at = NOW()
        WHERE p1.end_date IS NULL
        AND p1.is_active = TRUE
        AND EXISTS (
            SELECT 1 FROM ojr_section1_personnel p2
            WHERE p2.organization_name = p1.organization_name
            AND p2.position = p1.position
            AND p2.start_date > p1.start_date
            AND p2.is_active = TRUE
        )
    """

    if dry_run:
        # Показать какие записи будут затронуты
        cur.execute("""
            SELECT p1.id, p1.organization_name, p1.position, p1.full_name,
                   p1.start_date,
                   (SELECT MIN(p2.start_date) - INTERVAL '1 day'
                    FROM ojr_section1_personnel p2
                    WHERE p2.organization_name = p1.organization_name
                    AND p2.position = p1.position
                    AND p2.start_date > p1.start_date
                    AND p2.is_active = TRUE) as new_end_date
            FROM ojr_section1_personnel p1
            WHERE p1.end_date IS NULL
            AND p1.is_active = TRUE
            AND EXISTS (
                SELECT 1 FROM ojr_section1_personnel p2
                WHERE p2.organization_name = p1.organization_name
                AND p2.position = p1.position
                AND p2.start_date > p1.start_date
                AND p2.is_active = TRUE
            )
            ORDER BY p1.organization_name, p1.position, p1.start_date
        """)
        affected = cur.fetchall()
        print(f"\n[DRY RUN] Будет изменено записей: {len(affected)}")
        for a in affected:
            print(f"  id={a['id']} | {a['organization_name']} | {a['position']} | {a['full_name']} | "
                  f"start={a['start_date']} → end={a['new_end_date']}")
    else:
        cur.execute(sql)
        affected_count = cur.rowcount
        conn.commit()
        print(f"\n[EXECUTED] Закрыто записей: {affected_count}")

    # Проверка после миграции
    cur.execute("""
        SELECT organization_name, position, COUNT(*) as cnt
        FROM ojr_section1_personnel
        WHERE end_date IS NULL AND is_active = TRUE
        GROUP BY organization_name, position
        HAVING COUNT(*) > 1
    """)
    still_dupes = cur.fetchall()
    if still_dupes:
        print(f"\n[WARNING] Остались дубликаты с open end_date: {len(still_dupes)}")
        for d in still_dupes:
            print(f"  {d['organization_name']} / {d['position']}: {d['cnt']}")
    else:
        print(f"\n[OK] Все org+position имеют ≤1 открытую запись.")

    cur.close()
    conn.close()


def migrate_photos(dry_run=True):
    """БАГ 2: Восстановить local_path в tags для существующих фото."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Найти фото без local_path в tags
    cur.execute("""
        SELECT id, content as msg_id, tags, created_at
        FROM bot_memory_messages
        WHERE message_type = 'image'
        AND (tags->>'local_path' IS NULL OR tags->>'local_path' = 'null')
        ORDER BY created_at DESC
    """)
    photos = cur.fetchall()
    print(f"\n{'='*60}")
    print(f"[PHOTO] Изображений без local_path: {len(photos)}")
    print(f"{'='*60}")

    if not photos:
        print("[PHOTO] Все фото уже имеют local_path — миграция не требуется.")
        cur.close()
        conn.close()
        return

    # Попытка восстановить local_path из кеша
    CACHE_DIR = "/tmp/hermes-media-cache"
    restored = 0
    skipped = 0
    not_found = 0

    for p in photos:
        msg_id = p['msg_id']
        tags = p['tags'] or {}

        # Попробовать найти файл в кеше по msg_id
        found_path = None
        if os.path.isdir(CACHE_DIR):
            for fname in os.listdir(CACHE_DIR):
                if msg_id in fname:
                    found_path = os.path.join(CACHE_DIR, fname)
                    break

        if found_path and os.path.exists(found_path):
            if dry_run:
                print(f"  [DRY RUN] msg_id={msg_id} → {found_path}")
                restored += 1
            else:
                tags['local_path'] = found_path
                cur.execute(
                    "UPDATE bot_memory_messages SET tags = %s::jsonb WHERE id = %s",
                    (json.dumps(tags), p['id'])
                )
                print(f"  [RESTORED] msg_id={msg_id} → {found_path}")
                restored += 1
        else:
            if found_path:
                print(f"  [NOT FOUND] msg_id={msg_id} — файл в кеше не существует: {found_path}")
                not_found += 1
            else:
                print(f"  [SKIP] msg_id={msg_id} — файл не найден в кеше")
                skipped += 1

    if not dry_run:
        conn.commit()
        print(f"\n[EXECUTED] Восстановлено: {restored}, пропущено: {skipped}, файл не найден: {not_found}")
    else:
        print(f"\n[DRY RUN] Могло бы восстановиться: {restored}, пропущено: {skipped}, не найдено: {not_found}")

    cur.close()
    conn.close()


def main():
    dry_run = "--execute" not in sys.argv
    mode = "DRY RUN (--execute для реального выполнения)" if dry_run else "EXECUTE"

    print(f"╔{'═'*58}╗")
    print(f"║  Миграция: personnel end_date + photo local_path       ║")
    print(f"║  Режим: {mode:<47}║")
    print(f"╚{'═'*58}╝")

    try:
        migrate_personnel(dry_run=dry_run)
    except Exception as e:
        print(f"[ERROR] personnel migration: {e}")

    try:
        migrate_photos(dry_run=dry_run)
    except Exception as e:
        print(f"[ERROR] photo migration: {e}")


if __name__ == "__main__":
    main()
