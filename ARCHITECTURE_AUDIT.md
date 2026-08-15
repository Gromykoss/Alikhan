# АРХИТЕКТУРНЫЙ АУДИТ ПРОЕКТА ALIKHAN — v6 (Hermes Bridge)

**Дата аудита:** 12.08.2026  
**Версия архитектуры:** v6 (прямой Hermes Bridge, миграция 29.07.2026)  
**Объём:** 47 Python-файлов, ~8470 строк кода, 610 коммитов в CHRONOLOGY.md  
**Метод:** полный разбор всех исходных файлов

---

## 1. АРХИТЕКТУРНАЯ СХЕМА И ПОТОКИ ДАННЫХ

### 1.1. Уровневая архитектура (сверху вниз)

```
┌─────────────────────────────────────────────────────────────┐
│  WhatsApp Client (прорабы)                                   │
│  Группы: SANDBOX (песочница) + PRODUCTION (боевая)           │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS (Baileys webhook)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Hermes Bridge :3000 (bridge.js, Baileys, mode=bot)          │
│  systemd user: hermes-whatsapp-bridge                        │
│  Эндпоинты: /health, /messages, /send, /send-media,         │
│             /collect-messages, /collect-ack                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Hermes Gateway (hermes-gateway)                             │
│  Мультиплексор: WhatsApp + Telegram + Discord + Buzz         │
│  Адаптер: пробрасывает сообщения в диспетчер                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│  Диспетчер (v2)  │    │  Hermes Agent         │
│  whatsapp_       │    │  (Alikhan — прямой    │
│  commands.py     │    │   Bridge :3000)        │
│  (bot/ + profile)│    │  main_waha.py (1416    │
│  Ролевая модель: │    │  строк, ОСТАНОВЛЕН)   │
│  admin>op>viewer │    └──────────┬───────────┘
└────────┬─────────┘               │
         │              ┌──────────┼───────────┐
         │              ▼          ▼           ▼
         │      ┌──────────┐ ┌──────────┐ ┌──────────┐
         │      │ router.py│ │ handlers │ │  poll.py │
         │      └──────────┘ │  .py     │ └──────────┘
         │                   └──────────┘
         │                   ┌──────────┐ ┌───────────┐
         │                   │   qa.py  │ │  fill_ejo │
         │                   │  (536)   │ │  .py(848) │
         │                   └──────────┘ └───────────┘
         │                        │              │
         │                   ┌──────────┐ ┌──────────────┐
         │                   │  db.py   │ │data_sources  │
         │                   │  (1136)  │ │   .py (922)  │
         │                   └──────────┘ └──────────────┘
         │                        │              │
         │                   ┌───────────────────────────┐
         │                   │  PostgreSQL (Docker)       │
         │                   │  evolution-postgres:5432   │
         │                   │  БД: evolution_db           │
         │                   └───────────────────────────┘
         │
         ▼
┌──────────────────┐
│  document_extractor :8099
│  (Tesseract OCR rus+eng)
│  alikhan-document-extractor.service
└──────────────────┘
```

### 1.2. Ключевой путь данных

```
Прораб (WhatsApp) 
  → Bridge /collect-messages?only=PRODUCTION
  → whatsapp_commands.py (диспетчер v2)
    → QA: parse_qa() → Grok → validate → db.py → OJR таблицы
    → ЕЖО: fill_ejo.py → data_sources → 12 NamedTuples → Excel → send-media
    → Poll: poll.py → bot_poll_state / residuals → close → fill_ejo
    → Calendar: db.py → bot_calendar_events → reminder thread

Прораб (WhatsApp SANDBOX) 
  → Bridge /messages (основная очередь) → Hermes Agent (main_waha.py)
    → main loop: poll → route → reply
    → Команды: ЕЖО, опрос, календарь, снимок дня, раскрыть отчет
    → Фото: Grok vision → ojr_photo_log + bot_memory_messages
    → Документы: document_extractor :8099
```

### 1.3. Компоненты инфраструктуры

| Сервис | Роль | Статус |
|--------|------|--------|
| `hermes-whatsapp-bridge` | WhatsApp Bridge (Baileys, :3000, bot) | ✅ Active |
| `hermes-gateway` | Мультиплексор платформ | ✅ Active |
| `alikhan-document-extractor` | OCR документов (:8099) | ✅ Active |
| `evolution-postgres` | PostgreSQL Docker | ✅ Active |
| `alikhan.service` | Старый бот (Evolution API) | ❌ ОСТАНОВЛЕН |
| `main_waha.py` | Точка входа старого бота | ❌ НЕ ИСПОЛЬЗУЕТСЯ |
| `bridge_wrapper.py` | Monkey-patch слой | ❌ НЕ ИСПОЛЬЗУЕТСЯ (v6) |

---

## 2. РЕЕСТР ОБРАБОТЧИКОВ

### 2.1. main_waha.py (1416 строк) — главный цикл (ОСТАНОВЛЕН в v6)

**Статус:** код на диске, процесс не запущен. Продолжает существовать как исторический артефакт.

