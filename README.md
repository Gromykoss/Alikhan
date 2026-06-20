# Алихан — AI WhatsApp Agent

**Владелец:** [Gromykoss](https://github.com/Gromykoss)
**Репозиторий:** [Gromykoss/Alikhan](https://github.com/Gromykoss/Alikhan)
**Дата инвентаризации:** 2026-06-20
**Статус:** ⚙️ В работе (миграция)

## Обзор

Алихан — AI-агент для WhatsApp, построенный на n8n + evolution-api + xAI (Grok). Отвечает на сообщения в групповых чатах WhatsApp, сохраняет контекст диалога (Redis + PostgreSQL), анализирует документы, управляет календарём.

### Возможности

- **AI-чат** — отвечает на сообщения, понимает русский и казахский языки
- **Долгая память** — сохраняет историю диалогов в PostgreSQL, находит релевантные сообщения по ключевым словам  
- **Календарь** — отслеживает `bot_calendar_events`, отправляет напоминания в WhatsApp за N минут
- **Анализ документов** — распознаёт и обрабатывает загруженные PDF/DOCX/XLSX файлы
- **Интеллектуальный роутинг** — различает команды: `memory_status`, `only_name`, поиск, обычный диалог

## Архитектура

```
WhatsApp → evolution-api → n8n (Webhook) → Guard → Router → xAI API → WhatsApp
                                  ↓           ↓
                               Redis      PostgreSQL
                             (short mem)  (long mem + calendar)
```

### Компоненты

| Компонент | Тип | Порт | Назначение |
|-----------|-----|------|------------|
| n8n | Docker контейнер | 5678 | Оркестрация воркфлоу |
| evolution-api | Docker контейнер | 8080 | WhatsApp API мост |
| evolution-postgres | Docker контейнер | 5432 | База evolution-api |
| evolution-redis | Docker контейнер | 6379 | Кэш evolution-api |
| xAI (Grok) | Внешний API | — | AI-модель для ответов |
| PostgreSQL (n8n) | Внешний/контейнер | — | Бот-память и календарь |
| Redis (n8n) | Внешний/контейнер | — | Краткосрочная память диалогов |

## Воркфлоу n8n

### 1. Алихан AI-whatsApp agent

**ID:** `PwTANwctgUAVogTt`  
**Активен:** ✅  
**Триггер:** Webhook `/whatsapp` (входящие сообщения из evolution-api)

**Узлы (ноды):**

| Узел | Тип | Назначение |
|------|-----|------------|
| Guard Алихан | Code | Фильтр: только группа `120363400682390076@g.us`, не fromMe, содержит «алихан» |
| Router Алихан | Code | Классификация команд: `only_name`, `memory_status`, документы, поиск |
| Redis | Redis | Чтение краткой памяти по chatId |
| Execute a SQL query | Postgres | Сохранение входящего сообщения в `bot_memory_messages` |
| Execute a SQL query2 | Postgres | Загрузка долгой памяти (`bot_memory_summaries`) |
| Search Long Memory | Postgres | Семантический поиск по `bot_memory_messages` |
| Build Long Facts | Set | Сборка контекста (short memory + long memory + long facts) |
| HTTP Request к xAI | HTTP | Запрос к xAI API (модель Grok) |
| Edit Fields | Set | Формирование ответа (number + reply) |
| HTTP Request | HTTP | Отправка ответа через evolution-api |
| Redis1 | Redis | Сохранение ответа в краткую память |
| Execute a SQL query1 | Postgres | Сохранение ответа в `bot_memory_messages` |
| Postgres Memory Status | Postgres | Статистика памяти |
| Build Memory Status | Set | Форматирование статуса |
| WhatsApp HTTP Request | HTTP | Отправка статуса в WhatsApp |

### 2. Алихан Calendar Reminders

**ID:** `nsox5DrKIF1KLUYi`  
**Активен:** ✅  
**Триггер:** Schedule (каждую минуту)

**Узлы:**

| Узел | Тип | Назначение |
|------|-----|------------|
| Schedule Trigger | Schedule | Запуск каждую минуту |
| Get Due Calendar Reminders | Postgres | `SELECT` из `bot_calendar_events` где `remind_at <= NOW()` |
| Edit Fields | Set | Форматирование текста напоминания |
| HTTP Request | HTTP | Отправка напоминания через evolution-api |
| Update Reminder Flag | Postgres | `UPDATE reminder_sent = TRUE` |

## База данных

### Таблицы (в PostgreSQL, schema `n8n`)

#### `bot_memory_messages`

| Колонка | Тип | Описание |
|---------|-----|----------|
| id | SERIAL | PK |
| chat_id | VARCHAR | WhatsApp chat JID |
| sender | VARCHAR | Имя отправителя |
| message_time | TIMESTAMP | Время сообщения |
| role | VARCHAR | `user` / `assistant` |
| message_type | VARCHAR | `text` / `image` / `document` |
| content | TEXT | Текст сообщения |
| file_name | VARCHAR | Имя файла (для документов) |
| created_at | TIMESTAMP | Время записи |

#### `bot_memory_summaries`

| Колонка | Тип | Описание |
|---------|-----|----------|
| chat_id | VARCHAR | WhatsApp chat JID |
| summary | TEXT | Суммаризация истории |
| updated_at | TIMESTAMP | Время обновления |

#### `bot_calendar_events`

| Колонка | Тип | Описание |
|---------|-----|----------|
| id | SERIAL | PK |
| chat_id | VARCHAR | WhatsApp chat JID |
| title | VARCHAR | Название события |
| description | TEXT | Описание |
| location | VARCHAR | Место |
| timezone | VARCHAR | Часовой пояс |
| event_start | TIMESTAMP | Начало события |
| remind_at | TIMESTAMP | Когда напомнить |
| remind_minutes_before | INT | За сколько минут |
| status | VARCHAR | `active` / `cancelled` |
| reminder_sent | BOOLEAN | Отправлено ли |

## Зависимости

### Внешние API

| Сервис | Назначение | Переменная |
|--------|------------|------------|
| xAI (Grok) | AI-ответы | `XAI_API_KEY` |
| evolution-api | WhatsApp отправка | `apikey` header |
| Redis | Кэш памяти | `REDIS_URL` |
| PostgreSQL | Долгая память | `DATABASE_URL` |

### ENV (evolution-api)

```env
DATABASE_CONNECTION_URI=postgresql://evolution:***@postgres:5432/evolution_db
CACHE_REDIS_URI=redis://redis:***@redis:6379
DATABASE_PROVIDER=postgresql
CACHE_REDIS_ENABLED=true
SERVER_URL=http://72.60.16.105:8080
LOG_LEVEL=debug
```

## План миграции

- [x] Инвентаризация воркфлоу и контейнеров
- [x] Экспорт n8n workflows в JSON
- [x] Документирование архитектуры и БД
- [ ] Перенос evolution-api на новый хост
- [ ] Миграция PostgreSQL (структура + данные)
- [ ] Миграция Redis (опционально)
- [ ] Импорт n8n workflows на новый инстанс
- [ ] Тестирование end-to-end
- [ ] Обновление webhook URL в evolution-api

## Управление

```bash
# Посмотреть статус
docker ps --filter "name=evolution"

# Логи evolution-api
docker logs evolution-api --tail 50

# Рестарт
docker restart evolution-api evolution-postgres evolution-redis
```
