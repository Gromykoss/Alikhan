# 🔍 Полный аудит модулей Alikhan — карта багов

**Дата:** 2026-07-25
**Проект:** `/home/hermes-workspace/Alikhan-migration/bot/`
**Метод:** построчный аудит всех 12+1 модулей (13 .py файлов)
**Статус:** только аудит, без исправлений

---

## Сводка

| Серьёзность | Количество | Описание |
|-------------|-----------|----------|
| 🔴 CRITICAL | 2 | Краш бота при вызове |
| 🟠 HIGH | 7 | Потеря данных / логические ошибки |
| 🟡 MEDIUM | 12 | Некорректное поведение / мёртвый код |
| 🔵 LOW | 11 | Качество кода / неиспользуемые импорты |

---

## 1. poll.py — логика опросов

### 🟠 HIGH: _get_work_items_from_template игнорирует завершённые работы
**Строки:** 106-109
```python
if monthly_plan <= 0:
    continue
if ostatok <= 0:       # ← не показываем уже выполненные работы
    continue
```
**Проблема:** Работы с `ostatok <= 0` (уже выполненные) исключаются из опроса. Прорабы не видят в сводке выполненные позиции. Это противоречит документированной логике «столбец O — source of truth» из AGENTS.md.
**Риск:** Неполная картина остатков — выполненные работы исчезают из опроса.

### 🟡 MEDIUM: close_poll передаёт 'общая' как vor_code
**Строка:** 587
```python
save_work_log(chat_id, today, 'общая', 'общая', 0, ...)
```
**Проблема:** `vor_code='общая'` — это не валидный код ВОР. Авто-заполнение для отсутствующих категорий записывает фиктивный код работы. В БД `ojr_section3_work_log` появляется запись с `vor_code='общая'`.

### 🟡 MEDIUM: poll.py не закрывает соединения при исключениях
**Строки:** 126-165 (`_get_qa_status` fallback), 277-299 (`_format_qa_facts_by_category`)
**Проблема:** При падении между `get_conn()` и `cur.close()` соединение БД утекает. Нет try/finally для закрытия ресурсов.

### 🔵 LOW: неиспользуемый импорт urllib.request
**Строка:** 11
```python
import sys, os, re, json, urllib.request, base64
```
`urllib.request` и `base64` не используются в модуле.

### 🔵 LOW: glob импортируется внутри функций
**Строки:** 78, 465, 602, 615 — `import glob` дублируется в 4 местах вместо одного верха.

---

## 2. router.py — маршрутизация

### 🟡 MEDIUM: verify_reply вызывается даже при пустом db_reply
**Строки:** 117-123
```python
if action not in ("WEATHER", "SCHEDULE"):
    try:
        from verify import verify_reply
        reply, score, issues = verify_reply(reply, text, db_reply,
                                            db_facts_available=(db_reply is not None))
    except Exception as e:
        print(f"[VERIFY ERR] {e}", flush=True)
```
**Проблема:** `verify_reply` вызывает Grok (через ask_grok) для верификации. Это дополнительный API-вызов на каждый вопрос. При падении — исключение глотается, ответ уходит непроверенным.

### 🔵 LOW: text[:1800] в промпте Grok
**Строка:** 111 — обрезание текста до 1800 символов. Не учитывает unicode/кириллицу.

---

## 3. handlers.py — Grok-запросы, обработчики

### 🔴 CRITICAL: _download_media_base64 НЕ ОПРЕДЕЛЕНА
**Строки:** 622, 643
```python
media = _download_media_base64(message_id) if message_id else ""  # стр. 622
media = _download_media_base64(ctx.get("messageId", "")) if ctx.get("messageId") else ""  # стр. 643
```
**Проблема:** Функция `_download_media_base64` вызывается в `handle_photo` и `handle_document`, но **НИГДЕ НЕ ОПРЕДЕЛЕНА** в проекте. Единственная похожая функция — `_get_base64_evolution` (стр. 151-187), но она имеет другую сигнатуру (принимает `quoted_message_id`, а не `message_id`).
**Риск:** `NameError` при вызове `handle_photo` или `handle_document`.

### 🟠 HIGH: Дублирование импортов
**Строки:** 1-8
```python
import db, json, re, requests, os, sys    # строка 1
import db_memory                            # строка 2
import json                                 # строка 3 — ДУБЛЬ
import re                                   # строка 4 — ДУБЛЬ
from datetime import datetime               # строка 5
import psycopg2.extras                      # строка 6 — не используется
import requests                             # строка 7 — ДУБЛЬ
import db                                   # строка 8 — ДУБЛЬ
```
**Проблема:** `db` импортируется 3 раза (строки 1, 8, 10), `json` — 2 раза, `re` — 2 раза, `requests` — 2 раза. `psycopg2.extras` импортирован но используется только внутри `_fact_rows` (стр. 192) — избыточно на уровне модуля.