**Обработчики в основном цикле (строки 873-1416):**

| Строки | Обработчик | Описание |
|--------|-----------|----------|
| 608-629 | `calendar_reminder_loop` | Фоновый поток: проверка напоминаний каждые 60с |
| 642-868 | `production_listener_loop` | Фоновый поток: опрос боевой группы, сохранение медиа |
| 873-1416 | Главный цикл | Poll → dedup → save → route → reply |
| 905-912 | Сохранение текста | `save_message()` до обработки (AL-005) |
| 916-1038 | Фото-обработчик | Сохранение в DB + OJR + Grok Vision + фильтр стройплощадки |
| 1040-1095 | Документы | Сохранение + обновление шаблона ЕЖО + извлечение объёмов |
| 1097-1141 | Голосовые (STT) | Транскрибация аудио через stt.py |
| 1146-1170 | «Раскрыть отчёт» | Развернуть скрытые строки для месячного плана |
| 1171-1201 | «Напомни» | Создание календарного события |
| 1203-1219 | «Календарь/события» | Список событий |
| 1221-1245 | «Закрыть опрос» | Завершение опроса + ЕЖО |
| 1247-1257 | «Начать опрос» | Запуск опроса |
| 1259-1268 | «Статус опроса» | Сводка статуса |
| 1270-1272 | VOR-reply | Авто-детект ответов с кодами работ |
| 1274-1302 | ЕЖО принудительно | Генерация ЕЖО без проверок |
| 1304-1351 | ЕЖО | Генерация ЕЖО с проверкой готовности |
| 1353-1362 | «Снимок дня» | Композитный отчёт через generate_daily_snapshot() |
| 1364-1411 | `route()` | Финальная маршрутизация → AVR или Grok |

**Критическое наблюдение:** main_waha.py — **мёртвый код** в v6. Диспетчер (whatsapp_commands.py) выполняет ту же работу, но с другой архитектурой.

### 2.2. whatsapp_commands.py (1030 строк в bot/ + 282 в scripts/) — активный диспетчер

**24 функции-обработчика + 19 в HANDLERS словаре.** Это **действующий** обработчик после миграции v6.

**Основные обработчики (bot/whatsapp_commands.py):**

| Строки | Обработчик | Роль |
|--------|-----------|------|
| 80-95 | `_load_roles()` | Загрузка ролевой модели (admin/operator/viewer) |
| 97-130 | `get_role()/check_role()` | RBAC гварды на все мутирующие операции |
| 175-215 | `extract_text()` | Извлечение текста из 7 форматов сообщений Bridge |
| 335-405 | ЕЖО команды | fill_ejo + force + отправка |
| 410-445 | «Раскрыть отчёт» | Развернуть строки для месячного плана |
| 455-490 | Опрос: запуск | start_poll + build_poll_message |
| 495-530 | Опрос: статус | build_poll_summary |
| 535-575 | Опрос: закрытие | close_poll → fill_ejo → send_file |
| 585-620 | «Снимок дня» | generate_daily_snapshot |
| 625-660 | Календарь: создать | insert_calendar_event через Grok |
| 665-700 | Календарь: список | get_calendar_events |
| 705-730 | Календарь: напомни | create_calendar_event по шаблону |
| 735-765 | Календарь: удалить | delete_calendar_event |
| 775-800 | Погода | wttr.in API |
| 810-845 | AVR: генерация | generate_ks2 + generate_ks6 |
| 855-910 | QA: ручной парсинг | parse_qa() для боевой группы |
| 920-960 | Фото: обработка | Сохранение + Grok vision + OJR |
| 970-1005 | OCR: документы | document_extractor :8099 |
| 1015-1030 | main() | Главный цикл: collect-messages → обработка |

**Ролевая модель (строки 28-98):**
```python
ROLE_HIERARCHY = {"admin": 3, "operator": 2, "viewer": 1}
# admin: все команды
# operator: все кроме управления ролями
# viewer: только чтение (фото, QA, документы)
```

### 2.3. handlers.py (676 строк) — LLM-обработчики

| Строки | Обработчик | Описание |
|--------|-----------|----------|
| 93-113 | `ask_ollama()` | Локальная модель qwen2.5:14b, fallback → Grok |
| 116-142 | `ask_grok_raw()` | xAI Grok API (grok-4-latest) |
| 145-150 | `ask_grok()` | Диспетчер: vision → Grok, text → Ollama |
| 226-230 | `handle_only_name()` | «Я на связи» |
| 233-261 | `handle_memory_status()` | Статистика памяти |
| 264-277 | `handle_calendar_delete()` | Удаление события |
| 280-318 | `handle_document_compare()` | Сравнение документов через Grok |
| 328-368 | `handle_fact_lookup()` | Поиск фактов + Grok-суммаризация |
| 395-437 | `handle_calendar_create()` | Создание события через Grok |
| 440-459 | `handle_calendar_list()` | Список событий |
| 488-510 | `handle_period_summary()` | Сводка периода |
| 575-588 | `handle_who_are_you()` | Самоидентификация |
| 582-588 | `handle_ai()` | Свободный Grok-диалог |
| 590-596 | `handle_daily_snapshot()` | Делегирование в main_waha |
| 598-612 | `handle_weather()` | Погода через wttr.in |
| 615-632 | `handle_photo()` | Анализ фото через Grok |
| 635-653 | `handle_document()` | Анализ документа через Grok |

