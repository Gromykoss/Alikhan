# ПОЛНЫЙ АУДИТ — Worker A (Codex) — 12.08.2026

## 🏗️ 1. АРХИТЕКТУРА / ПОТОКИ ДАННЫХ

### Верхний уровень (v6 — прямой Hermes Bridge):

```
WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot)
           │
           ├── alikhan_whatsapp_commands.py (cron-диспетчер)
           │     ├── /collect-messages?only=PRODUCTION (listen-only)
           │     ├── /collect-messages?only=SANDBOX (отвечаем)
           │     └── /collect-ack (подтверждение обработки)
           │
           ├── qa.py (QA-парсер) → Hermes Agent → bot_memory_facts → ojr_section1/3
           ├── fill_ejo.py (ЕЖО) → data_sources.py → BД/API → Excel → WhatsApp
           ├── poll.py (опросы) → EJO-template → bot_poll_state → WhatsApp
           ├── handlers.py (Grok/Ollama) → xAI API / локальный Ollama
           └── router.py (маршрутизация сообщений)
```

### Граф зависимостей (по факту чтения кода):

```
Уровень 0 (фундамент):
  config.py, db.py, bridge_wrapper.py, secret_config.py, logging_config.py

Уровень 1 (сервисы):
  messaging.py → bridge_wrapper.py
  graceful.py, metrics.py, alerter.py, code_cache.py

Уровень 2 (обработчики):
  handlers.py → db.py, messaging.py, bridge_wrapper.py
  qa.py → bridge_wrapper.py
  stt.py → bridge_wrapper.py, handlers.py
  db_memory.py → db.py
  db_lookup.py → db.py, db_memory.py
  router.py → config.py, handlers.py, qa.py, db_lookup.py, verify.py

Уровень 3 (бизнес-логика):
  poll.py → db.py, bridge_wrapper.py, messaging.py
  data_sources.py → db.py, config.py
  verify.py → handlers.py
  vision_checklist.py → handlers.py (через xAI API)

Уровень 4 (композиция):
  fill_ejo.py → data_sources.py (12 NamedTuple)
  avr.py → pricing/EJO files

Уровень 5 (точки входа):
  main_waha.py → bridge_wrapper.py, config.py, messaging.py, router.py, handlers.py
  whatsapp_commands.py → bridge_wrapper.py (напрямую, через свой BRIDGE=:3000)
  daily_snapshot.py → bridge_wrapper.py, db.py, handlers.py
  watchdog_bridge.py (автономный)
  document_extractor.py (HTTP-сервер :8099)
```

### ⚠️ КРИТИЧЕСКОЕ НАРУШЕНИЕ АРХИТЕКТУРЫ:

Две (2) НЕЗАВИСИМЫЕ реализации диспетчера WhatsApp-сообщений:

1. **bot/whatsapp_commands.py** (1030 строк) — основной cron-диспетчер с системой ролей
2. **~/.hermes/profiles/alikhan/scripts/alikhan_whatsapp_commands.py** (282 строки) — устаревшая копия БЕЗ системы ролей

Эти два файла — РАЗНЫЕ, не синхронизированы. Профильная версия — старый код (v2 без ролей). Боевая — расширенная версия с ролями, обработкой фото, классификацией через vision, OCR документов.

---

## 📋 2. ИНВЕНТАРИЗАЦИЯ ОБРАБОТЧИКОВ

### Точки входа (3):

| Файл | Назначение | Строк |
|------|-----------|-------|
| `whatsapp_commands.py` | Основной cron-диспетчер, парсит /collect-messages, ролевая модель, обработка фото/документов/команд | 1030 |
| `main_waha.py` | Устаревшая точка входа (systemd-сервис ОСТАНОВЛЕН), но код всё ещё живой | 1416 |
| `daily_snapshot.py` | Ежедневный снимок (8:00/16:00) — погода, сообщения, документы, Grok-отчёт | 177 |

### Обработчики сообщений (7):

