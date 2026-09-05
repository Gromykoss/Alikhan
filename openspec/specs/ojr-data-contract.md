# Domain: ojr-data-contract

## Role
Хранилище ОЖР: **15 таблиц** (ГОСТ РД-11-05-2007). Единый источник правды по данным — `DATA_CONTRACT.md` (этот файл и есть готовый узел домена, не дублировать).

## Canonical Sources
- **`DATA_CONTRACT.md`** (полный контракт — читать его, не эту карточку)
- `db/ojr_schema.sql` (16 CREATE; 15 канон + pass_register/справочники отдельно)

## Code Owners
- `bot/db.py` (get_conn, SET TIME ZONE 'Asia/Bishkek')
- `bot/ojr_sync.py`
- `bot/data_sources.py` (NamedTuple-контракты)

## Neighbor Risks
- `data-ingestion` (сырьё)
- `qa-parser` (разбор фактов)
- `ejo-generation` (view на ojr_section3)

## Known Traps
- Канон 15, в БД 17 (`ojr_pass_register` + `ojr_vor_reference` — НЕ канон).
- `source_message_id` — BIGINT FK → `bot_memory_messages(id)`, НЕ синтетический хеш.

## Update Rule
Менялась схема → обнови `db/ojr_schema.sql` + DATA_CONTRACT.md + `tests/test_namedtuple_schemas.py`.
