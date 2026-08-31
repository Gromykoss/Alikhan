# CONTRACTS.md — Карта зависимостей и контрактов модулей Alikhan

> **Назначение:** единый источник истины о зависимостях, контрактах и правилах взаимодействия модулей.
> **Обновляется:** при любом изменении сигнатур функций, импортов или публичного API модулей.
> **Дата:** 12.08.2026 — обновлено после аудита: удалены main_waha.py, bridge_wrapper.py, daily_snapshot.py; точка входа v6 — whatsapp_commands.py
> **Используется:** `scripts/pre_delegation.py` для сборки контекста при делегировании задач в Codex/Grok Build.

---

## 1. Граф зависимостей

```
Уровень 0 (фундамент — без зависимостей от других модулей бота):
  config.py          ← os, datetime (чистые константы)
  db.py              ← psycopg2 (чистая БД)
  secret_config.py   ← os, pathlib (загрузка секретов из env)

Уровень 1 (сервисы):
  messaging.py  → Hermes Agent (прямой вызов, secret_config для KEY)
  alerter.py    → db.py, secret_config (алерты Telegram + ojr_incidents)
  office_forward.py → secret_config, requests (webhook офиса)

Уровень 2 (обработчики):
  qa.py         → Hermes Agent, secret_config
  handlers.py   → db.py, messaging.py, secret_config

Уровень 3 (бизнес-логика):
  poll.py         → db.py, messaging.py, secret_config
  data_sources.py → db.py, config.py

Уровень 4 (композиция):
  fill_ejo.py  → data_sources.py (12 NamedTuple), Hermes Agent

Уровень 5 (точка входа):
  whatsapp_commands.py → messaging.py, handlers.py, qa.py, poll.py, fill_ejo.py, alerter.py, office_forward.py
```

### Визуализация (ASCII-граф)

```
config.py ──────────────────────────────────────────────────────┐
                                                                 │
db.py ──────────────────────────────────────────────┐            │
secret_config.py ──┬─────┬──────────┐               │            │
                   │     │          │               │            │
         ┌─────────┘     │          │               │            │
         ▼               ▼          ▼               ▼            ▼
    messaging.py    handlers.py   qa.py     data_sources.py
         │               │          │               │
         │         ┌─────┘          │               │
         │         │                │               │
         ▼         ▼                │               │
      poll.py   alerter.py          │               │
         │                          │               │
         │                          │               │
         ▼                          ▼               ▼
    ┌──────────────────────────────────────────────────┐
    │           whatsapp_commands.py                    │
    │  (точка входа v6 — bridge :3000 → команды)       │
    └──────────────────────────────────────────────────┘
```

---

## 2. Контракты модулей

### 2.1. config.py — Централизованная конфигурация

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/config.py` |
| **Зависит от** | `os`, `datetime` |
| **Импортируется в** | `data_sources.py`, `whatsapp_commands.py` |

#### Экспортирует

| Имя | Тип | Описание |
|-----|-----|----------|
| `SIM_DATE` | `str \| None` | Дата симуляции (`None` = production) |
| `SANDBOX` | `str` | ID песочницы |
| `PRODUCTION` | `str` | ID production |
| `EVO_URL` | `str` | `"http://127.0.0.1:3000"` |
| `BRIDGE_URL` | `str` | `"http://127.0.0.1:3000"` |
| `XAI_URL` | `str` | xAI API endpoint |
| `OLLAMA_URL` | `str` | Ollama endpoint |
| `TEMPLATE_PATH` | `str` | Путь к шаблону ЕЖО |
| `SEEN_FILE` | `str` | Путь к `seen_ids.json` |
| `EJO_START_ROW` | `int` | `24` — первая строка данных в листе ЕЖО |
| `VOICE_TRIGGERS` | `list[str]` | Триггеры голосового ответа |
| `BUILDINGS` | `list[str]` | `['АБК', 'Общежитие', 'Галерея']` |
| `today_str()` | `() -> str` | Сегодняшняя дата (с учётом `SIM_DATE`) |
| `today_date()` | `() -> date` | Сегодняшняя дата как `date` |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не хардкодить пути** в других модулях — использовать `from config import TEMPLATE_PATH`.
2. **`SIM_DATE`** — единственный механизм симуляции. Не создавать своих «sim» переменных.
3. **Не менять `EJO_START_ROW = 24`** без проверки шаблона — сломается `fill_ejo.py`.

---

### 2.2. db.py — Единственная точка подключения к БД

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/db.py` (1136 строк) |
| **Зависит от** | `psycopg2`, `psycopg2.extras`, `ipaddress`, `os`, `subprocess`, `secret_config` |
| **Импортируется в** | `data_sources.py`, `handlers.py`, `alerter.py` |