### 2.4. qa.py (610 строк) — QA-парсер

| Строки | Функция | Описание |
|--------|---------|----------|
| 45-48 | `_audit_log()` | Аудит-лог в /tmp/alikhan_qa_audit.log |
| 51-63 | `is_qa()` | Детектор QA-текстов (триггеры + VOR-паттерны) |
| 68-80 | `validate_building()` | Валидация здания (АБК/Общежитие/общая) |
| 83-105 | `validate_category()` | Валидация категории (fuzzy match) |
| 108-110 | `validate_personnel_fact()` | Валидация персонала |
| 115-126 | `_parse_no_patterns()` | «нет»-паттерны |
| 129-167 | `_parse_personnel_fallback()` | Regex-парсинг персонала |
| 172-237 | `_extract_vor_codes()` | Извлечение VOR-кодов (regex, без LLM) |
| 242-267 | `_build_qa_prompt()` | Grok-промпт с few-shot примерами |
| 272-287 | `_smart_chunk()` | Разбиение на чанки по границам предложений |
| 292-610 | `parse_qa()` | **Главный pipeline:** regex VOR → Grok JSON → validate → save |

### 2.5. poll.py (619 строк) — Управление опросом

| Строки | Функция | Описание |
|--------|---------|----------|
| 27-61 | `ensure_poll_table()` | Создание таблиц bot_poll_state/residuals |
| 71-120 | `_get_work_items_from_template()` | Чтение остатков из ЕЖО-шаблона |
| 122-165 | `_get_qa_status()` | Статус QA-данных из OJR |
| 169-212 | `start_poll()` | Запуск опроса |
| 214-271 | `build_poll_message()` | Формирование сообщения |
| 301-423 | `parse_poll_reply()` | Парсинг ответа прораба |
| 425-461 | `get_poll_status()` | Статус опроса |
| 463-544 | `build_poll_summary()` | Сводка |
| 547-619 | `close_poll()` | Закрытие + auto-fill + fill_ejo |

### 2.6. data_sources.py (922 строки) — Единый модуль источников данных

**12 NamedTuple-контрактов + 12 функций.** Все fault-tolerant (при ошибке возвращают fallback).

### 2.7. fill_ejo.py (848 строк) — Генератор ЕЖО

Заполняет 4 листа Excel из data_sources. Делает `shutil.copy2` в TEMPLATE_PATH.

### 2.8. db.py (1136 строк) — Единственная точка БД

| Строки | Функция | Описание |
|--------|---------|----------|
| 27-45 | `resolve_db_host()` | Docker IP → env → fallback 172.22.0.4 |
| 61-70 | `get_conn()` | Подключение + SET TIME ZONE 'Asia/Bishkek' |
| 72-88 | `save_message()` | Дедупликация за 5 секунд |
| 236-331 | `insert_calendar_event()` | Календарь с CTE |
| 839-860 | `save_personnel()` | Персонал с закрытием предыдущих строк |
| 895-916 | `save_work_log()` | Запись в ojr_section3_work_log |

### 2.9. router.py (125 строк) — Маршрутизатор

Порядок проверок: AVR → QA → residual → name check → commands → schedule → weather/DB → Grok → verify

### 2.10. bridge_wrapper.py (275 строк) — Monkey-patch слой (ОСТАНОВЛЕН в v6)

Перехватывает `requests.post` и `urllib.request.urlopen` для трансляции Evolution API → Hermes Bridge. Буфер на 200 сообщений.

---

## 3. ИНВЕНТАРИЗАЦИЯ ПРОМПТОВ

### 3.1. QA-промпт (qa.py:242-267)
```
Извлеки ВСЕ факты из ответа прораба. Если сомневаешься — извлекай...
Возвращай ТОЛЬКО JSON-массив...
```
Содержит 3 few-shot примера (персонал + бетонирование/монтаж + документация/материалы).

### 3.2. Grok Vision — фото стройплощадки (main_waha.py:722, 953)
```
Это фото сделано на строительной площадке? ...
Ответь только 'да' или 'нет'.
```

### 3.3. Grok Vision — описание фото (main_waha.py:764-766, 992-994)
```
Опиши что видно на фото строительной площадки: состояние конструкций, 
наличие техники, материалов, людей. Не предполагай что работы ведутся — 
опиши только наблюдаемое состояние. 1-2 предложения на русском.
```

### 3.4. Grok System Prompt (handlers.py:132-133)
```
Ты Алихан — AI-ассистент в WhatsApp. Отвечай кратко, дружелюбно, на русском. 
Помогаешь с задачами, календарём, документами и памятью проекта.
```

