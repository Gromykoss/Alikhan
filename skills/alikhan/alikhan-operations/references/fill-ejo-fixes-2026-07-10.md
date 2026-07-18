# ЕЖО Fixes — 2026-07-10

Five fixes applied to `fill_ejo.py` and the EJO template. See session history for full context.

## 1. Template D853 spelling
`"Готовность обьекта в процентах"` → `"Готовность объекта в процентах"`

## 2. Руководитель hardcoded to 1
After `by_prof` fill on sheet "Персонал и техника", row 9 (Руководителя строительства) is forcibly set to `"1"` regardless of what the timesheet says.

## 3. volumes() missing category `объём`
**Root cause of "работы не заполнены":** `volumes()` only queried `бетонирование`, `монтаж`, `земляные работы`. Users send volume data with category `объём`. Fixed by adding `+ qa(date, 'объём')`. Added `[VOLUMES]` logging with warning when empty.

## 4. Materials parsing implemented (was `pass # TODO`)
Previous code unconditionally cleared template material values. Now:
- Parses QA facts for `материал` keyword across ALL categories
- Fills rows 14+ with (№, Наименование, Ед.изм, Кол-во)
- Without new data: only clears yellow cells, preserves non-yellow user corrections

## 5. Row 77 (3.3.2.1) verification
Template P77=S77=5790, K77=7981.29 → 72.5%. Cumulative calculation confirmed correct through the file chain.