#### Экспортирует (публичное API)

| Имя | Тип | Описание |
|-----|-----|----------|
| `get_conn()` | `() -> psycopg2.connection` | Единственная точка подключения к БД |
| `DB_CONFIG` | `dict` | Конфигурация подключения (host, port, user, password, dbname) |
| `resolve_db_host()` | `() -> str` | Разрешает хост БД (env → Docker → fallback `172.22.0.4`) |
| `save_message(...)` | — | Сохраняет входящее сообщение |
| `save_fact(...)` | — | Сохраняет QA-факт |
| `get_daily_personnel(ds)` | `-> list` | Персонал за дату |
| `get_daily_works(ds)` | `-> list` | Работы за дату |
| `save_weather(ds, data)` | — | Сохраняет погоду |
| `get_daily_incidents(ds)` | `-> list` | Инциденты за дату |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **`get_conn()` — единственная точка подключения.** Никакой модуль не создаёт `psycopg2.connect()` напрямую.
2. **Не хардкодить `DB_CONFIG`** в других модулях. Все параметры БД — только через `db.py`.
3. **`resolve_db_host()`** автоматически определяет IP контейнера. Не передавать хост статически.
4. **Закрывать курсоры** после использования. `get_conn()` открывает соединение, но курсоры — ответственность вызывающего.

---

### 2.3. secret_config.py — Единая загрузка секретов

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/secret_config.py` (71 строка) |
| **Зависит от** | `os`, `pathlib` |
| **Импортируется в** | `db.py`, `handlers.py`, `alerter.py`, `vision_checklist.py`, `messaging.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `get_secret` | `(*names, default="", required=False) -> str` | Единая загрузка секрета (env → secrets.env → /run/secrets) |
| `get_evo_key` | `(required=True) -> str` | Загрузка EVO_KEY |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Никаких прямых чтений `secrets.env`** — все модули используют `secret_config`.
2. **Никаких fallback-чтений JSON** (n8n workflows) — удалено (AUDIT-017).

---

### 2.4. messaging.py — Единственная точка отправки сообщений

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/messaging.py` (73 строки) |
| **Зависит от** | `secret_config` (для KEY), Hermes Bridge |
| **Импортируется в** | `handlers.py`, `poll.py`, `whatsapp_commands.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `send_msg` | `(chat_id: str, text: str) -> bool` | Отправить текст (макс. 3800 символов) |
| `send_voice` | `(chat_id: str, text: str) -> bool` | TTS → голосовое (edge-tts), fallback на текст |
| `send_document` | `(chat_id: str, path: str, filename: str = None) -> bool` | Отправить документ (base64-encode) |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Единственная точка отправки.** Никакой модуль не шлёт сообщения напрямую.
2. **Не дублировать `send_msg`** — в кодовой базе исторически было 3+ реализации. Все удалены (AUDIT-011).
3. **`send_voice` использует edge-tts** — должен быть установлен в системе.
4. **Текст обрезается до 3800 символов** в `send_msg` — WhatsApp ограничение.

---

### 2.4a. office_forward.py — Пересылка вопросов прорабов в офис

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/office_forward.py` |
| **Зависит от** | `requests`, `secret_config` |
| **Импортируется в** | `whatsapp_commands.py`, `scripts/test_office_forward_sandbox.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `classify_office_question` | `(text: str) -> str \| None` | Возвращает тему `кровля` / `наружка` / `материалы` / `смета` / `общее` только для явных офисных вопросов |
| `forward_to_office` | `(chat_id, message_id, sender, text, topic, *, async_send=True, post=requests.post, log_func=None, retries=1, join_timeout=25) -> bool` | POST в офисный webhook; штатный диспетчер вызывает синхронно, async-режим использует non-daemon тред и ждёт полный retry-бюджет с запасом |
| `get_last_http_status` | `() -> int \| None` | Последний HTTP-статус webhook-вызова для sandbox-проверок |

#### Контракт webhook

