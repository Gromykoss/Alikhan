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
