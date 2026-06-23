import psycopg2, psycopg2.extras
from datetime import datetime

DB_CONFIG = {
    "host": "172.22.0.3",
    "port": 5432,
    "user": "evolution",
    "password": "pass123",
    "dbname": "evolution_db"
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def save_message(chat_id, sender, role, content, message_type="text"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, message_time)
        VALUES (%s, %s, %s, %s, %s, %s)""",
        (chat_id, sender, role, message_type, content, datetime.utcnow()))
    conn.commit(); cur.close(); conn.close()

def get_upcoming_events(chat_id, limit=5):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT title, description, event_start, event_end, location
        FROM bot_calendar_events
        WHERE chat_id=%s AND status='active' AND event_start >= NOW()
        ORDER BY event_start LIMIT %s""", (chat_id, limit))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def search_messages(chat_id, query, limit=5):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""SELECT content, sender, message_time, summary
        FROM bot_memory_messages
        WHERE chat_id=%s AND content ILIKE %s
        ORDER BY message_time DESC LIMIT %s""",
        (chat_id, f"%{query}%", limit))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def get_messages_by_date_range(chat_id, start_date, end_date):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            id,
            chat_id,
            COALESCE(message_time, created_at) AS item_time,
            COALESCE(message_time, created_at)::date AS day,
            sender,
            role,
            message_type,
            file_name,
            content,
            summary
        FROM bot_memory_messages
        WHERE (chat_id = %s OR chat_id = 'project:main')
          AND COALESCE(message_time, created_at)::date BETWEEN %s::date AND %s::date
          AND COALESCE(message_type, 'text') IN ('text', 'image', 'document', 'conversation')
          AND COALESCE(content, '') NOT ILIKE '%%удалили данное сообщение%%'
          AND COALESCE(content, '') NOT ILIKE '%%deleted this message%%'
        ORDER BY COALESCE(message_time, created_at), id
    """, (chat_id, start_date, end_date))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def get_participants(chat_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            chat_id,
            participant_id,
            participant_alt,
            push_name,
            first_seen,
            last_seen,
            message_count,
            CASE WHEN chat_id = 'project:main' THEN 'Прошлое' ELSE 'Текущая группа' END AS source_label
        FROM bot_group_participants
        WHERE chat_id = %s OR chat_id = 'project:main'
        ORDER BY
            CASE WHEN chat_id = %s THEN 1 ELSE 2 END,
            message_count DESC,
            last_seen DESC
    """, (chat_id, chat_id))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def get_participant_activity(chat_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH messages AS (
            SELECT
                sender,
                message_type,
                COUNT(*) AS cnt
            FROM bot_memory_messages
            WHERE (chat_id = %s OR chat_id = 'project:main')
              AND sender IS NOT NULL
              AND sender NOT IN ('archive_photo', 'archive_document')
              AND COALESCE(content, '') NOT ILIKE '%%удалили данное сообщение%%'
              AND COALESCE(content, '') NOT ILIKE '%%deleted this message%%'
            GROUP BY sender, message_type
        )
        SELECT
            sender,
            COALESCE(SUM(cnt), 0) AS total_messages,
            COALESCE(SUM(cnt) FILTER (WHERE message_type IN ('text', 'conversation')), 0) AS text_messages,
            COALESCE(SUM(cnt) FILTER (WHERE message_type = 'image'), 0) AS image_messages,
            COALESCE(SUM(cnt) FILTER (WHERE message_type = 'document'), 0) AS document_messages
        FROM messages
        GROUP BY sender
        ORDER BY total_messages DESC, sender
    """, (chat_id,))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def get_message_by_id(msg_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            id,
            chat_id,
            COALESCE(message_time, created_at) AS item_time,
            sender,
            role,
            message_type,
            file_name,
            content,
            summary
        FROM bot_memory_messages
        WHERE id = %s
        LIMIT 1
    """, (msg_id,))
    row = cur.fetchone(); cur.close(); conn.close()
    return row

def delete_calendar_event(chat_id, event_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        UPDATE bot_calendar_events
        SET status = 'deleted',
            updated_at = NOW()
        WHERE id = %s
          AND chat_id = %s
          AND status = 'active'
        RETURNING
            id,
            title,
            description,
            location,
            timezone,
            event_start,
            event_end,
            remind_at,
            remind_minutes_before,
            status
    """, (event_id, chat_id))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    return row

