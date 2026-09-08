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

## GIVEN / WHEN / THEN

### GIVEN текст с VOR-кодами и планом `qa-parser.vor_code_extraction_numbers`
- WHEN `_extract_vor_codes('Планы на завтра 3.1.5 = 142,66')`
- THEN один факт: `code == '3.1.5'`, `volume == 142.66`, `category == 'план'`, `is_plan is True`

### GIVEN факты персонала с total и специальностями `qa-parser.personnel_specialties_aggregate_no_double_count`
- WHEN `_aggregate_personnel_facts` до save
- THEN `workers_total` агрегирован без двойного счёта специальностей

### GIVEN вопрос-текст (категория negative golden-набора) `qa-parser.question_text_is_not_qa`
- WHEN `is_qa(text)` на каждом negative-кейсах
- THEN False для всех (ни один не триггерит QA)

### GIVEN end-to-end разбор текста (parse_qa с живым xAI) `qa-parser.parse_qa_e2e_xai`
<!-- no-ci -->
- WHEN полный пайплайн с LLM
- THEN живой xAI API — в CI не переносим (прод-инвариант); 9 golden-тестов скипаются в CI
