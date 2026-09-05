# Domain: vor-import (ПИЛОТ — полная спецификация)

## Role
Детерминированный импорт справочника ВОР из Excel в `ojr_vor_reference`. Коды извлекаются regex'ом ДО LLM — Grok их не видит, не галлюцинирует.

## Canonical Sources
- `bot/CONTRACTS.md` §2.9b (vor_reference)
- `bot/vor_reference.py` (имплементация)
- `report/templates/ВОР.xlsx` + `ВОР_с_расценками.xlsx` (источник)

## Code Owners
- `bot/vor_reference.py` (`load_vor_reference`, `_code`, `_decimal`, `_load_prices`, `_load_vor_rows`)

## Neighbor Risks
- `avr-generation` (КС-2/КС-6 используют справочник кодов)

## Known Traps
- ВОР-коды хранятся строками: НЕ форматировать через `.15g` (5.10 ≠ 5.1).
- `unit_price` при конфликте — `COALESCE(EXCLUDED.unit_price, ojr_vor_reference.unit_price)` (не затирать цену).

## GIVEN / WHEN / THEN

### GIVEN корректный Excel с кодами ВОР
- WHEN `load_vor_reference(dry_run=True)` читает реальные файлы
- THEN `result.total > 500` И `result.with_price > 500` И `inserted == 0` И `updated == 0` (dry-run не пишет в БД)

### GIVEN код вида «5.10» и «5.1»
- WHEN вызван `_code(...)`
- THEN `_code("5.10") == "5.10"`, `_code("5.1") == "5.1"` (не схлопываются), `_code("2,1") == "2.1"` (запятая→точка)

### GIVEN строка уже есть в `ojr_vor_reference`, но work_name/unit изменились
- WHEN `load_vor_reference(dry_run=False)` встречает такой код
- THEN строка НЕ upsert-ится, `skipped_conflict` увеличивается, `inserted/updated` не меняются (конфликт идентичности)

### GIVEN цена (`unit_price`) уже есть в справочнике
- WHEN upsert нового источника без цены
- THEN существующая `unit_price` сохраняется (COALESCE), не затирается NULL

## Update Rule
Менялся импорт/формат кода → обнови `test_vor_reference.py` + CONTRACTS.md §2.9b.

## Regression Baseline (прогон 05.09.2026)
Фактические результаты `load_vor_reference(dry_run=False)` на актуальных `report/templates/ВОР.xlsx` + `ВОР_с_расценками.xlsx`:
- **dry_run=True:** `total=573`, `with_price=554`, `inserted=0`, `updated=0`, `skipped_conflict=0`
- **dry_run=False (реальный):** `total=573`, `inserted=0`, `updated=573`, `skipped_conflict=0`, `with_price=554`
- **Пост-прогон БД:** `ojr_vor_reference` = 573 строки, 554 с ценой, **573 distinct `vor_code`** (без задвоения, идемпотентно).

Инвариант: повторный прогон НЕ увеличивает `total` и НЕ создаёт дублей кодов; `inserted` остаётся 0 при неизменных файлах (всё уже в справочнике — upsert переписывает, не добавляет). Дрейф `total` или рост `distinct_codes` выше 573 = новый источник/файл ВОР — обновить базу.

