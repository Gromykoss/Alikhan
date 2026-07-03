import ipaddress
import os
import subprocess

import psycopg2, psycopg2.extras
from datetime import datetime

DB_PASS = "pass123"
try:
    with open('/home/hermes-workspace/.hermes/secrets.env') as f:
        for line in f:
            if line.startswith('EVO_DB_PASS=') or line.startswith('DB_PASS='):
                DB_PASS = line.strip().split('=', 1)[1]
except:
    pass

def _valid_ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False

def _docker_container_ip(container_name="evolution-postgres"):
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container_name,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
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
    "dbname": "evolution_db"
}

def get_conn():
    DB_CONFIG["host"] = resolve_db_host()
    return psycopg2.connect(**DB_CONFIG)

def save_message(chat_id, sender, role, content, message_type="text", file_name=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO bot_memory_messages (chat_id, sender, role, message_type, content, file_name, message_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (chat_id, sender, role, message_type, content, file_name, datetime.utcnow()))
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

def ensure_schedule_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_schedule_phases (
            id SERIAL PRIMARY KEY,
            building TEXT,
            phase_num INTEGER,
            phase_name TEXT,
            description TEXT,
            start_date DATE,
            end_date DATE,
            duration_days INTEGER,
            status TEXT DEFAULT 'planned',
            parent_phase_id INTEGER REFERENCES bot_schedule_phases(id),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    # Add parent_phase_id if table already exists without it (migration)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'bot_schedule_phases' AND column_name = 'parent_phase_id'
            ) THEN
                ALTER TABLE bot_schedule_phases ADD COLUMN parent_phase_id INTEGER REFERENCES bot_schedule_phases(id);
            END IF;
        END $$;
    """)
    conn.commit()
    cur.close()
    conn.close()

def seed_schedule():
    """Seed schedule from ГРАФИК СМР.pdf (53 tasks, 8 phases + 45 sub-tasks).
    Source: PDF extracted 02.07.2026. Dates verified against original document.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bot_schedule_phases")
    if cur.fetchone()[0] > 0:
        cur.close()
        conn.close()
        return

    # Phase definitions (8 high-level stages)
    phases = [
        (None, 1, 'ПСД, подготовка', 'Разработка ПСД, изыскания, согласования, сметы', '2025-04-30', '2026-06-26', 423, 'completed', None),
        (None, 2, 'Фундаменты, металлоконструкции', 'Фундаменты, МК 1 этажа, перекрытия', '2026-01-05', '2026-06-30', 177, 'active', None),
        (None, 3, 'М/каркас, перекрытия, цоколь', 'М/каркас 2-3 этажей, перекрытия, огнезащита, цокольные стены', '2026-05-23', '2026-07-31', 70, 'active', None),
        (None, 4, 'Ограждающие, кровля, окна', 'Сэндвич-панели, кровля, оконные блоки', '2026-06-15', '2026-10-30', 138, 'active', None),
        (None, 5, 'Внутренние системы, отделка', 'Отопление, вентиляция, водоснабжение, электрика, отделка', '2026-11-01', '2027-07-01', 243, 'active', None),
        (None, 6, 'СКС и безопасность', 'Структурированные кабельные системы, система безопасности', '2027-01-15', '2027-07-10', 177, 'active', None),
        (None, 7, 'Внутриплощадочные сети', 'Инженерно-техническое обеспечение', '2026-07-01', '2026-10-01', 93, 'active', None),
        (None, 8, 'Благоустройство, сдача', 'Благоустройство, документация, ввод в эксплуатацию', '2026-07-01', '2027-07-31', 396, 'active', None),
    ]
    phase_ids = {}
    for code, pnum, name, desc, start, end, days, status, resp in phases:
        cur.execute("""
            INSERT INTO bot_schedule_phases (building, code, phase_num, phase_name, description, start_date, end_date, duration_days, status, responsible)
            VALUES ('общая', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (code, pnum, name, desc, start, end, days, status, resp))
        phase_ids[pnum] = cur.fetchone()[0]

    # Sub-tasks from ГРАФИК СМР.pdf (45 items)
    tasks = [
        # --- Этап 1: ПСД, подготовка (23 sub-tasks) ---
        ('1.1', 1, 'Гарантийное письмо от Заказчика', '2025-04-30', '2025-04-30', 1, 'completed', 'Заказчик'),
        ('1.2', 1, 'Заключение договора', '2025-05-30', '2025-05-30', 1, 'completed', 'Стороны'),
        ('1.3', 1, 'Передача исходных данных', '2025-05-30', '2025-05-30', 1, 'completed', 'Заказчик'),
        ('1.4', 1, 'Передача строительной площадки', '2025-05-30', '2025-05-30', 1, 'completed', 'Заказчик'),
        ('1.5', 1, 'Разработка и согласование ПСД', '2025-06-02', '2026-06-26', 390, 'completed', 'Подрядчик'),
        ('1.6', 1, 'Выполнение инженерных изысканий', '2025-06-02', '2025-10-13', 134, 'completed', 'Подрядчик'),
        ('1.7', 1, 'Выдача Технических условий', '2025-09-10', '2025-09-19', 10, 'completed', 'Стороны'),
        ('1.8', 1, 'Разработка ОПР здания Общежития и АБК', '2025-06-25', '2025-07-07', 13, 'completed', 'Подрядчик'),
        ('1.9', 1, 'Согласование ОПР', '2025-07-08', '2025-08-21', 45, 'completed', 'Заказчик'),
        ('1.10', 1, 'Разработка эскизного проекта', '2025-08-22', '2025-09-18', 28, 'completed', 'Подрядчик'),
        ('1.11', 1, 'Согласование эскизного проекта', '2025-09-19', '2025-09-26', 8, 'completed', 'Заказчик'),
        ('1.12', 1, 'Получение Градостроительного заключения', '2025-09-27', '2025-10-06', 10, 'completed', 'Подрядчик'),
        ('1.13', 1, 'Разработка раздела КЖ', '2025-10-01', '2025-10-30', 30, 'completed', 'Подрядчик'),
        ('1.14', 1, 'Разработка раздела АР', '2025-10-07', '2026-02-10', 127, 'completed', 'Подрядчик'),
        ('1.15', 1, 'Разработка раздела КМ', '2025-10-07', '2026-02-10', 127, 'completed', 'Подрядчик'),
        ('1.16', 1, 'Разработка разделов инженерных сетей', '2025-10-07', '2026-02-10', 127, 'completed', 'Подрядчик'),
        ('1.17', 1, 'Согласование рабочего проекта Заказчиком', '2026-02-11', '2026-02-19', 9, 'completed', 'Заказчик'),
        ('1.18', 1, 'Получение заключений госэкспертиз', '2026-02-20', '2026-03-19', 28, 'completed', 'Подрядчик'),
        ('1.19', 1, 'Разработка детальных сметных расчетов', '2026-03-20', '2026-06-01', 74, 'completed', 'Подрядчик'),
        ('1.20', 1, 'Предоставление детальной сметной стоимости', '2026-06-02', '2026-06-02', 1, 'completed', 'Подрядчик'),
        ('1.21', 1, 'Согласование сметной стоимости', '2026-06-02', '2026-06-25', 24, 'completed', 'Заказчик'),
        ('1.22', 1, 'Акт сдачи-приемки по Этапу 1', '2026-06-26', '2026-06-26', 1, 'completed', 'Заказчик'),
        ('1.23', 1, 'Мобилизация техники, оборудования, рабочих', '2025-06-04', '2025-10-01', 120, 'completed', 'Подрядчик'),
        # --- Этап 2: Фундаменты, металлоконструкции (5 sub-tasks) ---
        ('2.1', 2, 'Устройство фундаментов', '2026-04-23', '2026-06-01', 40, 'completed', 'Подрядчик'),
        ('2.2', 2, 'Изготовление и поставка МК (АБК + галерея)', '2026-01-05', '2026-02-20', 47, 'completed', 'Подрядчик'),
        ('2.3', 2, 'Монтаж МК здания АБК и галереи', '2026-02-22', '2026-05-05', 73, 'completed', 'Подрядчик'),
        ('2.4', 2, 'Изготовление и поставка МК (Общежитие)', '2026-01-12', '2026-04-09', 88, 'completed', 'Подрядчик'),
        ('2.5', 2, 'Монтаж МК здания Общежития', '2026-03-10', '2026-06-30', 113, 'active', 'Подрядчик'),
        # --- Этап 3: М/каркас, перекрытия, цоколь (5 sub-tasks) ---
        ('3.1', 3, 'Межэтажные перекрытия (несъемная опалубка) АБК', '2026-05-23', '2026-06-30', 39, 'active', 'Подрядчик'),
        ('3.2', 3, 'Огнезащита МК здания АБК и галереи', '2026-06-01', '2026-07-15', 45, 'active', 'Подрядчик'),
        ('3.3', 3, 'Межэтажные перекрытия (несъемная опалубка) Общежития', '2026-06-16', '2026-07-15', 30, 'active', 'Подрядчик'),
        ('3.4', 3, 'Огнезащита МК здания Общежития', '2026-06-15', '2026-07-20', 36, 'active', 'Подрядчик'),
        ('3.5', 3, 'Цокольные стены и плита пола 1 этажа', '2026-05-23', '2026-07-31', 70, 'active', 'Подрядчик'),
        # --- Этап 4: Ограждающие, кровля, окна (2 sub-tasks) ---
        ('4.1', 4, 'Изготовление и поставка ограждающих конструкций, кровли, окон', '2026-06-15', '2026-10-01', 109, 'active', 'Подрядчик'),
        ('4.2', 4, 'Монтаж ограждающих конструкций, кровли, окон', '2026-07-15', '2026-10-30', 108, 'active', 'Подрядчик'),
        # --- Этап 5: Внутренние системы, отделка (4 sub-tasks) ---
        ('5.1', 5, 'Монтаж систем отопления и вентиляции', '2026-12-15', '2027-07-01', 199, 'active', 'Подрядчик'),
        ('5.2', 5, 'Монтаж систем водоснабжения и канализации', '2026-12-15', '2027-07-01', 199, 'active', 'Подрядчик'),
        ('5.3', 5, 'Электромонтажные работы', '2027-01-10', '2027-07-01', 173, 'active', 'Подрядчик'),
        ('5.4', 5, 'Внутренние отделочные работы', '2026-11-01', '2027-07-01', 243, 'active', 'Подрядчик'),
        # --- Этап 6: СКС и безопасность (1 sub-task) ---
        ('6.1', 6, 'Монтаж СКС и системы безопасности', '2027-01-15', '2027-07-10', 177, 'active', 'Подрядчик'),
        # --- Этап 7: Внутриплощадочные сети (1 sub-task) ---
        ('7.1', 7, 'Монтаж внутриплощадочных инженерных сетей', '2026-07-01', '2026-10-01', 93, 'active', 'Подрядчик'),
        # --- Этап 8: Благоустройство, сдача (4 sub-tasks) ---
        ('8.1', 8, 'Благоустройство и озеленение территории', '2027-05-01', '2027-07-10', 71, 'active', 'Подрядчик'),
        ('8.2', 8, 'Передача исполнительно-технической документации', '2027-07-02', '2027-07-11', 10, 'active', 'Подрядчик'),
        ('8.3', 8, 'Разрешение на ввод объекта в эксплуатацию', '2027-07-12', '2027-07-21', 10, 'active', 'Подрядчик'),
        ('8.4', 8, 'Итоговый акт сдачи-приемки работ', '2027-07-22', '2027-07-31', 10, 'active', 'Заказчик'),
        # --- Cross-cutting ---
        ('0.1', None, 'Авторский надзор на весь период СМР', '2026-04-05', '2027-08-04', 487, 'active', 'Подрядчик'),
    ]

    for code, phase_num, name, start, end, days, status, resp in tasks:
        pid = phase_ids[phase_num] if phase_num else None
        cur.execute("""
            INSERT INTO bot_schedule_phases (building, code, phase_num, phase_name, description, start_date, end_date, duration_days, status, responsible, parent_phase_id)
            VALUES ('общая', %s, %s, %s, '', %s, %s, %s, %s, %s, %s)
        """, (code, phase_num, name, start, end, days, status, resp, pid))

    conn.commit()
    cur.close()
    conn.close()

def get_schedule(building=None, status=None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = []
    params = []
    if building:
        where.append("building=%s")
        params.append(building)
    if status:
        where.append("status=%s")
        params.append(status)
    sql = "SELECT * FROM bot_schedule_phases"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY start_date"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_active_phases(today=None):
    from datetime import date
    if today is None:
        today = date.today()
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM bot_schedule_phases
        WHERE start_date <= %s AND end_date >= %s AND status != 'completed'
        ORDER BY start_date
    """, (today, today))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_upcoming_phases(today=None, days=30):
    from datetime import date, timedelta
    if today is None:
        today = date.today()
    end = today + timedelta(days=days)
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM bot_schedule_phases
        WHERE start_date BETWEEN %s AND %s AND status != 'completed'
        ORDER BY start_date
    """, (today, end))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def check_delays(today=None):
    from datetime import date
    if today is None:
        today = date.today()
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM bot_schedule_phases
        WHERE end_date < %s AND status != 'completed'
        ORDER BY end_date
    """, (today,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