### 3.5. Router Grok Fallback (router.py:105-111)
```
Ты — строительный инспектор на площадке ТЗРК Джеруй (Кыргызстан, горы, ~2700м). 
Строятся: АБК (2 этажа), Общежитие (3 этажа), Галерея...
```

### 3.6. Router Grok Summarizer (router.py:95-100)
```
Ты — строительный инспектор на площадке ТЗРК Джеруй (один объект). 
Строятся: АБК, Общежитие, Галерея. ПРОСУММИРУЙ все числа из фактов ниже...
```

### 3.7. Daily Snapshot Template (bot/prompts/daily_snapshot_prompt.md)
Структурированный промпт из 9 жёстких правил + пример. Загружается из файла, заполняет {weather}, {photo_block}, {doc_block}, {msg_block}, {poll_block}, {fact_block}.

### 3.8. Daily Snapshot Fallback (main_waha.py:273-302)
Встроенный fallback-промпт при отсутствии файла шаблона.

### 3.9. Calendar Create Prompt (handlers.py:397-405)
```
Извлеки событие календаря из текста пользователя. 
Верни только JSON без markdown...
```

### 3.10. Fact Lookup Prompt (handlers.py:358-367)
```
Ответь на вопрос пользователя строго по найденным документам и памяти проекта...
```

### 3.11. Document Compare Prompt (handlers.py:299-313)
```
Сравни строго старый документ с новым. Не фантазируй...
```

### 3.12. Quoted Document Vision (handlers.py:538-543)
```
Ты — прораб на площадке ТЗРК Джеруй (Кыргызстан, 2700м). 
Опиши фото: этап работ, техника, люди, материалы. 
Нарушения ТБ/ООС/пожарки если есть...
```

### 3.13. Knowledge Graph DeepSeek Prompt (query_tool.py)
```
Answer using only the knowledge graph below. Cite the specific edges that support your answer...
```

### Всего: 14 промптов. 7 используют Grok (xAI), 2 используют DeepSeek, 5 встроенные.

---

## 4. СХЕМА БД И ИСПОЛЬЗОВАНИЕ ТАБЛИЦ

### 4.1. Таблицы ОЖР (ГОСТ РД-11-05-2007) — 19 таблиц

| Таблица | Использование | Активно? |
|---------|--------------|----------|
| `ojr_title_page` | Титульный лист ОЖР | ✅ |
| `ojr_section1_personnel` | Персонал (ИТР/рабочие) | ✅ Активно |
| `ojr_section2_equipment` | Техника (учёт) | ⚠️ Слабо |
| `ojr_section3_work_log` | Журнал работ (основная) | ✅ Активно |
| `ojr_section4_checks` | Проверки | ⚠️ Слабо |
| `ojr_section5_asbuilt_docs` | Исполнительная документация | ⚠️ Слабо |
| `ojr_section6_gosstroynadzor` | Госстройнадзор | ⚠️ Слабо |
| `ojr_section7_author_supervision` | Авторский надзор | ⚠️ Слабо |
| `ojr_section8_commissioning` | Пусконаладка | ⚠️ Слабо |
| `ojr_section9_calendar_plan` | Календарный план | ⚠️ Слабо |
| `ojr_section10_safety` | Охрана труда | ⚠️ Слабо |
| `ojr_section11_environment` | Экология | ⚠️ Слабо |
| `ojr_section12_quality` | Контроль качества | ⚠️ Слабо |
| `ojr_section13_asbuilt` | Исполнительные схемы | ⚠️ Слабо |
| `ojr_section14_defects` | Дефекты | ⚠️ Слабо |
| `ojr_weather` | Погода | ✅ Активно |
| `ojr_photo_log` | Фото-фиксация | ✅ Активно |
| `ojr_daily_summary` | Ежедневная сводка | ✅ |
| `ojr_materials` | Материалы | ✅ |
| `ojr_incidents` | Инциденты | ✅ |

### 4.2. Legacy-таблицы

| Таблица | Записей | Использование |
|---------|---------|--------------|
| `bot_memory_messages` | ~443 | ✅ Активно (текст, фото, документы) |
| `bot_memory_facts` | ~266 | ✅ Активно (QA-факты) |
| `bot_schedule_phases` | 53 | ✅ Активно (график СМР) |
| `bot_poll_state` | — | ✅ Активно (опрос) |
| `bot_poll_residuals` | — | ✅ Активно (остатки опроса) |
| `bot_calendar_events` | — | ✅ Активно (календарь) |
| `bot_building_profiles` | — | ⚠️ Слабо |
| `bot_group_participants` | — | ⚠️ Слабо |

### 4.3. Ключевые запросы (наиболее частые)