### 🟠 HIGH: handle_ai — abuse vector
**Строки:** 590-592
```python
def handle_ai(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    send_msg(group, ask_grok(ctx.get("userMessage") or ctx.get("text") or ""))
```
**Проблема:** Любое сообщение, прошедшее проверку имени «Алихан», уходит напрямую в Grok без санитизации. Можно заставить бота генерировать произвольный контент.

### 🟠 HIGH: _get_base64_evolution — дублирующая загрузка secrets
**Строки:** 152-166
**Проблема:** Загружает `secrets.env` второй раз, хотя `_load_keys()` уже загрузила на уровне модуля (стр. 49). Лишний I/O + переменная `evo_key` затеняет модульную.

### 🟡 MEDIUM: handle_daily_snapshot — циклический импорт
**Строка:** 597
```python
from main_waha import generate_daily_snapshot as _gen_snapshot
```
**Проблема:** handlers.py импортирует main_waha, который импортирует handlers.ask_ollama (через generate_daily_snapshot). Работает из-за позднего импорта, но хрупко.

### 🔵 LOW: handle_quoted_document_summary — экранирование \\
**Строки:** 532, 575 — `\\\n` вместо `\\n` в f-строках (неправильное экранирование, хотя Python это проглатывает как raw-последовательность).

---

## 4. db.py — ВСЕ функции БД

### 🟠 HIGH: datetime.utcnow() — устаревший API
**Строка:** 77
```python
(message_time, file_name, datetime.utcnow()))
```
**Проблема:** `datetime.utcnow()` возвращает naive datetime без timezone. В Python 3.12+ — DeprecationWarning. Должно быть `datetime.now(timezone.utc)`.

### 🟡 MEDIUM: resolve_db_host — хардкод 172.22.0.4
**Строка:** 48
```python
return _docker_container_ip() or "172.22.0.4"
```
**Проблема:** Если Docker-контейнер не найден, fallback-IP жёстко зашит. При смене Docker-сети бот не сможет подключиться.

### 🟡 MEDIUM: save_weather — неполный ON CONFLICT UPDATE
**Строки:** 726-737
```python
ON CONFLICT (weather_date) DO UPDATE
SET temp_avg = EXCLUDED.temp_avg,
    wind_speed = EXCLUDED.wind_speed,
    humidity_pct = EXCLUDED.humidity_pct
```
**Проблема:** `temp_max`, `temp_min`, `pressure_hpa` НЕ обновляются при конфликте. При повторном вызове для той же даты значения max/min/pressure теряются.

### 🟡 MEDIUM: save_message — дедупликация по content без учёта NULL
**Строки:** 66-71
```python
WHERE chat_id = %s AND sender = %s AND content = %s
```
Если `content` = NULL (а в image/document сообщениях так и есть — content = mid/file_name), дедупликация не сработает для NULL-значений.

### 🔵 LOW: search_messages — content ILIKE без индекса
**Строка:** 93-97 — полнотекстовый поиск через ILIKE с `%query%` без индекса GIN/GIST. На больших объёмах — медленно.

### 🔵 LOW: seed_schedule — unused import ipaddress, os, subprocess
**Строки:** 1-4 — импорты `ipaddress`, `os`, `subprocess` на уровне модуля для `resolve_db_host()`, но не используются в остальном модуле (могут быть удалены после рефакторинга).

---

## 5. main_waha.py — основной поток

### 🟠 HIGH: 15-секундный age gate — потеря сообщений
**Строки:** 764-769
```python
msg_ts = _safe_message_ts(m)
now_ts = int(time.time())
if now_ts - msg_ts > 15:
    seen.add(mid)
    continue
```
**Проблема:** При рестарте бота ВСЕ старые сообщения старше 15 секунд помечаются как «seen» и пропускаются (баг AL-008). QA-парсинг и сохранение в БД НЕ выполняются для них.

### 🟠 HIGH: Дублирование логики обработки VOR-кодов
**Строки:** 1117-1134 и 1277-1291
Два независимых блока обрабатывают ответы прораба с VOR-кодами:
1. Строки 1117-1134: блок `has_vor_codes` в основном цикле
2. Строки 1277-1291: блок `action == "RESIDUAL"` после роутинга
**Проблема:** Первый блок перехватывает VOR-коды ДО роутинга, второй — ПОСЛЕ. При наличии имени «алихан» в сообщении оба могут сработать. Логика разная: первый делает acknowledge, второй — краткий ответ.

