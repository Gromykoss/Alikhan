#!/usr/bin/env python3
"""Alikhan: ежедневная сверка «сырьё vs результат».

Правило (DATA_CONTRACT.md): bot_memory_messages = сырьё (живой поток),
ojr_* = производные (разобранное). Если сырьё растёт, а результат нет —
это РАЗРЫВ РАЗБОРА, не потеря данных.

Вывод: тихая проверка. Печатает сообщение ТОЛЬКО при расхождении
(для cron no_agent watchdog-паттерна: пустой stdout = всё в норме).
"""
import subprocess
import sys
from datetime import datetime, timedelta, timezone

BISHKEK = timezone(timedelta(hours=6))

def q(sql: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "evolution-postgres", "psql", "-U", "evolution",
         "-d", "evolution_db", "-t", "-A", "-c", sql],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql err: {r.stderr[:200]}")
    return r.stdout.strip()

def main() -> int:
    today = datetime.now(BISHKEK).strftime("%Y-%m-%d")
    yesterday = (datetime.now(BISHKEK) - timedelta(days=1)).strftime("%Y-%m-%d")

    # Сырьё за вчера (полный бишкекский день)
    raw_img = q(
        f"SELECT COUNT(*) FROM bot_memory_messages WHERE message_type='image' "
        f"AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bishkek')::date = '{yesterday}';"
    )
    raw_doc = q(
        f"SELECT COUNT(*) FROM bot_memory_messages WHERE message_type='document' "
        f"AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bishkek')::date = '{yesterday}';"
    )
    raw_txt = q(
        f"SELECT COUNT(*) FROM bot_memory_messages WHERE message_type='text' "
        f"AND (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bishkek')::date = '{yesterday}';"
    )
    # Результат за вчера
    res_photo = q(f"SELECT COUNT(*) FROM ojr_photo_log WHERE photo_date = '{yesterday}';")
    res_s3 = q(f"SELECT COUNT(*) FROM ojr_section3_work_log WHERE work_date = '{yesterday}';")
    res_s1 = q(
        f"SELECT COUNT(*) FROM ojr_section1_personnel "
        f"WHERE (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bishkek')::date = '{yesterday}';"
    )

    raw_img, raw_doc, raw_txt = int(raw_img), int(raw_doc), int(raw_txt)
    res_photo, res_s3, res_s1 = int(res_photo), int(res_s3), int(res_s1)

    alerts = []
    # Фото: сырьё есть, но photo_log пуст — разрыв разбора
    if raw_img > 0 and res_photo == 0:
        alerts.append(f"image: сырьё {raw_img} → ojr_photo_log {res_photo} (разрыв разбора)")
    # Тексты/объёмы: сырьё есть, но section3/1 пусты
    if raw_txt > 0 and res_s3 == 0 and res_s1 == 0:
        alerts.append(f"text: сырьё {raw_txt} → ojr_section1/3 {res_s1}/{res_s3} (разрыв разбора)")
    # Документы: сырьё есть, но section5 пуст (после реализации маршрута)
    if raw_doc > 0:
        s5 = q(
            f"SELECT COUNT(*) FROM ojr_section5_asbuilt_docs "
            f"WHERE (created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bishkek')::date = '{yesterday}';"
        )
        if int(s5) == 0:
            alerts.append(f"document: сырьё {raw_doc} → ojr_section5 {s5} (разрыв разбора)")

    if alerts:
        print(f"⚠️ Alikhan разрыв разбора за {yesterday} (сырьё есть, результат нет):")
        for a in alerts:
            print(f"  - {a}")
        print("Данные в bot_memory_messages целы. Проверить диспетчер/маршрут.")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
