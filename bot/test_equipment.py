#!/usr/bin/env python3
"""Tests for equipment OJR helpers."""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _Cursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _Conn:
    def __init__(self, cursor):
        self.cursor_obj = cursor
        self.committed = False
        self.closed = False

    def cursor(self, *args, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_canon_equipment_name():
    from db import _canon_equipment_name

    assert _canon_equipment_name("Экскаватор CAT") == "Экскаватор"
    assert _canon_equipment_name("самосвал") == "Самосвал"


def test_save_equipment_replace_nulls_source_and_overwrites(monkeypatch):
    import db

    cursor = _Cursor()
    conn = _Conn(cursor)
    monkeypatch.setattr(db, "get_conn", lambda: conn)
    monkeypatch.setattr(db, "_get_active_title_id", lambda: 7)

    db.save_equipment(
        "chat",
        "2026-09-03",
        "Экскаватор CAT",
        quantity=4,
        source_message_id=123,
        mode="replace",
    )

    sql, params = cursor.executed[0]
    assert "WHEN %s = 'replace'" in sql
    assert "source_message_id = CASE" in sql
    assert params[0] == 7
    assert params[2] == "Экскаватор"
    assert params[4] == 4
    assert params[8] is None
    assert params[9] == "replace"
    assert params[12] == "replace"
    assert conn.committed
    assert conn.closed


def test_save_equipment_add_default_keeps_qa_semantics(monkeypatch):
    import db

    cursor = _Cursor()
    conn = _Conn(cursor)
    monkeypatch.setattr(db, "get_conn", lambda: conn)
    monkeypatch.setattr(db, "_get_active_title_id", lambda: 7)

    db.save_equipment("chat", "2026-09-03", "самосвал", quantity=2, source_message_id="42")

    sql, params = cursor.executed[0]
    assert "ELSE ojr_section2_equipment.quantity + EXCLUDED.quantity" in sql
    assert "ojr_section2_equipment.source_message_id = EXCLUDED.source_message_id" in sql
    assert params[2] == "Самосвал"
    assert params[4] == 2
    assert params[8] == 42
    assert params[9] == "add"
    assert params[12] == "add"


def test_get_daily_equipment_filters_work_date(monkeypatch):
    import db

    rows = [{"equipment_name": "Самосвал", "quantity": 2}]
    cursor = _Cursor(rows=rows)
    conn = _Conn(cursor)
    monkeypatch.setattr(db, "get_conn", lambda: conn)

    result = db.get_daily_equipment("2026-09-03")

    sql, params = cursor.executed[0]
    assert "WHERE work_date = %s::date" in sql
    assert params == ("2026-09-03",)
    assert result == rows
    assert conn.closed