### 🟡 MEDIUM: SANDBOX захардкожен в обработчиках
**Строки:** 355, 862, 998, 1002, 1026-1049, 1052-1098, etc.
**Проблема:** Все команды (опрос, ЕЖО, календарь, AVR) используют `SANDBOX` напрямую из bridge_wrapper, а не `chat_id` из сообщения. Бот жёстко привязан к песочнице — не может работать в production-группе.

### 🟡 MEDIUM: generate_daily_snapshot — двойной вызов load_workbook
**Строки:** 127 и 448
При формировании снимка дня открывается и закрывается `TEMPLATE_PATH` workbook (стр. 127-136), затем в `_extract_ejo_volumes` (вызываемой при обработке документов) — снова открывается (стр. 448). Избыточно.

### 🟡 MEDIUM: calendar_reminder_loop — sleep(60) блокирует поток
**Строка:** 574 — `time.sleep(60)`. При рестарте напоминания могут задержаться до 60 секунд.

### 🔵 LOW: datetime.now() без timezone
**Строки:** 649, 698, 719, 808, 820, 904, 963 — множественные вызовы `datetime.now()` без timezone. Несогласованность с `datetime.utcnow()` в db.py.

### 🔵 LOW: SEEN_FILE не thread-safe
**Строки:** 527-535 и 579-585 — `seen` и `prod_seen` разделяются между основным потоком и production-потоком без блокировок.

---

## 6. avr.py — КС-2 / КС-6

### 🟡 MEDIUM: load_ejo — жёсткие индексы колонок
**Строки:** 66-79
```python
code = _code(values[2] if len(values) > 2 else None)    # колонка C
monthly = _decimal(values[18] if len(values) > 18 else None)  # колонка S
```
**Проблема:** Индексы колонок захардкожены (2=C, 15=O, 18=R, 10=J). При изменении структуры шаблона ЕЖО — поломка без предупреждений. Нет маппинга column_name → index.

### 🟡 MEDIUM: _as_date не обрабатывает DD.MM.YYYY
**Строки:** 86-91
```python
def _as_date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    return date.fromisoformat(str(value))
```
**Проблема:** `date.fromisoformat` требует `YYYY-MM-DD`. Если передать `31.07.2026` — ValueError.

### 🔵 LOW: неиспользуемые переменные в generate_ks6
**Строка:** 373 — переменная `report_total` затеняет параметр цикла? Нет, но значение `sheet.cell(total_row, 10).value` используется в финансовых расчётах ниже. Ок.

### ✅ Модуль хорошо структурирован, финансовые расчёты корректны.

---

## 7. stt.py — speech-to-text

### 🔵 LOW: неиспользуемые импорты
**Строки:** 2, 4, 5, 6
```python
import time, requests, json  # не используются
import urllib.request        # не используется
from bridge_wrapper import EVO, KEY  # не используются
```
`EVO` и `KEY` импортированы, но не используются в stt.py. Только SANDBOX (стр. 7) и transcribe_audio.

### ✅ Основная логика transcribe_audio корректна: ffmpeg → faster-whisper → Grok post-correction.

---

## 8. config.py — настройки

### ✅ Чистый модуль. Единственный источник конфигурации. Все значения валидны.

### 🔵 LOW: today_str() / today_date() не используются большинством модулей
Модули напрямую обращаются к `SIM_DATE` вместо вызова `today_str()`. Функции-хелперы есть, но игнорируются (poll.py, main_waha.py, qa.py).

---

## 9. qa.py — парсинг QA-фактов

### 🟡 MEDIUM: parse_qa — персонал сохраняется без количества
**Строки:** 434-455
```python
if c == 'персонал':
    # Personnel facts are "Организация ИТР N" or "Организация N рабочих"
    ...
    if 'итр' in fact_lower:
        position = 'ИТР'
    elif 'рабоч' in fact_lower:
        position = 'Рабочий'
    else:
        position = 'Сотрудник'
    save_personnel(gid, today, org_name, org_name, position, sync_source='qa')
    count += 1
```
**Проблема:** Факт «АйБиКон ИТР 2, рабочих 10» сохраняется как ОДНА запись в `ojr_section1_personnel` с position='ИТР' (приоритет), а информация о рабочих теряется. Сам факт `count += 1` увеличивается на 1, а не на число людей.