def insert_calendar_event(data):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH input AS (
            SELECT
                %(chat_id)s::text AS chat_id,
                %(created_by)s::text AS created_by,
                %(source_message_id)s::text AS source_message_id,
                %(title)s::text AS title,
                %(description)s::text AS description,
                %(location)s::text AS location,
                %(event_date)s::text AS event_date,
                %(event_time)s::text AS event_time,
                COALESCE(NULLIF(%(timezone)s::text, ''), 'Asia/Bishkek') AS timezone,
                NULLIF(%(event_end_date)s::text, '') AS event_end_date,
                NULLIF(%(event_end_time)s::text, '') AS event_end_time,
                %(remind_minutes_before)s::integer AS remind_minutes_before
        ),
        prepared AS (
            SELECT
                *,
                ((event_date || ' ' || event_time)::timestamp AT TIME ZONE timezone) AS event_start,
                CASE
                    WHEN event_end_date IS NOT NULL AND event_end_time IS NOT NULL
                    THEN ((event_end_date || ' ' || event_end_time)::timestamp AT TIME ZONE timezone)
                    ELSE NULL
                END AS event_end
            FROM input
        ),
        inserted AS (
            INSERT INTO bot_calendar_events (
                chat_id,
                created_by,
                source_message_id,
                title,
                description,
                location,
                event_start,
                event_end,
                timezone,
                remind_at,
                remind_minutes_before,
                reminder_sent,
                status
            )
            SELECT
                chat_id,
                created_by,
                source_message_id,
                title,
                description,
                location,
                event_start,
                event_end,
                timezone,
                CASE
                    WHEN remind_minutes_before IS NOT NULL
                    THEN event_start - (remind_minutes_before || ' minutes')::interval
                    ELSE NULL
                END,
                remind_minutes_before,
                FALSE,
                'active'
            FROM prepared
            RETURNING *
        )
        SELECT
            id,
            chat_id,
            title,
            description,
            location,
            timezone,
            event_start,
            event_end,
            remind_at,
            remind_minutes_before,
            status
        FROM inserted
    """, {
        "chat_id": data.get("chat_id", ""),
        "created_by": data.get("created_by", "Unknown"),
        "source_message_id": data.get("source_message_id", ""),
        "title": data.get("title", "Событие"),
        "description": data.get("description", data.get("title", "Событие")),
        "location": data.get("location", ""),
        "event_date": data.get("date") or data.get("event_date", ""),
        "event_time": data.get("time") or data.get("event_time", ""),
        "timezone": data.get("timezone", "Asia/Bishkek"),
        "event_end_date": data.get("event_end_date", ""),
        "event_end_time": data.get("event_end_time", ""),
        "remind_minutes_before": data.get("remind_minutes_before"),
    })
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    return row

def get_calendar_events(chat_id, range='all'):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH bounds AS (
            SELECT
                %s::text AS chat_id,
                COALESCE(NULLIF(%s::text, ''), 'all') AS range,
                'Asia/Bishkek'::text AS default_timezone
        ),
        ranged AS (
            SELECT
                chat_id,
                range,
                CASE
                    WHEN range = 'today'
                    THEN (date_trunc('day', NOW() AT TIME ZONE default_timezone) AT TIME ZONE default_timezone)
                    WHEN range = 'tomorrow'
                    THEN ((date_trunc('day', NOW() AT TIME ZONE default_timezone) + interval '1 day') AT TIME ZONE default_timezone)
                    WHEN range = 'week'
                    THEN NOW()
                    ELSE NOW()
                END AS start_at,
                CASE
                    WHEN range = 'today'
                    THEN ((date_trunc('day', NOW() AT TIME ZONE default_timezone) + interval '1 day') AT TIME ZONE default_timezone)
                    WHEN range = 'tomorrow'
                    THEN ((date_trunc('day', NOW() AT TIME ZONE default_timezone) + interval '2 days') AT TIME ZONE default_timezone)
                    WHEN range = 'week'
                    THEN NOW() + interval '7 days'
                    ELSE NULL
                END AS end_at
            FROM bounds
        )
        SELECT
            e.id,
            e.chat_id,
            e.title,
            e.description,
            e.location,
            e.timezone,
            e.event_start,
            e.event_end,
            e.remind_at,
            e.remind_minutes_before,
            e.status
        FROM bot_calendar_events e
        JOIN ranged r ON r.chat_id = e.chat_id
        WHERE e.status = 'active'
          AND e.event_start >= r.start_at
          AND (r.end_at IS NULL OR e.event_start < r.end_at)
        ORDER BY e.event_start, e.id
    """, (chat_id, range))
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows
