#!/usr/bin/env python3
"""
tag_old_photos.py — Tag photos without building tags in the DB.
Sets building='общий' for untagged image messages (AUDIT-009 fix).
Runs once to clean up old data, then can be called periodically.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2.extras
from db import get_conn

def tag_untagged_photos(dry_run=False):
    """Find photos with missing building tag and assign 'общий'.
    Args:
        dry_run: if True, only report count, don't update.
    Returns:
        (tagged_count, total_untagged) tuple
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Find photos with missing building tag
    cur.execute("""
        SELECT id, tags, content FROM bot_memory_messages
        WHERE message_type = 'image'
        AND (tags IS NULL OR tags->>'building' IS NULL OR tags->>'building' = '' OR tags->>'building' = 'без тега')
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()

    total = len(rows)
    tagged = 0

    if dry_run:
        print(f"[DRY RUN] Found {total} untagged photos")
        cur.close()
        conn.close()
        return (0, total)

    for row in rows:
        import json as _json
        msg_id = row['id']
        try:
            tags = row['tags'] if isinstance(row['tags'], dict) else (_json.loads(row['tags']) if row['tags'] else {})
        except (json.JSONDecodeError, TypeError):
            tags = {}

        tags['building'] = 'общий'
        cur.execute(
            "UPDATE bot_memory_messages SET tags = %s WHERE id = %s",
            (_json.dumps(tags), msg_id)
        )
        tagged += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"[TAG] Tagged {tagged}/{total} photos as 'общий'", flush=True)
    return (tagged, total)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    tagged, total = tag_untagged_photos(dry_run=dry)
    if dry:
        print(f"Found {total} untagged photos. Run without --dry-run to tag them.")
    else:
        print(f"Done. Tagged {tagged} photos.")
