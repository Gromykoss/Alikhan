"""Fail-closed validation gate for Alikhan data claims.

This module turns data assertions into observed database evidence before the
router lets an LLM summarize facts.
"""

import sys
from pathlib import Path

import psycopg2.sql

sys.path.insert(0, str(Path(__file__).resolve().parent))

from authority import (  # noqa: E402
    CORE_DATA_TABLES,
    DATA_EVIDENCE_KIND,
    Claim,
    Evidence,
    Verdict,
    validate_claim,
)
from db import get_conn  # noqa: E402


ALLOWED_COUNT_TABLES = frozenset(
    (
        "bot_memory_messages",
        "bot_memory_facts",
        "ojr_section1_personnel",
        "ojr_section3_work_log",
        "ojr_photo_log",
    )
)

CLAIM_TABLES = {
    "personnel_ok": ("bot_memory_facts",),
    "volume_ok": ("ojr_section3_work_log",),
    "photo_ok": ("ojr_photo_log",),
    "not_lost": CORE_DATA_TABLES,
    "data_ok": CORE_DATA_TABLES,
}

TABLE_DATE_WHERE = {
    "bot_memory_messages": "WHERE COALESCE(message_time, created_at)::date = CURRENT_DATE",
    "bot_memory_facts": "WHERE fact_date = CURRENT_DATE",
    "ojr_section1_personnel": "WHERE start_date = CURRENT_DATE",
    "ojr_section3_work_log": "WHERE work_date = CURRENT_DATE",
    "ojr_photo_log": "WHERE photo_date = CURRENT_DATE",
}


def _validate_table(table: str) -> None:
    if table not in ALLOWED_COUNT_TABLES:
        raise ValueError(f"Недопустимая таблица для count_rows: {table}")


def _validate_where(where: str) -> str:
    where = (where or "").strip()
    if not where:
        return ""
    if not where.upper().startswith("WHERE "):
        raise ValueError("where должен начинаться с WHERE")
    if ";" in where or "--" in where or "/*" in where or "*/" in where:
        raise ValueError("where содержит запрещённый SQL-фрагмент")
    return where


def _count_sql_text(table: str, where: str = "") -> str:
    where = _validate_where(where)
    return f"SELECT count(*) FROM {table}" + (f" {where}" if where else "")


def count_rows(table: str, where: str = "") -> int:
    """Run SELECT count(*) against a whitelisted table and return an int.

    Database/query failures are intentionally raised to the caller so the gate
    can fail closed instead of silently treating missing evidence as success.
    """

    _validate_table(table)
    where = _validate_where(where)

    query = psycopg2.sql.SQL("SELECT count(*) FROM {}").format(
        psycopg2.sql.Identifier(table)
    )
    if where:
        query += psycopg2.sql.SQL(" ") + psycopg2.sql.SQL(where)

    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(query)
            row = cur.fetchone()
            return int(row[0])
        finally:
            cur.close()
    finally:
        conn.close()


def build_evidence(claim_kind: str, counts: dict) -> Evidence:
    """Build observed SELECT-count evidence for authority.validate_claim."""

    sql_source = counts.get("source") or counts.get("sql") or ""
    value = counts.get("counts", counts)
    return Evidence(
        kind=DATA_EVIDENCE_KIND,
        source=str(sql_source),
        value=value,
        observed=True,
        note=f"claim_kind={claim_kind}",
    )


def assert_data_claim(claim_kind: str) -> tuple[bool, Verdict, str]:
    """Validate a data claim using real SELECT count evidence.

    Any database or contract problem returns a blocking verdict instead of
    raising to the router.
    """

    tables = CLAIM_TABLES.get(claim_kind)
    if not tables:
        return (
            False,
            Verdict.INVALID_CONTRACT,
            f"Недопустимый data-claim: {claim_kind}",
        )

    try:
        counts = {}
        sql_sources = []
        for table in tables:
            where = TABLE_DATE_WHERE[table]
            counts[table] = count_rows(table, where)
            sql_sources.append(_count_sql_text(table, where))

        evidence = build_evidence(
            claim_kind,
            {
                "counts": counts,
                "source": ";\n".join(sql_sources),
            },
        )
        claim = Claim(kind=claim_kind, evidence=[evidence])
        verdict = validate_claim(claim)
        if verdict.passes:
            return True, verdict, f"БД проверена: {counts}"
        return False, verdict, f"Data-claim не подтверждён: {verdict.value}; counts={counts}"
    except Exception as exc:
        return False, Verdict.INCONCLUSIVE, f"БД недоступна: {exc}"


__all__ = [
    "ALLOWED_COUNT_TABLES",
    "CLAIM_TABLES",
    "count_rows",
    "build_evidence",
    "assert_data_claim",
]
