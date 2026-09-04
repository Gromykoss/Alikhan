#!/usr/bin/env python3
"""One-shot migration of vehicle pass documents from section5 to pass register.

Does not delete rows from ojr_section5_asbuilt_docs. Safe to re-run: skips
records with the same pass_date + full_name + vehicle_plate in ojr_pass_register.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from db import get_conn  # noqa: E402
from whatsapp_commands import (  # noqa: E402
    _extract_docx_text,
    _is_pass_document,
    _parse_pass_document,
)


def _get_title_id(cur):
    cur.execute("SELECT id FROM ojr_title_page WHERE is_active = TRUE LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else 1


def _register_duplicate_exists(cur, parsed):
    cur.execute(
        """
        SELECT 1
        FROM ojr_pass_register
        WHERE pass_date IS NOT DISTINCT FROM %s::date
          AND full_name IS NOT DISTINCT FROM %s
          AND vehicle_plate IS NOT DISTINCT FROM %s
        LIMIT 1
        """,
        (
            parsed.get("pass_date"),
            parsed.get("full_name"),
            parsed.get("vehicle_plate"),
        ),
    )
    return cur.fetchone() is not None


def migrate():
    checked = 0
    found_passes = 0
    inserted = 0
    duplicates = 0
    non_passes = []

    conn = get_conn()
    cur = conn.cursor()
    try:
        title_id = _get_title_id(cur)
        cur.execute(
            """
            SELECT id, doc_name, file_message_id, file_path
            FROM ojr_section5_asbuilt_docs
            WHERE file_path IS NOT NULL
              AND lower(file_path) LIKE '%%.docx'
            ORDER BY id
            """
        )
        rows = cur.fetchall()

        for section5_id, doc_name, file_message_id, file_path in rows:
            if not file_path or not os.path.isfile(file_path):
                continue
            checked += 1
            text = _extract_docx_text(file_path)
            if not _is_pass_document(text):
                non_passes.append((section5_id, doc_name))
                continue

            found_passes += 1
            parsed = _parse_pass_document(text, doc_name or os.path.basename(file_path))
            if _register_duplicate_exists(cur, parsed):
                duplicates += 1
                continue

            cur.execute(
                """
                INSERT INTO ojr_pass_register
                (title_id, pass_date, full_name, organization_name, position, pass_type,
                 pass_number, vehicle_plate, status, file_message_id, file_path, notes,
                 created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'выдан', %s, %s, %s, NOW(), NOW())
                """,
                (
                    title_id,
                    parsed.get("pass_date"),
                    parsed.get("full_name"),
                    parsed.get("organization_name"),
                    parsed.get("position"),
                    parsed.get("pass_type"),
                    parsed.get("pass_number"),
                    parsed.get("vehicle_plate"),
                    file_message_id,
                    file_path,
                    parsed.get("notes"),
                ),
            )
            inserted += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print(f"Всего .docx проверено: {checked}")
    print(f"Найдено пропусков: {found_passes}")
    print(f"Вставлено новых: {inserted}")
    print(f"Пропущено дублей: {duplicates}")
    print("НЕ-пропуска:")
    for section5_id, doc_name in non_passes:
        print(f"- {section5_id}: {doc_name}")


if __name__ == "__main__":
    migrate()