| Поле | Значение |
|------|----------|
| **URL/key** | Только `office_webhook_url` и `office_webhook_key` через `secret_config.get_secret()` или env `OFFICE_WEBHOOK_URL` / `OFFICE_WEBHOOK_KEY` |
| **Метод** | `POST` |
| **Успех** | Только HTTP `2xx` |
| **Повторы** | 1 retry по тому же `message_id` по умолчанию |
| **Timeout** | 10 секунд на HTTP-вызов |
| **Join timeout** | 25 секунд по умолчанию: `2 x 10s` HTTP timeout + запас; daemon fire-and-forget запрещён |
| **Текст** | Обрезается до 4000 символов |
| **Логи ошибок** | Только через `log_func` диспетчера; без URL, query-параметров и ключей |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не пересылать QA-факты, poll-ответы и команды бота** (`ежо`, `опрос`, `Алихан ...`) в офис.
2. **Классификация служебных слов только по границам слов** — `никто` не должен матчить `кто`, `никак` не должен матчить `как`.
3. **Классификация topic-keywords только по границам слов** — `акт` не должен матчить `факт`.
4. **Не логировать исключение `requests` как строку** — оно может содержать URL с query/token.
5. **Не ACK-ать офисный вопрос при неуспешной пересылке** — `_save_prod_text()` возвращает `False`, чтобы `message_id` остался на retry.

---

### 2.5. qa.py — Парсинг QA-фактов

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/qa.py` (620 строк) |
| **Зависит от** | `secret_config` (для EVO, KEY) |
| **Импортируется в** | `whatsapp_commands.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `is_qa` | `(text: str) -> bool` | Проверка: текст содержит QA-факты |
| `parse_qa` | `(chat_id: str, text: str, date_str: str = None) -> int` | Парсинг и сохранение фактов, возвращает количество |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не менять сигнатуру `parse_qa`** — используется в `whatsapp_commands.py`.
2. **`ALLOWED_BUILDINGS`, `ALLOWED_CATEGORIES`** — валидационные множества, не удалять.

---

### 2.6. handlers.py — Обработчики (Grok, Ollama)

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/handlers.py` (676 строк) |
| **Зависит от** | `db.py`, `messaging.py` (`send_msg`), `secret_config` |
| **Импортируется в** | `whatsapp_commands.py`, `router.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `ask_grok` | `(prompt, max_tokens=700, image_base64=None, image_mime=None, force_grok=False) -> str` | Запрос к Grok/Ollama |
| `ask_grok_raw` | — | Сырой запрос с image_base64 |
| `ask_ollama` | `(prompt, system=None, max_tokens=700) -> str` | Запрос к локальной Ollama |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **XAI_KEY загружается через `secret_config`** — не через n8n workflows (удалено, AUDIT-017).
2. **`ask_grok` сигнатура** — используется в `whatsapp_commands.py` и `router.py`.

---

### 2.7. poll.py — Управление опросом

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/poll.py` (617 строк) |
| **Зависит от** | `db.py` (`get_conn`), `messaging.py` (`send_msg`), `secret_config` |
| **Импортируется в** | `whatsapp_commands.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `start_poll` | `(chat_id: str, date_str: str) -> dict` | Запустить опрос |
| `parse_poll_reply` | `(text: str, chat_id: str, date_str: str) -> dict` | Обработать ответ с кодами работ |
| `close_poll` | `(chat_id: str, date_str: str) -> dict` | Закрыть опрос |
| `get_poll_status` | `(chat_id: str) -> dict` | Статус текущего опроса |
| `ensure_poll_table` | `() -> None` | Создать таблицу `bot_poll_state` |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Таблица `bot_poll_state`** — poll зависит от неё. Не удалять и не менять схему без миграции.
2. **Все коммуникации через `send_msg`** — не слать сообщения напрямую.

---

