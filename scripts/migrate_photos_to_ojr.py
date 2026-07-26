#!/usr/bin/env python3
"""Migrate existing photos from bot_memory_messages → ojr_photo_log.

One-shot migration: for every bot_memory_messages row with message_type='image'
and a local_path in tags, create the corresponding ojr_photo_log record
if it doesn't already exist.

Safe to run multiple times — skips already-migrated photos.
"""

import sys
import os

# Add bot/ to path for db module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bot'))

from db import get_conn

def migrate():
    conn = get_conn()
    cur = conn.cursor()

    # Count candidates
    cur.execute("""
        SELECT COUNT(*)
        FROM bot_memory_messages
        WHERE message_type = 'image'
          AND tags->>'local_path' IS NOT NULL
          AND id NOT IN (SELECT file_message_id FROM ojr_photo_log WHERE file_message_id IS NOT NULL)
    """)
    candidates = cur.fetchone()[0]
    print(f"[MIGRATE] Candidates: {candidates} photos to migrate")

    if candidates == 0:
        print("[MIGRATE] Nothing to do — all photos already in ojr_photo_log.")
        cur.close()
        conn.close()
        return

    # Get active title_id
    cur.execute("SELECT id FROM ojr_title_page WHERE is_active = TRUE LIMIT 1")
    title_row = cur.fetchone()
    title_id = title_row[0] if title_row else 1
    print(f"[MIGRATE] Using title_id={title_id}")

    # Run migration
    cur.execute("""
        INSERT INTO ojr_photo_log (title_id, photo_date, building, file_message_id,
                                   file_path, ai_description, created_at)
        SELECT
            %s,
            DATE(created_at),
            COALESCE(tags->>'building', 'Общий план'),
            id,
            tags->>'local_path',
            tags->>'description',
            created_at
        FROM bot_memory_messages
        WHERE message_type = 'image'
          AND tags->>'local_path' IS NOT NULL
          AND id NOT IN (SELECT file_message_id FROM ojr_photo_log WHERE file_message_id IS NOT NULL)
    """, (title_id,))
    conn.commit()

    inserted = cur.rowcount
    print(f"[MIGRATE] Inserted {inserted} photos into ojr_photo_log")

    # Verify
    cur.execute("SELECT COUNT(*) FROM ojr_photo_log")
    total = cur.fetchone()[0]
    print(f"[MIGRATE] Total ojr_photo_log rows now: {total}")

    cur.close()
    conn.close()
    print("[MIGRATE] Done.")

if __name__ == '__main__':
    migrate()
