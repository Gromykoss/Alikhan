# EJO Volume Extraction (`_extract_ejo_volumes`)

Added 10.07.2026 to `main_waha.py`. Extracts work volumes from uploaded ЕЖО `.xlsx` files and saves them as `bot_memory_facts`.

## Purpose

When a user uploads an ЕЖО .xlsx to the sandbox group, the bot automatically reads VOR codes with non-zero volumes and persists them as QA facts. This allows the bot to answer questions like "сколько сделано по 2.2.3.3" without re-parsing the Excel file.

## Function Signature

```python
_extract_ejo_volumes(b64_data: str, fname: str, chat_id: str) -> None
```

## Location

Defined in `main_waha.py` (~line 146), called from the sandbox document handler (~line 574):

```python
# Extract volumes from ЕЖО .xlsx files (both ЕЖО and any .xlsx with codes)
if fname and fname.endswith('.xlsx'):
    try:
        _extract_ejo_volumes(b64, fname, SANDBOX)
    except Exception as ex:
        print(f"[EJO EXTRACT CALL ERR] {ex}", flush=True)
```

Runs on **any** `.xlsx` (not just those with "ЕЖО" in the name), so regular Excel files with VOR codes also get their volumes extracted.

## Extraction Logic

### Sheet
- Sheet name: `Ежедневный отчет`
- Data rows: 24 → `ws.max_row`
- Column C (3): VOR code (e.g., `2.2.3.3`)
- Column L (12): план за сутки
- Column M (13): факт за сутки

### Filters
1. Column C must match regex `^\d+(\.\d+)+$` — at least one dot with digits
2. Either plan (L) or fact (M) > 0.0 — skip empty rows
3. Volume = `fact` (if > 0) else `plan`

### Category mapping by section

| Section (code prefix) | Category |
|----------------------|----------|
| 2.* | `земляные работы` |
| 3.*, 4.* | `монтаж` |
| 5.*, 6.*, 7.*, 8.*, 9.* | `бетонирование` |

### DB insert

```sql
INSERT INTO bot_memory_facts (chat_id, fact_date, building, category, fact, source)
VALUES (%s, %s, 'общая', %s, %s, 'qa')
```

- `fact` format: `"{code} = {volume}"` (e.g., `2.2.3.3 = 420.0`)
- `source = 'qa'` — matches how poll.py and qa.py store volume facts
- `building = 'общая'` — generic, no per-building breakdown

### Date extraction priority

1. Cell D6 (merged cell `Дата:`) — parsed as `datetime` or string
2. Filename regex `\d{2}.\d{2}.\d{4}` — e.g., `ЕЖО_27.06.2026`
3. Fallback: `datetime.now()`

## Pitfalls

1. **Только суточные колонки (L, M).** Не читает накопительные (P=16, S=19) или плановые (K=11). Если факт стоит только в накопительных колонках — строка будет пропущена.
2. **Не deduplicates.** Каждый вызов создаёт новые строки в `bot_memory_facts`. Если один и тот же файл попадёт в обработку дважды — будет дубликат.
3. **`bot_memory_facts` не имеет UNIQUE constraints.** Дубликаты нужно чистить вручную через SQL.
4. **Не сохраняет единицы измерения.** Объём — голое число без `м³`, `тн`, `шт`. Потребитель должен знать контекст кода.
5. **Temp-файл:** `/tmp/ejo_extract_{filename}` — создаётся и удаляется в `finally`. Если процесс упадёт в момент чтения — файл останется.
