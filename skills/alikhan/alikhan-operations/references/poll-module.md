# Poll Module Reference

Added 06.07.2026 (T-128). The poll/опрос module was lost during the 30.06 modular refactoring (commit 7e76ccc) and restored in this session.

## Module: bot/poll.py

Location: `/home/hermes-workspace/Alikhan-migration/bot/poll.py` (~420 lines)

### Functions

| Function | Purpose |
|----------|---------|
| `ensure_poll_table()` | Creates `bot_poll_state` + `bot_poll_residuals` tables |
| `start_poll(chat_id)` | Reads active residuals from EJO template, saves to DB |
| `build_poll_message(state)` | Builds status message: collected ✅ / missing ❌ |
| `parse_poll_reply(chat_id, text, sender)` | Parses foreman reply: VOR codes, personnel, equipment |
| `get_poll_status(chat_id)` | Returns current poll state |
| `build_poll_summary(state)` | Summary of collected data |
| `close_poll(chat_id)` | Auto-fills missing categories → generates EJO |

### DB Tables

**bot_poll_state:**
- `id`, `chat_id`, `poll_date`, `status` (active/closed), `started_at`, `closed_at`
- UNIQUE(chat_id, poll_date)

**bot_poll_residuals:**
- `id`, `poll_id` (FK → bot_poll_state), `code`, `building`, `name`, `unit`
- `plan_volume`, `residual_volume`, `actual_today`
- `updated_by`, `updated_at`
- UNIQUE(poll_id, code)

### Commands (in main_waha.py)

| Trigger | Action |
|---------|--------|
| `начать опрос` / `запустить опрос` | `start_poll()` → show residuals |
| `закончить опрос` / `завершить опрос` | `close_poll()` → EJO |
| `статус опроса` / `что собрано` | `get_poll_status()` → summary |
| `заполни ежо` / `сформируй ежо` | Check data completeness → EJO (blocks if incomplete) |
| `ежо принудительно` / `ежо все равно` | **Force EJO** — closes poll, generates EJO, sends file. No data checks. |
| VOR code in reply (`2.1.1 = 85.5`) | `parse_poll_reply()` → update residuals |

### Message Flow

```
WhatsApp → main_waha.py (poll 3s)
  → Guard (skip fromMe, age >5min)
  → QA Parser (qa.py — save facts)
  → **Work-code bypass** (router.py — RESIDUAL, NEW 07.07.2026)
  → Name check (алихан)
  → Poll handlers (BEFORE Grok):
    - start poll / close poll / status
    - VOR code auto-detect
  → Router → Grok → Reply
```

**NEW 07.07.2026 — RESIDUAL bypass:** If the message contains a VOR code pattern (`x.x.x = value`), `router.py` returns `"RESIDUAL"` before the name check. The main loop then calls `parse_poll_reply()` directly, accepting data even without "алихан" in the message. This fixes "Работы выполнены" commands being silently ignored.

### Verification

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile poll.py
python3 -c "from poll import ensure_poll_table; ensure_poll_table(); print('OK')"
```

### Pitfalls

1. **Шаблон ЕЖО может не иметь кэшированных значений в столбце «Остаток» (col 21).**
   После ручной правки пользователем Excel-файл сохраняется без вычисленных формул — `openpyxl(data_only=True)` возвращает `None` для col 21.
   **Fix:** `_get_work_items_from_template()` имеет fallback: если col 21 пуст → остаток = план (col 18) − факт (col 19).
   Не меняй этот fallback — он критичен для работы опроса после любой ручной правки шаблона.

2. **Work items = 0 при первом запуске опроса** — всегда проверяй через `_get_work_items_from_template()` отдельно,
   сколько остатков найдено. Если 0 — проблема в шаблоне (col 21 пуст И col 18/19 тоже пусты, или секции не ACTIVE_SECTIONS).

3. **RESIDUAL bypass (router.py) — не все сообщения с VOR-кодами попадают в poll.**
   Сообщение проверяется на `\d+\.\d+\.\d+(?:\.\d+)?\s*[=—–\-:\s]+\s*\d+` ДО name check. Если формат не совпадает (например, код без значения, или значение без «=»), сообщение проходит в обычный роутинг. Проверяй `has_vor_codes` в main_waha.py L429 — там аналогичный regex для VOR auto-detect внутри poll-хендлера.

4. **Section 3.1 was missing from ACTIVE_SECTIONS (fixed 07.07.2026).**
   Work items in section 3.1 (e.g., 3.1.1, 3.1.2) were excluded from polls because `ACTIVE_SECTIONS = {"2.1", "2.2", "2.3", "2.4", "3.2", "3.3"}` was missing `"3.1"`. **Fix:** Added `"3.1"` to the set.

5. **`int(None)` crash in format strings (fixed 07.07.2026).**
   Three locations in `poll.py` called `int(value)` where `value` could be `None` from the DB:
   - Line 280: `item['ostatok'] == int(item['ostatok'])`
   - Line 470: `r['residual_volume'] == int(r['residual_volume'])`
   - Line 471: `r['actual_today'] == int(r['actual_today'])`
   **Fix:** Added `is not None` guards before each `int()` call, with `else '0'` fallback for display.
