# Plan Parsing Bug — Reproduction & Fix

## Symptom
Grok QA parser merges "Планы" keyword with the last work code fact.
Example: message `"Работы: 3.1.5 - 142  Планы  2.1.5 - 50"` produces QA facts:
- `3.1.5 = 142.0Планы` (категория: объём)
- `2.1.5 = 50` is COMPLETELY LOST

## Root cause
Grok doesn't split "Планы" into a separate fact. The suffix "Планы" gets appended to the preceding work code.

## Fix: position-based plan detection

### In volumes() (line ~421)
```python
# WRONG:
is_plan = 'план' in txt.lower() or x.get('category') == 'план'

# CORRECT:
plan_pos = txt.lower().find('план')
is_plan = x.get('category') == 'план' or (plan_pos >= 0 and plan_pos < m.start())
```

### DB fallback for missed plans (line ~429)
When QA facts miss "Планы" codes, query raw messages:
```python
cur.execute("""
    SELECT content FROM bot_memory_messages 
    WHERE chat_id = '120363179621030401@g.us' 
    AND created_at::date = %s::date 
    AND content ILIKE '%%план%%'
    ORDER BY created_at DESC LIMIT 10
""", (date.isoformat(),))
for row in cur.fetchall():
    raw = (row['content'] or '').replace(',', '.')
    for cd, vl in re.findall(r'(?:планы?)\s+(\d+\.\d+\.\d+(?:\.\d+)?)\s*[-=]\s*(\d+(?:\.\d+)?)', raw, re.I):
        pn[cd] = float(vl)
```

### Same fix in plan sheet filling (line ~1051)
The plan filling code has its OWN independent QA parsing — must apply the same fix plus DB fallback.

## Template layout for plans sheet (from corrected EJO)

```
Row 13: " № п/п"
Row 14: "1 | АБК"           ← header
Row 15: item (if any)
Row 17: "2 | Общежитие"     ← header
Row 18: item (if any)
Row 22: "3 | Галерея"       ← header
Row 23: item (if any)
```

**Headers written explicitly** — шаблон и исправленный ЕЖО расходятся в строках.

## Clear boundaries
```python
bld_rows = {'АБК': (14, 15), 'Общежитие': (17, 18), 'Галерея': (22, 23)}
# Clear only items between this header and next building's header
# DO NOT clear header rows
for bld in ['АБК', 'Общежитие', 'Галерея']:
    hdr_row, item_row = bld_rows[bld]
    next_hdr = 27
    for b in ['АБК', 'Общежитие', 'Галерея']:
        if bld_rows[b][0] > hdr_row:
            next_hdr = bld_rows[b][0]
            break
    clear_end = min(item_row + 5, next_hdr)
    for cr in range(item_row, clear_end):
        for cc in [1, 2, 3, 4, 6]:
            sw(ws, cr, cc, None, True)
```

## N column: always 100%

L = M всегда (план на день = факт за день). Поэтому N = M/L = 100%.

```python
sw(ws, r, 14, 1, True)                      # value 1.0
ws.cell(row=r, column=14).number_format = '0%'  # displays as "100%"
```

## Timesheet reading: local cache, not Evolution API

После миграции с Evolution API на Hermes Bridge табель читается из `/tmp/hermes-media-cache/`.

```python
local_path = tags.get('local_path', '')
if local_path and os.path.exists(local_path):
    wb = load_workbook(local_path, data_only=True)
```

При сохранении документа бот пишет `local_path` в tags. При повторной загрузке дубликата — `UPDATE tags = tags || jsonb` вместо INSERT.
