# Архитектура Алихан

## Диаграмма компонентов

```
┌─────────────────────────────────────────────────────────────────┐
│                         WhatsApp                                 │
│                  Группа: 120363400682390076@g.us                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Webhook
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      evolution-api                              │
│                 http://72.60.16.105:8080                         │
│                                                                 │
│  /message/sendText/bot1  ←  n8n отправляет ответы              │
│  /webhook/whatsapp       →  n8n получает сообщения              │
└──────┬────────────────────────────────────────────┬─────────────┘
       │                                            │
       ▼                                            ▼
┌──────────────┐                          ┌──────────────────┐
│ evo-postgres │                          │   evo-redis      │
│ PostgreSQL   │                          │   Redis          │
│ :5432        │                          │   :6379           │
└──────────────┘                          └──────────────────┘

                           │
                           │ Webhook POST
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         n8n (основной)                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Алихан AI-whatsApp agent                         │  │
│  │                                                          │  │
│  │  Webhook → Guard → Router ─┬─→ only_name                 │  │
│  │                            ├─→ memory_status              │  │
│  │                            ├─→ search (Long Memory)      │  │
│  │                            └─→ default (AI chat)         │  │
│  │                                    │                      │  │
│  │            ┌───────────────────────┘                      │  │
│  │            ▼                                              │  │
│  │  [Redis GET] → [Build Context] → [xAI API] → [Reply]    │  │
│  │       │              ▲                                   │  │
│  │       ▼              │                                   │  │
│  │  [Postgres]    [Long Memory Search]                      │  │
│  │  (save msg)    (semantic SQL)                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Алихан Calendar Reminders                        │  │
│  │                                                          │  │
│  │  Schedule (1 min) → Get Due Events → Format → Send       │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────────────┬───────────┘
               │                                      │
               ▼                                      ▼
┌──────────────────────┐                ┌──────────────────────────┐
│   Redis (n8n)        │                │   PostgreSQL (n8n)       │
│   short memory       │                │                          │
│   key: memory:{id}   │                │ bot_memory_messages      │
│   TTL: persistent    │                │ bot_memory_summaries     │
└──────────────────────┘                │ bot_calendar_events      │
                                        └──────────────────────────┘

                           │
                           │ API call
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                       xAI API (Grok)                             │
│                  model: grok-2 (или новее)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Поток сообщения

### Входящее сообщение

1. WhatsApp → evolution-api (webhook)
2. evolution-api → n8n Webhook `/whatsapp`
3. **Guard Алихан:** проверка группы, не fromMe, содержит «алихан»
4. **Router Алихан:** определение команды
   - `only_name` → простое приветствие
   - `memory_status` → статистика БД
   - Документ/файл → анализ содержимого
   - Default → AI-диалог
5. **Redis GET:** загрузка краткой памяти (последние N сообщений)
6. **Postgres SELECT:** загрузка долгой памяти (summary)
7. **Search Long Memory:** семантический поиск по `bot_memory_messages`
8. **Build Context:** сборка полного контекста
9. **xAI API:** запрос к Grok с контекстом
10. **HTTP Request:** отправка ответа через evolution-api
11. **Redis SET:** сохранение в краткую память
12. **Postgres INSERT:** сохранение в `bot_memory_messages`

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
