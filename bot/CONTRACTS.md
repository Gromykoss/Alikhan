# CONTRACTS.md — Карта зависимостей и контрактов модулей Alikhan

> **Назначение:** единый источник истины о зависимостях, контрактах и правилах взаимодействия модулей.
> **Обновляется:** при любом изменении сигнатур функций, импортов или публичного API модулей.
> **Используется:** `scripts/pre_delegation.py` для сборки контекста при делегировании задач в Codex/Grok Build.

---

## 1. Граф зависимостей

```
Уровень 0 (фундамент — без зависимостей от других модулей бота):
  bridge_wrapper.py  ← stdlib + requests (патчит на уровне import)
  config.py          ← os, datetime (чистые константы)
  db.py              ← psycopg2 (чистая БД)

Уровень 1 (сервисы):
  messaging.py  → bridge_wrapper.py
  router.py     → config.py

Уровень 2 (обработчики):
  qa.py         → bridge_wrapper.py
  handlers.py   → db.py, messaging.py, bridge_wrapper.py

Уровень 3 (бизнес-логика):
  poll.py         → db.py, bridge_wrapper.py, messaging.py
  data_sources.py → db.py, config.py

Уровень 4 (композиция):
  fill_ejo.py  → data_sources.py (12 NamedTuple), bridge_wrapper.py

Уровень 5 (точка входа):
  main_waha.py → bridge_wrapper.py, config.py, messaging.py, poll.py (ленивый import)
```

### Визуализация (ASCII-граф)

```
config.py ──────────────────────────────────────────────────────┐
                                                                 │
db.py ──────────────────────────────────────────────┐            │
                                                     │            │
bridge_wrapper.py ────────────────────────┐          │            │
                                          │          │            │
         ┌────────────────────────────────┤          │            │
         ▼                                ▼          ▼            ▼
    messaging.py                    data_sources.py         router.py
         │                                │
         │         ┌──────────────────────┤
         │         │                      │
         ▼         ▼                      │
      poll.py   fill_ejo.py               │
         │         │                      │
         │         │                      │
         ▼         ▼                      ▼
    ┌──────────────────────────────────────────┐
    │              main_waha.py                 │
    │  (точка входа, ленивые import'ы)          │
    └──────────────────────────────────────────┘
         │              │
         ▼              ▼
      handlers.py    qa.py
```

---

## 2. Контракты модулей

### 2.1. bridge_wrapper.py — Фундамент: мост Evolution API → Hermes Bridge

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/bridge_wrapper.py` |
| **Зависит от** | stdlib (`requests`, `urllib`, `json`, `os`, `time`, `base64`, `functools`) |
| **Импортируется в** | `messaging.py`, `qa.py`, `handlers.py`, `poll.py`, `fill_ejo.py`, `main_waha.py` |

#### Экспортирует

| Имя | Тип | Описание |
|-----|-----|----------|
| `EVO` | `str` | `"http://127.0.0.1:3000"` — URL Evolution API (dummy, не используется напрямую после monkey-patch) |
| `KEY` | `str` | `"bridge"` — API-ключ (dummy) |
| `SANDBOX` | `str` | ID песочницы из `WHATSAPP_SANDBOX` |
| `PRODUCTION` | `str` | ID production-группы из `WHATSAPP_PRODUCTION` |
| `_fetch_and_buffer()` | `() -> None` | Забирает все сообщения с Hermes Bridge и кладёт в буфер |

#### Сайд-эффекты при `import`

- **Monkey-patch `requests.post`** — все вызовы к `.../chat/findMessages/...`, `.../message/sendText/...`, `.../message/sendMedia/...` перенаправляются на Hermes Bridge (`http://127.0.0.1:3000`)
- **Monkey-patch `urllib.request.Request` + `urllib.request.urlopen`** — sendText и sendMedia через Hermes Bridge, getBase64FromMediaMessage — чтение из локального кеша/БД
- **Буфер сообщений** — `/messages` эндпоинт Bridge деструктивный, поэтому bridge_wrapper кеширует все сообщения в `_BUFFER` и фильтрует по `remoteJid`

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Импортировать ТОЛЬКО как** `from bridge_wrapper import EVO, KEY`. Никогда не хардкодить `EVO="http://127.0.0.1:3000"` или `KEY="bridge"` в других модулях.
2. **Не дублировать логику отправки сообщений** — она уже запатчена на уровне `requests.post` и `urllib`. Любой код, вызывающий `requests.post(EVO + "/message/sendText/...")`, автоматически идёт через Bridge.
3. **`_fetch_and_buffer()`** — единственная точка синхронизации с Bridge. Вызывается при каждом `requests.post` к `/chat/findMessages/`.
4. **Не менять сигнатуру `_patched_requests_post`** — от неё зависят все модули, отправляющие сообщения.
5. **Буфер ограничен 200 сообщениями** — старые вытесняются.