1. `SELECT ... FROM ojr_section3_work_log WHERE work_date = $1::date` — ядро ЕЖО
2. `SELECT ... FROM ojr_section1_personnel WHERE start_date <= $1::date AND (end_date >= $1::date OR end_date IS NULL)` — персонал
3. `INSERT ... ON CONFLICT (work_date, vor_code, building, category) DO UPDATE` — журнал работ
4. `INSERT ... ON CONFLICT (title_id, organization_name, full_name, position, start_date) DO NOTHING` — персонал
5. `SELECT ... FROM bot_memory_messages WHERE chat_id=$1 AND created_at >=$2` — сообщения

---

## 5. БАГИ, RACE CONDITIONS, SILENT FAILURES, ОТСУТСТВУЮЩИЕ ИНДЕКСЫ, АРХИТЕКТУРНЫЕ ДЕФЕКТЫ

### 🔴 КРИТИЧЕСКИЕ (P0 — остановка сервиса / потеря данных)

#### B1. Диспетчер читает только боевую группу — песочница игнорируется
**Файл:** `scripts/alikhan_whatsapp_commands.py:51`  
**Проблема:** `/collect-messages?only=120363400682390076@g.us` — жёстко задан фильтр на боевую группу. Песочница (`120363179621030401@g.us`) не читается через `/collect-messages`.  
**Следствие:** Команды из песочницы (ЕЖО, опрос) не обрабатываются если main_waha.py остановлен (v6).  
**CONTRACTS.md:** не документирует это раздвоение очередей.

#### B2. 60 потерянных сообщений (Pitfall 27) — drain в неправильную очередь
**Файл:** `bridge_wrapper.py:46-58` (`_drain_buffer`)  
**Проблема:** Буфер drain по `remoteJid` использует `==`, но сообщения из боевой группы и песочницы могут оказаться в одной очереди `/messages`. В v6 main_waha.py остановлен → никто не дренирует песочницу.  
**Следствие:** Сообщения накапливаются (queueLength=44 на 11.08.2026).

#### B3. main_waha.py остановлен — двойная система обработчиков
**Файл:** `bot/main_waha.py` (весь) vs `bot/whatsapp_commands.py` (весь)  
**Проблема:** Существует ДВА обработчика сообщений с разной логикой:
- `main_waha.py`: основной цикл + production listener thread  
- `whatsapp_commands.py`: диспетчер v2 с ролевой моделью  
**CONTRACTS.md утверждает:** main_waha.py — точка входа (уровень 5).  
**AGENTS.md утверждает:** main_waha.py ОСТАНОВЛЕН.  
**Следствие:** Неопределённость. 1416 строк дублирующего кода.

#### B4. bridge_wrapper.py загружает `db.py` через monkey-patch urllib
**Файл:** `bridge_wrapper.py:226-269`  
**Проблема:** `_patched_urlopen` импортирует `db.get_conn` и `psycopg2.extras` внутри monkey-patch'а. При импорте `bridge_wrapper.py` до `db.py` → `ImportError`.  
**CONTRACTS.md правило:** `from bridge_wrapper import *` должен быть ПЕРВЫМ import.  
**Следствие:** Порядок импортов критичен. Нарушение → крах при старте.

#### B5. ON CONFLICT без явных колонок в bot_memory_facts (qa.py:534)
**Файл:** `bot/qa.py:534`  
**Проблема:** `ON CONFLICT (chat_id, fact_date, building, category, fact) DO NOTHING` — использует 5 колонок. Но если в таблице есть составной уникальный индекс с другими колонками — конфликт не сработает.  
**Тесты:** `test_contracts.py:291-330` проверяет это правило, но только для `db.py`, не для `qa.py`.

### 🟠 ВЫСОКИЕ (P1 — нарушение функциональности)

#### B6. Race condition: multi-insert в save_personnel
**Файл:** `bot/db.py:839-860`  
**Проблема:** При параллельных вызовах `save_personnel()` две вставки могут создать дублирующие открытые строки для одного slot_name. Закрытие предыдущих строк (end_date=today-1) выполняется перед INSERT, но без SELECT FOR UPDATE.  
**CHRONOLOGY.md:** упоминается Pitfall 27 — 60 lost messages от drain в неправильную очередь.

#### B7. Bare `except:` в db.py:15
**Файл:** `bot/db.py:15`  
**Проблема:** `except:` (голый) при загрузке секретов — подавляет ВСЕ ошибки включая SyntaxError, KeyboardInterrupt.

#### B8. 167 `except Exception` + 25 `except:` по кодовой базе
**Файлы:** все `bot/*.py`  
**Проблема:** Большинство except блоков молча подавляют ошибки:
- `except: pass` (db.py:15, main_waha.py:589, bridge_wrapper.py:43)
- `except Exception as e: print(...)` — ошибка логируется, но исполнение продолжается
- Отсутствует structured error handling / circuit breaker  
**Следствие:** Частичные отказы маскируются. Невозможно отличить «данных нет» от «БД упала».

#### B9. fill_ejo.py subprocess вместо прямого вызова
**Файл:** `bot/main_waha.py:1293, 1342`, `bot/poll.py:612`  
**Проблема:** `subprocess.run([sys.executable, "fill_ejo.py", today])` — запускает fill_ejo.py как отдельный процесс. Ошибки в fill_ejo не возвращаются вызывающему. Нет проверки exit code.  
**Следствие:** main_waha сообщает «ЕЖО отправлен» даже при ошибке fill_ejo.

