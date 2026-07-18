# Poll System — Detailed Reference

## DB Schema

```sql
-- Created by ensure_poll_table() in poll.py
CREATE TABLE IF NOT EXISTS bot_poll_state (
    id SERIAL PRIMARY KEY,
    chat_id TEXT NOT NULL,
    poll_date DATE NOT NULL,
    status TEXT DEFAULT 'active',  -- active / closed
    started_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    UNIQUE(chat_id, poll_date)
);

CREATE TABLE IF NOT EXISTS bot_poll_residuals (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER REFERENCES bot_poll_state(id),
    code TEXT NOT NULL,
    building TEXT,
    name TEXT,
    unit TEXT,
    plan_volume NUMERIC,
    residual_volume NUMERIC,
    actual_today NUMERIC,
    updated_by TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(poll_id, code)
);
```

## Module: poll.py

Location: `bot/poll.py`
Dependencies: `openpyxl`, `psycopg2`, `secret_config`, `db`

### Function Reference

#### `ensure_poll_table()`
Creates `bot_poll_state` and `bot_poll_residuals` if not exist. Safe to call on every start.

#### `start_poll(chat_id, poll_date_str=None)` → (poll_id, work_items, qa_status)
1. Creates/activates poll record (ON CONFLICT upsert by chat_id + poll_date)
2. Reads ЕЖО template (or latest auto-generated v-file by mtime) via `_get_work_items_from_template()`
3. Filters rows: active sections (2.1, 2.2, 2.3, 2.4, 3.2, 3.3), building not None, ostatok > 0
4. Saves each work item as `bot_poll_residuals` (ON CONFLICT upsert)
5. Gets QA status via `_get_qa_status()` — counts of facts for персонал, техника, инцидент, материалы, фото, планы per poll_date

#### `build_poll_message(work_items, qa_status)` → str
Builds formatted WhatsApp message:
- ✅/❌ per category (personnel, equipment, incidents, materials, photos, plans)
- 📊 Work residuals table: grouped by building (Общежитие/АБК/Галерея)
- Format per item: `• code — name — остаток: N unit`
- Instruction: "Напишите по каждому коду сколько сделано сегодня: код = объём"

#### `parse_poll_reply(text, chat_id, poll_date_str=None)` → dict {codes_updated, facts_saved}
Handles foreman reply to poll. Parsing order:
1. Find active poll for today
2. Regex: `r'(\d+\.\d+\.\d+(?:\.\d+)?)\s*[=—–\-:\s]+\s*(\d+(?:[.,]\d+)?)\s*(\S*)?'`
   - Group 1: VOR code (e.g. "2.1.1", "2.3.2")
   - Group 2: volume (e.g. "85.5", "50")
   - Group 3: unit (e.g. "м3", "м²") — optional
3. Fallback: simpler space-separated if no delimiter found
4. Updates `bot_poll_residuals.actual_today` for matching codes
5. Inserts non-matching codes as new residuals
6. Always saves as `bot_memory_facts` (category='объём', source='qa')

#### `get_poll_status(chat_id, poll_date_str=None)` → dict or None
Returns:
- `poll`: active poll record
- `residuals`: all residuals for poll, with actual_today status
- `qa_status`: counts of collected data (personnel, equipment, incidents, materials, photos, plans)

#### `build_poll_summary(status)` → str
Builds summary showing what's collected and what's missing.
- Per-category ✅/❌
- Residuals updated: `N/total codes`
- Missing sections list
- If all done: "✅ Все данные собраны! Напишите «Алихан закончить опрос»"

#### `close_poll(chat_id, poll_date_str=None)` → (poll_id, ejo_path)
1. Auto-fills missing categories (бетонирование, монтаж, земляные работы, документация → "не выполнялось")
2. Marks poll as closed (status='closed', closed_at=NOW())
3. Runs `fill_ejo.py <today>` via subprocess
4. Returns path to generated file (latest v-file in /tmp/)

### Work Items Source (`_get_work_items_from_template()`)
- Reads from ЕЖО_шаблон.xlsx (or latest auto-generated v-file if newer by mtime)
- Sheet: 'Ежедневный отчет'
- Row range: 22 to max_row
- Column mapping: 1=building, 3=code, 4=name, 5=unit, 21=остаток
- Active sections filter: {"2.1", "2.2", "2.3", "2.4", "3.2", "3.3"}
- Filters: building not None/empty/—, code not None, ostatok > 0

### QA Status Check (`_get_qa_status(poll_date_str)`)
Queries `bot_memory_facts` for each category by date + source='qa':
- персонал, техника, инцидент — direct category count
- работы — regex for VOR code pattern in fact text
- материалы — categories 'документация', 'материалы'
- фото — COUNT from bot_memory_messages WHERE message_type='image' AND DATE(created_at)=today, grouped by tags->>'building'
- планы — ILIKE '%план%' in fact text

## Integration in main_waha.py

The poll handlers run **before routing** — they're checked in the main message-processing loop (lines 309-380 approx). Order:

1. Photo message → DB save → continue
2. Document message → DB save + extract + template update → continue
3. Audio/voice → STT → DB save → continue (falls through to text)
4. Text processing:
   a. **Close poll** (`закрыть опрос`, etc.) → show summary → close_poll() → send EJO
   b. **Start poll** (`начать опрос`) → start_poll() → build_poll_message() → send
   c. **Poll status** (`статус опроса`) → get_poll_status() → build_poll_summary() → send
   d. **VOR code auto-detect** (regex match `\d+\.\d+\.\d+(?:\s*[=—–\-:\s]\s*\d+)`) → parse_poll_reply() → show summary
   e. **Fill EJO** (`заполни ежо`) → check poll status → conditional close or show missing
   f. Route to router.py

## Pitfalls

1. **VOR code regex ordering**: The space-separated fallback (`код значение`) will match numbers in non-VOR contexts like "план 2.1.1 100". The first pattern (with `=`/`—`/`:`) is tried first and is more reliable. Always prefer explicit delimiters.

2. **Template staleness**: `_get_work_items_from_template()` compares mtime of template vs latest auto-generated v-file. If the auto-file is older, template wins. If no template exists, falls back to `/tmp/ЕЖО_20*_v*.xlsx` sorted reverse.

3. **Multiple poll per day**: `bot_poll_state` has UNIQUE(chat_id, poll_date). Starting a second poll on the same day re-activates the existing one (status='active', closed_at=NULL).

4. **Thread safety**: No row-level locking. In production with one bot, this is fine. With multiple instances, consider SELECT FOR UPDATE on bot_poll_state.

5. **fill_ejo.py dependency**: `close_poll()` calls `fill_ejo.py` via subprocess with `sys.executable`. Make sure the venv has `openpyxl` installed.