---

### 2.2. config.py — Централизованная конфигурация

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/config.py` |
| **Зависит от** | `os`, `datetime` |
| **Импортируется в** | `router.py`, `data_sources.py`, `main_waha.py` |

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

### 2.3. db.py — Единственная точка подключения к БД

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/db.py` (924 строки) |
| **Зависит от** | `psycopg2`, `psycopg2.extras`, `ipaddress`, `os`, `subprocess` |
| **Импортируется в** | `data_sources.py`, `handlers.py`, `poll.py` (лениво через `main_waha.py`) |

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

### 2.4. messaging.py — Единственная точка отправки сообщений

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/messaging.py` (73 строки) |
| **Зависит от** | `bridge_wrapper.py` (`EVO`, `KEY`) |
| **Импортируется в** | `handlers.py`, `poll.py`, `main_waha.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `send_msg` | `(chat_id: str, text: str) -> bool` | Отправить текст (макс. 3800 символов) |
| `send_voice` | `(chat_id: str, text: str) -> bool` | TTS → голосовое (edge-tts), fallback на текст |
| `send_document` | `(chat_id: str, path: str, filename: str = None) -> bool` | Отправить документ (base64-encode) |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Единственная точка отправки.** Никакой модуль не шлёт сообщения через `requests.post(EVO + "/message/sendText/...")` или `urllib` напрямую.
2. **Не дублировать `send_msg`** — в кодовой базе исторически было 3+ реализации. Все удалены (AUDIT-011).
3. **`send_voice` использует edge-tts** — должен быть установлен в системе.
4. **Текст обрезается до 3800 символов** в `send_msg` — WhatsApp ограничение.

---

### 2.5. router.py — Маршрутизация сообщений

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/router.py` (125 строк) |
| **Зависит от** | `config.py` (`SIM_DATE`, `VOICE_TRIGGERS`), лениво: `handlers`, `qa`, `db_lookup`, `verify` |
| **Импортируется в** | `main_waha.py` |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `route` | `(text: str, chat_id: str, sender: str = "") -> (action: str, reply: str, voice_triggered: bool)` | Маршрутизация: QA → команды → Grok → DB lookup |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не менять сигнатуру `route()`** — возвращает tuple `(action, reply, voice)`, от этого зависит `main_waha.py`.
2. **Ленивые импорты внутри `route()`** — `from handlers import ask_grok`, `from qa import is_qa, parse_qa` — это намеренно, для избежания циклических зависимостей.
3. **Порядок проверок важен:** QA → residual → name check → commands → Grok → DB. Не менять без понимания последствий.

---

### 2.6. qa.py — Парсинг QA-фактов

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/qa.py` (536 строк) |
| **Зависит от** | `bridge_wrapper.py` (`EVO`, `KEY`) |
| **Импортируется в** | `router.py` (лениво), `main_waha.py` (лениво) |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `is_qa` | `(text: str) -> bool` | Проверка: текст содержит QA-факты |
| `parse_qa` | `(chat_id: str, text: str, date_str: str = None) -> int` | Парсинг и сохранение фактов, возвращает количество |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не менять сигнатуру `parse_qa`** — используется в `router.py`.
2. **`ALLOWED_BUILDINGS`, `ALLOWED_CATEGORIES`** — валидационные множества, не удалять.

---

### 2.7. handlers.py — Обработчики (Grok, Ollama)

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/handlers.py` (674 строки) |
| **Зависит от** | `db.py`, `messaging.py` (`send_msg`), `bridge_wrapper.py` (`EVO`) |
| **Импортируется в** | `router.py` (лениво), `main_waha.py` (лениво) |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `ask_grok` | `(prompt: str, max_tokens: int = 200, image_base64: str = None, image_mime: str = None) -> str` | Запрос к xAI Grok |
| `ask_grok_raw` | — | Сырой запрос с image_base64 |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не хардкодить `XAI_KEY`** — загружается из `secrets.env`.
2. **`ask_grok` сигнатура** — используется в `router.py` и `main_waha.py`.

---

### 2.8. poll.py — Управление опросом

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/poll.py` (617 строк) |
| **Зависит от** | `db.py` (`get_conn`), `bridge_wrapper.py` (`EVO`, `KEY`), `messaging.py` (`send_msg`) |
| **Импортируется в** | `main_waha.py` (лениво) |

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
3. **Сигнатура `parse_poll_reply`** — используется в `main_waha.py`.