#### B10. seen_ids.json не ограничен — unbounded growth
**Файл:** `bot/main_waha.py:581-601`  
**Проблема:** `seen` set и `prod_seen` set сохраняются в JSON каждый раз при новом сообщении (на каждое сообщение `json.dump(list(seen), f)`). За месяцы эксплуатации файл вырастает до десятков тысяч записей, каждый цикл — полная перезапись.  
**Следствие:** Деградация производительности со временем. IO на каждый message ID.

#### B11. bridge_wrapper буфер — race condition между потоками
**Файл:** `bridge_wrapper.py:31-58`  
**Проблема:** `_BUFFER` — глобальный список. `_fetch_and_buffer()` вызывается из production_listener_loop (фоновый поток) и из главного цикла sandbox. Без блокировок.  
**Следствие:** При одновременном вызове — потеря сообщений из буфера.

### 🟡 СРЕДНИЕ (P2 — некорректное поведение)

#### B12. Дублирование логики фото-обработки
**Файлы:** `main_waha.py:916-1038` (sandbox) vs `main_waha.py:686-805` (production)  
**Проблема:** Логика обработки фото (Grok Vision filter + description + OJR) дублируется в двух местах с небольшими отличиями. ~240 строк дубликата.  
**CONTRACTS.md:** не документирует это дублирование.

#### B13. Поле caption читается из неверного пути в production_listener
**Файл:** `main_waha.py:682`  
**Проблема:** `caption = (msg.get("_media") or {}).get("fileName", "")` — берёт fileName вместо caption для поиска building-тега. caption может быть в `msg.get("_media", {}).get("caption")`.

#### B14. ЕЖО: «опрос не проводился» как fallback без проверки
**Файл:** `main_waha.py:269`  
**Проблема:** `{poll_block}` заменяется на `poll_info if poll_info else "опрос не проводился"`, но в daily_snapshot_prompt.md нет fallback логики — если poll_block пуст, шаблон ломается.

#### B15. date_str в whatsapp_commands.py не использует SIM_DATE
**Файл:** `scripts/alikhan_whatsapp_commands.py:104` (profile)  
**Проблема:** `today = time.strftime("%Y-%m-%d")` — всегда реальная дата. Нет поддержки симуляции (`SIM_DATE` из config.py).  
**Следствие:** Тестирование диспетчера с симулированной датой невозможно.

#### B16. parse_poll_reply не передаёт building в save_work_log
**Файл:** `poll.py:393-401`  
**Проблема:** `save_work_log(chat_id, today, code, building, vol, ...)` — building извлекается из `_get_work_items_from_template()`, но если код не в шаблоне, используется `'общая'`.

### 🟢 НИЗКИЕ (P3 — косметические)

#### B17. Мёртвый код: `_handle_vor_reply()` вызывается дважды
**Файл:** `main_waha.py:1270-1272, 1404-1406`  
**Проблема:** VOR-ответ обрабатывается и в строке 1271, и снова в строке 1405 (если route вернул RESIDUAL). Двойной вызов.

#### B18. Хардкод `/tmp/ЕЖО_*_АйБиКон.xlsx` в 5+ файлах
**Файлы:** `fill_ejo.py`, `main_waha.py`, `poll.py`, `whatsapp_commands.py`, `data_sources.py`  
**Проблема:** Путь к выходным ЕЖО-файлам хардкожен в каждом модуле. Изменение требует правки 5+ файлов.

#### B19. `calendar_reminder_loop` работает даже в остановленном main_waha.py
**Файл:** `main_waha.py:608-630`  
**Проблема:** Если main_waha.py остановлен — поток календаря не работает. В whatsapp_commands.py нет аналога.

#### B20. `_resolve_media_local_path` — дубликат логики
**Файл:** `main_waha.py:12-37`  
**Проблема:** Эта функция дублирует логику bridge_wrapper.py:210-221 (поиск mediaUrls).

---

## 6. НАРУШЕНИЯ КОНТРАКТОВ МЕЖДУ МОДУЛЯМИ

### 6.1. CONTRACTS.md: main_waha.py — точка входа (уровень 5) — НАРУШЕН
**CONTRACTS.md:360-380:** «Точка входа: главный цикл (poll → route → reply). systemd alikhan.service.»  
**Факт:** main_waha.py остановлен с 29.07.2026. Точка входа — `whatsapp_commands.py` (не описан в CONTRACTS.md).  
**Степень:** КРИТИЧЕСКАЯ — документация не соответствует реальности.

### 6.2. CONTRACTS.md: bridge_wrapper.py должен импортироваться первым — НАРУШЕН (частично)
**CONTRACTS.md:94:** «Импортировать ТОЛЬКО как `from bridge_wrapper import EVO, KEY`»  
**Факт:** `data_sources.py` импортирует `from config import SANDBOX` и `from db import get_conn` — не `bridge_wrapper`. B10 уже был зафиксирован ранее.  
**Степень:** СРЕДНЯЯ — data_sources.py НЕ зависит от bridge_wrapper (это корректно), но history повторяется.

