# PostgreSQL Regex in psycopg2: `\d` vs `[0-9]`

## Problem

`smart_evening_check.py::get_qa_status()` uses `~ E'\d+\.\d+\.\d+'` for matching VOR codes in facts. PostgreSQL regex engine does NOT support `\d` as a digit class — use `[0-9]` bracket syntax instead.

## Wrong

```python
# Does NOT work (returns 0 matches):
cur.execute("SELECT count(*) FROM bot_memory_facts WHERE fact ~ E'\\d+\\.\\d+\\.\\d+'")
```

## Right

```python
# Works (returns correct count):
cur.execute("SELECT count(*) FROM bot_memory_facts WHERE fact ~ E'[0-9]+[.][0-9]+[.][0-9]+'")
```

## Why

PostgreSQL `~` operator uses POSIX regex syntax, NOT Perl-compatible `\d` shorthand. `\d` is treated as literal backslash-d, not digit class. Use explicit character classes: `[0-9]` for digits, `[.]` for literal dot.

## Affected code

- `smart_evening_check.py` line 67: `fact ~ E'[0-9]+[.][0-9]+[.][0-9]+'`
- Any future PostgreSQL `~` regex queries in the project