---

### 2.9. data_sources.py — Единый модуль источников данных

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
| `VolumeData` | `works: dict[str, float], plans: dict[str, float]` | Объёмы и планы (взаимоисключающие) |
| `PhotoFile` | `building: str, msg_id: str, local_path: str` | Одно фото |
| `PhotoData` | `counts: dict[str, int], files: list[PhotoFile]` | Все фото |
| `EquipmentData` | `items: dict[str, int]` | Техника (название → кол-во) |
| `MaterialItem` | `name: str, qty: str, unit: str` | Один материал |
| `MaterialData` | `items: list[MaterialItem]` | Все материалы |
| `ActivePhases` | `phases: set[int]` | Активные фазы строительства |
| `PlanData` | `plans: dict[str, float]` | Планы из сообщений |
| `CodeSource` | `codes: dict[str, tuple[str, str, str]]` | Коды из последнего ЕЖО |

#### Экспортирует: 12 функций-источников

| Функция | Возвращает | Primary источник | Fallback |
|---------|------------|-----------------|----------|
| `get_weather(date)` | `WeatherData` | Open-Meteo API → `ojr_weather` | defaults |
| `get_incidents(date)` | `IncidentCount` | `ojr_incidents` | `bot_memory_facts` |
| `get_staff(date)` | `StaffData` | `ojr_section1_personnel` | `bot_memory_facts` |
| `get_volumes(date)` | `VolumeData` | `ojr_section3_work_log` | `bot_memory_facts` + `get_plans_from_messages` |
| `get_photos(date)` | `PhotoData` | `ojr_photo_log` | `bot_memory_messages` |
| `get_aibikon_headcount(date)` | `dict` | Табель (xlsx) | `ojr_section1_personnel` |
| `get_equipment(date)` | `EquipmentData` | `bot_memory_facts` («техника») | empty dict |
| `get_materials(date)` | `MaterialData` | `ojr_materials` | `bot_memory_facts` |
| `get_active_phases(date)` | `ActivePhases` | `bot_schedule_phases` | `{3,4,5,6,7}` |
| `get_plans_from_messages(date, sandbox_id)` | `PlanData` | `bot_memory_messages` | empty dict |
| `get_code_source()` | `CodeSource \| None` | Последний ЕЖО xlsx | `None` |
| `get_phase_end_dates()` | `dict[str, date]` | `bot_schedule_phases` | hardcoded |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **`fill_ejo.py` использует ТОЛЬКО `data_sources`**, никогда не ходит в `db/get_conn` напрямую.
2. **Не менять сигнатуры функций-источников** — 12 функций, все принимают `date`, возвращают строго типизированные NamedTuple.
3. **Не добавлять обращения к БД в обход `db.py`** — data_sources использует `from db import get_conn`, но это единственное разрешённое место.
4. **Имена NamedTuple — часть контракта.** `fill_ejo.py` импортирует их по имени.
5. **Все функции fault-tolerant** — при ошибке возвращают fallback (пустые данные, defaults), не кидают исключения наружу.

---

