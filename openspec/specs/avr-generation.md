# Domain: avr-generation

## Role
АВР (акт выполненных работ): КС-2 (акт за период, 15 колонок) и КС-6 (накопительный журнал, 4 раздела).

## Canonical Sources
- `MASTER_SPEC.md` §6
- `report/templates/ВОР_с_расценками.xlsx` (837 кодов ВОР)

## Code Owners
- `bot/avr.py` (КС-2/КС-6, 780+ строк)

## Neighbor Risks
- `ejo-generation` (источник — ЕЖО колонки K/P/S, НЕ ojr_section3)
- `vor-import` (справочник кодов)

## Known Traps
- Источник АВР — `ЕЖО_шаблон.xlsx` (колонки K/P/S), НЕ `ojr_section3_work_log`.
- Команды: `АВР`, `формируй АВР`, `кс-2`, `кс-6`, `АВР за июнь`.

## Update Rule
Менялся формат КС-2/КС-6 → обнови `test_avr.py` + MASTER_SPEC §6.

## GIVEN / WHEN / THEN

### GIVEN прайс-лист с кодом `2.1.1` по колонке F `avr-generation.pricing_exact_vor_code_no_prefix_match`
- WHEN загрузка прайса через load_pricing
- THEN `unit_price` = 600 по точному коду `2.1.1`, префикс `2.1` НЕ матчится (запрет префикс-дрейфа)

### GIVEN ЕЖО-шаблон (колонки K/P/S) с 5 строками работ `avr-generation.ks2_from_ejo_columns`
- WHEN generate_ks2 за период июль 2026
- THEN КС-2: заказчик в B1, строка `2.1.1` с планом 1007 в колонке E и ценой 600 в F

### GIVEN те же ЕЖО-данные `avr-generation.ks6_grouped_rows_complete`
- WHEN generate_ks6 за тот же период
- THEN один файл `КС-6_2026-07.xlsx` с группированной таблицей, каждая ЕЖО-строка с фактом присутствует
