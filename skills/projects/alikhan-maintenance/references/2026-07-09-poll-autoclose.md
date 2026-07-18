# Poll Auto-Close After EJO Corrections — 2026-07-09

## Problem

После загрузки исправленного ЕЖО бот принимает правки и обновляет шаблон, но опрос остаётся активным.
При запросе «статус опроса» бот показывает «⚠️ Не хватает данных», хотя ЕЖО уже готов.

## Root cause

`_update_template_from_correction()` (main_waha.py) обновляет шаблон, но НЕ закрывает опрос в `bot_poll_state`.

## Fix — two files

### 1. main_waha.py — auto-close poll after correction

In `_update_template_from_correction()`, after `send_msg(SANDBOX, summary)`:

```python
# Auto-close poll for this date — EJO is finalized
try:
    from poll import close_poll as _close_poll_correction
    _close_poll_correction(SANDBOX, date_str)
    print(f"[TEMPLATE] Auto-closed poll for {date_str}", flush=True)
except Exception as ex:
    print(f"[TEMPLATE] Could not close poll: {ex}", flush=True)
```

### 2. poll.py — check EJO existence in build_poll_summary()

At the top of `build_poll_summary()`:

```python
import glob as _g
today = status.get('poll', {}).get('poll_date', datetime.now().strftime("%Y-%m-%d"))
existing = sorted(_g.glob(f"/tmp/ЕЖО_{today}_v*.xlsx"))
if existing:
    return f"📊 ЕЖО за {today} уже готов (v{len(existing)}). Правки загружены в шаблон."
```

## Verification

After corrections accepted, `SELECT status FROM bot_poll_state WHERE chat_id='<sandbox>' AND poll_date='<date>'` should return 'closed'.