### 2.10. fill_ejo.py — Генератор ЕЖО

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/fill_ejo.py` (788 строк) |
| **Зависит от** | `data_sources.py` (все 12 NamedTuple + все функции), `bridge_wrapper.py` (`EVO`, `KEY`, `_fetch_and_buffer`) |
| **Импортируется в** | `main_waha.py` (лениво) |

#### Экспортирует

| Имя | Сигнатура | Описание |
|-----|-----------|----------|
| `fill_ejo` | `(date, chat_id) -> str` | Заполнить ЕЖО, вернуть путь к файлу |
| `calc_completion_pct` | `(ws) -> int` | Процент завершения |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **`fill_ejo` зависит от ВСЕХ 12 NamedTuple из `data_sources`.** Изменение любого NamedTuple → проверка `fill_ejo.py`.
2. **Не ходить в БД напрямую** — только через `data_sources`.
3. **Шаблон `TEMPLATE`** — хардкод пути к `templates/ЕЖО_шаблон.xlsx`.

---

### 2.11. main_waha.py — Точка входа

| Свойство | Значение |
|----------|----------|
| **Файл** | `bot/main_waha.py` (1340 строк) |
| **Зависит от** | `bridge_wrapper.py` (все), `config.py`, `messaging.py`, `poll.py` (лениво), `router.py` (лениво), `handlers.py` (лениво) |
| **Импортируется в** | — (точка входа, systemd `alikhan.service`) |

#### Экспортирует

| Имя | Описание |
|-----|----------|
| `main()` | Главный цикл: poll messages → route → reply |
| `generate_daily_snapshot(chat_id)` | Ежедневный снимок |

#### ⛔ КРИТИЧЕСКИЕ ПРАВИЛА

1. **Не запускать вручную** — только через `systemctl --user restart alikhan`.
2. **`from bridge_wrapper import *`** — должен быть ПЕРВЫМ import, до любых других, использующих `requests`/`urllib`.
3. **Не дублировать логику** из `messaging.py`, `router.py`, `poll.py` — `main_waha.py` только оркестрирует.

---

## 3. Таблица влияния: «Если ломаешь X — проверь Y»

| Меняешь модуль | Затронутые модули | Что проверять |
|----------------|-------------------|---------------|
| **bridge_wrapper.py** | `messaging.py`, `qa.py`, `handlers.py`, `poll.py`, `fill_ejo.py`, `main_waha.py` | Отправка сообщений, приём сообщений, скачивание медиа, TTS, document upload |
| **config.py** | `router.py`, `data_sources.py`, `main_waha.py` | `SIM_DATE` (симуляция), пути к шаблонам, ID групп |
| **db.py** | `data_sources.py`, `handlers.py`, `poll.py` | Подключение к БД, все CRUD-операции, `get_conn()` |
| **messaging.py** | `handlers.py`, `poll.py`, `main_waha.py` | Отправка текста, голоса, документов — ВСЯ коммуникация |
| **router.py** | `main_waha.py` | Маршрутизация команд, QA-парсинг, Grok-ответы |
| **qa.py** | `router.py`, `main_waha.py` | Парсинг QA-фактов, категории, здания |
| **handlers.py** | `router.py`, `main_waha.py` | Grok API, Ollama, верификация ответов |
| **poll.py** | `main_waha.py` | Опрос, таблица `bot_poll_state`, `parse_poll_reply` |
| **data_sources.py** | `fill_ejo.py` | ВСЕ 12 NamedTuple + 12 функций. Заполнение ЕЖО целиком |
| **fill_ejo.py** | `main_waha.py` | Генерация ЕЖО, вставка фото, расчёт процентов |
| **main_waha.py** | — (точка входа) | Полный цикл: приём → обработка → ответ. systemd service |

### Приоритеты проверки

| Приоритет | Модули | Почему |
|-----------|--------|--------|
| 🔴 **P0** | `bridge_wrapper.py`, `db.py`, `messaging.py` | Фундамент — ломает ВСЁ |
| 🟠 **P1** | `data_sources.py`, `config.py` | Ломает ЕЖО и конфигурацию |
| 🟡 **P2** | `poll.py`, `fill_ejo.py`, `router.py` | Ломает конкретные фичи |
| 🟢 **P3** | `qa.py`, `handlers.py` | Ломает парсинг/Grok |

---

## 4. Известные баги, вызванные нарушением контрактов

### B10 — Рефакторинг data_sources убил bridge_wrapper

| Поле | Значение |
|------|----------|
| **ID** | B10 |
| **Дата** | 2026-07 |
| **Симптом** | После рефакторинга `data_sources.py` перестали приходить сообщения |
| **Причина** | Разработчик заменил `from bridge_wrapper import EVO, KEY` на хардкод `EVO="http://127.0.0.1:3000"` внутри `data_sources.py`. Monkey-patch `requests.post` не сработал, потому что вызовы шли через другой путь. |
| **Нарушенный контракт** | bridge_wrapper.py: **Импортировать ТОЛЬКО как `from bridge_wrapper import EVO, KEY`. Никогда не хардкодить.** |
| **Исправление** | Откат хардкода, восстановление импорта из `bridge_wrapper` |
| **Урок** | Любое изменение в `data_sources.py` требует проверки bridge-трафика |

---

## 5. Машиночитаемый граф зависимостей

> **Внимание:** эта секция используется `scripts/pre_delegation.py`.
> Не менять формат без синхронного обновления парсера.

```json
{
  "dependency_graph": {
    "bridge_wrapper.py": [],
    "config.py": [],
    "db.py": [],
    "router.py": ["config.py"],
    "messaging.py": ["bridge_wrapper.py"],
    "handlers.py": ["db.py", "messaging.py", "bridge_wrapper.py"],
    "qa.py": ["bridge_wrapper.py"],
    "poll.py": ["db.py", "bridge_wrapper.py", "messaging.py"],
    "data_sources.py": ["db.py", "config.py"],
    "fill_ejo.py": ["data_sources.py", "bridge_wrapper.py"],
    "main_waha.py": ["bridge_wrapper.py", "config.py", "messaging.py", "poll.py"]
  },
  "modules": {
    "bridge_wrapper.py": {
      "level": 0,
      "priority": "P0",
      "description": "Фундамент: мост Evolution API → Hermes Bridge. Monkey-patch requests + urllib.",
      "exports": ["EVO", "KEY", "SANDBOX", "PRODUCTION", "_fetch_and_buffer"],
      "critical_rules": [
        "Импортировать ТОЛЬКО как `from bridge_wrapper import EVO, KEY`",
        "Никогда не хардкодить EVO/KEY в других модулях",
        "_fetch_and_buffer() — единственная точка синхронизации с Bridge"
      ]
    },
    "config.py": {
      "level": 0,
      "priority": "P1",
      "description": "Централизованная конфигурация: константы, пути, SIM_DATE.",
      "exports": ["SIM_DATE", "SANDBOX", "PRODUCTION", "TEMPLATE_PATH", "EJO_START_ROW", "VOICE_TRIGGERS", "BUILDINGS", "today_str", "today_date"],
      "critical_rules": [
        "Не хардкодить пути в других модулях — использовать config.TEMPLATE_PATH",
        "SIM_DATE — единственный механизм симуляции"
      ]
    },
    "db.py": {
      "level": 0,
      "priority": "P0",
      "description": "Единственная точка подключения к БД (PostgreSQL/psycopg2).",
      "exports": ["get_conn", "DB_CONFIG", "resolve_db_host", "save_message", "save_fact", "get_daily_personnel", "get_daily_works", "save_weather", "get_daily_incidents"],
      "critical_rules": [
        "get_conn() — единственная точка подключения. Никакой модуль не создаёт psycopg2.connect() напрямую",
        "Не хардкодить DB_CONFIG в других модулях"
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
    "router.py": {
      "level": 1,
      "priority": "P2",
      "description": "Маршрутизация сообщений: QA → команды → Grok → DB lookup.",
      "exports": ["route"],
      "critical_rules": [
        "Сигнатура route(text, chat_id, sender) -> (action, reply, voice)",
        "Ленивые импорты внутри route() — не выносить наверх"
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
      "description": "Обработчики: Grok API, Ollama, верификация ответов.",
      "exports": ["ask_grok", "ask_grok_raw"],
      "critical_rules": [
        "Не хардкодить XAI_KEY — загружается из secrets.env",
        "Сигнатура ask_grok(prompt, max_tokens, image_base64, image_mime)"
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
      "description": "Единый модуль источников данных: 12 NamedTuple + 12 функций. Все обращения к БД/API/файлам — только здесь.",
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
        "Имена NamedTuple — часть контракта. fill_ejo.py импортирует их по имени",
        "Все функции fault-tolerant — при ошибке возвращают fallback, не кидают исключения"
      ]
    },
    "fill_ejo.py": {
      "level": 4,
      "priority": "P2",
      "description": "Генератор ЕЖО: заполнение шаблона xlsx данными из data_sources.",
      "exports": ["fill_ejo", "calc_completion_pct"],
      "critical_rules": [
        "Зависит от ВСЕХ 12 NamedTuple из data_sources. Изменение любого → проверка fill_ejo.py",
        "Не ходить в БД напрямую — только через data_sources"
      ]
    },
    "main_waha.py": {
      "level": 5,
      "priority": "P2",
      "description": "Точка входа: главный цикл (poll → route → reply). systemd alikhan.service.",
      "exports": ["main", "generate_daily_snapshot"],
      "critical_rules": [
        "from bridge_wrapper import * должен быть ПЕРВЫМ import",
        "Не запускать вручную — только через systemctl",
        "Не дублировать логику из messaging/router/poll"
      ]
    }
  }
}
```
