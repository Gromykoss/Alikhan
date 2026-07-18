# OJR Migration — Routing Patterns (2026-07-18)

After the OJR migration, data flows through these routing rules across all modules.

## qa.py → OJR routing

| User fact category | OJR target table | DB helper | Key logic |
|---|---|---|---|
| VOR codes (regex) | `ojr_section3_work_log` | `save_work_log()` | Extracted BEFORE Grok, category from prefix detection |
| `персонал` | `ojr_section1_personnel` | `save_personnel()` | Parses org name + ITR/worker from fact text |
| `инцидент` | `ojr_incidents` | `save_incident()` | severity='minor' by default |
| `документация` / `материалы` | `ojr_materials` | `save_material()` | Whole fact text as material_name |
| `бетонирование` / `монтаж` / `земляные работы` / `техника` / `план` / `объём` | `ojr_section3_work_log` | `save_work_log()` | Tries to extract VOR code; falls back to work_name=fact |

## poll.py → OJR routing

| Poll action | OJR target | Helper |
|---|---|---|
| `parse_poll_reply()` code=volume | `ojr_section3_work_log` | `save_work_log(created_by='poll', source_poll_id=…)` |
| `close_poll()` auto-fill (бетонирование, монтаж, земляные) | `ojr_section3_work_log` | `save_work_log(created_by='auto')` |
| `close_poll()` auto-fill (документация) | `ojr_materials` | `save_material()` |
| `_get_qa_status()` | All OJR tables via `get_ojr_qa_status()` | New db helper |

Backward compatibility: `bot_poll_state` + `bot_poll_residuals` still used for poll lifecycle management.

## fill_ejo.py → OJR sources

| EJO section | Primary source | Legacy fallback |
|---|---|---|
| Weather | `ojr_weather` (saves on every fill_ejo run) | — |
| Incidents | `ojr_incidents` via `get_daily_incidents()` | `bot_memory_facts` |
| Staff | `bot_memory_facts` (still reads via `qa()`) ⚠️ future: `ojr_section1_personnel` | — |
| Volumes (works) | `ojr_section3_work_log` via `get_daily_works()` | `bot_memory_facts` regex parse |
| Photos | `ojr_photo_log` (primary), then `bot_memory_messages` | Both checked |

## main_waha.py → OJR sources

| Snapshot component | OJR source | Notes |
|---|---|---|
| QA facts (works) | `ojr_section3_work_log` | queried by `work_date` |
| QA facts (incidents) | `ojr_incidents` | queried by `incident_date` |
| Photos | `bot_memory_messages` + `ojr_photo_log` | Both sources merged, dedup not needed |
| Messages | `bot_memory_messages` | Unchanged |
| EJO volume extraction | `ojr_section3_work_log` (new) + `bot_memory_facts` (legacy) | Dual-write for backward compat |

## Graceful fallback pattern

Every OJR read has this structure:
```python
try:
    from db import get_daily_works
    works = get_daily_works(date_str)
    # ... process OJR data
except Exception as e:
    print(f"[MODULE OJR ERR] {e}, falling back to legacy", flush=True)
    # ... legacy bot_memory_facts query
```

This ensures the bot doesn't break if OJR tables are missing or schema changes.
