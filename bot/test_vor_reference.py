#!/usr/bin/env python3
"""Tests for VOR reference importer."""

from decimal import Decimal
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_code_keeps_distinct_decimal_like_strings():
    from vor_reference import _code

    assert _code("5.10") == "5.10"
    assert _code("5.1") == "5.1"
    assert _code("2,1") == "2.1"


def test_load_vor_reference_dry_run_reads_real_files():
    from vor_reference import load_vor_reference

    result = load_vor_reference(dry_run=True)

    assert result["total"] > 500
    assert result["with_price"] > 500
    assert result["inserted"] == 0
    assert result["updated"] == 0


class _ConflictCursor:
    def __init__(self):
        self.fetchone_result = None

    def execute(self, sql, params=None):
        if "SELECT vor_code, work_name, unit" in sql:
            self.fetchone_result = ("1.1", "Старая работа", "м2")
        elif "INSERT INTO ojr_vor_reference" in sql:
            raise AssertionError("conflicting row must not be upserted")

    def fetchone(self):
        return self.fetchone_result

    def close(self):
        pass


class _ConflictConn:
    def __init__(self):
        self.cursor_obj = _ConflictCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_load_vor_reference_skips_conflicting_identity(monkeypatch):
    import vor_reference

    conn = _ConflictConn()
    monkeypatch.setattr(vor_reference, "_load_prices", lambda path: {})
    monkeypatch.setattr(
        vor_reference,
        "_load_vor_rows",
        lambda path, prices: {
            "1.1": {
                "vor_code": "1.1",
                "stage": "1",
                "work_name": "Новая работа",
                "unit": "м3",
                "quantity": Decimal("1"),
                "unit_price": None,
                "source": "test.xlsx",
            }
        },
    )
    monkeypatch.setattr(vor_reference, "get_conn", lambda: conn)

    result = vor_reference.load_vor_reference(dry_run=False)

    assert result["total"] == 1
    assert result["skipped_conflict"] == 1
    assert result["inserted"] == 0
    assert result["updated"] == 0
    assert conn.committed
    assert conn.closed
