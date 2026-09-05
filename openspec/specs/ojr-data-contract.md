# Domain: ojr-data-contract

## Role
Хранилище ОЖР: **15 таблиц** (ГОСТ РД-11-05-2007). Единый источник правды по данным — `DATA_CONTRACT.md` (этот файл и есть готовый узел домена, не дублировать).

## Canonical Sources
- **`DATA_CONTRACT.md`** (полный контракт — читать его, не эту карточку)
- `db/ojr_schema.sql` (16 CREATE; 15 канон + pass_register/справочники отдельно)

## Синк-распределение (facts → OJR; модуль `ojr_sync.py` НЕ существует и НЕ БЫЛО в git)
- `bot/db.py` — facts → `ojr_section1_personnel` / `ojr_section3_work_log`; погода → `ojr_weather` (`save_weather`)
- `bot/whatsapp_commands.py` — фото → `ojr_photo_log`; документы → `ojr_section5_asbuilt_docs`; пропуска → `ojr_pass_register`

## Code Owners
- `bot/db.py` (get_conn, SET TIME ZONE 'Asia/Bishkek', синк facts→section1/3 + weather)
- `bot/whatsapp_commands.py` (синк фото/доков/pass_register)
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
