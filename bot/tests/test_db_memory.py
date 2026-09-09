"""GWT tests for db_memory against an isolated test Postgres."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import psycopg2
import pytest


BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))


def _reset_schema(conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS bot_memory_facts, bot_memory_messages")
    cur.execute(
        """
        CREATE TABLE bot_memory_messages (
            id SERIAL PRIMARY KEY,
            chat_id TEXT,
            sender TEXT,
            role TEXT,
            content TEXT,
            message_type TEXT DEFAULT 'text',
            file_name TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    conn.commit()
    cur.close()


@pytest.fixture(scope="function")
def db_conn(monkeypatch):
    dsn = os.environ.get("GWT_TEST_DB_DSN")
    if not dsn:
        pytest.skip("GWT_TEST_DB_DSN не задан — db_memory тесты CI-only")

    import db as db_mod

    params = psycopg2.extensions.parse_dsn(dsn)
    monkeypatch.setitem(db_mod.DB_CONFIG, "host", params["host"])
    monkeypatch.setitem(db_mod.DB_CONFIG, "port", params["port"])
    monkeypatch.setitem(db_mod.DB_CONFIG, "user", params["user"])
    monkeypatch.setitem(db_mod.DB_CONFIG, "password", params["password"])
    monkeypatch.setitem(db_mod.DB_CONFIG, "dbname", params["dbname"])
    monkeypatch.setattr(db_mod, "resolve_db_host", lambda: params["host"])

    conn = psycopg2.connect(**db_mod.DB_CONFIG)
    _reset_schema(conn)
    yield conn
    conn.close()


@pytest.mark.scenario("data-ingestion.ensure_memory_tables_idempotent")
def test_ensure_memory_tables_idempotent(db_conn):
    import db_memory

    db_memory.ensure_memory_tables()
    db_memory.ensure_memory_tables()

    cur = db_conn.cursor()
    cur.execute("SELECT to_regclass('bot_memory_facts') IS NOT NULL")
    assert cur.fetchone()[0] is True
    cur.execute(
        """
        SELECT data_type, udt_name
        FROM information_schema.columns
        WHERE table_name = 'bot_memory_messages'
          AND column_name = 'tags'
        """
    )
    assert cur.fetchone() == ("jsonb", "jsonb")
    cur.close()


@pytest.mark.scenario("data-ingestion.save_fact_roundtrip_lookup")
def test_save_fact_roundtrip_lookup(db_conn):
    import db_memory

    db_memory.ensure_memory_tables()
    fact_id = db_memory.save_fact(
        chat_id="c1",
        fact_date=date(2026, 9, 9),
        building="B1",
        category="clean",
        fact="помыл пол",
        source_ids=[1, 2],
    )

    # ВАЖНО: save_fact возвращает cur.lastrowid — в psycopg2 это OID-прокси
    # (0 на таблицах без OIDS), НЕ SERIAL id; контракт функции — факт записи,
    # id читается через fact_lookup, поэтому здесь только type-sanity.
    assert fact_id is None or isinstance(fact_id, int)
    rows = db_memory.fact_lookup(chat_id="c1")
    assert len(rows) == 1
    row = rows[0]
    assert row["chat_id"] == "c1"
    assert row["fact_date"] == date(2026, 9, 9)
    assert row["building"] == "B1"
    assert row["category"] == "clean"
    assert row["fact"] == "помыл пол"
    assert row["source_ids"] == [1, 2]
    assert db_memory.fact_lookup(chat_id="c1", category="other") == []


@pytest.mark.scenario("data-ingestion.fact_lookup_filters_and_order")
def test_fact_lookup_filters_and_order(db_conn):
    import db_memory

    db_memory.ensure_memory_tables()
    db_memory.save_fact("c1", date(2026, 9, 7), "B1", "work", "d7")
    db_memory.save_fact("c1", date(2026, 9, 9), "B1", "work", "d9")
    db_memory.save_fact("c1", date(2026, 9, 8), "B2", "work", "d8")

    assert [row["fact_date"] for row in db_memory.fact_lookup("c1")] == [
        date(2026, 9, 9),
        date(2026, 9, 8),
        date(2026, 9, 7),
    ]
    assert len(db_memory.fact_lookup("c1", limit=2)) == 2
    assert len(db_memory.fact_lookup("c1", building="B2")) == 1
    assert len(db_memory.fact_lookup("c1", start_date=date(2026, 9, 8))) == 2
    assert len(db_memory.fact_lookup("c1", end_date=date(2026, 9, 8))) == 2


@pytest.mark.scenario("data-ingestion.tag_message_untagged_flow")
def test_tag_message_untagged_flow(db_conn):
    import db_memory

    db_memory.ensure_memory_tables()
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO bot_memory_messages (chat_id, sender, role, content)
        VALUES (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s)
        RETURNING id
        """,
        ("c1", "s1", "user", "m1", "c1", "s2", "user", "m2", "c2", "s3", "user", "other-chat"),
    )
    id1, id2, id_other = [row[0] for row in cur.fetchall()]
    db_conn.commit()
    cur.close()

    rows = db_memory.get_untagged_messages(chat_id="c1")
    assert [row["id"] for row in rows] == [id1, id2]

    db_memory.tag_message(id1, {"theme": "фото"})

    rows = db_memory.get_untagged_messages(chat_id="c1")
    assert [row["id"] for row in rows] == [id2]
    # фильтр chat_id: чужие сообщения не попадают в выборку c1
    rows = db_memory.get_untagged_messages(chat_id="c2")
    assert [row["id"] for row in rows] == [id_other]
    rows = db_memory.get_untagged_messages()
    assert [row["id"] for row in rows] == [id2, id_other]