| Файл | Функции | Назначение |
|------|---------|-----------|
| `handlers.py` | `ask_grok`, `ask_grok_raw`, `ask_ollama`, `handle_*` (12+ handlers) | Запросы к Grok/Ollama, обработка календаря, памяти, расписания |
| `router.py` | `route()` | Маршрутизация: QA → команды → Grok → DB lookup |
| `qa.py` | `is_qa`, `parse_qa` | Парсинг QA-фактов из сообщений прорабов |
| `stt.py` | `transcribe_audio` | Speech-to-text через faster-whisper + Grok коррекция |
| `verify.py` | `verify_reply`, `verify_qa_facts` | Верификация ответов агента (Claude Code pattern) |
| `vision_checklist.py` | `checklist_from_image`, `checklist_category` | Классификация фото стройплощадки через Grok Vision |
| `db_lookup.py` | `lookup_facts`, `lookup_schedule` | Поиск фактов/погоды/графика по запросу |

### Бизнес-логика (5):

| Файл | Функции | Назначение |
|------|---------|-----------|
| `fill_ejo.py` | `fill()` | Генерация ЕЖО xlsx из data_sources |
| `data_sources.py` | 12 функций `get_*` | Единый модуль источников данных (БД/API/файлы) |
| `poll.py` | `start_poll`, `parse_poll_reply`, `close_poll`, `get_poll_status` | Управление опросами персонала |
| `avr.py` | `generate_ks2`, `generate_ks6` | Генерация КС-2/КС-6 актов |
| `update_template.py` | `update()` | Обновление шаблона ЕЖО новыми кодами работ |

### Инфраструктура (14):

