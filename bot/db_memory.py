import psycopg2, psycopg2.extras, json
from db import get_conn

def ensure_memory_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("ALTER TABLE bot_memory_messages ADD COLUMN IF NOT EXISTS tags JSONB")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_memory_facts (
            id SERIAL PRIMARY KEY,
            chat_id TEXT NOT NULL,
            fact_date DATE,
            building TEXT,
            category TEXT,
            fact TEXT NOT NULL,
            source_ids INTEGER[],
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit(); cur.close(); conn.close()

def save_fact(chat_id, fact_date, building, category, fact, source_ids=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO bot_memory_facts (chat_id, fact_date, building, category, fact, source_ids) VALUES (%s,%s,%s,%s,%s,%s)",
               (chat_id, fact_date, building, category, fact, source_ids))
    conn.commit()
    fid = cur.lastrowid
    cur.close(); conn.close()
    return fid

def fact_lookup(chat_id, building=None, start_date=None, end_date=None, category=None, limit=10):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT * FROM bot_memory_facts WHERE chat_id=%s"
    params = [chat_id]
    if building:
        query += " AND building=%s"; params.append(building)
    if start_date:
        query += " AND fact_date >= %s"; params.append(start_date)
    if end_date:
        query += " AND fact_date <= %s"; params.append(end_date)
    if category:
        query += " AND category=%s"; params.append(category)
    query += " ORDER BY fact_date DESC LIMIT %s"; params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def tag_message(msg_id, tags_dict):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE bot_memory_messages SET tags=%s WHERE id=%s", (json.dumps(tags_dict), msg_id))
    conn.commit(); cur.close(); conn.close()

def get_untagged_messages(chat_id=None, limit=20):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT id, content, file_name, message_type FROM bot_memory_messages WHERE tags IS NULL"
    params = []
    if chat_id:
        query += " AND chat_id=%s"; params.append(chat_id)
    query += " ORDER BY id LIMIT %s"; params.append(limit)
    cur.execute(query, params)
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows
