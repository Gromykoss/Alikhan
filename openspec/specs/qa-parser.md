# Domain: qa-parser

## Role
Разбор текста прорабов → факты (персонал, техника, объёмы, VOR) через Grok. VOR-коды — regex'ом ДО LLM (Grok не видит коды).

## Canonical Sources
- `bot/CONTRACTS.md` §2.5 (qa.py)
- `bot/tests/schemas/qa_fact.json` / `qa_facts_array.json`

## Code Owners
- `bot/qa.py` (`parse_qa`, `_aggregate_equipment_facts`, `_equipment_items_from_fact`)

## Neighbor Risks
- `data-ingestion` (сырьё-текст)
- `ojr-data-contract` (факты → таблицы)

## Known Traps
- Профессии ≠ техника: `крановщик` / `машинист крана` НЕ техника (нормализация `ё→е`, префиксы `машинист\w*`).
- Техника агрегируется ДО save (суммирование по канон-имени).

## Update Rule
Менялся парсер → обнови `test_qa_parser.py` + `tests/test_qa_golden.py` + CONTRACTS.md §qa.