### 6.3. CONTRACTS.md: messaging.py — единственная точка отправки — СОБЛЮДЁН
✅ Все сообщения идут через `send_msg()`, `send_voice()`, `send_document()`.

### 6.4. CONTRACTS.md: db.py — единственная точка подключения — СОБЛЮДЁН
✅ Все модули используют `get_conn()`. Ни одного прямого `psycopg2.connect()`.

### 6.5. CONTRACTS.md: fill_ejo.py использует только data_sources — СОБЛЮДЁН
✅ fill_ejo.py не ходит в БД напрямую. Все данные через 12 NamedTuple.

### 6.6. CONTRACTS.md: router.py сигнатура route() — НАРУШЕН (избыточный вызов)
**CONTRACTS.md:208:** «Сигнатура `route(text, chat_id, sender) -> (action, reply, voice)`»  
**Факт:** В main_waha.py:1364 `action, reply, voice = route(text, SANDBOX, sender)`, но перед этим в строке 905 текст УЖЕ сохранён через `save_message()`. В строке 1368-1369 — повторное сохранение.  
**Степень:** НИЗКАЯ — дублирование, не потеря данных.

### 6.7. Неописанный контракт: whatsapp_commands.py
**Файл:** `bot/whatsapp_commands.py` (1030 строк) + `scripts/alikhan_whatsapp_commands.py` (282 строки)  
**Проблема:** Оба файла НЕ описаны в CONTRACTS.md. Это ДЕЙСТВУЮЩИЙ обработчик в v6.  
**Степень:** КРИТИЧЕСКАЯ — документация неполна.

---

## 7. МЁРТВЫЙ КОД

### 7.1. main_waha.py (1416 строк) — ПОЛНОСТЬЮ МЁРТВЫЙ
Статус: ОСТАНОВЛЕН с 29.07.2026. alikhan.service остановлен. Код на диске, не исполняется.

### 7.2. bridge_wrapper.py (275 строк) — ПОЛНОСТЬЮ МЁРТВЫЙ В v6
Monkey-patch для Evolution API. После миграции на прямой Hermes Bridge — не нужен.

### 7.3. messaging.py — ЧАСТИЧНО МЁРТВЫЙ
`send_msg()` и `send_voice()` используются, но сам модуль создавался для bridge_wrapper-эпохи.

### 7.4. router.py (125 строк) — ЧАСТИЧНО МЁРТВЫЙ
Используется только main_waha.py. whatsapp_commands.py имеет собственную маршрутизацию.

### 7.5. db_lookup.py — МЁРТВЫЙ
Импортируется только из router.py → main_waha.py.

### 7.6. daily_snapshot.py — МЁРТВЫЙ
Удалён по AUDIT-007. Но `generate_daily_snapshot()` осталась в main_waha.py.

### 7.7. alerter.py, metrics.py, backup_db.py, graceful.py — МЁРТВЫЕ
Не импортируются ни из одного активного модуля.

### 7.8. stt.py — ЧАСТИЧНО МЁРТВЫЙ
Импортируется только в main_waha.py (строка 577).

### 7.9. building_profiles.py — СЛАБО ИСПОЛЬЗУЕТСЯ
Один вызов в `main_waha.py`.

### 7.10. verify.py — ЧАСТИЧНО МЁРТВЫЙ
Импортируется только в router.py.

### Итого мёртвого кода: ~2500 строк из ~8470 (~30%)

---

## 8. РЕКОМЕНДАЦИИ (РАНЖИРОВАНЫ ПО КРИТИЧНОСТИ)

### 🔴 P0 — Немедленно (блокирует работу)

1. **Унифицировать диспетчеры.** Выбрать ОДИН обработчик: либо `main_waha.py` (перезапустить), либо `whatsapp_commands.py` (доработать). Удалить неиспользуемый. Сейчас две параллельные системы с разной логикой.

2. **Восстановить обработку песочницы.** `/collect-messages?only=PRODUCTION` не читает SANDBOX. Добавить второй вызов или использовать `/messages` для песочницы.

3. **Разобрать очередь из 44+ сообщений.** `queueLength=44` на 11.08.2026 — сообщения накапливаются без обработки.

4. **Синхронизировать CONTRACTS.md с реальностью.** Описать `whatsapp_commands.py` как точку входа v6. Пометить main_waha.py, bridge_wrapper.py, router.py как ОСТАНОВЛЕННЫЕ.

### 🟠 P1 — Критично (приведёт к ошибкам)

5. **Добавить блокировку в bridge_wrapper буфер.** `_BUFFER` — глобальный список без threading.Lock. При одновременном вызове из двух потоков — потеря сообщений.

6. **Добавить проверку exit code для subprocess.run.** `fill_ejo.py` вызывается как subprocess, ошибки игнорируются. Заменить на прямой импорт или проверять returncode.