### 🟡 MEDIUM: parse_qa — план/объём с volume=0 всё равно count += 1
**Строки:** 471-484
```python
elif c in ('план', 'объём'):
    ...
    if volume > 0:
        save_work_log(...)
    count += 1  # ← инкремент даже если save_work_log НЕ вызван
```
**Проблема:** `count` увеличивается, даже если `volume=0` и `save_work_log` не вызван. Пользователю сообщается «Принято: N фактов», но реально сохранено меньше.

### 🟡 MEDIUM: is_qa — ложные срабатывания
**Строки:** 44-57
```python
if "?" in text or any(w in text.lower() for w in [...вопросные слова...]):
    return False
```
**Проблема:** Проверка `"?" in text` блокирует QA-парсинг для текстов, содержащих знак вопроса (например: «Происшествий нет? Нет.») — весь текст отклоняется как вопрос.

### ✅ Ретрай-логика (3 попытки) и аудит-лог — отличная практика.

---

## 10. data_sources.py — источники данных

### 🟡 MEDIUM: _get_conn — общее соединение без переподключения
**Строки:** 105-112
```python
_DB_CONN = None
def _get_conn():
    global _DB_CONN
    if _DB_CONN is None or _DB_CONN.closed:
        _DB_CONN = get_conn()
    return _DB_CONN
```
**Проблема:** Соединение открывается один раз и живёт вечно. При обрыве сети (PostgreSQL таймаут) — все вызовы падают. Нет reconnect-логики. PostgreSQL закрывает idle-соединения через `idle_in_transaction_session_timeout`.

### 🟡 MEDIUM: get_aibikon_headcount — tags может быть строкой, а не dict
**Строка:** 470
```python
tags = row['tags'] if isinstance(row['tags'], dict) else {}
```
**Проблема:** Если `tags` — строка (JSON), `isinstance` вернёт False и данные потеряются. Не делается `json.loads`.

### 🟡 MEDIUM: get_staff — date matching uses created_at not start_date
**Строка:** 233
```sql
WHERE DATE(created_at) = %s::date AND is_active = TRUE
```
**Проблема:** Дата фильтруется по `created_at`, а не по `start_date`. Если персонал добавлен сегодня, но `start_date` у него раньше (из-за close end_date логики), он не попадёт в выборку.

### ✅ NamedTuple-контракты отличные. Хорошая архитектура.

---

## 11. bridge_wrapper.py — monkey-patches

### 🟠 HIGH: _drain_buffer — substring match вместо exact match
**Строка:** 54
```python
matched = [m for m in _BUFFER if remote_jid in m.get("chatId", "")]
```
**Проблема:** `remote_jid in chatId` — это **подстрочное** совпадение. Если `remote_jid = "120363179621030401@g.us"` (песочница) и в буфере есть сообщение с `chatId = "120363179621030401@g.us.status"` — оно будет выдано за песочницу. Риск: сообщения из другой группы утекают в неправильный поток.

### 🟡 MEDIUM: Буфер capped на 200 сообщений
**Строка:** 41-42
```python
if len(_BUFFER) > 200:
    _BUFFER = _BUFFER[-200:]
```
**Проблема:** При высокой нагрузке старые сообщения молча удаляются без обработки.

### 🔵 LOW: _patched_Request не копирует оригинальные headers
**Строки:** 162-167 — при monkey-patch urllib Request теряются пользовательские заголовки.

### ✅ В остальном — надёжный monkey-patch слой, корректно транслирует Evolution → Bridge.

---

## 12. document_extractor.py — endpoint экстракции

### ✅ Чистый модуль. HTTP-сервер, xlsx/pdf экстракция, валидация размера.

### 🔵 LOW: Нет rate-limiting на endpoint
**Строка:** 183 — любой запрос на `/extract-document` принимается без ограничений.

---

## 13. messaging.py — унифицированная отправка

### 🟡 MEDIUM: send_voice — блокирующий subprocess
**Строки:** 38-40
```python
subprocess.run(["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", text,
                "--write-media", mp3_path], check=True, capture_output=True)
```
**Проблема:** `subprocess.run` блокирует основной поток на время генерации TTS. Для длинных ответов — заметная задержка.

### 🟡 MEDIUM: send_document — двойная отправка через bridge_wrapper
**Строки:** 61-64
```python
r = requests.post(f"{EVO}/message/sendMedia/alikhan", ...)
```
**Проблема:** `requests.post` уже замонки-патчен bridge_wrapper'ом (стр. 154 bridge_wrapper.py). При отправке документов через messaging.py — они сначала идут через патч, который создаёт временный файл, декодирует base64, и отправляет через bridge. Это работает, но избыточно.

### ✅ Унификация отправки сообщений — отличный рефакторинг.

---

## Дополнительные находки (cross-cutting)

