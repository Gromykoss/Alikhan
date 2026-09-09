# Domain: data-ingestion

## Role
Сырьё-слой: `bot_memory_messages` — ЖИВОЙ поток (песочница + боевая). Диспетчер пишет каждое сообщение/фото/документ ДО ack. Если строка есть здесь — факт прихода НЕ потерян.

## Canonical Sources
- `DATA_CONTRACT.md` (источник сырья + правило разрыва)

## Code Owners
- `bot/db_memory.py`
- `bot/whatsapp_commands.py` (`_save_prod_text` / `_save_prod_photo` / `_save_prod_document`)

## Neighbor Risks
- `ojr-data-contract` (разбор сырья → ojr_*)
- `qa-parser` (текст → факты)

## Known Traps
- «Сырьё растёт, ojr_* не растёт = разрыв РАЗБОРА, не потеря данных». Чинить разбор (код), НЕ «восстанавливать данные».

## Update Rule
Менялся маршрут записи сырья → обнови DATA_CONTRACT.md + эту карточку.

### GIVEN боевая БД, фото за сегодня `data-ingestion.photo_pipeline_smoke`
<!-- no-ci -->
- WHEN SELECT из ojr_photo_log + bot_memory_messages за сегодня
- THEN фото с local_path существуют; 0 = WARNING не FAIL (семантика smoke-теста); live-DB — в CI не переносим (bot/test_smoke.py::test_smoke_photo_pipeline)

### GIVEN тестовая Postgres `data-ingestion.ensure_memory_tables_idempotent`
- WHEN `ensure_memory_tables()` вызывается дважды
- THEN оба вызова без исключений; `bot_memory_facts` существует; колонка `tags` (JSONB) у `bot_memory_messages` существует

### GIVEN тестовая Postgres `data-ingestion.save_fact_roundtrip_lookup`
- WHEN `save_fact()` пишет факт (building/category/date/source_ids) и `fact_lookup()` читает
- THEN roundtrip полей точный (INTEGER[] source_ids сохраняется), lookup по другому category пуст

### GIVEN тестовая Postgres `data-ingestion.fact_lookup_filters_and_order`
- WHEN факты за 3 даты/2 здания, `fact_lookup()` с фильтрами
- THEN ORDER BY fact_date DESC, LIMIT отсекает, фильтры building/start_date/end_date сужают до ожидаемых строк

### GIVEN тестовая Postgres `data-ingestion.tag_message_untagged_flow`
- WHEN `tag_message()` проставляет теги сообщению
- THEN `get_untagged_messages()` исключает тегнутое, фильтр chat_id работает
