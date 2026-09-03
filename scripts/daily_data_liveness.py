#!/usr/bin/env python3
"""Ежесуточная проверка ФАКТА работы системы Alikhan.

Проверяет не код (это делает daily_health_check.py), а живость данных:
  - накапливаются ли новые записи в сырьё (bot_memory_messages) за 24ч;
  - накапливаются ли записи в OJR-таблицы (работы/персонал/техника/фото/доки/погода);
  - накапливаются ли файлы/фото в хранилище на диске.

Подключение к БД — через bot/db.get_conn() (secret_config сам берёт DB_PASS
из env/secrets.env). Бишкек UTC+6 (get_conn ставит SET TIME ZONE).

Вывод — компактный, без таймстампов в числах (для monitor-совместимости).
Формат (stdout verbatim):
    LIVENESS OK
    сырьё: +N | работы: +N | персонал: +N | техника: +N | фото: +N | доки: +N | погода: +N
    диск: фото=N, документы=N
    последняя запись: <YYYY-MM-DD HH:MM>
"""
import os
import sys
import time
from pathlib import Path

BOT_DIR = "/home/hermes-workspace/Alikhan-migration/bot"
sys.path.insert(0, BOT_DIR)

CACHE_IMAGES = Path("/home/hermes-workspace/.hermes/profiles/alikhan/cache/images")
CACHE_DOCS = Path("/home/hermes-workspace/.hermes/profiles/alikhan/cache/documents")

# Таблицы: (метка, таблица, date-колонка для «последней» записи)
OJR_TABLES = [
    ("работы", "ojr_section3_work_log"),
    ("персонал", "ojr_section1_personnel"),
    ("техника", "ojr_section2_equipment"),
    ("фото", "ojr_photo_log"),
    ("доки", "ojr_section5_asbuilt_docs"),
    ("погода", "ojr_weather"),
]


def _count_24h(cur, table):
    """Число записей в таблице за последние 24 часа (по created_at)."""
    cur.execute(
        f"SELECT COUNT(*) FROM {table} WHERE created_at >= NOW() - INTERVAL '24 hours'"
    )
    return int(cur.fetchone()[0])


def _files_24h(directory):
    """Число файлов в каталоге, изменённых за 24 часа."""
    if not directory.exists():
        return 0
    cutoff = time.time() - 24 * 3600
    n = 0
    for p in directory.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime >= cutoff:
                n += 1
        except OSError:
            pass
    return n


def main():
    from db import get_conn
    import psycopg2.extras

    conn = get_conn()
    cur = conn.cursor()
    try:
        # Сырьё
        cur.execute(
            "SELECT COUNT(*) FROM bot_memory_messages "
            "WHERE COALESCE(message_time, created_at) >= NOW() - INTERVAL '24 hours'"
        )
        raw_24h = int(cur.fetchone()[0])

        # OJR за 24ч
        counts = {}
        for label, table in OJR_TABLES:
            counts[label] = _count_24h(cur, table)

        # Последняя запись в сырьё (факт живости конвейера)
        cur.execute(
            "SELECT COALESCE(message_time, created_at) FROM bot_memory_messages "
            "ORDER BY COALESCE(message_time, created_at) DESC LIMIT 1"
        )
        row = cur.fetchone()
        last_ts = row[0] if row else None
    finally:
        cur.close()
        conn.close()

    disk_photos = _files_24h(CACHE_IMAGES)
    disk_docs = _files_24h(CACHE_DOCS)

    last_str = last_ts.strftime("%Y-%m-%d %H:%M") if last_ts else "—"

    # Итог: живость = есть ли хоть какое-то движение за 24ч
    movement = raw_24h + sum(counts.values()) + disk_photos + disk_docs
    status = "OK" if movement > 0 else "STALL"

    print(f"LIVENESS {status}")
    print(
        f"сырьё: +{raw_24h} | работы: +{counts['работы']} | персонал: +{counts['персонал']} | "
        f"техника: +{counts['техника']} | фото: +{counts['фото']} | доки: +{counts['доки']} | "
        f"погода: +{counts['погода']}"
    )
    print(f"диск: фото={disk_photos}, документы={disk_docs}")
    print(f"последняя запись: {last_str}")


if __name__ == "__main__":
    main()