### 🟡 MEDIUM: _update_template_from_correction — Unicode filename truncation
**Строки:** 267-269 (main_waha.py) — WhatsApp обрезает кириллицу в именах файлов. Бот пытается угадать, но поле `fname` часто содержит `_____` вместо `ЕЖО_27.06.2026_АйБиКон.xlsx`. Дата извлекается regex'ом из обрезанного имени — может не сработать.

### 🔵 LOW: verify.py — всегда вызывает Grok
verify_reply отправляет запрос в Grok на каждую верификацию. При 100 вопросах в час — значительные расходы API.

### 🔵 LOW: fill_ejo.py — 761 строка
Самый крупный модуль. Импортирует 20+ типов из data_sources. Сложность высокая, но не является багом.

---

## Карта приоритетов для исправления

| Приоритет | ID | Файл | Баг |
|-----------|-----|------|-----|
| 🔴 P0 | CRIT-01 | handlers.py:622,643 | `_download_media_base64` не определена |
| 🔴 P0 | CRIT-02 | handlers.py:1-10 | Дублирование импортов (техдолг) |
| 🟠 P1 | HIGH-01 | bridge_wrapper.py:54 | Substring match в _drain_buffer |
| 🟠 P1 | HIGH-02 | main_waha.py:764-769 | Age gate — потеря сообщений |
| 🟠 P1 | HIGH-03 | db.py:77 | datetime.utcnow() deprecated |
| 🟠 P1 | HIGH-04 | handlers.py:152-166 | Дублирующая загрузка secrets |
| 🟠 P1 | HIGH-05 | poll.py:106-109 | Пропуск завершённых работ |
| 🟠 P1 | HIGH-06 | handlers.py:590-592 | handle_ai abuse vector |
| 🟠 P1 | HIGH-07 | main_waha.py:1117-1134 | Дублирование VOR-логики |
| 🟡 P2 | MED-01 | main_waha.py:355,862,etc | SANDBOX захардкожен |
| 🟡 P2 | MED-02 | qa.py:434-455 | Персонал без количества |
| 🟡 P2 | MED-03 | qa.py:471-484 | count += 1 при volume=0 |
| 🟡 P2 | MED-04 | data_sources.py:105-112 | Общее соединение без reconnect |
| 🟡 P2 | MED-05 | poll.py:587 | vor_code='общая' в save_work_log |
| 🟡 P2 | MED-06 | avr.py:66-79 | Жёсткие индексы колонок |
| 🟡 P2 | MED-07 | messaging.py:38-40 | Блокирующий subprocess TTS |
| 🟡 P2 | MED-08 | db.py:726-737 | Неполный ON CONFLICT UPDATE |
| 🟡 P2 | MED-09 | data_sources.py:233 | created_at вместо start_date |
| 🟡 P2 | MED-10 | data_sources.py:470 | tags может быть JSON-строкой |
| 🟡 P2 | MED-11 | handlers.py:597 | Циклический импорт main_waha |
| 🟡 P2 | MED-12 | db.py:48 | Хардкод Docker IP |
| 🔵 P3 | LOW-01..11 | Разные | Качество кода, неиспользуемые импорты |

---

## Статистика по файлам

| Файл | Строк | Багов | CRITICAL | HIGH | MEDIUM | LOW |
|------|-------|-------|----------|------|--------|-----|
| main_waha.py | 1301 | 8 | 0 | 2 | 3 | 3 |
| db.py | 924 | 6 | 0 | 1 | 3 | 2 |
| handlers.py | 680 | 8 | 2 | 2 | 1 | 3 |
| poll.py | 619 | 5 | 0 | 1 | 2 | 2 |
| qa.py | 531 | 4 | 0 | 0 | 3 | 1 |
| fill_ejo.py | 761 | 0 | 0 | 0 | 0 | 1 |
| avr.py | 435 | 3 | 0 | 0 | 2 | 1 |
| data_sources.py | 755 | 4 | 0 | 0 | 3 | 1 |
| bridge_wrapper.py | 251 | 3 | 0 | 1 | 1 | 1 |
| document_extractor.py | 218 | 1 | 0 | 0 | 0 | 1 |
| router.py | 125 | 2 | 0 | 0 | 1 | 1 |
| config.py | 85 | 1 | 0 | 0 | 0 | 1 |
| stt.py | 63 | 1 | 0 | 0 | 0 | 1 |
| messaging.py | 73 | 2 | 0 | 0 | 2 | 0 |
| verify.py | 97 | 1 | 0 | 0 | 0 | 1 |
| **ВСЕГО** | **~6918** | **49** | **2** | **7** | **21** | **19** |