| Файл | Назначение |
|------|-----------|
| `db.py` (1136 строк) | Единственная точка подключения к БД |
| `db_memory.py` | Работа с `bot_memory_facts` |
| `bridge_wrapper.py` | Monkey-patch Evolution API → Hermes Bridge |
| `config.py` | Централизованная конфигурация |
| `messaging.py` | Единая отправка сообщений (текст, голос, документы) |
| `secret_config.py` | Загрузка секретов из secrets.env |
| `logging_config.py` | Структурированное логирование |
| `metrics.py` | Prometheus-метрики (:9090) |
| `alerter.py` | Telegram-алерты |
| `graceful.py` | Graceful degradation (fallback'и) |
| `code_cache.py` | Кеш code→name из шаблона ЕЖО |
| `backup_db.py` | Резервное копирование БД |
| `watchdog_bridge.py` | Мониторинг Hermes Bridge (:3000) |
| `document_extractor.py` | HTTP-сервер распознавания документов (:8099) |

### Утилиты (4):

| Файл | Назначение |
|------|-----------|
| `tag_old_photos.py` | Тегирование старых фото без building |
| `memory_tagging.py` | Пакетное тегирование старых записей через Grok |
| `building_profiles.py` | Профили зданий |
| `validate_ejo.py` / `verify_ejo.py` | Валидация сгенерированных ЕЖО |

---

## 🤖 3. ИНВЕНТАРИЗАЦИЯ ПРОМПТОВ

### Встроенные промпты (в коде):

| Файл | Промпт | Назначение | Строки |
|------|--------|-----------|--------|
| `handlers.py` | `ask_grok()` — системный промпт прораба | Ответы на вопросы прорабов | ~200 |
| `router.py` | Промпт для `ask_grok` (инспектор ТЗРК Джеруй) | Маршрутизация DB-фактов | 94-112 |
| `verify.py` | Промпт верификации (точность/полнота/формат) | Верификация ответов агента | 28-43 |
| `verify.py` | `verify_qa_facts` — проверка потери фактов | QA-верификация | 82-88 |
| `qa.py` | `_build_qa_prompt()` — few-shot промпт для Grok | Извлечение QA-фактов | 258-300 |
| `vision_checklist.py` | `CHECKLIST_PROMPT` — структурированный JSON | Классификация фото | 65-101 |
| `whatsapp_commands.py` | `_classify_photo_via_vision()` — промпт категоризации | Классификация боевых фото | ~600 |
| `whatsapp_commands.py` | `_ocr_document_tags()` — OCR теги из документов | Извлечение тегов из xlsx/pdf | ~840 |
| `daily_snapshot.py` | Промпт для Grok — ежедневный отчёт | Структурированный снимок дня | 120-149 |
| `main_waha.py` | `generate_daily_snapshot()` — промпт для Ollama | Нарратив дня | 273-302 |
| `stt.py` | Промпт коррекции STT через Grok | Исправление ошибок распознавания | 42-49 |
| `handlers.py` | Промпты для `handle_document_compare` | Сравнение документов | ~280-320 |

### Файловые шаблоны промптов:

| Путь | Назначение |
|------|-----------|
| `bot/prompts/daily_snapshot_prompt.md` | Структурированный шаблон ежедневного снимка (v2) |
| `bot/prompts/gather_snapshot_data.py` | Сбор данных для снимка |

### Общее количество LLM-вызовов:

- **Grok (xAI)**: ask_grok, ask_grok_raw, verify_reply, verify_qa_facts, STT-коррекция, vision-классификация, OCR-теги, снимок дня — **~8 различных промптов**
- **Ollama (qwen2.5:14b)**: ask_ollama — **1 промпт** (снимок дня, fallback для Grok)

---

## 🗄️ 4. СОСТОЯНИЕ БАЗЫ ДАННЫХ

### Таблицы (подтверждено схемой):

**ОЖР (19 таблиц):**
`ojr_section1_personnel`, `ojr_section2_equipment`, `ojr_section3_work_log`, `ojr_section4_checks`, `ojr_section5_asbuilt_docs`, `ojr_section6_gosstroynadzor`, `ojr_section7_author_supervision`, `ojr_section8_commissioning`, `ojr_section9_calendar_plan`, `ojr_section10_safety`, `ojr_section11_environment`, `ojr_section12_quality`, `ojr_section13_asbuilt`, `ojr_section14_defects`, `ojr_weather`, `ojr_photo_log`, `ojr_daily_summary`, `ojr_materials`, `ojr_incidents`

**Legacy/служебные (8+ таблиц):**
`bot_memory_messages` (443 записи), `bot_memory_facts` (266), `bot_calendar_events`, `bot_schedule_phases`, `bot_poll_state`, `bot_poll_residuals`, `bot_group_participants`, `bot_building_profiles`

### Статистика (из документации):

| Таблица | Записей |
|---------|---------|
| `bot_memory_messages` | 443 |
| `bot_memory_facts` | 266 |
| `bot_schedule_phases` | 53 (8 фаз + 45 подзадач из ГРАФИК СМР.pdf) |

### Индексы (анализ схемы):

Из db.py:
- `bot_memory_messages` — нет явных индексов кроме PK (id SERIAL)
- `bot_poll_state` — UNIQUE(chat_id, poll_date)
- `bot_poll_residuals` — UNIQUE(poll_id, code)
- `bot_calendar_events` — без индексов на поисковые поля (event_start, status, chat_id)
- `bot_memory_facts` — без индексов (поиск по chat_id, fact_date, category без индексов)
- `bot_schedule_phases` — PK (id), FK на parent_phase_id

### ⚠️ Пробелы в индексах (CRITICAL для производительности):

1. **bot_memory_messages** — нет составного индекса на `(chat_id, COALESCE(message_time, created_at))` — каждый `generate_daily_snapshot()` делает seq scan
2. **bot_memory_messages** — нет индекса на `(message_type, created_at)` — фото-запросы seq scan
3. **bot_calendar_events** — нет индекса на `(chat_id, status, event_start)` — seq scan при каждом lookup
4. **bot_memory_facts** — нет индекса на `(chat_id, fact_date, category)`
5. **ojr_section3_work_log** — нет индекса на `(work_date)` — каждый daily report делает seq scan

---

## 🐛 5. ВСЕ НАЙДЕННЫЕ БАГИ (ранжированные)

### 🔴 CRITICAL (блокирующие / потеря данных):

#### B-C1: ДВЕ НЕЗАВИСИМЫЕ РЕАЛИЗАЦИИ ДИСПЕТЧЕРА
- **Файлы**: `bot/whatsapp_commands.py` (1030 строк) vs `~/.hermes/profiles/alikhan/scripts/alikhan_whatsapp_commands.py` (282 строки)
- **Симптом**: Разные версии кода выполняют одну роль — непредсказуемое поведение после обновлений
- **Причина**: Профильная версия — устаревшая копия без ролевой модели, без обработки фото/OCR
- **Исправление**: Удалить профильную версию. Оставить только `bot/whatsapp_commands.py`

#### B-C2: Нет индекса на bot_memory_messages (chat_id, message_time)  
- **Файл**: `db.py` (нет CREATE INDEX)
- **Симптом**: Каждый `generate_daily_snapshot()` делает полный seq scan на 443+ строках
- **Исправление**: `CREATE INDEX ON bot_memory_messages (chat_id, COALESCE(message_time, created_at) DESC)`

#### B-C3: Нет дедупликации между основным и профильным диспетчером
- **Файлы**: оба `whatsapp_commands.py`
- **Симптом**: Два процесса могут одновременно читать одни и те же сообщения с Bridge
- **Причина**: Разные SEEN_FILE (оба /tmp/alikhan_seen.json)
- **Исправление**: Удалить профильную копию. Использовать единый seen-файл.

### 🟠 HIGH (серьёзные, влияют на бизнес-логику):

#### B-H1: bare `except:` повсеместно — скрытые ошибки
- **Файлы**: 15+ файлов, >30 вхождений
- **Симптом**: Ошибки API, БД, файловой системы проглатываются молча
- **Примеры**: `main_waha.py:229 except:`, `handlers.py:30 except:`, `db.py:15 except:`, `poll.py:68 except: pass`
- **Исправление**: Заменить все `except:` на `except Exception as e:` с логированием

#### B-H2: `_DB_CONN` — глобальное открытое соединение в data_sources.py
- **Файл**: `data_sources.py:103-107`
- **Симптом**: `_DB_CONN` никогда не закрывается. При простое >нескольких часов соединение обрывается сервером, следующий вызов падает
- **Исправление**: Закрывать соединение после использования, либо добавить connection pool с keepalive

#### B-H3: `from bridge_wrapper import *` — неявные зависимости
- **Файлы**: `main_waha.py:1`
- **Симптом**: Непонятно что импортировано. Нарушение контракта CONTRACTS.md (п.2.1 — «Импортировать ТОЛЬКО как from bridge_wrapper import EVO, KEY»)
- **Исправление**: Заменить на явные импорты

#### B-H4: fill_ejo.py ходит в БД напрямую в обход data_sources
- **Файл**: `fill_ejo.py:33` — `from db import get_conn`
- **Симптом**: Нарушение контракта CONTRACTS.md (п.2.9 — «fill_ejo.py использует ТОЛЬКО data_sources, никогда не ходит в db/get_conn напрямую»)
- **Исправление**: Перенести `_refresh_weather_if_stale` в `data_sources.py`

#### B-H5: whatsapp_commands.py ходит в БД через qa.py БЕЗ проверки коннекта
- **Файл**: `whatsapp_commands.py:202` → `from qa import parse_qa`
- **Симптом**: Если БД недоступна, qa.py падает с необработанным исключением, диспетчер не получает сообщение
- **Исправление**: Добавить try/except вокруг вызова parse_qa в whatsapp_commands.py:203-209

### 🟡 MEDIUM (умеренные):

#### B-M1: Дублирование импортов в handlers.py
- **Файл**: `handlers.py:1-13`
- **Симптом**: `import db`, `import json`, `import re`, `import requests` импортированы дважды
- **Исправление**: Убрать дубликаты (строки 1-6 vs 8-13)

#### B-M2: Мёртвый код: `daily_snapshot.py` дублирует `generate_daily_snapshot` из `main_waha.py`
- **Файлы**: `daily_snapshot.py:37-64` vs `main_waha.py:75-310`
- **Симптом**: Две разные реализации погоды (wttr.in в daily_snapshot, Open-Meteo в main_waha)
- **Исправление**: Удалить `daily_snapshot.py`, использовать `main_waha.generate_daily_snapshot`

#### B-M3: `calendar_reminder_loop` и `production_listener_loop` из main_waha.py — dead code
- **Файл**: `main_waha.py:608, 642`
- **Симптом**: main_waha.py как systemd-сервис ОСТАНОВЛЕН. Эти функции никогда не вызываются.
- **Исправление**: Удалить или пометить как deprecated

#### B-M4: Несоответствие CONTRACTS.md и реального кода
- **Файл**: `CONTRACTS.md:94-96`
- **Симптом**: Контракт говорит «НЕ импортировать EVO/KEY из bridge_wrapper в fill_ejo.py» — тест test_contracts.py проверяет обратное
- **Причина**: Контракт устарел после v6 миграции
- **Исправление**: Обновить CONTRACTS.md для отражения текущей архитектуры v6

#### B-M5: `_DB_CONN` в data_sources.py — гонка данных
- **Файл**: `data_sources.py:103-107`
- **Симптом**: Глобальная переменная без блокировки. При одновременных вызовах из нескольких потоков — гонка
- **Исправление**: Добавить `threading.Lock` или использовать connection pool

#### B-M6: Глобальная переменная `_model` в stt.py без thread-safety
- **Файл**: `stt.py:11-18`
- **Симптом**: `_model` лениво инициализируется без блокировки — возможна двойная загрузка WhisperModel
- **Исправление**: Добавить `threading.Lock`

### 🟢 LOW (косметические / маловероятные):

#### B-L1: `lastrowid` в db_memory.py — недокументированное поведение psycopg2
- **Файл**: `db_memory.py:28` — `fid = cur.lastrowid`
- **Симптом**: После INSERT без RETURNING, lastrowid может быть None
- **Исправление**: Использовать `RETURNING id`

#### B-L2: `CHRONOLOGY.md` — бинарный файл?
- **Файл**: `CHRONOLOGY.md` — read_file сообщает «Binary file»
- **Симптом**: Нечитаемый для автоматических тулзов
- **Исправление**: Проверить кодировку

#### B-L3: `memory_tagging.py:46-48` — жёстко закодированные теги (stub)
- **Файл**: `memory_tagging.py:46-48`
- **Симптом**: Все записи получают `building='общая площадка'` независимо от реального содержания
- **Исправление**: Интегрировать Grok-классификацию (как в whatsapp_commands.py)

#### B-L4: `safe_set` в update_template.py не обрабатывает merged cells для всех столбцов
- **Файл**: `update_template.py:11-18`
- **Симптом**: При записи в merged cell может молча записать в неправильную ячейку
- **Исправление**: Проверять merged cells для каждого столбца

#### B-L5: `PROJECT.md` — бинарный файл
- **Файл**: `PROJECT.md` — read_file сообщает «Binary file»
- **Симптом**: Нечитаемый
- **Исправление**: Проверить кодировку

---

## 📜 6. НАРУШЕНИЯ КОНТРАКТОВ (CONTRACTS.md)

### Подтверждённые нарушения:

| # | Контракт | Нарушение | Файл | Строка |
|---|----------|-----------|------|--------|
| C1 | «Импортировать ТОЛЬКО как `from bridge_wrapper import EVO, KEY`» | `from bridge_wrapper import *` | `main_waha.py` | 1 |
| C2 | «fill_ejo.py использует ТОЛЬКО data_sources, никогда не ходит в db/get_conn напрямую» | `from db import get_conn` | `fill_ejo.py` | 33 |
| C3 | «Единственная точка отправки. Никакой модуль не шлёт сообщения через requests.post напрямую» | `daily_snapshot.py` шлёт через urllib напрямую | `daily_snapshot.py` | 158-165 |
| C4 | «ВСЕ коммуникации через send_msg» в poll.py | `daily_snapshot.py` собственная send_to_sandbox | `daily_snapshot.py` | 156-165 |
| C5 | «Не дублировать send_msg — удалены все дубликаты (AUDIT-011)» | `daily_snapshot.py` имеет собственную реализацию отправки | `daily_snapshot.py` | 156-165 |

### Устаревший контракт:

| # | Контракт | Проблема |
|---|----------|----------|
| C6 | CONTRACTS.md:94-96 — про bridge_wrapper в fill_ejo.py | Контракт устарел. Тест test_contracts.py проверяет ОБРАТНОЕ (fill_ejo НЕ должен импортировать bridge_wrapper). Контракт и тесты расходятся. |

---

## 💀 7. МЁРТВЫЙ КОД

| Файл | Строки | Описание | Почему мёртвый |
|------|--------|----------|----------------|
| `main_waha.py` | 608-641 | `calendar_reminder_loop()` | main_waha.py systemd-сервис ОСТАНОВЛЕН |
| `main_waha.py` | 642-1416 | `production_listener_loop()` | main_waha.py systemd-сервис ОСТАНОВЛЕН |
| `daily_snapshot.py` | 37-64 | `get_weather()` — дубликат | Дублирует `data_sources.get_weather()` + `main_waha.generate_daily_snapshot()` |
| `daily_snapshot.py` | 95-154 | `generate_report()` — дубликат | Дублирует `main_waha.generate_daily_snapshot()` |
| `daily_snapshot.py` | 156-165 | `send_to_sandbox()` — дубликат | Дублирует `messaging.send_msg()` |
| `~/.hermes/profiles/alikhan/scripts/alikhan_whatsapp_commands.py` | весь (282 строки) | Устаревшая копия диспетчера | Заменён `bot/whatsapp_commands.py` (1030 строк) |
| `memory_tagging.py` | 46-48 | Stub-классификация | Заглушка, не использует Grok |
| `handlers.py` | 1-6 vs 8-13 | Дубли импортов | `import db`, `import json`, `import re`, `import requests` — дважды |

---

## ⚡ 8. ПРИОРИТЕТЫ ИСПРАВЛЕНИЙ

### 🔴 Фаза 1 — BLOCKING (немедленно):

1. **Удалить `~/.hermes/profiles/alikhan/scripts/alikhan_whatsapp_commands.py`** — два диспетчера = непредсказуемое поведение
2. **Добавить индексы БД** на: bot_memory_messages, bot_memory_facts, bot_calendar_events, ojr_section3_work_log
3. **Заменить все bare `except:` на `except Exception as e:` с логированием**

### 🟠 Фаза 2 — HIGH (эта неделя):

4. **Убрать `from bridge_wrapper import *` из `main_waha.py`** — заменить на явные импорты
5. **Убрать `from db import get_conn` из `fill_ejo.py`** — перенести `_refresh_weather_if_stale` в data_sources
6. **Добавить обработку ошибок в `whatsapp_commands.py:202-209`** — try/except вокруг parse_qa
7. **Закрыть `_DB_CONN`** в data_sources.py — либо закрывать, либо добавить keepalive

### 🟡 Фаза 3 — MEDIUM (следующая неделя):

8. **Удалить `daily_snapshot.py`** полностью — весь функционал дублируется
9. **Убрать дубли импортов** в handlers.py
10. **Обновить CONTRACTS.md** для архитектуры v6 — устаревшие правила
11. **Удалить `calendar_reminder_loop` и `production_listener_loop`** из main_waha.py
12. **Добавить `threading.Lock`** для _DB_CONN и _model

### 🟢 Фаза 4 — LOW (технический долг):

13. **Заменить `stub` в memory_tagging.py** на реальную Grok-классификацию
14. **Проверить кодировку** CHRONOLOGY.md и PROJECT.md
15. **Использовать RETURNING id** вместо lastrowid в db_memory.py
16. **Починить safe_set** в update_template.py для merged cells

---

## 📊 KPI-заключение

| Метрика | Статус | Риски |
|---------|--------|-------|
| ЕЖО — отправка | 🟢 100% дней | B-C2 (нет индексов) замедляет генерацию |
| QA-сбор | 🟢 ≥90% | B-H1 (bare except) может скрывать потери фактов |
| Bridge uptime | 🟢 ≥99% | watchdog_bridge.py мониторит |
| Потеря сообщений | 🔴 Риск | B-C1 (два диспетчера) — риск двойной обработки |
| Баги/неделя | 🟡 Растёт | 18 багов найдено этим аудитом |

**Итоговая оценка кодовой базы**: 6.5/10. Архитектура v6 стабильна, но накопился значительный технический долг: дублирование кода, устаревшие контракты, отсутствие индексов БД, повсеместные bare except. Требуется ~2 недели плановой работы для приведения в порядок.