### 2.8. data_sources.py — Единый модуль источников данных

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/data_sources.py` (756 строк) |
| **Зависит от** | `db.py` (`get_conn`, `save_weather`, `get_daily_incidents`, `get_daily_works`), `config.py` (`SANDBOX`) |
| **Импортируется в** | `fill_ejo.py` |

#### Экспортирует: 12 NamedTuple-контрактов

| NamedTuple | Поля | Описание |
|------------|------|----------|
| `WeatherData` | `temp, wind, humidity, pressure, visibility` | Погода (все `str`) |
| `IncidentCount` | `count: str` | Количество инцидентов |
| `StaffOrg` | `total: int, itr: int, workers: int` | Персонал одной организации |
| `StaffData` | `orgs: dict[str, StaffOrg]` | Персонал всех организаций |
| `VolumeData` | `works: dict[str, float], plans: dict[str, float]` | Объёмы и планы |
| `PhotoFile` | `building: str, msg_id: str, local_path: str` | Одно фото |
| `PhotoData` | `counts: dict[str, int], files: list[PhotoFile]` | Все фото |
| `EquipmentData` | `items: dict[str, int]` | Техника (название → кол-во) |
| `MaterialItem` | `name: str, qty: str, unit: str` | Один материал |
| `MaterialData` | `items: list[MaterialItem]` | Все материалы |
| `ActivePhases` | `phases: set[int]` | Активные фазы строительства |
| `PlanData` | `plans: dict[str, float]` | Планы из сообщений |
| `CodeSource` | `codes: dict[str, tuple[str, str, str]]` | Коды из последнего ЕЖО |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **`fill_ejo.py` использует ТОЛЬКО `data_sources`**, никогда не ходит в `db/get_conn` напрямую.
2. **Не менять сигнатуры 12 функций-источников.**
3. **Имена NamedTuple — часть контракта.** `fill_ejo.py` импортирует их по имени.
4. **Все функции fault-tolerant** — при ошибке возвращают fallback (пустые данные, defaults).

---

### 2.9. fill_ejo.py — Генератор ЕЖО

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/fill_ejo.py` (788 строк) |
| **Зависит от** | `data_sources.py` (все 12 NamedTuple + все функции) |
| **Импортируется в** | `whatsapp_commands.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `fill_ejo` | `(date, chat_id) -> str` | Заполнить ЕЖО, вернуть путь к файлу |
| `calc_completion_pct` | `(ws) -> int` | Процент завершения |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **`fill_ejo` зависит от ВСЕХ 12 NamedTuple из `data_sources`.** Изменение любого → проверка `fill_ejo.py`.
2. **Не ходить в БД напрямую** — только через `data_sources`.
3. **Шаблон `TEMPLATE`** — хардкод пути к `templates/ЕЖО_шаблон.xlsx`.

---

### 2.10. alerter.py — Алерты (Telegram + ojr_incidents)

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/alerter.py` (103 строки) |
| **Зависит от** | `db.py`, `secret_config` |
| **Импортируется в** | `whatsapp_commands.py` |

#### Экспортирует

| Имя | Описание |
|-----|----------|
| `send_alert(title, msg, level)` | Отправить алерт в Telegram |
| `check_incidents_table()` | Проверить ojr_incidents на пустоту >3 дней (AUDIT-017) |

---

