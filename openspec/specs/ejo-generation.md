# Domain: ejo-generation

## Role
ЕЖО (ежедневный отчёт) = view на `ojr_section3_work_log` за дату → Excel 4 листа из шаблона.

## Canonical Sources
- `MASTER_SPEC.md` §6 (колонки ЕЖО, данные)
- `bot/tests/schemas/` (JSON Schema колонок K–U)

## Code Owners
- `bot/fill_ejo.py` (генерация)
- `bot/ejo_backfill.py` (обратный разбор ЕЖО → ОЖР)
- `bot/update_template.py`

## Neighbor Risks
- `ojr-data-contract` (источник данных)

## Known Traps
- `readiness` (готовность %) — формула `base × 0.94 + 6`, НЕ менять без approval (26% корректно).
- Фото читаются через zipfile `xl/media/`, сут.факт = колонка M(13).

## Update Rule
Менялись колонки/формула → обнови `tests/test_ejo_template_contract.py` + MASTER_SPEC §6.

## GIVEN / WHEN / THEN

### GIVEN golden-snapshot шаблона ЕЖО `ejo-generation.template_columns_k_u_contract`
- WHEN чтение заголовков колонок K–U (строки 20/21 листа «Ежедневный отчет»)
- THEN group/detail заголовки точно равны канону (K=11 контрактный объём, M=13 факт сут, U=21 остаток), колонка-буква ↔ номер согласованы

### GIVEN те же заголовки снапшота `ejo-generation.template_columns_match_readers`
- WHEN сверка колонок с кодом читателей
- THEN ejo_backfill читает column=12 (План) и column=13 (Факт), readiness column=11, poll читает column=15 (col O) и column=21 (col U)

### GIVEN лист ЕЖО с «Готовность объекта» на произвольной строке `ejo-generation.readiness_found_by_label_not_row`
- WHEN backfill_ejo разбирает лист
- THEN readiness найден по текстовой метке (НЕ хардкод строки), значение в диапазоне (0, 100]
