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
