# Архитектура Алихан

## Диаграмма компонентов

```
┌─────────────────────────────────────────────────────────────────┐
│                         WhatsApp                                 │
│                  Группа: 120363400682390076@g.us                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Poll 3s
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     main_waha.py (EVO v5)                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Guard       │→→│  QA Parser   │→→│  Poll Module         │  │
│  │  (fromMe,    │  │  (qa.py)     │  │  (poll.py)           │  │
│  │   age filter)│  │  save facts  │  │  start/close/parse   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                         │                      │                │
│                         ▼                      ▼                │
│                  ┌──────────────┐  ┌──────────────────────┐  │
│                  │  Name Filter │  │  Command Detection   │  │
│                  │  [ао]л[еи]   │  │  cmd_words → CMD     │  │
│                  └──────────────┘  └──────────────────────┘  │
│                         │                                      │
│                         ▼                                      │
│                  ┌──────────────────┐                          │
│                  │   Router         │                          │
│                  │  (router.py)     │                          │
│                  │                  │                          │
│                  │  Schedule→DB    │                          │
│                  │  /Weather→Grok  │                          │
│                  │  → Verify       │                          │
│                  └──────────────────┘                          │
│                         │                                      │
│                         ▼                                      │
│                  ┌──────────────────┐                          │
│                  │   Reply          │                          │
│                  │ sendText/Media   │                          │
│                  └──────────────────┘                          │
└──────┬────────────────────────────────────────────┬─────────────┘
       │                                            │
       ▼                                            ▼
┌──────────────┐                          ┌──────────────────┐
│ evo-postgres │                          │   evolution-api  │
│ :5432        │                          │   :8080          │
│ ─ bot_memory_│                          └──────────────────┘
│   messages   │
│ ─ bot_memory_│
│   facts      │
│ ─ bot_poll_  │
│   state      │
│ ─ bot_poll_  │
│   residuals  │
└──────────────┘
```

## Поток сообщения

### Входящее сообщение

1. WhatsApp → evolution-api (poller 3s)
2. main_waha.py демон — Evolution API `/chat/findMessages` (poll 3s)
3. **Guard:** skip fromMe, skip age > 5min
4. **QA Parser:** если есть данные (персонал, техника, VOR-коды) → save to `bot_memory_facts`
5. **Name check:** если нет «алихан» → IGNORE
6. **Command detection:** если CMD → skip Grok
7. **Poll handlers (до Grok):**
   - `начать опрос` → start_poll() → опрос с остатками работ
   - `закончить опрос` → close_poll() → ЕЖО
   - `статус опроса` → get_poll_status() → сводка
   - VOR-коды в тексте → parse_poll_reply() → update residuals
8. **Router:** Schedule → Weather/DB → Grok
9. **Verification:** verify.py (REJECT <40 / FLAG <70 / OK 90+)
10. **Reply:** sendText / sendMedia (document, audio)

### Напоминание календаря

1. **Schedule Trigger:** каждую минуту
2. **Postgres SELECT:** `bot_calendar_events` WHERE `remind_at <= NOW()` AND `reminder_sent = FALSE`
3. **Format:** сборка текста напоминания
4. **HTTP Request:** отправка в WhatsApp
5. **Postgres UPDATE:** `reminder_sent = TRUE`

## Сетевая схема

```
Docker Network: evolution-api_default (172.18.0.0/16)

  172.18.0.2  evolution-api        :8080
  172.18.0.X  evolution-postgres   :5432  
  172.18.0.X  evolution-redis      :6379

Docker Network: n8n_default (хост)

  n8n                            :5678 (внутренний)
  PostgreSQL (n8n)               :5432 (внешний/контейнер)
  Redis (n8n)                    :6379 (внешний/контейнер)
```

## Безопасность

- evolution-api использует `apikey` заголовок (`SuperSecretKey_Grok2026_!@#`) — **нужно сменить при миграции**
- PostgreSQL пароли хранятся в environment variables — **нужно сменить при миграции**
- n8n credentials (xAI, Redis, Postgres) зашифрованы в БД n8n
- WhatsApp группа захардкожена: `120363400682390076@g.us`