7. **Устранить bare `except:` в db.py:15.** Заменить на `except (FileNotFoundError, IOError) as e:`.

8. **Добавить structured error handling.** Вместо 167 `except Exception` — внедрить circuit breaker + retry с exponential backoff для критических путей (БД, Bridge API, Grok API).

9. **Ограничить рост seen_ids.json.** Внедрить кольцевой буфер (последние 10000 ID) вместо неограниченного множества.

### 🟡 P2 — Важно (качество/техдолг)

10. **Устранить дублирование фото-обработки.** Вынести логику Grok Vision filter + description + OJR в отдельную функцию вместо копипасты sandbox/production.

11. **Добавить поддержку SIM_DATE в whatsapp_commands.py.** Сделать диспетчер тестируемым с симулированной датой.

12. **Вынести путь `/tmp/ЕЖО_*_АйБиКон.xlsx` в config.py.** Одна константа вместо хардкода в 5+ файлах.

13. **Удалить мёртвый код.** ~2500 строк мёртвого кода увеличивают поверхность для багов и путают агентов. Удалить: main_waha.py, bridge_wrapper.py, alerter.py, backup_db.py, graceful.py, daily_snapshot.py (если не используется).

14. **Добавить calendar_reminder_loop в whatsapp_commands.py.** Иначе календарные напоминания не работают при остановленном main_waha.py.

### 🟢 P3 — Желательно (улучшения)

15. **Стандартизировать формат seen-файлов.** `seen_ids.json` и `prod_seen_ids.json` — разные форматы в разных файлах. Унифицировать.

16. **Добавить индексы на часто используемые колонки.** `ojr_section3_work_log(work_date)`, `bot_memory_messages(chat_id, created_at)`, `bot_memory_facts(fact_date, source)` — проверить существование.

17. **Обновить AGENTS.md — убрать упоминания main_waha.py и bridge_wrapper.py.** AGENTS.md:88 говорит «нет main_waha.py, bridge_wrapper.py», но оба файла продолжают существовать на диске.

18. **Задокументировать Pitfall 27 как архитектурное решение.** Потеря 60 сообщений из-за drain в неправильную очередь — записать в CONTRACTS.md как known issue.

---

## 9. СВОДНАЯ ТАБЛИЦА НАХОДОК

| # | Тема | Серьёзность | Файл:строка | Статус |
|---|------|------------|-------------|--------|
| B1 | Песочница не читается | 🔴 P0 | whatsapp_commands.py:51 | ❌ |
| B2 | 60 потерянных сообщений | 🔴 P0 | bridge_wrapper.py:46-58 | ❌ |
| B3 | Двойная система обработчиков | 🔴 P0 | main_waha.py vs whatsapp_commands.py | ❌ |
| B4 | Порядок импортов критичен | 🔴 P0 | bridge_wrapper.py:226 | ⚠️ |
| B5 | ON CONFLICT без колонок | 🔴 P0 | qa.py:534 | ⚠️ |
| B6 | Race condition save_personnel | 🟠 P1 | db.py:839-860 | ❌ |
| B7 | Bare except | 🟠 P1 | db.py:15 | ❌ |
| B8 | 167 silent exceptions | 🟠 P1 | Все файлы | ❌ |
| B9 | subprocess без проверки | 🟠 P1 | main_waha.py:1293 | ❌ |
| B10 | seen_ids unbounded growth | 🟠 P1 | main_waha.py:581 | ❌ |
| B11 | buffer race condition | 🟠 P1 | bridge_wrapper.py:31-58 | ❌ |
| B12 | Дублирование фото-логики | 🟡 P2 | main_waha.py:916/686 | ❌ |
| B13 | Неверный caption | 🟡 P2 | main_waha.py:682 | ❌ |
| B14 | poll_block null | 🟡 P2 | main_waha.py:269 | ❌ |
| B15 | Нет SIM_DATE в диспетчере | 🟡 P2 | whatsapp_commands.py:104 | ❌ |
| B16 | building в parse_poll | 🟡 P2 | poll.py:393 | ❌ |
| B17 | Двойной вызов VOR | 🟢 P3 | main_waha.py:1270+1404 | ❌ |
| B18 | Хардкод пути ЕЖО | 🟢 P3 | 5+ файлов | ❌ |
| B19 | Нет calendar в v6 | 🟢 P3 | whatsapp_commands.py | ❌ |
| C1 | CONTRACTS vs реальность | 🔴 P0 | CONTRACTS.md | ❌ |
| C2 | Неописан whatsapp_commands | 🔴 P0 | CONTRACTS.md | ❌ |
| D1 | ~2500 строк мёртвого кода | 🟡 P2 | 9+ файлов | ❌ |

---

**Всего:** 22 бага/дефекта + 2 нарушения контрактов + 1 проблема мёртвого кода.  
**Критических:** 7. **Высоких:** 7. **Средних:** 6. **Низких:** 5.  
**Процент мёртвого кода:** ~30% (2500 из 8470 строк).