### 2.11. whatsapp_commands.py — Точка входа v6

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/whatsapp_commands.py` (1030 строк) |
| **Зависит от** | `messaging.py`, `handlers.py`, `qa.py`, `poll.py`, `fill_ejo.py`, `alerter.py`, `config.py`, `db.py` |
| **Импортируется в** | — (точка входа, запускается Hermes Agent) |

#### Экспортирует

| Имя | Описание |
|-----|----------|
| `main()` | Главный цикл: poll Bridge :3000 → маршрутизировать команды → reply |
| `load_seen()` / `save_seen()` | Управление seen_ids (кеп на 1000, AUDIT-B10) |
| `send_collect_ack()` | Подтверждение обработки батча Bridge |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **v6 архитектура:** прямое подключение к Hermes Bridge :3000 (без Evolution API, без bridge_wrapper.py).
2. **seen_ids capped at 1000** — предотвращает unbounded growth (AUDIT-B10).
3. **Не дублировать логику** из `messaging.py`, `handlers.py`, `poll.py` — `whatsapp_commands.py` только оркестрирует.

---

## 3. Таблица влияния: «Если ломаешь X — проверь Y»

| Меняешь модуль | Затронутые модули | Что проверять |
|----------------|-------------------|---------------|
| **secret_config.py** | `db.py`, `handlers.py`, `alerter.py`, `vision_checklist.py`, `messaging.py` | Загрузка всех секретов |
| **config.py** | `data_sources.py`, `whatsapp_commands.py` | `SIM_DATE` (симуляция), пути к шаблонам, ID групп |
| **db.py** | `data_sources.py`, `handlers.py`, `alerter.py` | Подключение к БД, все CRUD-операции, `get_conn()` |
| **messaging.py** | `handlers.py`, `poll.py`, `whatsapp_commands.py` | Отправка текста, голоса, документов — ВСЯ коммуникация |
| **qa.py** | `whatsapp_commands.py` | Парсинг QA-фактов, категории, здания |
| **handlers.py** | `whatsapp_commands.py` | Grok API, Ollama, верификация ответов |
| **poll.py** | `whatsapp_commands.py` | Опрос, таблица `bot_poll_state` |
| **data_sources.py** | `fill_ejo.py` | ВСЕ 12 NamedTuple + 12 функций. Заполнение ЕЖО целиком |
| **fill_ejo.py** | `whatsapp_commands.py` | Генерация ЕЖО, вставка фото, расчёт процентов |
| **alerter.py** | `whatsapp_commands.py` | Telegram-алерты, мониторинг ojr_incidents |
| **whatsapp_commands.py** | — (точка входа) | Полный цикл: Bridge poll → обработка → ответ |

### Приоритеты проверки

| Приоритет | Модули | Почему |
|-----------|--------|--------|
| 🔴 **P0** | `secret_config.py`, `db.py`, `messaging.py` | Фундамент — ломает ВСЁ |
| 🟠 **P1** | `data_sources.py`, `config.py` | Ломает ЕЖО и конфигурацию |
| 🟡 **P2** | `poll.py`, `fill_ejo.py`, `whatsapp_commands.py` | Ломает конкретные фичи |
| 🟢 **P3** | `qa.py`, `handlers.py`, `alerter.py` | Ломает парсинг/Grok/алерты |

---

## 4. Известные баги, вызванные нарушением контрактов

### B10 — seen_ids unbounded growth

| Поле | Значение |
|------|----------|
| **ID** | B10 |
| **Дата** | 2026-07 |
| **Симптом** | `seen_ids.json` рос без ограничений, замедлял загрузку |
| **Причина** | Не было кепа на размер сохраняемого множества |
| **Исправление** | `save_seen()` теперь сохраняет только последние 1000 ID (AUDIT-B10) |
| **Урок** | Всегда кепировать множества на диске |

---

## 5. Машиночитаемый граф зависимостей

> **Внимание:** эта секция используется `scripts/pre_delegation.py`.
> Не менять формат без синхронного обновления парсера.

```json
{
  "dependency_graph": {
    "secret_config.py": [],
    "config.py": [],
    "db.py": ["secret_config.py"],
    "messaging.py": ["secret_config.py"],
    "handlers.py": ["db.py", "messaging.py", "secret_config.py"],
    "qa.py": ["secret_config.py"],
    "poll.py": ["db.py", "messaging.py", "secret_config.py"],
    "data_sources.py": ["db.py", "config.py"],
    "fill_ejo.py": ["data_sources.py"],
    "alerter.py": ["db.py", "secret_config.py"],
    "whatsapp_commands.py": ["messaging.py", "handlers.py", "qa.py", "poll.py", "fill_ejo.py", "alerter.py", "config.py", "db.py"]
  },
  "modules": {
    "secret_config.py": {
      "level": 0,
      "priority": "P0",
      "description": "Единая загрузка секретов: env → secrets.env → /run/secrets.",
      "exports": ["get_secret", "get_evo_key"],
      "critical_rules": [
        "Никаких прямых чтений secrets.env — только через secret_config",
        "Никаких fallback-чтений JSON (n8n workflows) — удалено (AUDIT-017)"
      ]
    },
    "config.py": {
      "level": 0,
      "priority": "P1",
      "description": "Централизованная конфигурация: константы, пути, SIM_DATE.",
      "exports": ["SIM_DATE", "SANDBOX", "PRODUCTION", "TEMPLATE_PATH", "SEEN_FILE", "EJO_START_ROW", "VOICE_TRIGGERS", "BUILDINGS", "today_str", "today_date"],
      "critical_rules": [
        "Не хардкодить пути в других модулях — использовать config.TEMPLATE_PATH",
        "SIM_DATE — единственный механизм симуляции"
      ]
    },
    "db.py": {
      "level": 0,
      "priority": "P0",
      "description": "Единственная точка подключения к БД (PostgreSQL/psycopg2). DB_PASS через secret_config.",
      "exports": ["get_conn", "DB_CONFIG", "resolve_db_host", "save_message", "save_fact", "get_daily_personnel", "get_daily_works", "save_weather", "get_daily_incidents"],
      "critical_rules": [
        "get_conn() — единственная точка подключения. Никакой модуль не создаёт psycopg2.connect() напрямую",
        "Не хардкодить DB_CONFIG в других модулях",
        "DB_PASS загружается через secret_config — не читать secrets.env напрямую"
      ]
    },
    "messaging.py": {
      "level": 1,
      "priority": "P0",
      "description": "Единственная точка отправки сообщений (текст, голос, документы).",
      "exports": ["send_msg", "send_voice", "send_document"],
      "critical_rules": [
        "Единственная точка отправки. Никакой модуль не шлёт сообщения напрямую",
        "Не дублировать send_msg — удалены все дубликаты (AUDIT-011)"
      ]
    },
    "qa.py": {
      "level": 2,
      "priority": "P3",
      "description": "Парсинг QA-фактов (персонал, техника, инциденты).",
      "exports": ["is_qa", "parse_qa"],
      "critical_rules": [
        "Не менять сигнатуру parse_qa(chat_id, text, date_str)",
        "ALLOWED_BUILDINGS, ALLOWED_CATEGORIES — валидационные множества"
      ]
    },
    "handlers.py": {
      "level": 2,
      "priority": "P3",
      "description": "Обработчики: Grok API, Ollama, верификация ответов. Ключи через secret_config.",
      "exports": ["ask_grok", "ask_grok_raw", "ask_ollama"],
      "critical_rules": [
        "XAI_KEY загружается через secret_config (не через n8n — удалено, AUDIT-017)",
        "Сигнатура ask_grok(prompt, max_tokens, image_base64, mimetype, force_grok)"
      ]
    },
    "poll.py": {
      "level": 3,
      "priority": "P2",
      "description": "Управление опросом: запуск, парсинг ответов, закрытие.",
      "exports": ["start_poll", "parse_poll_reply", "close_poll", "get_poll_status", "ensure_poll_table"],
      "critical_rules": [
        "Таблица bot_poll_state — не удалять и не менять схему без миграции",
        "Все коммуникации через send_msg"
      ]
    },
    "data_sources.py": {
      "level": 3,
      "priority": "P1",
      "description": "Единый модуль источников данных: 12 NamedTuple + 12 функций.",
      "exports": [
        "WeatherData", "IncidentCount", "StaffOrg", "StaffData", "VolumeData",
        "PhotoFile", "PhotoData", "EquipmentData", "MaterialItem", "MaterialData",
        "ActivePhases", "PlanData", "CodeSource",
        "get_weather", "get_incidents", "get_staff", "get_volumes", "get_photos",
        "get_aibikon_headcount", "get_equipment", "get_materials",
        "get_active_phases", "get_plans_from_messages", "get_code_source", "get_phase_end_dates"
      ],
      "critical_rules": [
        "fill_ejo.py использует ТОЛЬКО data_sources, никогда не ходит в db/get_conn напрямую",
        "Не менять сигнатуры 12 функций-источников",
        "Имена NamedTuple — часть контракта",
        "Все функции fault-tolerant"
      ]
    },
    "fill_ejo.py": {
      "level": 4,
      "priority": "P2",
      "description": "Генератор ЕЖО: заполнение шаблона xlsx данными из data_sources.",
      "exports": ["fill_ejo", "calc_completion_pct"],
      "critical_rules": [
        "Зависит от ВСЕХ 12 NamedTuple из data_sources",
        "Не ходить в БД напрямую — только через data_sources"
      ]
    },
    "alerter.py": {
      "level": 2,
      "priority": "P3",
      "description": "Алерты: Telegram-уведомления + мониторинг ojr_incidents.",
      "exports": ["send_alert", "check_incidents_table"],
      "critical_rules": [
        "Telegram credentials через secret_config (не читать secrets.env напрямую)",
        "check_incidents_table() — алерт если ojr_incidents пуст >3 дней (AUDIT-017)"
      ]
    },
    "whatsapp_commands.py": {
      "level": 5,
      "priority": "P2",
      "description": "Точка входа v6: прямой Bridge poll → команды. seen_ids capped at 1000.",
      "exports": ["main", "load_seen", "save_seen", "send_collect_ack"],
      "critical_rules": [
        "v6: прямой Hermes Bridge :3000 (без Evolution API, без bridge_wrapper.py)",
        "seen_ids capped at 1000 (AUDIT-B10)",
        "Не дублировать логику из messaging/handlers/poll"
      ]
    }
  }
}
```
