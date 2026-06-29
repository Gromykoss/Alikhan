#!/usr/bin/env python3
"""
Batch tagger for old records in bot_memory_messages (evolution_db only)
"""
import psycopg2
import psycopg2.extras
import json
import time
from datetime import datetime

from db import get_conn


def ensure_tags_column():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE bot_memory_messages 
        ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '{}'::jsonb
    """)
    conn.commit()
    cur.close()
    conn.close()

def batch_tag_old_records(batch_size=20):
    """Tag existing untagged records using Grok classification (stub for now)"""
    ensure_tags_column()
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT id, content, message_type, file_name 
        FROM bot_memory_messages 
        WHERE tags IS NULL OR tags = '{}'::jsonb
        ORDER BY id 
        LIMIT %s
    """, (batch_size,))
    
    records = cur.fetchall()
    print(f"Found {len(records)} untagged records")
    
    for rec in records:
        # Stub classification - in real would call Grok
        tags = {
            "building": "общая площадка",
            "work_type": "документация" if rec['message_type'] == 'text' else "фотофиксация",
            "key_facts": {"people": [], "quantities": [], "dates": []}
        }
        cur2 = conn.cursor()
        cur2.execute("""
            UPDATE bot_memory_messages 
            SET tags = %s 
            WHERE id = %s
        """, (json.dumps(tags), rec['id']))
        conn.commit()
        cur2.close()
        print(f"Tagged message {rec['id']}")
    
    cur.close()
    conn.close()
    return len(records)

if __name__ == "__main__":
    ensure_tags_column()
    total = 0
    while True:
        processed = batch_tag_old_records(20)
        total += processed
        if processed == 0:
            break
        time.sleep(1)
    print(f"Total tagged: {total}")
