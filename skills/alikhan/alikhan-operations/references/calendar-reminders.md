# Calendar Reminders — Implementation Reference

Restored 06.07.2026. This documents the exact implementation for future maintenance.

## Architecture

```
main_waha.py
│
├── [daemon thread] calendar_reminder_loop()
│   └── every 60s:
│       1. db.get_due_reminders()
│       2. for each: send_msg(chat_id, formatted_message)
│       3. db.mark_reminder_sent(event_id)
│
└── [message handler]
    ├── regex: напомни <title> <DD.MM[.YY]> <HH:MM>
    │   └── db.create_calendar_event()
    └── trigger: календарь / события / ивенты
        └── db.get_calendar_events(range='week')
```

## Code locations

| Component | File | Line |
|-----------|------|------|
| Background thread | `bot/main_waha.py` | ~L162 |
| Calendar command parser | `bot/main_waha.py` | ~L333 |
| `get_due_reminders()` | `bot/db.py` | ~L575 |
| `mark_reminder_sent()` | `bot/db.py` | ~L590 |
| `create_calendar_event()` | `bot/db.py` | ~L600 |

## Regex for command parsing

```python
remind_match = re.search(
    r'напомни\s+(.+?)\s+(\d{1,2}[.]\d{1,2}(?:[.]\d{2,4})?)\s+(\d{1,2}[:]\d{2})',
    text.lower()
)
```

Captures:
- Group 1: title (non-greedy until date)
- Group 2: date (DD.MM or DD.MM.YY or DD.MM.YYYY)
- Group 3: time (HH:MM)

## Reminder message format

```
⏰ Напоминание за 30 мин
📌 Совещание по графику
📍 Офис АйБиКон
🕐 15.07.2026 14:00 (Asia/Bishkek)
```

## Verification

```bash
# Check due reminders (before they're sent)
docker exec evolution-postgres psql -U evolution -d evolution_db -c \
  "SELECT id, title, remind_at, reminder_sent FROM bot_calendar_events WHERE status='active' ORDER BY remind_at"

# Create test event
docker exec evolution-postgres psql -U evolution -d evolution_db -c \
  "INSERT INTO bot_calendar_events (chat_id, title, event_start, remind_at, remind_minutes_before, timezone, status, reminder_sent)
   VALUES ('120363179621030401@g.us', 'TEST', NOW() + interval '2 minutes', NOW(), 2, 'Asia/Bishkek', 'active', FALSE)"

# Watch logs
tail -f /tmp/alikhan.log | grep CALENDAR
```

## n8n origin

The original workflow `nsox5DrKIF1KLUYi` (Calendar Reminders) ran in n8n:
- Schedule Trigger (every minute)
- Postgres SELECT → due reminders
- Edit Fields (format)
- HTTP Request → evolution-api send
- Postgres UPDATE → reminder_sent = TRUE

The Python port is functionally identical.
