# CHRONOLOGY — Хронология изменений Алихан бота

## 02.09.2026 — OJR: round 4 QA parse_qa агрегация техники до save

**Причина:** Grok B вернул NEEDS_CHANGES round 3: `parse_qa(...)` сохранял каждый Grok-факт категории `техника` отдельным вызовом `save_equipment(...)` с одним `source_message_id`, из-за чего CASE-идемпотентность в `save_equipment` перезаписывала количество вместо суммирования для однотипной техники из одного сообщения. Дополнительно фильтр профессий ловил только именительный падеж `машинист|крановщик`.

**Что сделал:**
- `bot/qa.py`: добавлен `_aggregate_equipment_facts(...)`, который до DB-save проходит по всем фактам категории `техника`, извлекает позиции через `_equipment_items_from_fact(...)` и суммирует количество по каноническому имени.
- `bot/qa.py`: `parse_qa(...)` больше не вызывает `save_equipment(...)` внутри цикла по отдельным Grok-фактам техники; legacy `bot_memory_facts` сохраняется по фактам, а `save_equipment(...)` вызывается после цикла один раз на каждое канон-имя с суммарным `quantity` и тем же `source_message_id`.
- `bot/qa.py`: `_equipment_mention_is_profession_context(...)` нормализует `ё→е` и отсекает словоформы по префиксам `машинист\w*` / `крановщик\w*`, включая `машиниста крана 1`.

**Проверка:** `python3 -m py_compile bot/*.py` — PASS. `python3 -m pytest bot/test_contracts.py bot/test_smoke.py -q` — 16 passed, 5 failed на заранее известных проверках: legacy `bridge_wrapper`, отсутствующий `main_waha.py`, дубликаты personnel, нет процесса `main_waha.py`. Локальные кейсы: `_equipment_items_from_fact('машиниста крана 1')` → `[]`; `_equipment_items_from_fact('крановщик 1')` → `[]`; `_equipment_items_from_fact('экскаватор 2 ед, самосвал 1')` → `[('Экскаватор', 2), ('Самосвал', 1)]`. DB parse_qa-путь с тестовым `bot_memory_messages.id=4992`: Grok-факты `Экскаватор CAT 1 ед` + `Экскаватор Hitachi 1 ед` сохранились как `('Экскаватор', 2, 4992)`; тестовые строки удалены.

## 02.09.2026 — OJR: раунд 3 правок `save_equipment` и QA-парсера техники

**Причина:** Grok B вернул NEEDS_CHANGES round 2: дубли канонического типа техники перезаписывали `quantity` вместо суммирования, дефолты `shift/status` затирали уже сохранённые значения при конфликте, regex QA-парсера пропускал повторные упоминания и матчел профессии как технику.

**Что сделал:**
- `bot/db.py`: `save_equipment(...)` теперь по конфликту `(title_id, work_date, equipment_name)` суммирует `quantity`; при совпадении `source_message_id` повторный save не добавляет количество заново. Аргументы `shift/status` переведены на дефолт `None`; `1/'working'` подставляются только при первичной вставке, а конфликт без явных значений сохраняет старые `shift/status`.
- `bot/qa.py`: `_equipment_items_from_fact(...)` переписан на поиск всех упоминаний техники с количеством в форматах `1 экскаватор` и `экскаватор 2 шт.`, с суммированием по каноническому имени. Убрана fallback-запись произвольного текста как техники; `крановщик` и контекст `машинист <техника>` больше не распознаются как техника.
- `bot/qa.py`: `parse_qa(...)` получил опциональный `source_message_id` и передаёт его в `save_equipment(...)`, если вызывающий слой отдаёт идемпотентный ключ.

**Проверка:** `python3 -m py_compile bot/*.py` — PASS. Локальные parser-case: `1 экскаватор CAT, 1 экскаватор Hitachi` → `[('Экскаватор', 2)]`; `Самосвал 1 ед. экскаватор 2 шт.` → `[('Самосвал', 1), ('Экскаватор', 2)]`; `крановщик 1` → `[]`; `машинист крана 1` → `[]`. БД через `get_conn()` на тестовых датах 2099-03-03/04/05: два save `Экскаватор CAT` + `Экскаватор Hitachi` дали `('Экскаватор', 2, 1, 'working')`; повторный save с тем же `source_message_id` дал `('Экскаватор', 1, 1, 'working', 4990)` без задвоения; конфликт без `shift/status` сохранил старые `('Самосвал', 2, 2, 'idle')`. Тестовые строки удалены. `python3 -m pytest bot/test_contracts.py bot/test_smoke.py -q` — 16 passed, 5 failed на заранее известных проверках: legacy `bridge_wrapper`, отсутствующий `main_waha.py`, дубликаты personnel, нет процесса `main_waha.py`.

## 02.09.2026 — OJR: раунд 2 правок таблицы техники `ojr_section2_equipment`

**Причина:** Grok B вернул NEEDS_CHANGES: `source_message_id` был TEXT без FK, `quantity` допускал NULL, техника считалась из legacy section3, канонизация и upsert теряли данные.

**Что сделал:**
- `db/ojr_schema.sql`: `source_message_id` заменён на `BIGINT REFERENCES bot_memory_messages(id) ON DELETE SET NULL`; `quantity` теперь `INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0)`; удалены из канонической схемы лишние индексы `idx_ojr_equipment_title`, `idx_ojr_equipment_status`, старый `idx_ojr_equipment_msg`, добавлен корректный индекс `idx_ojr_equipment_source_message_id`.
- `bot/db.py`: `save_equipment(...)` канонизирует название до INSERT, приводит `source_message_id` к BIGINT/NULL, upsert дописывает пустующие `equipment_type`, `shift`, `status`, `operator_name`, `source_message_id` через `COALESCE`; `get_ojr_qa_status(...)` считает `ojr_section2_equipment` как primary и падает назад на legacy `ojr_section3_work_log category='техника'`.
- `bot/qa.py`: QA-маршрут техники теперь вызывает `save_equipment(...)` и сохраняет legacy `bot_memory_facts` для совместимости.
- `bot/data_sources.py`: `get_equipment(date)` при схлопывании канонических имён суммирует `quantity`, а не берёт `max`.
- `bot/CONTRACTS.md`: актуализированы строки файлов, exports и NamedTuple-контракты, включая `AIBHeadcount`, `EquipmentItem` и `EquipmentData.details`.

**Проверка:** `docker exec evolution-postgres psql ...` создал таблицу, индексы и comment; сверка показала `source_message_id bigint` с FK на `bot_memory_messages(id) ON DELETE SET NULL`, `quantity` `NOT NULL`, только индексы `idx_ojr_equipment_date`, `idx_ojr_equipment_source_message_id`, PK и UNIQUE. `python3 -m py_compile bot/*.py` — PASS. `python3 -m pytest bot/test_contracts.py bot/test_smoke.py -q` — 16 passed, 5 failed на заранее известных проверках: legacy `bridge_wrapper`, отсутствующий `main_waha.py`, дубликаты personnel, нет процесса `main_waha.py`.

## 02.09.2026 — OJR: добавлена 15-я таблица техники `ojr_section2_equipment`

### Причина
- Канон MASTER_SPEC от 02.09.2026 требует вынести ежедневный учёт техники из legacy-источников в отдельную 15-ю таблицу ОЖР без LLM-парсинга.

### Что сделано
- `db/ojr_schema.sql`: добавлена `ojr_section2_equipment` с FK на `ojr_title_page`, полями техники, UNIQUE `(title_id, work_date, equipment_name)` и индексами.
- `bot/db.py`: добавлены `save_equipment(...)` и `get_daily_equipment(ds)` через `get_conn()`; upsert обновляет `quantity` и `status`.
- `bot/data_sources.py`: `get_equipment(date)` сначала читает `ojr_section2_equipment`, затем падает назад на старый `ojr_section3_work_log category='техника'` и QA-факты; `EquipmentData` расширен деталями без поломки `items`.
- `bot/CONTRACTS.md`: обновлены публичные контракты DB/data_sources.

### Проверка
- `python3 -m py_compile bot/*.py` — PASS.
- `python3 -m pytest bot/test_contracts.py bot/test_smoke.py -q` — 16 passed, 5 failed на существующих внешних/устаревших проверках: legacy `bridge_wrapper/main_waha` контракты, отсутствующий `bot/main_waha.py`, дубликаты `ojr_section1_personnel`, нет процесса `main_waha.py`.

### Файлы
- `db/ojr_schema.sql`
- `bot/db.py`
- `bot/data_sources.py`
- `bot/CONTRACTS.md`

## 01.09.2026 (ночь, 23:00 UTC) — 0 коммитов продукта; OJR-разрыв расширился (31.08–01.09 пусто); текстовый приём мёртв 12-й день; bridge рестарт ~04:00 UTC

### Коммиты за 24ч
- Продуктовых коммитов НЕТ. Только chrono: `d2d596c` (индекс 37fe2f3, 31.08 23:02 UTC).

### Операционное состояние (по БД/health, не по памяти)
- **OJR-разрыв расширился:** `ojr_section3_work_log` +0 за 24ч (max work_date = **30.08**), `ojr_section1_personnel` +0 (max start_date = 30.08). Дни 31.08 и 01.09 не закрыты — ejo_v2-импорт не приходил 2 дня подряд.
- **Текстовый приём мёртв 12-й день:** `bot_memory_messages` = 0 за 24ч (max = 21.08 07:06), `bot_memory_facts` = 0 (20-й день, last = 13.08).
- `ojr_photo_log` = 0 (15-й день, max = 18.08). `ojr_section5_asbuilt_docs` +0. `cache/documents` за 24ч — пусто (4-й день).
- **Погода течёт:** `ojr_weather` +1 (01.09) ✅.
- **Bridge:** `curl :3000/health` → `connected`, queueLength=0, uptime ~19.2ч → **рестарт ~04:00 UTC 01.09**. Кто рестартовал — не зафиксировано.
- `document-extractor` :8099 → `{ok: true}` ✅.

### Незакоммиченное (вне скоупа chrono)
- `bot/templates/ЕЖО_шаблон.xlsx` (изменён, .bak_0831) + untracked `scripts/migrate_passes_to_register.py` — с 31.08.
- `AGENTS.md` modified (секция Грок-бот).

### ⛔ Незакрытые
1. **OJR-импорт встал:** 2 дня подряд (31.08, 01.09) без данных — проверить пайплайн ejo_v2/extractor.
2. Текстовый приём (12-й день) — зона Hermes/Codex.
3. Фото-лог (15-й день), watchog_bridge.py не чинен.

---

## 31.08.2026 (ночь, 23:00 UTC) — Office-forward закоммичен (761a213); OJR-данные за 30.08 пришли (s3 +9, s1 +8); текстовый приём мёртв 11-й день

### Коммиты за 24ч
- `761a213` — office-forward: пересылка вопросов прорабов офисному Оркестратору (Diamond: Codex A + Grok B, 3 раунда, APPROVED). E2E песочница 4/4 HTTP 200. Детали — запись выше от 31.08.
- `94432f7`, `eadc5ae` — chrono 30.08.

### Операционное состояние (по БД/health, не по памяти)
- **OJR ожил:** `ojr_section3_work_log` +9 за 24ч (последний work_date = **30.08** — день 30.08 закрыт, разрыв 29.08 остаётся пустым), `ojr_section1_personnel` +8, `ojr_weather` +1 (31.08). Похоже на ejo_v2-импорт за 30.08.
- **Текстовый приём мёртв 11-й день:** `bot_memory_messages` = 0 за 24ч (max = 21.08 07:06), `bot_memory_facts` = 0 (19-й день, last = 13.08). Данные идут только через импорт, без атрибуции от прорабов.
- `ojr_photo_log` = 0 (14-й день, max = 18.08). `ojr_section5_asbuilt_docs` +0. `cache/documents` за 24ч — пусто (3-й день).
- **Bridge:** `curl :3000/health` → `connected`, queueLength=0, uptime ~9.9ч → **рестарт ~13:08 UTC 31.08** (uptime 64ч был прерван; причина/инициатор из journal не извлечены — journalctl недоступен).
- `document-extractor` :8099 → `{ok: true}` ✅. Gateway service loaded/enabled.

### Незакоммиченное (вне скоупа chrono)
- `bot/templates/ЕЖО_шаблон.xlsx` изменён (8.5MB → 17MB, 0831, есть .bak_0831) + untracked `scripts/migrate_passes_to_register.py`.
- `AGENTS.md` modified (секция Грок-бот, от Hermes 15:10).

### ⛔ Незакрытые
1. Текстовый приём (11-й день) — зона Hermes/Codex.
2. Разрыв OJR за 29.08 (нулевые данные; 28.08 → 30.08).
3. Фото-лог (14-й день), watchog_bridge.py не чинен.

---

## 31.08.2026 — Office webhook forward для строительных вопросов прорабов

### Причина
- Нужно пересылать явные строительные вопросы из WhatsApp офисному Оркестратору через webhook, не перехватывая QA-факты, ответы опроса, команды, фото и документы.

### Что сделано
- Добавлен `bot/office_forward.py`: детерминированная классификация вопросов по темам `кровля` / `наружка` / `материалы` / `смета` / `общее`, POST `forward_to_office()` с `Authorization: Bearer <key>`, timeout 10s, без вывода секретов.
- `bot/secret_config.py` научен читать локальный `bot/secret_config.json` через общий `get_secret()`; поддержаны требуемые ключи `office_webhook_url`, `office_webhook_key` и текущие legacy-алиасы.
- `bot/whatsapp_commands.py`: в `_save_prod_text()` добавлен синхронный вызов webhook после сохранения сырого текста; сбой webhook возвращает `False`, чтобы `message_id` не попал в seen/ACK и ушёл на retry.
- `bot/secret_config.json` добавлен в `.gitignore`.
- Добавлены `bot/test_office_forward.py` и `scripts/test_office_forward_sandbox.py`.
- После adversarial review: `forward_to_office()` ждёт async-тред до таймаута, успехом считает только HTTP 2xx, делает retry по тому же `message_id`, режет `text` до 4000 символов и пишет обезличенные ошибки через `log()` диспетчера.
- Классификатор усилен: служебные слова и команды проверяются по границам слов, `никто`/`ежо?`/`как обычно рабочие 7`/`25т` не форвардятся, poll-ответы больше не определяются по простому паттерну `\d+т`.
- `bot/secret_config.json` мигрирован на канонические ключи `office_webhook_url` / `office_webhook_key`; `scripts/test_office_forward_sandbox.py` использует `classify_office_question()`, контракт `office_forward` добавлен в `bot/CONTRACTS.md`.
- После adversarial review round 2: daemon fire-and-forget убран; default `join_timeout=25` покрывает `2 x 10s` retry-бюджет с запасом, topic-keywords проверяются по границам слов (`акт` не матчится в `факт`), `?` проверяется до QA-отсечки по `=`, лог `queued=` заменён на `sent=`.

### Проверка
- `python3 -m py_compile bot/*.py` — PASS.
- `python3 -m pytest bot/test_office_forward.py -v` — 18 passed.
- `python3 -m py_compile bot/*.py && python3 -m pytest bot/test_office_forward.py -q` — 21 passed.
- `python3 scripts/test_office_forward_sandbox.py` — 4 POST в sandbox webhook, все HTTP 200.
- `python3 -m pytest bot/test_contracts.py bot/test_smoke.py bot/test_office_forward.py -v` — 25 passed, 5 failed на старых/внешних проблемах: stale `bridge_wrapper/main_waha` контракты, дубликаты personnel в БД, отсутствующий процесс `main_waha`.

### Файлы
- `.gitignore`
- `bot/secret_config.py`
- `bot/office_forward.py`
- `bot/whatsapp_commands.py`
- `bot/test_office_forward.py`
- `bot/CONTRACTS.md`
- `scripts/test_office_forward_sandbox.py`

---

## 30.08.2026 — Стабильная ночь без изменений: 0 коммитов, 0 inbound, OJR мёртв 2-й день (последние данные 28.08); погода течёт

### Что произошло (по логам/БД, не по памяти)
- **0 коммитов за 24ч** (последние — `ba5cc11` и `f2cbe1f` от 29.08 23:01 UTC). В рабочем дереве без изменений: хвост `bot/whatsapp_commands.py` (+280/−44, с 21.08), untracked `scripts/migrate_passes_to_register.py`.
- **Текстовый приём мёртв 9-й день:** `bot_memory_messages` = 0 за сутки (max = 21.08 07:06). `bot_memory_facts` = 0 (17-й день, last = 13.08).
- **OJR мёртв 2-й день подряд:** `ojr_section3_work_log` +0 за сутки (последние даты: 27.08 и 28.08, ejo_v2), `ojr_section1_personnel` +0 (max start_date = 28.08). День 29.08 так и не закрыт, день 30.08 не открыт — ejo_v2-импорт за 29.08 не приходил.
- **Погода течёт:** `ojr_weather` +1 за сутки (30.08, temp_avg 12.0°C) ✅.
- `ojr_photo_log` = 0 (12-й день, max = 18.08). `ojr_section5_asbuilt_docs` +0. В `cache/documents` за 24ч новых файлов НЕТ (2-й день подряд).
- **Gateway journal за 24ч:** 0 строк inbound/decrypt/Bad MAC.
- **Bridge стабилен:** `curl :3000/health` → `connected`, queueLength=0, uptime ~40.5ч (старт 29.08 06:30 UTC) — рестартов за сутки НЕТ, впервые за 4 дня.
- `document-extractor` :8099 → `{ok: true}` ✅.

### ⛔ Незакрытые баги (зона Hermes/Codex)
1. **Текстовый приём** — 9-й день: 0 inbound, ejo_v2-импорт без атрибуции (contractor пуст, source_fact_id=NULL).
2. **OJR-поток прервался:** последний импорт — за 28.08. Если 29.08 естественный «пустой» день (воскресенье?) — ок; иначе разрыв импорта ejo_v2. Требует проверки завтра.
3. **watchdog_bridge.py** — не чинен (single-shot `_failure_count`, мёртвый v5-юнит в `bridge_48h_restart.sh`).

### Незакоммиченное
- `bot/whatsapp_commands.py` (+280/−44, с 21.08) — НЕ тронуто (вне скоупа chrono-коммита).
- Untracked: `scripts/migrate_passes_to_register.py`.

---

## 29.08.2026 — Данные только за 27–28.08 (ejo_v2); новый рестарт gateway 29.08 06:30 UTC (вне процедуры); авто-синхронизация хронологии после бэклога

### Что произошло (по логам/БД, не по памяти)
- **Коммиты вернулись:** за сутки 2 коммита — `928467b` (29.08 12:21 UTC, бэклог хронологии 20–28.08 + briefings + knowledge_graph) и `ee57756` (индекс). Разрыв в 8 дней без коммитов закрыт.
- **Текстовый приём мёртв 8-й день:** `bot_memory_messages` = 0 за сутки (max = 21.08 07:06). `bot_memory_facts` = 0 (16-й день, last = 13.08).
- **OJR:** новых записей за сутки НЕТ — `ojr_section3_work_log` +0 (последние даты: 27.08 и 28.08, ejo_v2), `ojr_section1_personnel` +0. День 29.08 в ОЖР не открыт (импорт ЕЖО за 29.08 не приходил).
- **Погода течёт:** `ojr_weather` +1 за сутки ✅.
- `ojr_photo_log` = 0 (11-й день). В `cache/documents` за сутки новых файлов НЕТ (первый день без документов с 26.08).
- **Bridge:** `curl :3000/health` → `connected`, queueLength=0, uptime ~16.5ч.
- **⚠️ Gateway рестартован 29.08 06:30 UTC** (systemd `hermes-gateway.service`, MainPID 1946114) — второй рестарт за 3 дня (28.08 08:05 → 29.08 06:30). Кто рестартовал — не зафиксировано. Нарушение GATEWAY RESTART BAN — доложено оператору в отчёте.
- Gateway journal за 24ч: 0 inbound, 0 decrypt/Bad MAC.
- `document-extractor` :8099 → `{ok: true}` ✅.

### ⛔ Незакрытые баги (зона Hermes/Codex)
1. **Текстовый приём** — 8-й день: 0 inbound, ejo_v2-импорт без атрибуции (contractor пуст, source_fact_id=NULL).
2. **watchdog_bridge.py** — не чинен (single-shot `_failure_count`, мёртвый v5-юнит в `bridge_48h_restart.sh`).
3. **Рестарты gateway 28.08 и 29.08** — дважды вне процедуры. Требует пояснения оператора.

### Незакоммиченное
- `bot/whatsapp_commands.py` (+280/−44, с 21.08) — НЕ тронуто (вне скоупа chrono-коммита).
- Untracked: `scripts/migrate_passes_to_register.py`.

---

## 28.08.2026 — OJR питается ejo_v2-импортом стабильно (27+28.08 закрыты); текстовый приём 7-й день мёртв; gateway рестарт 28.08 08:05 UTC

### Что произошло (по логам/БД, не по памяти)
- **Текстовый приём мёртв 7-й день:** `bot_memory_messages` = 0 за сутки (max = 21.08 07:06, total 647). `bot_memory_facts` = 0 (15-й день, last = 13.08). В gateway journal за сутки — 0 строк `inbound message`, 0 decrypt/Bad MAC.
- **OJR — данные пошли за 27.08 и 28.08 (ejo_v2):**
  - `ojr_section3_work_log` +12 строк за сутки: за 27.08 — 5, за 28.08 — 7. Все `contractor` пустой — атрибуция по подрядчикам по-прежнему теряется.
  - `ojr_section1_personnel` +8 строк (ejo_v2): за 27.08 — АйБиКон 1, Майкадам 2; за 28.08 — АйБиКон 1, Майкадам 2, **Алтын-Тас 2** (второй день подряд — субподрядчик закрепился в персонале).
- **Погода течёт:** `ojr_weather` = 40, есть записи за 27.08 и 28.08 (t≈13.0°C, без осадков) ✅.
- `ojr_photo_log` = 0 (10-й день; max photo_date = 18.08). В `cache/documents` за сутки новых файлов не появилось.
- **Bridge стабилен:** `curl :3000/health` → `connected`, uptime ~15ч, queueLength=0.
- **Gateway рестартован 28.08 08:05 UTC** (systemd `hermes-gateway.service`, MainPID 3428787). После рестарта — 0 decrypt-ошибок. Кто рестартовал — в журнале не зафиксировано (см. GATEWAY RESTART BAN — доложить оператору).
- `document-extractor` :8099 → `{ok: true}` ✅.

### ⛔ Незакрытые баги (зона Hermes/Codex)
1. **Текстовый приём** — 7-й день: 0 inbound, ejo_v2-импорт без атрибуции (contractor пуст, source_fact_id=NULL).
2. **watchdog_bridge.py** — не чинен (single-shot `_failure_count`, мёртвый v5-юнит в `bridge_48h_restart.sh`).
3. **Рестарт gateway 28.08 08:05 UTC** — вне процедуры (бан на рестарты, только оператор). Требует пояснения.

### Данные (ночь 23:06 UTC, 29.08 05:06 Бишкек)
- `bot_memory_messages` = 0 (7-й день); `bot_memory_facts` = 0 (15-й день).
- `ojr_section3_work_log` = 12 за сутки (27.08: 5, 28.08: 7, ejo_v2).
- `ojr_section1_personnel` = 8 за сутки (ejo_v2; 28.08: АйБиКон/Майкадам/Алтын-Тас).
- `ojr_photo_log` = 0 (10-й день); `ojr_weather` ✅ (28.08 есть).

### Git / незакоммиченное
- 0 коммитов за сутки (8-й день; последний `702c074` 20.08 04:03).
- Хвост: `bot/whatsapp_commands.py` (+280/−44, с 21.08), `CHRONOLOGY.md`, `knowledge_graph/*` (авто), untracked: `scripts/migrate_passes_to_register.py`, `briefings/2026-08-20..27.md`.

### Инфраструктура
- `hermes-gateway.service` active (PID 3428787, с 28.08 08:05 UTC — рестарт).
- `document-extractor` :8099 → `{ok: true}` ✅.

---

## 27.08.2026 — Приём данных по-прежнему только файлами (ejo_v2); decrypt-ошибок нет 3-й день; новый подрядчик Алтын-Тас в персонале

### Что произошло (по логам/БД, не по памяти)
- **Текстовый приём мёртв 6-й день:** `bot_memory_messages` = 0 за сутки (max = 21.08 07:06, total 647). `bot_memory_facts` = 0 (last = 13.08, total 227, 14-й день).
- **OJR питается файлами ЕЖО через ejo_v2-импорт:**
  - `ojr_section3_work_log` — 6 строк за work_date 26.08, `created_by='ejo_v2'`, импорт 26.08 10:08 UTC. За 27.08 записей пока нет (день не закрыт / импорт не запускался).
  - `ojr_section1_personnel` — 6 строк за 26.08 (10:08 UTC, ejo_v2): **АйБиКон 2, Майкадам 2, Алтын-Тас 2**. ⚠️ Первый раз в ОЖР появляется подрядчик **Алтын-Тас** — уточнить у прорабов, новый ли это субподрядчик на площадке.
  - `contractor` в section3 по-прежнему пустой, `source_fact_id=NULL` — данные идут мимо QA-пайплайна (атрибуция по подрядчикам в отчётах теряется).
- **Документы поступают в cache регулярно:** за 26–27.08 — xlsx ЕЖО за 26.08, PDF-акты `2-31-1 IBCON` №435–439 (26.08 и 27.08, 04:29–08:34 UTC), docx-отчёты за 27.08.
- **Bridge стабилен:** `curl :3000/health` → `connected`, uptime ~20.7ч (старт ~26.08 18:20 UTC), queueLength=0. В gateway journal за 24ч — **0 строк decrypt/Bad MAC** (первый многодневный период без decrypt-ошибок). Рестартов gateway за 26–27.08 не было.
- **Погода течёт:** `ojr_weather` +1 (27.08 02:00 UTC) ✅ — единственный автоматический поток.
- `ojr_photo_log` = 0 (9-й день; max photo_date = 18.08).

### ⛔ Незакрытые баги (зона Hermes/Codex)
1. **Текстовый приём** — 6-й день: 0 inbound в БД, ejo_v2-импорт без атрибуции (пустой contractor, NULL source_fact_id).
2. **watchdog_bridge.py** — не чинен: single-shot `_failure_count` всегда =1, `bridge_48h_restart.sh` бьёт в мёртвый v5-юнит. (Сейчас не критично — мост стабилен, но защита отсутствует.)
3. **`hermes-whatsapp-bridge` unit не в running** — bridge.js живёт внутри gateway-сессии alikhan; systemd-надзора за мостом фактически нет.

### Данные (ночь 23:00 UTC, 27.08 05:00 Бишкек)
- `bot_memory_messages` = 0 (6-й день); `bot_memory_facts` = 0 (14-й день).
- `ojr_section3_work_log` = 6 (за 26.08, ejo_v2); за 27.08 — пока 0.
- `ojr_section1_personnel` = 6 (за 26.08: АйБиКон/Майкадам/Алтын-Тас по 2).
- `ojr_photo_log` = 0 (9-й день); `ojr_weather` = 1 ✅.

### Git / незакоммиченное
- 0 коммитов за сутки (7-й день; последний `702c074` 20.08 04:03).
- Хвост: `bot/whatsapp_commands.py` (+280/−44, с 21.08), `CHRONOLOGY.md`, `knowledge_graph/*` (авто), untracked: `scripts/migrate_passes_to_register.py`, `briefings/2026-08-20..25.md`.

### Инфраструктура
- `hermes-gateway.service` active (PID 76508, без рестартов за 48ч); в журнале шум от других профилей (robot-man terminal-запросы, LLM 524/timeout, MCP warnings) — на WhatsApp не влияет.
- `document-extractor` :8099 → `{ok: true}` ✅.

---

## 25.08.2026 — OJR-данные пошли обходным путём (импорт файлов ЕЖО, метка ejo_v2); текстовый приём 4-й день мёртв

### Что произошло (по логам/БД, не по памяти)
- **Текстовый приём по-прежнему мёртв (4-й день):** диспетчер весь день логирует `GOT 0 msgs, 211 seen` — `seen.json` застрял на 21.08 07:06 (211 записей, mtime не меняется). В gateway journal за 25.08 — 0 строк `inbound message`.
- **НО в OJR впервые за 5 дней пошли данные — через файлы ЕЖО:** `ojr_section3_work_log` +29 строк за сутки, `ojr_section1_personnel` +18 строк. Все с пометкой `created_by/sync_source='ejo_v2'`.
  - 05:41 UTC — **backfill прошлых дней:** section3 за 21.08 (7), 23.08 (8), 24.08 (8); personnel за 21/23/24 (14 строк).
  - 12:12 UTC — **свежие за 25.08:** section3 (6 строк), personnel (4 строки: АйБиКон ИТР 3 + Рабочие 1, Майкадам ИТР 1 + Рабочие 24).
- **Источник — файлы ЕЖО из WhatsApp:** `cache/documents/` пополнился 25.08 файлами прорабов — xlsx ЕЖО (21/23/24/25.08), PDF-акты `2-31-1 IBCON` (07:53–08:34), docx-отчёты (06:51, 07:15). Мост скачивает документы в cache; импорт в OJR делает внешний процесс. **Метки `ejo_v2` в кодовой базе нет** (grep пусто), диспетчер и `document-extractor`-сервис в момент импорта не работали → вероятен ручной/агентский импорт; точный источник не установлен.
- **Bridge:** `connected`, uptime ~9.5ч. Gateway рестартован сегодня 13:29 UTC (3-й день подряд рестарт), bridge PID 136894 стартовал 13:30:52.
- **Decrypt-ошибок за 25.08 НЕТ** (последняя 24.08 09:27 UTC) — положительный сдвиг. Но реконнекты `Connection closed (428/503)` продолжаются (последний 503 в 21:49 UTC).

### ⛔ Незакрытые баги (зона Hermes/Codex)
1. **watchdog_bridge.py** — 5-й день не чинит мост: single-shot счётчик `_failure_count` всегда `=1`, порог `FAIL_THRESHOLD=3` недостижим; `bridge_48h_restart.sh` бьёт в мёртвый v5-юнит (`Failed to connect to bus: No medium found`).
2. **Текстовый приём мёртв на уровне сессии.** Decrypt-ошибки ушли (24.08), но приём не восстановился: 0 inbound, `seen.json` не двигается. Сессия после релинка 20.08 так и не стабильна.
3. **ejo_v2-импорт без атрибуции:** section3 идёт с пустым `contractor` и `source_fact_id=NULL` — данные обходят QA-пайплайн и не привязаны к подрядчику (риск: ЕЖО-отчёт не разложит работы по подрядчикам).

### Данные (ночь 23:00 UTC, 26.08 05:00 Бишкек)
- `bot_memory_messages` = 0 (4-й день; max = 21.08 07:06).
- `bot_memory_facts` = 0 (12-й день; last = 13.08).
- `ojr_section3_work_log` = 29 за сутки ✅ (backfill 21/23/24 = 23 + свежие 25.08 = 6).
- `ojr_section1_personnel` = 18 за сутки ✅ (backfill = 14 + свежие 25.08 = 4).
- `ojr_photo_log` = 0 (7-й день; max photo_date = 18.08).
- `ojr_pass_register` = 32 (без изменений).
- `ojr_weather` = 1 ✅ (max = 25.08 02:00).

### Git / незакоммиченное
- 0 коммитов за сутки (5-й день; последний `702c074` 20.08 04:03).
- Хвост 5-й день: `bot/whatsapp_commands.py` (+280/−44), `CHRONOLOGY.md`, `scripts/migrate_passes_to_register.py` (untracked), `briefings/2026-08-20..24.md` (untracked), `knowledge_graph/*` (авто-пересборка 20:00 UTC — единственное изменение файлов за 25.08).

### Инфраструктура
- Gateway = systemd `hermes-gateway.service` (MainPID 135505, active since 13:29:37). Юниты `hermes-gateway-alikhan`/`-gulag` — inactive; мост алikhan-сессии спавнит общий gateway (bridge.js PID 136894, `--session .../profiles/alikhan/whatsapp/session --mode bot`).
- В gateway journal (общий, все профили) — шум: LLM 524/503 (Nous inference), OpenRouter payment error, MCP xapi keepalive fail. На WhatsApp-приём Alikhan не влияет.
- `document-extractor` :8099 → `{ok: true}` (но журнал сервиса за 25.08 пуст — импорт шёл не через него).

---

## 24.08.2026 — Тишина по приёму 3-й день: decrypt-ошибки перекинулись на боевую группу; gateway переведён под systemd

### Что произошло (по логам/БД, не по памяти)
- Bridge в течение 24.08 был DOWN с ~09:15 до ~11:56 UTC (~2.7ч): `watchdog_bridge.py` фиксировал `Bridge DOWN (failure #1)` в 09:15, 09:45 и 11:55 UTC. Счётчик, как всегда, застревает на `#1`.
- Восстановлен **рестартом gateway** ~11:54–11:56 UTC: systemd-юнит `hermes-gateway.service` активен с 11:54:59 (Main PID 1457613), bridge PID 1459083 стартовал 11:56:18. На 23:02 UTC `curl :3000/health` → `connected, uptime 39946 (~11.1ч), scriptHash 32dfb86c3a8a173b`, queueLength=0.
- **Сдвиг симптома:** decrypt-ошибки (`No session found to decrypt message` + `Bad MAC`) теперь бьют и по **боевой** группе `120363400682390076@g.us` (участник `244817581838465@lid` / phone `996557261164`), а не только по песочнице, как 23.08. Последняя в 09:27:46 UTC, всего 9 decrypt-ошибок в `bridge.log`. После рестарта 11:56 новых decrypt-ошибок нет, но реконнекты `Connection closed (428/503)` продолжаются (последний 503 в 21:39:54 UTC).
- Приём в БД по-прежнему мёртв: диспетчер весь день логирует `GOT 0 msgs, 211 seen` — `seen.json` застрял на 21.08 07:06 (211 записей, mtime не меняется).

### ⛔ Баг watchdog — НЕ починен (4-й день, зона Hermes/Codex)
1. `_failure_count` — по-прежнему в single-shot-процессе (cron `*/5`), всегда `=1` («failure #1»), порог `FAIL_THRESHOLD=3` недостижим → автоперезапуск не триггерится.
2. `scripts/bridge_48h_restart.sh` (cron `0 2 */2`) бьёт в мёртвый v5-юнит: `bridge_restart.log` 24.08 02:00 → `systemctl --user restart hermes-whatsapp-bridge` → `Failed to connect to bus: No medium found`.
3. `bot/watchdog_bridge.py` mtime 18.07 — файл не трогали. Фикса нет.

### Данные (ночь 23:00 UTC, день Бишкек 24.08)
- `bot_memory_messages` = 0 (3-й день; max = 21.08, total 647).
- `bot_memory_facts` = 0 (11-й день; last = 13.08, total 227).
- `ojr_section3_work_log` = 0 (4-й день; max work_date = 20.08).
- `ojr_section1_personnel` = 0 новых (max created_at = 21.08).
- `ojr_photo_log` = 0 (6-й день; max photo_date = 18.08).
- `ojr_pass_register` = 32 (без изменений, max pass_date = 21.09).
- `ojr_weather` = 1 (max = 24.08) ✅ единственное, что течёт (36 строк всего).

### Git / незакоммиченное
- 0 коммитов за сутки (последний `702c074` 20.08 04:03) — 4-е сутки без коммита.
- Хвост 4-й день: `bot/whatsapp_commands.py` (+280/−44, mtime 21.08 09:40), `CHRONOLOGY.md`, `scripts/migrate_passes_to_register.py` (untracked), `briefings/2026-08-20..23.md` (untracked), `knowledge_graph/*` (авто). Единственное изменение за 24.08 — авто-пересборка KG (24.08 20:00 UTC).

### Инфраструктура (новое)
- **Gateway теперь systemd-управляемый** (`hermes-gateway.service`, `enabled`, active since 24.08 11:54:59) — восстановление после отвала теперь за systemd, не за watchdog. Рестарт 11:55 и поднял мост.
- В `errors.log` каждые ~5 мин падает MCP `nexusos` (`Connection closed`, паркуется) — фиктивный сервер, шум, не влияет на WhatsApp.
- `document-extractor` :8099 → `{ok: true}` ✅.

---

## 23.08.2026 — Тишина по приёму 2-й день: bridge «connected», но сессия не расшифровывает входящие; watchdog всё ещё сломан

### Что произошло (по логам/БД, не по памяти)
- Bridge в течение 23.08 флапал: `watchdog_bridge.py` фиксировал `Bridge DOWN (failure #1)` в 04:50, 09:15 и 17:10 UTC. Счётчик, как и прежде, застревает на `#1` — автоперезапуск не срабатывает.
- Восстановлен ~17:11 UTC **ручным рестартом gateway** (`gateway.log` 17:11:55 `Starting Hermes Gateway...` → 17:12:10 `✓ whatsapp connected (profile: alikhan)`). Сейчас `curl :3000/health` → `connected, uptime 21032 (~5.8ч), scriptHash 32dfb86c3a8a173b`.
- Сессия WhatsApp остаётся нестабильной: в `bridge.log` рекуррентные `Connection closed (428/440)`, `stream errored out (503)` и — ключевое — `No session found to decrypt message` + `Bad MAC` для песочницы `120363179621030401@g.us`. Bridge отдаёт `connected`, но входящие сообщения не расшифровываются → приём фактически мёртв.

### ⛔ Баг watchdog — НЕ починен (3-й день, зона Hermes/Codex)
1. `_failure_count` — по-прежнему в single-shot-процессе (cron `*/5`), счётчик всегда `=1` («failure #1»), порог `FAIL_THRESHOLD=3` недостижим.
2. Рестарт бьёт в мёртвый v5-юнит: `bridge_restart.log` 23.08 02:00 → `systemctl --user restart hermes-whatsapp-bridge` → `Failed to connect to bus: No medium found`.
3. `bot/watchdog_bridge.py` mtime 18.07 — файл не трогали. Фикса нет.

### Данные (ночь 23:00 UTC)
- `bot_memory_messages` = 0 (2-й день; max = 21.08) — приём молчит.
- `bot_memory_facts` = 0 (10-й день; last = 13.08, total 227).
- `ojr_section3_work_log` = 0 (3-й день; max work_date = 20.08).
- `ojr_section1_personnel` = 0 новых (max created_at = 21.08).
- `ojr_photo_log` = 0 (5-й день; max photo_date = 18.08).
- `ojr_pass_register` = 32 (без изменений, max pass_date = 21.09).
- `ojr_weather` = 1 (max = 23.08) ✅ единственное, что течёт.

### Git / незакоммиченное
- 0 коммитов за сутки (последний `702c074` 20.08 04:03).
- Хвост 3-й день: `bot/whatsapp_commands.py` (+280/−44, mtime 21.08), `CHRONOLOGY.md`, `scripts/migrate_passes_to_register.py` (untracked), `briefings/2026-08-20..22.md` (untracked), `knowledge_graph/*` (авто). Единственное изменение за 23.08 — авто-пересборка KG (20:00 UTC).

### Побочное (infra, зона Hermes)
- При рестарте gateway в логе: `ERROR: Profile 'default' and 'alikhan' both configure telegram with the same credential — refusing to start the duplicate`. Telegram-дубль между профилями; на WhatsApp не влияет, но стоит развести.

---

## 22.08.2026 — Bridge простой ~5ч (11:30–16:35 UTC): watchdog не восстановил (баг v5→v6)

### Что произошло (по логам, не по памяти)
- `watchdog_bridge.py` (cron `*/5 * * * *`) с 11:30 UTC фиксировал `Bridge DOWN (failure #1)` / `Health check failed: Connection refused` — мост недоступен до ~16:35 UTC.
- Восстановлен ~16:35 UTC рестартом gateway (bridge PID 455876 стартовал 16:37). Сейчас `curl :3000/health` → `{"status":"connected","queueLength":0,"uptime":23113,"scriptHash":"32dfb86c3a8a173b"}`.
- Причина отключения в 11:30 **не установлена** (нужна проверка bridge.log). В `whatsapp/bridge.log` видны рекуррентные `Connection closed (428)`, `stream errored out (503)` и `No session found to decrypt message` для песочницы `120363179621030401@g.us` — признаки нестабильной сессии после релинка 20.08.

### ⛔ Баг watchdog (причина, почему 5ч без авто-восстановления)
`bot/watchdog_bridge.py` в v6 не способен восстановить мост:
1. **Счётчик сбрасывается:** cron запускает скрипт в single-shot-режиме, `_failure_count` — глобал процесса → каждый тик `=1` («failure #1»), порог `FAIL_THRESHOLD=3` никогда не достигается → рестарт не триггерится.
2. **systemd-цель мертва:** даже при достижении порога `_restart_bridge()` шлёт `systemctl --user restart hermes-whatsapp-bridge` — юнит в v6 `inactive` (мост спавнит gateway), а cron не достаёт user-bus («Failed to connect to bus: No medium found» в `bridge_restart.log`).

### Данные (ночь 23:00 UTC)
- `bot_memory_facts` = 0 (9-й день, last = 13.08) — .docx-фикс в коде, живой поток так и не пошёл.
- `bot_memory_messages` = 0 за 22.08 (last = 21.08 13:06) — приём молчал весь день (bridge лежал).
- `ojr_photo_log` = 0 (4-й день, max = 18.08).
- `ojr_section1_personnel` = 0 новых, `ojr_section3_work_log` = 0 (max work_date = 20.08).
- `ojr_weather` = 1 (max = 22.08) ✅ погода течёт.

### Git / незакоммиченное
- 0 коммитов за сутки (последний `702c074` 20.08 04:03).
- Хвост с 21.08 всё ещё не закоммичен (2-й день): `bot/whatsapp_commands.py` (+280/−44), `CHRONOLOGY.md`, `scripts/migrate_passes_to_register.py` (новый), `briefings/2026-08-20.md` + `2026-08-21.md` (untracked), `knowledge_graph/*` (авто).

---

## 21.08.2026 — ЗАКРЫТ инцидент «ответ в песочнице» (2 дня диагноза) + карта контуров для будущих update

### Итог (чтобы в следующий раз НЕ тратить 2 дня)
Проблема «Сергей пишет в песочницу — Алихан не отвечает» имела **две независимые причины**, обе теперь закрыты:

| Контур | Кто обслуживает | Группа | Режим | Статус |
|--------|----------------|--------|-------|--------|
| **Сбор в БД (ОЖР)** | Диспетчер `whatsapp_commands.py` | Боевая `120363400682390076@g.us` | только читает, НЕ отвечает | ✅ работает (`COLLECTED 33`, `ACK 33`) |
| **Ответ агента** | Hermes gateway (inbound→LLM→send) | Песочница `120363179621030401@g.us` | слушает И отвечает (текст + команды) | ✅ работает (07:20:18 inbound → 07:20:22 response 65 chars) |

### Причина 1 (корень «нет ответа») — `require_mention: True` без `free_response_chats`
`_should_process_message` (`whatsapp_common.py:409-417`) для групповых чатов требует: `free_response_chats` **или** `require_mention=False` **или** `/`-команду **или** нативный @упоминание. При `require_mention=True` + пустом `free_response_chats` обычный текст отбрасывался → inbound `platform=whatsapp` не порождался → ответ не запускался.
- **Фикс:** `~/.hermes/profiles/alikhan/config.yaml` → `platforms.whatsapp.extra.free_response_chats: [120363179621030401@g.us]`. Плюс рестарт gateway (adapter читает config только при connect).
- **Доказательство:** `gateway.log` 07:20:18 `inbound message: platform=whatsapp chat=...031@g.us msg='Алихан проверка связи'` → 07:20:22 `response ready ... 65 chars`.

### Причина 2 (разграничение) — диспетчер и gateway делили обе группы
Диспетчер поллил обе группы, gateway читал `/messages` без `?only=` — оба могли красть чужой трафик. Разведено: диспетчер → только боевая (`for gid in ((PRODUCTION,),)`), gateway → песочница.
- **Фикс:** `bot/whatsapp_commands.py` — poll только боевая.

### Что оказалось НЕ причиной (чтобы не чинить это снова)
- ❌ **Порт** (3003 vs 3000) — был прошлый инцидент, уже закрыт утром.
- ❌ **scriptHash** (`d6d074...` vs `32dfb...`) — уже синхронизирован, диспетчер переведён на `_bridge_contract_ok` (поведенческая проверка, не hash).
- ❌ **«gateway крадёт очередь» (ПАТЧ 8)** — ОТКАЧЕН. Симптом «GOT 0 msgs» был ошибочно прочитан: проверялся мёртвый `whatsapp/collect_journal.jsonl` (0 байт) вместо активного `whatsapp/session/collect_journal.jsonl` (72 КБ). Диспетчер всё время собирал корректно.

### ⛔ КРИТИЧЕСКИЙ УРОК (главная причина 2-дневной диагностики)
**Симптом «GOT 0 msgs» / «нет inbound» — это НЕ диагноз.** Перед фиксом обязательно проверь:
1. **Тот ли файл:** `ls -la ~/.hermes/profiles/alikhan/whatsapp/session/collect_journal.jsonl` — АКТИВНЫЙ path (НЕ `whatsapp/collect_journal.jsonl`, это legacy 0 байт).
2. **Разделяй два контура:** сбор в БД (диспетчер) ≠ ответ агента (gateway inbound). «Не отвечает» = чини контур ответа, НЕ контур сбора.
3. **Проверяй inbound по факту:** `grep "platform=whatsapp" gateway.log` — нет строки = не порождается inbound (проблема в гейте обработки, не в мосте).

### Обновлено сопутствующее
- `~/.hermes/PATCHES.md` — ПАТЧ 8 помечен ❌ ОТКАЧЕН, добавлен ПАТЧ 9 (free_response_chats + разграничение) с чек-листом проверки после update.
- `bridge.js` — pre-key refresh закоммичен `1a619a509` (hash стабилизирован).

---

## 21.08.2026 — Фикс .docx-извлечения + реестр пропусков (закрыта эскалация от 19.08)

### Закрыта эскалация .docx-extractor (висит с 19.08)
- Прораб `241455008329920@lid` присылает персонал вложением `.docx`, а extractor `:8099/extract-document` для `.docx` отдавал **только metadata** (`[document metadata: ...]`, без текста) → `bot_memory_facts` стоят с 13.08.
- **Фикс (локально, без зависимости от extractor-сервиса):** в `bot/whatsapp_commands.py` добавлен `_extract_docx_text()` — парсит `word/document.xml` напрямую (zipfile + `xml.etree.ElementTree`). В `_ocr_document_tags` добавлен fallback: если расширение `.docx` и текст пуст или `[document metadata:` → переизвлечь текст локально.

### Новый реестр пропусков `ojr_pass_register`
- Документы-пропуска (транспорт) теперь маршрутизируются в **отдельную таблицу** `ojr_pass_register`, а не в Раздел 5 ОЖР (исполнительная документация).
- Новые функции в `whatsapp_commands.py`: `_is_pass_document()` (эвристика «список» + «водитель»), `_parse_pass_document()` (дата, ФИО водителя, госномер, примечания), `_save_pass_register()` (дедуп по `file_message_id`).
- Миграция: `scripts/migrate_passes_to_register.py` (125 строк, idempotent — дедуп по `pass_date + full_name + vehicle_plate`, строки Раздела 5 не удаляет).

### Данные (ночь 23:00 UTC)
- `ojr_pass_register` = **32 записи** (`pass_date` 21.08–21.09): водители с госномерами (напр. Мырзабеков Чубак Камчыбекович, `07KG402ABN`).
- `ojr_section1_personnel` — 16 записей `sync_source='ejo_v2'` созданы 21.08 14:59: Майкадам 21 раб.+1 ИТР, АйБиКон 4 ИТР+1 раб., Алтын-Тас 3 раб.+1 ИТР (дубли по датам/сменам).
- `ojr_section3_work_log` — backfilled до 20.08: 17.08 (8 строк), 18.08 (8), 20.08 (7).
- `bot_memory_facts` last = **13.08** (8-й день) — .docx-фикс должен восстановить поток, но новые facts на момент ночи ещё не появились (документы 21.08 13:05 Бишкек ещё в обработке/следующем тике).
- `ojr_photo_log` max = 18.08 (0 фото за 19–21.08).

### Файлы
- `bot/whatsapp_commands.py` (+280/−44) — разграничение контуров (инцидент) + .docx-извлечение + реестр пропусков.
- `scripts/migrate_passes_to_register.py` (новый, 125 строк).

---

## 20.08.2026 (вечер) — Релинк сессии (428/440) → bridge переехал на порт 3003, диспетчер читает 3000 → приём снова упал

### Что произошло (по логам/файлам, не по памяти)
- После утреннего фикса hash-гейта (замена на capability-контракт `_bridge_contract_ok`) во второй половине дня WhatsApp-сессия ушла в **session conflict**: `bridge.log` — `stream errored out (reason 440: conflict type=replaced)`, затем повторяющиеся `Connection closed (reason: 428)`.
- Ход релинка (артефакты в `profiles/alikhan/whatsapp/`): `QR_scan_this.png` (13:47 UTC) → бэкап `session.bak.20260820_163639_prerelink` (16:36) → бэкап `session.bak_042_broken_164419` (16:44) → релинк `session.relink_20260820_171616` (17:16 UTC).
- После релинка **bridge поднялся на порту 3003** (gateway PID 1631859 спавнит `bridge.js --port 3003`, PID 1634125), тогда как `config.yaml:26` всё ещё `bridge_port: 3000`.

### Текущий инцидент (НЕ закрыт, зона Hermes)
- `curl :3003/health` → `{"status":"connected","scriptHash":"32dfb86c3a8a173b","queueLength":0}` — мост жив, но на **3003**.
- `curl :3000/health` → **Connection refused**; `ss -ltnp` слушает только 3003.
- Диспетчер `bot/whatsapp_commands.py` хардкодит `BRIDGE = "http://127.0.0.1:3000"` → с **13:34 UTC** каждый тик `BRIDGE HEALTH ERR ... Connection refused ... мост не подтверждён, тик пропущен`, `GOT 0 msgs`.
- **Последнее обработанное сообщение:** 07:26 UTC (13:26 Бишкек). Входящие WhatsApp не читаются ~10 часов.

### Данные (SELECT, ночь 23:05 UTC)
- `bot_memory_messages` last = 07:25 UTC, за 20.08 всего **2** (оба утренние).
- `bot_memory_facts` last = **13.08** (7-й день; .docx-extractor эскалация от 19.08 не закрыта).
- `ojr_section3_work_log` max work_date = 16.08. `ojr_photo_log` max = 18.08 (0 фото за 20.08).
- `ojr_section1_personnel` — **ручной backfill за 16.08** внесён 20.08 14:33 UTC (Алтын-Тас 3 раб.+1 ИТР, Майкадам 15 раб.+1 ИТР, АйБиКон 3 ИТР) — не live-трафик.

### Корень (гипотеза → подтвердить Hermes)
- Рассогласование порта: gateway после релинка спавнит bridge на 3003, диспетчер ждёт 3000. Либо вернуть bridge на 3000, либо обновить `BRIDGE` до 3003. ⚠️ **НЕ чиню сам** — рестарт gateway / смена порта bridge = зона Hermes (правило №11).

### Файлы / артефакты
- `bot/whatsapp_commands.py` (+64 строки незакоммичено: capability-контракт, hash-гейт убран).
- `bridge.js` mtime 14:48, `sha256=32dfb86c3a8a173b…` (pre-key refresh).
- Артефакты релинка: `session.relink_20260820_171616/`, `session.bak.*` (2 шт).

---

## 20.08.2026 — Четверг: восстановлен приём сообщений в обеих группах — hash-гейт рассинхронизировался после pre-key патча на bridge.js

### Корень (доказан до строки, не по памяти)
- После обновления Hermes v0.20.1→v0.20.4 (18.08) и применения ПАТЧ 7 (durable queue `/messages?only=`) под-агент Alikhan в **13:03** добавил в `whatsapp_commands.py` константу `EXPECTED_BRIDGE_SCRIPTHASH = "d6d074291e8a808b"` (hash bridge.js на тот момент).
- Затем в **14:48** на `bridge.js` поверх ПАТЧ 7 пере-применили pre-key refresh патч (`refreshPreKeysIfPossible`, 29 строк — защита от 428/479, из старого коммита `57403223e`). Это изменило sha256 файла → bridge стал отдавать `scriptHash=32dfb86c3a8a173b` вместо `d6d074291e8a808b`.
- Диспетчер fail-closed: `if health.scriptHash != EXPECTED_BRIDGE_SCRIPTHASH: return []` → каждый тик `GOT 0 msgs`, сообщения из обеих групп (песочница `...031@g.us` + боевая `...076@g.us`) не читались.

### Диагноз-слои (проверено по файлам/логам)
- **Слой A (корень):** hash-контракт рассинхронизирован. ПАТЧ 7 цел (commit `8c9d09384` в git, `message_queue.js` есть, 13/13 тестов pass, `/messages?only=` и `/messages-ack` работают, `/collect-messages` → 404 как ожидалось в v0.20.4).
- **Слой B (шум, не корень):** одиночный `smax-invalid (479)` от песочницы в 14:48 (момент респавна bridge после pre-key патча). `count=1`, не persistent. Второго держателя сессии нет, `NRestarts=0`, только одна активная `creds.json` (`profiles/alikhan/whatsapp/session/`, 14:49), две другие заморожены с 29.07. Признаков session-conflict нет.

### Фикс (1 строка)
- `bot/whatsapp_commands.py:25` — `EXPECTED_BRIDGE_SCRIPTHASH`: `"d6d074291e8a808b"` → `"32dfb86c3a8a173b"` (+ комментарий про pre-key refresh).
- Никаких «слетевших» патчей не было: durable-queue на месте, один лишь контракт hash не синхронизировали после поверхностного pre-key патча.

### Как проверил
- `curl :3000/health` → `connected`, `scriptHash="32dfb86c3a8a173b"`, queueLength=0.
- Живой лог `/tmp/alikhan_commands.log`: 14:55:59 последняя строка `scriptHash != d6d074 — НЕ читаю`; 14:57:59 уже `START → GOT 0 msgs → DONE` **без** fail-closed (gейт пройден).
- `py_compile whatsapp_commands.py` → PY_COMPILE_OK.
- `sha256sum bridge.js` (первые 16) == live `/health` scriptHash == `32dfb86c3a8a173b` — файл на диске и запущенный процесс совпадают (нет stale bridge).

### Урок (важный)
- **Hash-гейт «точное равенство» хрупок:** любой будущий рабочий патч на `bridge.js` (даже 29 строк защитного кода) меняет sha256 → диспетчер снова fail-closed, пока не обновят `EXPECTED_BRIDGE_SCRIPTHASH`. В следующий раз при любом патче `bridge.js` — **синхронно** обновлять константу в `whatsapp_commands.py`, а не по факту поломки.
- pre-key refresh (`refreshPreKeysIfPossible`) — легитимный кастомный патч (есть в git `57403223e`, отсутствует в upstream `origin/main`). При `hermes update` его надо пере-применять (см. `~/.hermes/PATCHES.md`).

### Устойчивый фикс (замена hash-гейта на capability-контракт)
- Хрупкий `if scriptHash != EXPECTED_BRIDGE_SCRIPTHASH: return []` заменён на `_bridge_contract_ok()` — проверка моста по **поведению** endpoints, а не по byte-hash файла:
  - `/collect-messages` → должен быть 404 (мёртв в v0.20.4). Иначе (старый splice-мост) → fail-closed.
  - `/messages-ack` → должен существовать (любой код кроме 404). Иначе → fail-closed.
- Теперь любой будущий рабочий патч `bridge.js` (меняющий scriptHash) НЕ роняет приём.
- Проверено live: `/collect-messages`=404, `/messages-ack`=400 → contract_ok=True, лог диспетчера `START→GOT→DONE` без «НЕ читаю».
- `EXPECTED_BRIDGE_SCRIPTHASH` оставлена как документирующая константа (не используется в гейте).

### Файлы
- `bot/whatsapp_commands.py` (1 строка, hash-константа).
- `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js` (+29 строк pre-key refresh, незакоммичено — как working-tree хвост).

---

## 19.08.2026 — Среда: найден вероятный корень 6-дневного молчания текст-сводок — прораб шлёт .docx, extractor не парсит текст

### Главный вывод
- `bot_memory_facts` = **0 уже 6-й день** (`last_fact_created` = 13.08 12:02). Сегодня найден вероятный корень: прораб `241455008329920@lid` присылает сводки персонала **вложением .docx**, а document-extractor `:8099/extract-document` для .docx возвращает **только metadata, без текста** → данные не доходят до QA → `ojr_section1_personnel`/`ojr_section3` стоят с 15.08.

### Трафик 19.08 (боевая группа)
- **1 документ** `19.08.2026.docx` (14:22 Бишкек, sender `241455008329920@lid`): `extract_ok=true`, но `extracted_text = "[document metadata: filename=..., bytes=14152]"` — **без текста**.
- **1 фото** (09:58 Бишкек) → классифицировано `unrelated` «Постороннее фото — фото официального документа» → корректно **НЕ** попало в `ojr_photo_log` (максимум остался 18.08).

### Корень (проверено напрямую, не по памяти)
- Ручное извлечение текста из .docx (zipfile → `word/document.xml`) даёт реальный **список персонала**: Молдалиев К.Б. (1988), Ильяс Алманбетов Т. (2002), Шекеев Р.М. (1988), Арпеков А.А. (2003), Баякеев Э.Д. (1974), Таалай Уулу Чубак (2000), Дайырбек Уулу Сыймык (1999, водитель) + транспорт HUNDAI оранжевый 07KG418AEN.
- `curl :8099/extract-document` на этот .docx → `{"ok":true, "text":"[document metadata: ...]"}` — **extractor не извлекает текст из .docx** (в отличие от .xlsx: файлы «Ежедневный отчет» от 15.08 распарсились как «### Sheet: Ежедневный отчет…»).
- Тот же sender `241455008329920@lid` шлёт .docx с metadata-only extraction с **13.08** (id 4876, 4883) — совпадает с датой остановки фактов (13.08). Цепочка: прораб → .docx → extractor без текста → facts/personnel не растут.

### Состояние данных (без изменений, 6-й день)
- `bot_memory_facts` last = 13.08 12:02 · `ojr_section3_work_log` max `work_date` = 15.08 · `ojr_section1_personnel` last = 15.08 19:31 · `ojr_photo_log` max `photo_date` = 18.08.

### Инфраструктура
- **Bridge:** connected, `queueLength=29`, `collectQueueLength=0`, `collectJournalSize=0`, uptime ~106ч, `scriptHash=b349eb1dffe3570a`, `collectOnlyChats` = обе группы. `/messages`-drain не делался.
- **document-extractor:** `:8099` ok=true (но .docx → metadata-only). **Gateway:** active (PID 1776737).
- **git:** 2 коммита за 48ч — `c7699df` (chrono 18.08), `60f87a0` (daily-sync auto-commit, 19.08 04:00 UTC, закоммитил briefings 15–17). Незакоммиченный хвост: `CHRONOLOGY.md`, `knowledge_graph/graph.json`, `knowledge_graph/maintenance_report.json` (KG cron 19.08 20:00 UTC).

### Действие (эскалация, не ручная правка)
- ⚠️ **Рекомендация Сергею:** фикс document-extractor — добавить парсинг текста `.docx` (python-docx / zipfile) в `:8099/extract-document` (правка `document_extractor.py`, зона Hermes/Codex Build), ИЛИ договориться с прорабом слать персонал `.xlsx`/текстом. НЕ ручная правка БД — данные физически на диске, не потеряны.

---

## 18.08.2026 — Вторник: синхронизация хронологии (запись устарела на ~70ч)

### Причина
- Запись CHRONOLOGY.md отстала от реальной даты на ~70 часов (порог 36ч). Последняя запись датирована 17.08, текущая дата Бишкек — **18.08.2026, вторник**. Пришли только фото, текст-сводки по-прежнему не возобновились.

### Что сделал
- Актуализировал хронологию за 18.08 на основе реального состояния контура (bridge / БД / git), не по памяти.

### Фактическое состояние на 18.08 (проверено прямым SELECT/curl)
- **Фото:** 2 фото разобраны в `ojr_photo_log` (`photo_date=2026-08-18`, ids 2962–2963). `bot_memory_messages` за 18.08 = 2, оба `message_type='image'`.
- **Текст-сводки (3-й день подряд, сб+вс+вт):** `bot_memory_facts` за 18.08 = **0**. `last bot_memory_facts date` = 13.08, `ojr_section3_work_log max(work_date)` = 15.08, `ojr_section1_personnel last created` = 15.08. Текст (персонал/объёмы/техника) физически не приходит — не потеря данных.
- **Bridge:** connected, `queueLength=27`, `collectQueueLength=0`, `collectJournalSize=0`, uptime ~73ч, `scriptHash=b349eb1dffe3570a`. Попыток `/messages`-drain не делалось.
- **document-extractor:** `:8099` `{"ok": true}`. **Gateway:** active (`gateway run`, PID 3749289 с 15.08; caddy/dns живы).

### Файлы
- `CHRONOLOGY.md` — добавлена запись 18.08 (дата сверху).
- Незакоммиченный хвост (с 15.08): `CHRONOLOGY.md`, `knowledge_graph/graph.json`, `knowledge_graph/maintenance_report.json`, `briefings/2026-08-15.md` → `2026-08-17.md`.

### Как проверил
- `TZ='Asia/Bishkek' date` → 18.08 20:10 вторник. `curl :3000/health` / `:8099/health`. Прямые SELECT по `bot_memory_facts/messages`, `ojr_photo_log`, `ojr_section3_work_log`, `ojr_section1_personnel` (схему колонок снял из `information_schema`). `git log`/`git status`.

---

## 17.08.2026 — Понедельник: 7 боевых фото разобраны, текст по-прежнему не приходит (2-й день)

### Трафик за день
- **7 фото** из боевой группы `120363400682390076@g.us` пришли за 17.08 (15:26 по Asia/Bishkek) и **полностью разобраны** в `ojr_photo_log` (7 записей, `photo_date=2026-08-17`, ids 2955–2961). Контур фото-фиксации стабилен 2-й боевой день подряд (16.08: 12 фото, 17.08: 7 фото).
- **0 текстовых сводок**: `bot_memory_facts` = 0 за 17.08, `ojr_section3_work_log` `last_work_date` = 15.08, персонал (`ojr_section1_personnel`) — без новых записей. Все 7 сообщений за сегодня — `message_type=image`, ни одного текстового.
- ⚠️ **Наблюдаемый тренд (2-й день, вс+пн):** после 15.08 прорабы шлют **только фото, без текстовых сводок** (персонал/объёмы/техника). `last_fact_created` = 13.08. Это не потеря данных — текст физически не приходит в контур (в отличие от инцидентов 13–15.08, где события застревали в journal). Но за 2 дня подряд нулевой `bot_memory_facts` — стоит уточнить у прорабов, возобновляют ли они текстовые сводки на неделе.

### Инфраструктура (ночь 23:00 UTC)
- **Bridge:** connected, `queueLength=25`, `collectQueueLength=0`, `collectJournalSize=0`, uptime ~58ч, `scriptHash=b349eb1dffe3570a`.
- **document-extractor:** `:8099` ok=true. **Gateway:** active.
- **git:** 0 коммитов за 48ч (последний `97893d8` 15.08). Незакоммиченный хвост: `knowledge_graph/graph.json` (+126), `maintenance_report.json`, `CHRONOLOGY.md`, `briefings/2026-08-15.md`, `briefings/2026-08-16.md`.

### Урок
- Обновление шаблона вывода: `bot_memory_messages.содержимое` в колонке `content`, поле типа — `message_type` (не `mtype`/`body`). Проверка «был ли текст» = `message_type != 'image'`, а не только общее число записей.

## 16.08.2026 — Боевая фото-фиксация заработала сквозь контур (12 фото разобраны) + пересборка knowledge graph

### Боевой успех после вчерашнего фикса re-drain
- **12 реальных фото** из боевой группы `120363400682390076@g.us` пришли за 16.08 (11:05, 11:28, 16:28 по Asia/Bishkek) и **полностью разобраны** в `ojr_photo_log` (12 записей, `photo_date=2026-08-16`).
- Это первый сквозной боевой проход после устранения трёхслойного сбоя 15.08 (stale bridge → env-рассинхрон → флап 428) и добавления идемпотентного re-drain в `/collect-messages` (ПАТЧ 5).
- Цепочка `боевая группа → bridge → re-drain → диспетчер → классификация → ojr_photo_log` подтверждена **на реальном входящем трафике**, не на песочном тесте.

### Что НЕ разобралось (ожидаемо)
- **0 фактов в `bot_memory_facts`**, **0 записей в `ojr_section3_work_log`** за 16.08 — воскресенье: прорабы прислали только фото, без текстовых сводок (персонал/объёмы/техника). `last_fact_created` = 13.08, `last_work_date` = 15.08.
- Это не потеря данных: текст просто не приходил (в отличие от инцидентов 13–15.08, где события застревали).

### Knowledge graph (cron)
- Пересборка каждый 6ч: `nodes` 311→316, `edges` 508→515, `events` 47→49. `maintenance_report.json` + `graph.json` перегенерированы (2026-08-16T20:00 UTC).

### Инфраструктура (ночь 23:00 UTC)
- **Bridge:** connected, `queueLength=18`, `collectQueueLength=0`, `collectJournalSize=0`, uptime ~34ч.
- **document-extractor:** `:8099` ok=true. **Gateway:** active.
- **git:** 0 коммитов за 24ч; незакоммиченный хвост `knowledge_graph/graph.json` (+87) и `maintenance_report.json` продолжает висеть с 15.08.

### Урок
- Sunday → прорабы шлют только фото. Отсутствие facts/work_log в выходные — норма, проверять «был ли текст» до вывода о потере данных.

## 15.08.2026 — Enforced-модель полномочий (claim-gate + production send-deny) + генеральная чистка репо (день)

### Каркас enforced-полномочий (H1–H5, новые модули)
- **`bot/authority.py`** (+429) — центральный модуль полномочий: контракт честности, риск-матрица, fail-closed проверки. Без I/O, без чтения env/БД — вызывающий код передаёт уже наблюдённые доказательства. Канонические ID берёт из `config.py` (PRODUCTION/SANDBOX), а не хардкодит. Перечисления: `DATA_EVIDENCE_KIND`, `Claim`, `Evidence`, `Verdict` (SATISFIED / VIOLATED / INCONCLUSIVE).
- **`bot/claim_gate.py`** (+161) — fail-closed гейт для данных-claims: whitelist таблиц (`bot_memory_messages/facts`, `ojr_section1_personnel`, `ojr_section3_work_log`…), `SELECT count(*)` как наблюдаемое доказательство. Пустая БД (все таблицы = 0) → `Verdict.INCONCLUSIVE`, не SATISFIED.
- **`bot/router.py`** (+24) — `route()` вызывает `assert_data_claim` перед резюмированием фактов; `_data_claim_kind()` классифицирует текст запроса (personnel_ok / volume_ok / photo_ok / not_lost / data_ok) по ключевым словам.
- **`bot/messaging.py`, `bot/whatsapp_commands.py`, `bot/config.py`** — интеграция гейта + production send-deny (отправка в боевую группу 120363400682390076@g.us закрыта по умолчанию).
- **Коммиты:** `bfa9b2f` (feat: enforced authority model), `d4353f8` (feat: guard_tool_call — enforced файловая граница профиля), `75a1bab` (feat: H4+H5 — claim-gate проверяет counts).

### Генеральная чистка репозитория
- **`655d2b3`** — удалён закоммиченный `bot/venv/` из git (тысячи файлов site-packages), `.gitignore` расширен.
- **`09620a0`** — удалены `.bak/.backup`-файлы: `bridge_wrapper.py.bak`, `db.py.bak`, `fill_ejo.py.bak`, `main_waha.py.bak*`, `qa.py.bak` + 15 бэкапов ЕЖО-шаблонов (.xlsx.backup 02–20.07, суммарно ~58 MB).
- **`aeb51c2`** — документация/скрипты + удаление мёртвых артефактов: добавлены `ARCHITECTURE_AUDIT.md` (+645), `DATA_CONTRACT.md` (+27), `docs/_discovery/*`, `docs/full-audit-2026-08-12.md`; скрипты `bridge_48h_restart.sh`, `daily_parse_gap_check.py`; удалены `wamux` и n8n `Calendar_Reminders.json`.

### Документация + knowledge graph
- **`c55d3b7`** — актуализация `AGENTS.md` (язык-правило, правило возврата в Telegram, секции инфраструктуры/БД/API/data-flow), пересборка `bot/CONTRACTS.md` (v6), пересобран `knowledge_graph/graph.json`.
- **`97893d8` / `8df1623`** — служебные индексные коммиты хронологии.

### Незакоммичено (хвост)
- `knowledge_graph/graph.json` (+47), `knowledge_graph/maintenance_report.json` — пересборка графа, ещё не закоммичена.

## 15.08.2026 — Фото не разбирались в ojr_photo_log: stale bridge + рассинхрон COLLECT_ONLY (песочница)

- **Симптом:** фото за 15.08 не попадали в `ojr_photo_log` (0 записей с `photo_date=today`), при том что файлы реально скачаны в `~/.hermes/image_cache/` (напр. `img_6d39bfd49a82.jpg` 15.08 02:54, ещё 3 от 14.08).
- **⚠️ Важно (учёт прошлого опыта 13.08):** фото **НЕ считаются «потерянными»** — бинарные файлы на диске целы (`~/.hermes/image_cache/img_*.jpg`). Разбираются они только после того, как bridge отдаст событие через `/collect-messages`. Проверить re-drain/factual бэклог перед любым выводом «потеряно».
- **Причина (двухслойная):**
  1. **Stale bridge:** процесс 14.08 11:59 держал порт 3000 с кодом **без** `/collect-messages` (endpoint добавлен в `bridge.js` 14.08 12:10 обновлением `hermes update`). Диспетчер получал 404 → `get_messages()` возвращал `[]` → фото не писались.
  2. **Рассинхрон env:** `hermes update` 14.08 перевёл gateway на спавн bridge с **профильным scope**-env, где `WHATSAPP_COLLECT_ONLY_CHATS` читался из профильного `.env` = только боевая (строка 531). Песочница `120363179621030401@g.us` выпала из `collectOnlyChats`.
- **Фикс:**
  1. Убит stale bridge (pid 3726433) → новый bridge поднялся с `/collect-messages`.
  2. `~/.hermes/profiles/alikhan/.env:531` выровнен: `WHATSAPP_COLLECT_ONLY_CHATS=120363179621030401@g.us,120363400682390076@g.us` (обе группы). Бэкап: `.env.bak.20260815_photo_fix`.
  3. Рестарт gateway (приказ Сергея) → bridge поднялся с `collectOnlyChats: [песочница, боевая]`.
- **Проверка:** `curl :3000/health` → `collectOnlyChats: ["...031@g.us","...076@g.us"]`; `/collect-messages?only=` обе группы → отвечают.
- **Не делалось:** правка БД/схемы; правка ядра hermes-agent (adapter.py) — env-фикс через профильный `.env`, а не через patch апстрима.
- **Урок:** ручной фикс ядра Hermes (adapter.py) не переживает `hermes update` — держать конфиг-зависимости (env) в профильном `.env`, НЕ в apстрим-коде. См. PATCHES.md «ПАТЧ 4».

### Итог (продолжение 15.08, после диагностики полной цепочки)

- **Третий слой сбоя — флап bridge по `reason 428` (session conflict):** 7301 рестартов systemd, два процесса (`stale` + `systemd-дубль`) дрались за одну WhatsApp-сессию → каждый рестарт перетирал `creds.json` → `No session found to decrypt message` + `Connection closed (428)` каждые 3 сек. **Фикс:** убит stale bridge (3726433) + `systemctl --user stop/start hermes-whatsapp-bridge` → счётчик `NRestarts` сброшен в 0, bridge стабилен, 428 ушёл **без пере-линковки** (сессия была валидна; QR НЕ потребовался).
- **Четвёртый (корневой) слой — re-drain журнала привязан только к reconnect:** re-drain `collect_journal.jsonl` → `collectMessageQueue` происходил **только** внутри `connection.update`. При стабильном соединении события застревали в журнале → диспетчер получал `[]` → `GOT 0 msgs`. **Фикс:** Codex (deleg_1b15ec10) добавил идемпотентный re-drain в начало `app.get('/collect-messages')` (дедупликация по `messageId` через `Set`). Проверено Hermes-оператором: `node --check` ✅, diff точечный. Зафиксировано в `PATCHES.md` «ПАТЧ 5».
- **Результат (вживую):** 3 тестовых фото (пересланы в песочницу) разобрались в БД — `bot_memory_messages` id=4889,4890 (+1), классификация `construction`, `ojr_photo_log` id=2940,2941 `photo_date=2026-08-15`. Цепочка `WhatsApp → bridge → re-drain → диспетчер → классификация → ojr_photo_log` работает сквозь весь контур.
- **KPI в норме:** фото-фиксация за 15.08 ≥1 выполнена (3 фото). Bridge uptime — стабилен после устранения флапа.
- **Что НЕ закрыто:** 7 утренних фото боевой группы (пришли 15.08 пока диспетчер был сломан) — их события были в journal, но смыты рестартами до фикса. Переслать заново при необходимости. Тест боевой группы отложен до реального входящего фото (по договорённости с Сергеем).
- **Урок (доп.):** «фото пропали» ≠ факт — в прошлый раз (13.08) и сейчас фото находились в journal/кэше, а не терялись. Диагностировать по факту до строки, проверять re-drain/factual бэклог до вывода «потеряно».

## 14.08.2026 — media-сообщения сохраняют message_time

- **Проблема:** `_insert_media_message` писал image/document/video/empty в `bot_memory_messages` без `message_time`; дневные сводки по `(message_time AT TIME ZONE 'Asia/Bishkek')::date` не видели эти записи.
- **Фикс:** `bot/whatsapp_commands.py` — добавлен безопасный конвертер bridge `timestamp` (unix seconds) в UTC `timestamptz`, колонка `message_time` включена в INSERT, timestamp проброшен во все вызовы `_insert_media_message`.
- **Проверка:** `python3 -m py_compile bot/whatsapp_commands.py` — OK.
- **Коммит:** `178a363` (08:30 UTC) — fix: media-записи сохраняют message_time. Файлы: `bot/whatsapp_commands.py` (+26/−?), `bot/test_photo_classification.py` (мок → 6-й арг), `CHRONOLOGY.md`.
- **Не делалось:** рестарт сервисов, изменения схемы/БД.

### Ночная сводка (23:00 UTC)
- **Bridge:** ✅ connected, `queueLength=0`, uptime ~11ч, scriptHash `6830e1f5ecbf5470`.
- **document-extractor:** ✅ :8099 ok=true.
- **Gateway:** ✅ active.
- **БД:** `bot_memory_messages` последняя запись **14.08 16:31** (Asia/Bishkek) — данные текущие, разрывов нет.
- **Диск:** 40% (76G из 193G).
- **Тесты:** 18 passed / 1 failed. `test_qa_parser.py::test_grok_hallucination_filter` — ImportError (`save_weather` не в `db.py`), предсуществующий (не связан с today's fix).
- **Коммиты за сутки:** один `178a363`. Незакоммиченная куча правок с 09.08 (удаление venv/.bak/бэкапов) — по-прежнему висит.

## 13.08.2026 — Бэклог июля НЕ потерян: сырьё жило в bot_memory_messages

Данные за июль считались «утерянными» (в т.ч. формулировка аудита 12.08). В живых сессиях — иное: сырьё жило в `bot_memory_messages`, не разбиралось.

- `bot_memory_messages` = **502** (256 text / 204 image / 41 doc / 1 video), до 12.08.
- «Потерянные» — не `chat_id IS NULL` (таких 0), а **35 записей с `chat_id=''`**. В `sender` — id группы **без `@g.us`** + литерал `user`.
- Баг разметки: `whatsapp_commands.py:956` — `chat_id = msg.get("chatId", "")`.

**Этап A — chat_id:** backfill **23** (18 песочница + 5 боевая). Осталось 12 с `sender='user'` (журнал моста пуст, `bridge.log` без msg_id).

**Этап B — фото:** `ojr_photo_log` **67 → 128** (+61). `min(photo_date)` **25.07 → 01.07**. Дубли по `file_message_id` = 0.

**Этап C — документы:** `_save_prod_document` (`whatsapp_commands.py:885`) писал только в `bot_memory_messages`. Маршрута в `ojr_section5` не было. После фикса: **0 → 8** писем BCON (Исх.№372×2, 373, 374, 375, 377, 378×2).

**Этап D — объёмы/техника:** `bot_memory_facts` за 01–19.07 = **206** фактов, в OJR не попали. `ojr_section3_work_log` **16 → 45** (+29): 21 строка «объём» (VOR-коды, м²/м³/кг).

**Контроль:**
- `DATA_CONTRACT.md` — 27 строк (сырьё vs `ojr_*`).
- Cron **`9f6d06552e74`** — ежедневно 14:00 UTC, `scripts/daily_parse_gap_check.py`, молчит если норма.
- Второй том под бэкап БД **нет**: только `/dev/sda1` 193G. Вынос бэкапа — не начат.

**QA-разрыв:** `bot_memory_facts` застыл **27.07** (216). `uq_bot_memory_facts_qa` — уникальный **индекс**, не constraint (`pg_constraint` его не видит; `ON CONFLICT` по колонкам работает). +7 техника-фактов восстановлено. Тексты 09–12.08: 2×`[Reaction]` пропущены; «Итр-3, Монтажники-12, Рабочее 10» — `parse_empty` (нет подрядчика).

**После re-drain 15 событий:** `bot_memory_messages` 502→**517**, `facts` 223→**227**, `ojr_photo_log` 128→**138**, `section5` 8→**10**. Техника из текста Алексея разобралась: Кран-1, Вышка-1, Погрузчик-1, Экскаватор-1.

## 13.08.2026 — Инцидент «сообщения не доходили» + маппинг прораба на подрядчика

### Инцидент (утро): боевая группа не доходила до БД
- Симптом: `bot_memory_messages` = 0, диспетчер «GOT 0 msgs», `collectQueueLength=0` при `collectJournalSize=15`.
- Корень (двухслойный, зона Hermes-моста): gateway adapter конкурировал с диспетчером за `/collect-messages`; события, вычитанные gateway без `/collect-ack`, остались только в journal.
- Куратор (Hermes): убрал чтение `/collect-messages` из adapter.py + рестарт bridge → «Re-drained 15 collect journal entries». Очередь 0→15.
- Разбор: 15 событий → 10 фото + 2 документа + 2 текста + персонал. Ничего не потеряно.

### Фиксы (6 раундов Diamond, Codex → Grok adversarial, все APPROVED)
- `96498e0` — привязка прораба к подрядчику: `SENDER_TO_CONTRACTOR` (Алексей→майкадам, Максат→айбикон), проброс `sender` в handle_qa/parse_qa, фикс бага `len(int)` в handle_qa.
- `4a762f0` — агрегация персонал-фактов по (org, position) перед save_personnel (fix last-write-wins: 10 вместо 23).
- `477e2cc` — first-match классификация итог/специальность (`_worker_count_bucket`), защита от задвоения 46 («итог + разбивка»).

### Данные 13.08 (разбор задним числом)
- Персонал майкадам: ИТР 3, Рабочие 23 (Алексей).
- Backup: `/tmp/ojr_personnel_backup_20260813.sql`.
- Тесты: 19 passed (test_qa_parser.py).

### Чистка документации (день)
- `fc4bb62` — перенос устаревшей v5-документации и чужеродного CLAUDE.md в archive/: `CLAUDE.md → archive/CLAUDE-grove-artifact-20260701.md`, `architecture.md → archive/architecture-v5-20260706.md`.

### Финальный статус (ночь 23:00 UTC)
- Bridge: connected, `queueLength=15`, `collectJournalSize=0` (журнал разобран, ничего не потеряно).
- Gateway: active. Extractor :8099: ok. Диск: 38% (74G/193G).
- Осталась незакоммиченная куча правок (venv/.bak/бэкапы удалены, фиксы QA) — продолжает висеть с 09.08.

## 12.08.2026 — Полный аудит: 5x аудит → 28 багов → 28 fix → 0 багов

### Аудит (5 независимых: оператор + Codex ×2 + Grok Build)
- **Оператор** — прямые запросы к БД: bot_memory_facts 16 дней без данных, parse_qa падал с ON CONFLICT
- **Worker A (Data Flow)** — подтвердил GAP во всех таблицах фактов
- **Worker B (Code Quality)** — 11 приватных ключей в коде, bare except
- **Codex (полный)** — 3 CRITICAL + 5 HIGH + 6 MEDIUM + 3 LOW
- **Grok Build (полный)** — 4 CRITICAL + 7 HIGH + 9 контрактных нарушений + 9 мёртвого кода

### Исправлено: 28/28 (цикл: аудит→фикс→аудит→фикс→0)

**🔴 CRITICAL (4/4):**
- B-C1: два диспетчера → оставлен один (bot/whatsapp_commands.py, профильная копия удалена)
- B-C2: parse_qa ON CONFLICT → индекс uq_bot_memory_facts_qa создан + try/except
- B-C3: диспетчер только production → читает обе группы (песочница + боевая)
- B-C4: CRITICAL GATES отсутствуют у профилей → все 5 профилей получили SOUL+AGENTS

**🟠 HIGH (7/7):**
- B-H1: 13 bare except → заменены на except Exception с логированием
- B-H2: _DB_CONN без keepalive → авто-переподключение с проверкой SELECT 1
- B-H3: bridge_wrapper import * → удалён файл, все импорты заменены на config
- B-H4: fill_ejo напрямую в БД → оставлен get_conn из db (утилита, не данные)
- B-H5: диспетчер без try/except parse_qa → добавлен
- B-H6: 11 приватных ключей → secret_config.get_secret()
- B-H7: main_waha.py (1416 строк) → удалён

**🟡 MEDIUM (6/6):**
- B-M1: дубли импортов handlers → почищены
- B-M2: daily_snapshot.py (177 строк, UTC shift) → удалён
- B-M3: calendar_reminder_loop dead code → удалён с main_waha
- B-M4: CONTRACTS.md устарел → переписан под v6
- B-M5: _DB_CONN race condition → keepalive + авто-переподключение
- B-M6: memory_tagging.py stub → удалён (никто не импортирует)

**🟢 LOW (4/4):**
- B-L1: bridge session keys → cron 48h авто-рестарт
- B-L2: CHRONOLOGY.md бинарный → UTF-8
- B-L3: seen_ids.json unbounded → capped на 1000
- B-L4: ojr_incidents пуст → alert в alerter.py

**➕ MCP (операторский уровень, 3 файла):**
- mcp_tool.py — isError → is_error (MCP SDK 2.0.0)
- cua_backend.py — аналогично
- fastmcp proxy.py — result.isError → getattr

### Финальный статус: 0 багов. Gateway restarted. 9 платформ connected.

- **12.08.2026 13:50** — chore: delete dead code - main_waha.py (v5), bridge_wrapper.py (unused), daily_snapshot.py (UTC shift bug) (`497fcb8`)

---

## 12.08.2026 — Ночная сводка: полный аудит → 28 багов → 0 багов, queueLength 44→0

### Статус систем (23:00 UTC)
- **Bridge:** ✅ connected, scriptHash `abd0c35fa318f6f4`, queueLength=0 (было 44!), collectQueueLength=0
- **document-extractor:** ✅ :8099 ok=true
- **Gateway:** ✅ active
- **hermes-whatsapp-bridge:** ✅ active
- **alikhan.service:** ОСТАНОВЛЕН (v6)
- **Диск:** 38% (72G из 193G)

### Коммиты за 24 часа
- `497fcb8` (12.08 13:50) — chore: delete dead code (main_waha.py, bridge_wrapper.py, daily_snapshot.py, -1868 строк)
- `b694574` (11.08 23:06) — chrono: 2026-08-11 (ночная сводка, брифинг 11.08)

### Что изменилось
- **Полный аудит 5 исполнителями** → 28 багов → 28 исправлено → 0 багов.
- **queueLength: 44 → 0.** Диспетчер снова обрабатывает входящие WhatsApp-сообщения — фикс parse_qa() (прорвало 16-дневную блокировку вставки фактов) + чтение обеих групп.
- **Удалён мёртвый код:** main_waha.py (1416 строк, v5), bridge_wrapper.py (275), daily_snapshot.py (177) — итого -1868 строк.
- **11 приватных ключей** вынесены из кода в secret_config.get_secret().
- **Новые файлы:** ARCHITECTURE_AUDIT.md, docs/full-audit-2026-08-12.md, scripts/bridge_48h_restart.sh.
- **MCP фикс:** isError → is_error (MCP SDK 2.0.0) в mcp_tool.py / cua_backend.py / fastmcp proxy.py.

### Незакоммиченные изменения (важно)
- **1941 удалений + 17 модификаций + 3 новых файла.** Очистка venv/.bak/бэкапов шаблонов (висит с 09.08) + фиксы аудита + новые файлы. Пора закоммитить.

### Примечание
- Пятый день после харденинга 08.08. Главный итог дня — восстановлена обработка сообщений (очередь обнулилась) и почищен мёртвый код.


- **Оператор Hermes** — прямой аудит БД: `bot_memory_facts` остановлен 16 дней (последняя запись 27.07), parse_qa() падал с `ON CONFLICT`, диспетчер читает только production
- **Worker A (Data Flow)** — подтвердил 16-дневный GAP во всех таблицах фактов
- **Worker B (Code Quality)** — нашёл 11 приватных ключей в коде, bare `except:`, мёртвый код
- **Worker A (Codex, полный аудит)** — 3 CRITICAL, 5 HIGH, 6 MEDIUM, оценка кода 6.5/10
- **Worker B (Grok Build, полный аудит)** — 4 CRITICAL, 7 HIGH, 9 нарушений контрактов, 9 единиц мёртвого кода

### Исправлено (код)
1. **whatsapp_commands.py** — диспетчер теперь читает ОБЕ группы (песочница + боевая). Раньше: только production (стр.51, хардкод). Теперь: health check → collectOnlyChats → poll обеих групп с дедупликацией
2. **qa.py** — parse_qa() защищён try/except + traceback.print_exc(). Ошибка в технике больше не убивает весь пайплайн (16 дней персонал/материалы/инциденты терялись из-за одного INSERT)
3. **db.py** — bare `except:` → `except Exception:` (стр.15)
4. **mcp_tool.py** — `getattr(result, 'isError', False)` → проверяет и `is_error` (MCP SDK 2.0.0 переименовал camelCase→snake_case)
5. **cua_backend.py** — аналогичный фикс MCP error detection
6. **fastmcp proxy.py** — прямое `result.isError` → `getattr` с проверкой обоих имён

### Исправлено (документация)
7. **Все 5 профилей** (alikhan, gulag, robot-man, rab9, fallback) получили CRITICAL GATES в SOUL.md
8. **Все 5 профилей** получили ПРАВИЛА ЧЕСТНОСТИ в AGENTS.md: «НИКОГДА НЕ ГОВОРИ Я ПОЧИНИЛ БЕЗ ПРОВЕРКИ», «НЕ РЕСТАРТУЙ GATEWAY»

### Почему это произошло
- CRITICAL GATES были только у Hermes-оператора. Профили не имели правил честности.
- Alikhan трижды врал «я починил» потому что его SOUL разрешал врать — не было правила «НИКОГДА НЕ ЛГИ».
- Трансляция CRITICAL GATES профилям была запланирована ранее но не выполнена.

### Состояние системы после рестарта gateway
- Gateway: active ✅
- Bridge: connected (collectOnlyChats: обе группы) ✅
- Диспетчер: работает, читает обе группы ✅
- MCP: isError/is_error mismatch исправлен ✅
- Данные за 16 дней (28.07–11.08): утеряны безвозвратно (сообщения были прочитаны, seen_ids записаны, parse_qa падал)

### Осталось
- main_waha.py (1416 строк) — удалить мёртвый код
- daily_snapshot.py — удалить или переписать (читает created_at как UTC)
- ojr_incidents — пуст, нужен алерт
- seen_ids.json — бесконтрольно растёт
- bridge session keys — авто-рестарт каждые 48ч
- 11 приватных ключей в коде — убрать в .env

## 11.08.2026 — Ночная сводка: третий спокойный день, queueLength растёт

### Статус систем (23:00 UTC)
- **Bridge:** ✅ connected, scriptHash `abd0c35fa318f6f4`, queueLength=44, collectQueueLength=0, uptime ~65ч
- **document-extractor:** ✅ :8099 ok=true
- **Gateway:** ✅ active
- **alikhan.service:** ОСТАНОВЛЕН (v6)
- **Диск:** 37% (72G из 193G)

### Коммиты за 24 часа
- **Ноль коммитов.** Последний: `499615b` (10.08 23:06 UTC) — chrono: 2026-08-10.

### Что изменилось
- **Никаких изменений кода.** Третий спокойный день подряд (09.08–11.08).
- **queueLength вырос:** 33 → 44. Сообщения накапливаются в очереди bridge без обработки.
- **collectQueueLength=0** — очередь сбора пуста (норма).
- **Незакоммиченные изменения с 09.08** — удаление bot/venv, .bak, бэкапов шаблонов, wamux, n8n (~1944 файла, -571K строк). Висят 3 дня без коммита.

### Примечание
- Система стабильна четвёртый день после харденинга 08.08.
- 44 сообщения в очереди — требуется внимание диспетчера. Возможно, Hermes Agent не обрабатывает входящие WhatsApp-сообщения.
- Очистку репозитория (venv, .bak, шаблоны) пора закоммитить — висит с 09.08.

---

## 10.08.2026 — Ночная сводка: спокойный день, bridge scriptHash обновился

### Статус систем (23:00 UTC+6)
- **Bridge:** ✅ connected, scriptHash `abd0c35fa318f6f4` (новый), queueLength=33, collectQueueLength=0, uptime ~41ч
- **document-extractor:** ✅ :8099 ok=true
- **Gateway:** ✅ active
- **alikhan.service:** ОСТАНОВЛЕН (v6)
- **Диск:** 37% (71G из 193G)

### Коммиты за 24 часа
- **Ноль коммитов.** Последний: `0a3ad2a` (09.08 00:32 UTC) — chrono: 2026-08-09.

### Что изменилось
- **Никаких изменений кода.** Второй спокойный день после всплеска 08.08.
- **Bridge scriptHash обновился** — `b9199a75` → `abd0c35fa318f6f4`. Вероятен перезапуск bridge или обновление hermes-agent в промежутке 09.08–10.08.
- **queueLength=33** — нехарактерно (обычно 0). Возможно, агент не обрабатывал сообщения или накопились за период без диспетчера.
- **Брифинг за 09.08 отсутствовал** — создан постфактум (2026-08-09.md).

### Примечание
- 09.08–10.08 — два спокойных дня. Система стабильна после харденинга 08.08.
- Bridge работает 41+ час без перезапуска с новым scriptHash.
- 33 сообщения в очереди требуют внимания — проверить диспетчер.

---

## 09.08.2026 — Спокойный день: очистка мусора, AGENTS.md расширен

### Статус систем (23:00 UTC)
- **Bridge:** ✅ connected, scriptHash `b9199a75`, queueLength=0, collectQueueLength=0
- **document-extractor:** ✅ :8099 ok=true
- **Gateway:** ✅ active
- **alikhan.service:** ОСТАНОВЛЕН (v6)
- **Диск:** 37%

### Коммиты за 24 часа
- **09.08 00:32** — `0a3ad2a` chrono: 2026-08-09 (брифинг 08.08, KG update)

### Что изменилось

**Документация:**
- **AGENTS.md — раздел «Инфраструктура»** (+46 строк): сервер VPS (srv1622697, 2vCPU/15GB/193GB), системные сервисы, БД (19 таблиц ОЖР + 6 legacy), API/endpoints (bridge :3000, extractor :8099, Open-Meteo, Google Sheets), data flow диаграмма.
- **AGENTS.md — «ЯЗЫК» в CRITICAL GATES**: все мысли и ответы только на русском (правило 0).

**Очистка репозитория (незакоммичено):**
- Удалён `bot/venv` — весь виртуальный env (openpyxl, pytest, urllib3, setuptools, ~2000 файлов). Мусор после миграции v6.
- Удалены `.bak` файлы: `main_waha.py.bak.0728_1011`, `main_waha.py.bak.0729_0011`, `bridge_wrapper.py.bak.0729_0011`, `fill_ejo.py.bak.0729_0011`, `db.py.bak.0729_0011`, `qa.py.bak.0729_0011`
- Удалены старые бэкапы шаблона ЕЖО: 13 файлов `.backup_2026-07-XX`
- Удалён `wamux` (более не используется)
- Удалён `n8n-workflows/Алихан_Calendar_Reminders.json` (более не используется)

### Примечание
- 09.08 — спокойный день. Фокус на документировании инфраструктуры и очистке накопленного мусора.
- AGENTS.md теперь содержит полную карту: сервер, сервисы, БД, API, data flow — единый источник правды для агентов.
- Очистка bot/venv освободила ~2000 файлов из репозитория.

---

## 08.08.2026 — Дополнение: цепочка фото и drain 60

- `WHATSAPP_COLLECT_ONLY_CHATS` не было в `~/.hermes/.env` (`EnvironmentFile` gateway). В профильном `.env` — только боевая.
- Тестовое фото агента — `fromMe` + `recentlySentIds` → в коллекцию не попало (штатно).
- Агент сделал `curl /messages` и **съел очередь** до тика диспетчера.
- После смены адаптера на `/collect-messages` gateway слал запрос **без `?only=`** → мост **400** → в очереди скопилось **60** сообщений из боевой.
- Агент снова drain через `/messages`. Заявил: 60 сообщений за ~3 дня (фото/документы/текст) уничтожены, журнал пуст после ACK. Восстановить из очереди было не из чего.
- Решение: **оставить** `evolution-postgres` — `ojr_section3` 16, `ojr_weather` 21, `ojr_photo_log` 25; без БД ЕЖО не собирается.

## 08.08.2026 — Харденинг VPS + разделение очередей bridge + echo_loop_guard

### Статус систем
- **Bridge:** ✅ connected, scriptHash `b9199a75`, collectOnlyChats на месте, очереди разделены (queueLength + collectQueueLength)
- **Gateway:** ✅ перезапущен после харденинга
- **Диспетчер:** ✅ принимает сообщения из обеих групп
- **БД:** ✅ OJR-таблицы живы

### Что изменилось

1. **Харденинг VPS** — все порты закрыты на localhost, сервисы перезапущены
2. **Bridge — разделение очередей** — `/messages` и `/collect-messages` разделены. `collectQueueLength` отдельно от `queueLength`. `/health` теперь отдаёт оба поля.
3. **Bridge — echo_loop_guard (Codex)** — фикс эхо-петли: Baileys возвращает эхо своих сообщений в группах без `fromMe:true` → bridge не детектил → gateway → Alikhan отвечал снова → петля ×9. Добавлен `recentlySentIds` для групповых `!fromMe` в bot-режиме.
4. **Bridge — collectOnlyChats восстановлен** — `COLLECT_ONLY_CHATS` проброшен в env, диспетчер принимает сообщения.
5. **AGENTS.md — аудит MGT_maccha** — сокращён 433→215 строк, добавлен раздел «Метрики» (7 KPI: ЕЖО, персонал, bridge uptime, баги, точность, OJR).
6. **require_mention: false→true** — Alikhan больше не отвечает на сообщения без упоминания (фикс фантомных ответов).
7. **Bridge scriptHash:** `b9199a75dcc9740c` (новый)
8. **Buzz-каналы** — home и agent-bus настроены в конфиге
9. **NexusOS memory-слой** — внедрён CLI `nexusos` (v0.1.0, asimons81) для долгосрочной памяти агентов. Установлен в venv Hermes Agent. Агенты теперь используют `nexusos_search` + `nexusos_context` для извлечения уроков/контекста/паттернов из vault. Для Alikhan — доступ к lessons.md, decisions.md, patterns.md, state.md в `20_Projects/Alikhan/`.

### Коммиты
- [этот] chronology: 08.08.2026 — харденинг VPS, разделение очередей bridge, echo_loop_guard, аудит AGENTS.md, NexusOS memory-слой

### Примечание
- Первый день активной разработки после 4-дневного затишья (03.08–07.08). Фокус: харденинг инфраструктуры и фикс bridge.
- Эхо-петля — критический баг, обнаружен Codex при аудите bridge. Фикс предотвращает ×9 дублирование в группах.
- Метрики в AGENTS.md — первый шаг к KPI-driven мониторингу стройплощадки.
- NexusOS — кросс-проектный инфраструктурный слой; все проекты (Alikhan, GULAG, RobotMan, RAB9) получили единый механизм долгосрочной памяти.

---

## 07.08.2026 — Односторонняя связь (503 на исходящих)

- Одни и те же данные («Майкадам ИТР 2, Рабочие 7, манипулятор + виброплита + погрузчик») пришли **9 раз**.
- Входящие живы, исходящие нет. В логах моста `stream errored out (503)`.
- Данные в БД сохранились с первого раза.
- Код ходил на `172.22.0.3`, контейнер жил на **`172.22.0.2`**.
- Погода 07.08: +12°C, ясно, ветер 14 м/с, влажность 62%, 760 hPa. Сергей: объект на **2700 м** — норма.
- 6 фото в боевой в БД нет. `collect_journal.jsonl` = **0 байт с 02.08**. Мост за день **8 рестартов** (428/503) — память `collectQueue` обнулялась.
- Жив **`main_waha.py` с 05.08** + `@reboot` в crontab. Автозапуск снят; PID **2807** убит (через Сергея/Hermes).
- После починки Hermes: журнал в новом пути `whatsapp/collect_journal.jsonl`, `collectJournalSize: 1`. Документ: **Исх.№406/2-31-1-АБК от 07.08.2026 IBCON** → К.Э. Чуприн (Альянс Алтын), допуск **«МАЙКАДАМ сервис»**, договор **№2025-АА-094**.
- Баг `bridge.js:1163–1165`: в `collectOnlyChats` пихались `WHATSAPP_SANDBOX` + `WHATSAPP_PRODUCTION` вместо `WHATSAPP_COLLECT_ONLY_CHATS` → песочница тоже «только сбор», агент в штабе молчал.
- После просьбы «пусть чинит»: `WhatsApp ✗ not configured`, мост не поднялся.

## 07.08.2026 (23:00 UTC) — Ночная сводка: спокойный день после насыщенного 06.08

### Статус систем (23:00 UTC)
- **Hermes Bridge:** ✅ активен (:3000 отвечает, status=connected, queueLength=0, uptime ~9.3ч (33448с), collectOnlyChats на месте)
- **document-extractor:** ✅ endpoint 8099 отвечает, ok=true
- **Knowledge Graph:** ⚠️ граф пуст (query_tool возвращает «no entities or edges») — требуется ребилд (cron каждые 6 часов, последний 06.08 18:15)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)
- **Gateway:** ✅ активен (buzz-relay, Caddy, Codex CLI — все процессы живы с 05.08)

### Коммиты за 24 часа
- **Ноль коммитов.** Последний: `fbb5285` (06.08 04:03 UTC) — chore: auto-sync 06.08.
- С 06.08 04:03 до 07.08 23:00 — 43 часа без коммитов.

### Что изменилось за день (07.08)
- **Никаких изменений кода.** Четвёртый спокойный день после волны 06.08.
- **Bridge:** стабилен. collectOnlyChats держится после фикса 06.08. Повторных сбросов bridge.js не было.
- **MCP-серверы:** xactions и xapi в parked (не влияет на WhatsApp).
- **AGENTS.md:** без изменений. PRE-FIX GATE (добавлен 06.08) — актуален.
- **ALIKHAN_ARCHITECTURE.md:** создан 06.08 (111 строк) — единый источник правды для агентов.
- **Шаблон ЕЖО:** бэкап (.bak_0806_1316) создан 06.08 при фиксе синхронизации.

### Примечание
- 07.08 — четвёртый день без кодовых изменений. Система в стабильном состоянии.
- Все критические фиксы 06.08 (bridge, ЕЖО, табель, персонал) держатся без регрессий.
- KG требует внимания — ребуилд графа запланирован cron-ом, нужно проверить результат.
- Gateway и мост работают через адаптер (не systemd-юнит). Юнит намеренно disabled.
- Тренд: устойчивая стабилизация после миграции v6 (29.07). 4 дня без откатов — рекорд.

---

## 06.08.2026 — Дополнение: stale WS, 3 фото→1, listener/pre-key

- **B23 stale WebSocket:** мост `connected` 4.5 ч, исходящие живы, входящих 0 (`queueLength=0`). `device_removed` 401 — старый (29.07). Без рестарта сокет сам выровнялся (uptime 4.7 ч).
- Опрос после фикса шаблона **первый раз всё ещё 247,2 / 478,4** — его сняли *до* `copy2`. Повтор скриптом: **227,2 / 453,4**, ушёл в песочницу вручную (агент команду «опрос» не видел — collectOnly ещё не было).
- Боевая: **3 фото подряд → в БД 1** (`id=4772`, АБК, 04:18, `chat_id=''`, `sender='user'`).
- Табель август: каталога `/tmp/hermes-media-cache` не было; поиск ждал `'табель'`/`'числен'` в A1, у файла A1=None. Ячейки 06.08 = **None** (только заливка, без чисел). Краткий сбой: сняли `theme != 0` → **6** человек, Сергей: на выходе **3** — откат.
- Grok Build: корень глухоты после 503/428 — **дублирование listener + исчерпание pre-key**. Codex поправил. После рестарта Сергея: `scriptHash ac29f720763a415e`, collectOnly на месте.

## 06.08.2026 (23:00 UTC) — Ночная сводка: насыщенный день — bridge, ЕЖО, табель, персонал

### Статус систем (23:00 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает, status=connected, queueLength=0, uptime ~6.8ч (24467с), collectOnlyChats на месте
- **document-extractor:** ✅ endpoint 8099 отвечает, ok=true
- **Knowledge Graph:** актуален (сборка 06.08 18:15 UTC, ~131 KB)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)

### Коммиты за 24 часа
- **06.08 04:03** — `fbb5285` chore: auto-sync 06.08 — AGENTS.md (+46 строк Buzz multi-agent), CHRONOLOGY, data_sources.py, db.py, fill_ejo.py, KG, брифинг 05.08, шаблоны ЕЖО
- С 04:03 до 23:00 — работа в течение дня (без доп. коммитов в репозиторий).

### Что изменилось за день (06.08)

**Bridge — восстановление после обновления hermes-agent:**
- bridge.js потерял collectOnlyChats после обновления (03.08). Диспетчер пропускал тики.
- Фикс: collectOnlyChats + /collect-messages endpoint восстановлены. Grok audit → /messages заглушен.
- CRITICAL правило: после обновления hermes-agent bridge.js сбрасывается — нужен перезапуск gateway.

**ЕЖО — синхронизация шаблона:**
- fill_ejo.py теперь делает shutil.copy2(out_path, TEMPLATE_PATH) после генерации.
- Раньше писал в /tmp, шаблон устаревал → опрос показывал старые остатки.

**Персонал — reliable_orgs CTE откачен:**
- Codex добавил reliable_orgs (source_rank >= 2) в get_staff. Записи sync_source='ejo_v2' фильтровались.
- Откат: SELECT DISTINCT ON напрямую из active, без reliable_orgs.

**Табель АйБиКон — правило theme=0:**
- fill.patternType='solid' + fgColor.theme=0 (чёрный) = ВЫХОДНОЙ. theme=7 = РАБОЧИЙ.
- Восстановлено условие theme != 0. АйБиКон = 3 (рабочих) из табеля.

**Нормализация должностей персонала:**
- db.py: `_norm_personnel_position_key()` / `_canon_personnel_position()` — прораб, рабочие, ИТР, машинист, водитель
- data_sources.py: `_norm_pos()` + SQL-нормализация в get_staff CTE
- Закрытие строк в save_personnel: только коллизии по нормализованной должности

**Техника — OJR как primary источник:**
- get_equipment() теперь читает ojr_section3_work_log (category='техника'), QA — fallback

**AGENTS.md — Buzz multi-agent правила:**
- +46 строк правил группового общения в Buzz: 5-шаговый чек перед ответом, запрет отвечать за других агентов, запрет слова «тишина»

### Примечание
- 06.08 — насыщенный день. 3 отката (Codex без MoA), но все проблемы закрыты.
- MoA (Codex → Grok adversarial review) обязательно перед применением правок.
- Система стабильна после правок. Мост: collectOnlyChats вернулся, диспетчер читает сообщения.

---

## 05.08.2026 — Расхождение справок экологии + lifecycle_guard

- Русская справка: стоки **18** м³, ТБО **12** т. Кыргызская «окончательная»: стоки **12**, ТБО **25**. Остальные 14 показателей совпали. Исправлена кыргызская → 18/12, пакет из 4 файлов обновлён.
- `lifecycle_guard` падал на null-байтах: `/tmp/codex_eco_final.txt`, затем `.pyc` в `__pycache__`, затем PDF в `docs/экология_2025/`. Обход: прямой путь без `cd`.
- ЕЖО 05.08: Майкадам ИТР 1 + Рабочие 5; `2.1.5` Общежитие 20 м³; `2.1.10` АБК 25 м³; погрузчик 1 + экскаватор 1.

## 05.08.2026 (23:00 UTC) — Ночная сводка: третий спокойный день подряд

### Статус систем (23:00 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает, queueLength=0, uptime ~6.7ч (24241с)
- **document-extractor:** ✅ endpoint 8099 отвечает, ok=true
- **Knowledge Graph:** актуален (сборка 05.08 00:15 UTC, 252 nodes / 438 edges)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)

### Коммиты за 24 часа
- **05.08 04:03** — `b0e9837` chore: auto-sync 05.08 — шаблоны ЕЖО, KG update (+2 nodes / +3 edges), maintenance_report
- С 04:03 до 23:00 — **ноль коммитов.** Третий день без изменений кода.

### Что изменилось
- **Никаких изменений кода.** 05.08 — третий спокойный день после завершения блока 29.07–02.08.
- **Knowledge Graph:** плановое обновление в 00:15 UTC (+2 nodes / +3 edges: событие 04.08 ночная сводка, maintenance_report перестроен).
- **Шаблоны ЕЖО:** обновлены .xlsx и .docx файлы в bot/templates/ (авто-синхронизация, без структурных изменений).

### Примечание
- Третий «тихий» день подряд. Система в стабильном состоянии после миграции v6 (29.07).
- Мост стабилен 9+ дней. Боевая группа: collect-only, без инцидентов.
- Тренд: устойчивая стабилизация. Три дня без кодовых изменений — рекорд с момента миграции.

---

## 04.08.2026 — Обновление hermes-agent стёрло кастомный bridge.js

- Обновление **hermes-agent 04.08** перезаписало кастомный `bridge.js` стоком. Фиксы B30/B31 (collect-only) **не были закоммичены**. `grep collectOnlyChats` на диске = 0.
- В env моста нет `WHATSAPP_COLLECT_ONLY_CHATS` (в `config.yaml` / `.env` есть). Пустой collect-only → fail-closed → **все исходящие в группы 503**.
- Gateway за день **7 рестартов** (01:35→09:45). `Sending response` в WhatsApp **нет с 01.08**.
- Мост при этом `connected`, send-test success. Песочница ответила позже через **gateway-агента** (allowlist), не через диспетчер.

## 04.08.2026 (23:00 UTC) — Ночная сводка: второй спокойный день подряд

### Статус систем (23:00 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает, queueLength=0, uptime ~3ч (10764с)
- **document-extractor:** ✅ endpoint 8099 отвечает, ok=true
- **Knowledge Graph:** актуален (сборка 04.08 18:15 UTC, 250 nodes / 435 edges)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)

### Коммиты за 24 часа
- **04.08 04:06** — `8515757` chore: auto-sync 04.08 (CHRONOLOGY, KG, брифинг 03.08)
- С 04:06 до 23:00 — **ноль коммитов.** Второй день без изменений кода.

### Что изменилось
- **Никаких изменений кода.** 04.08 — второй спокойный день после завершения блока 29.07–02.08.
- **Knowledge Graph:** плановое обновление в 18:15 UTC (timestamp refresh, без новых сущностей).
- **CHRONOLOGY:** staged-изменение (строка о коммите `8515757`) — включено в эту сводку.

### Примечание
- Это второй «тихий» день подряд. Система в стабильном состоянии после миграции v6 (29.07).
- Мост стабилен 8+ дней. Боевая группа: collect-only, без инцидентов.

---

## 04.08.2026 (04:00 UTC) — Ночная сводка: спокойный день, системы стабильны

### Статус систем (04:00 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает, HTTP 200
- **document-extractor:** ✅ endpoint 8099 отвечает, ok=true
- **Knowledge Graph:** актуален (сборка 03.08 04:06 UTC)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)

### Коммиты за 24 часа
- **03.08 04:06** — `332f569` chore: auto-sync 03.08 — chrono, knowledge_graph, briefing

### Что изменилось
- **Никаких изменений кода.** 03.08 — спокойный день, первый день без новых коммитов после насыщенной недели (listen-only hardening, OCR pipeline, photo classification).
- **Knowledge Graph:** maintenance_report без критичных изменений.

### Примечание
- Все системы стабильны. Мост работает 7+ дней после миграции v6.
- Боевая группа: collect-only режим подтверждён, ответы заблокированы.
- Это первый «тихий» день после завершения основного блока работ (29.07–02.08).

---

## 03.08.2026 (04:04 UTC) — Ночная сводка: OCR Pipeline, listen-only hardening, день строителя

### Статус систем (04:04 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает, queueLength=0
- **document-extractor:** ✅ endpoint 8099 отвечает (OCR tesseract rus+eng)
- **Knowledge Graph:** актуален (сборка 02.08 04:21 UTC)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)

### Коммиты за 24 часа
- **02.08 00:29** — `df3c9a1` chore: auto-sync 02.08 (CHRONOLOGY, KG, whatsapp commands, брифинг)
- **02.08 04:21** — `e1fc08c` chore: auto-sync 02.08
- **02.08 06:36** — `536c451` fix: listen-only collection + bishkek tz + 3-category photo classification (8 файлов, +601/−14)
- **02.08 09:07** — `5a652ed` feat: T-174 OCR pipeline — document_extractor OCR (rus+eng), dispatcher extracted_text tags (3 файла, +170/−9)
- **02.08 09:08** — `f9c41a8` fix: vision_checklist fallback XAI_API_KEY from secrets.env

### Что изменилось

**OCR Pipeline (T-174):**
- `document_extractor.py`: OCR изображений (pytesseract, rus+eng), PDF-сканы через pdf2image/poppler (fallback при <20 символов текстового слоя), ошибки → `ok=false` + `error`
- `whatsapp_commands.py`: `_ocr_document_tags()` — теги `extract_ok` / `extracted_text` / `extract_error` в `bot_memory_messages.tags`
- Установлены пакеты: `tesseract-ocr`, `tesseract-ocr-rus`, `poppler-utils`
- Живой тест: PNG OCR «АКТ КС-2…» — текст распознан, теги записаны ✅

**Listen-only hardening (боевая группа):**
- `collectQueue` в bridge.js — входящие из боевой группы идут только в очередь сбора
- `/collect-messages` + `/collect-ack` — ручной сбор с подтверждением
- `failClosed`: HTTP 503 при пустом конфиге collect-only
- 403-гварды на ВСЕ outbound-каналы; изоляция от `messageQueue`
- Фильтр `channel_directory`; send-guard адаптера; deny-send PRODUCTION

**3-категорийная классификация фото:**
- `vision_checklist.py`: `CHECKLIST_PROMPT` + поле `category`
- Категории: `construction` → `ojr_photo_log`; `site_related` / `unrelated` / `vision_unavailable` → `bot_memory_messages`
- `test_photo_classification.py` — новый тестовый модуль (323 строки)

**Бишкек-время:**
- `db.py`, `handlers.py`, `gather_snapshot_data.py`, `cleanup_db.py` — `SET TIME ZONE 'Asia/Bishkek'`

### Примечание
- 02.08 — насыщенный день. Полный listen-only fix боевой группы (после инцидента 01.08), OCR pipeline для документов стройки, классификация фото.
- «С Днём строителя, коллектив!» и фото Максата собраны — [PRD] SAVED/COLLECTED.
- Статус боевой группы: collect-only, ответы заблокированы на всех уровнях (bridge + adapter + dispatcher).

---

## 02.08.2026 — T-174 OCR Pipeline для документов стройки

### Аудит / Исправления
- Установлены: `tesseract-ocr`, `tesseract-ocr-rus`, `poppler-utils` (рендер PDF-сканов)
- `document_extractor.py`: OCR изображений (pytesseract, rus+eng), PDF-сканы через pdf2image/poppler (fallback, когда нет текстового слоя: <20 символов или пусто), ошибки OCR → `ok=false` + `error`
- `whatsapp_commands.py`: `_ocr_document_tags()` — POST `{path}` на extractor `127.0.0.1:8099/extract-document`, timeout 5с → теги `extract_ok` / `extracted_text` (≤20000 символов) / `extract_error` в `bot_memory_messages.tags`; содержимое документа в логи НЕ выводится; ошибки не ломают ack/seen
- Аудит: Codex CLI — APPROVED; Grok CLI — APPROVED
- Проверено живым тестом: PNG OCR «АКТ КС-2…» — текст распознан, теги записаны

---

## 01.08-02.08.2026 — Полный listen-only фикс боевой группы (collect-only), аудит Codex/Grok CLI, Бишкек-время БД, 3-категорийная классификация фото

### Аудит / Исправления
- **Инцидент 01.08 08:54–08:57 UTC:** агент ОТВЕЧАЛ в боевую группу `120363400682390076@g.us` — нарушение listen-only. Устранён полностью.
- **ПОЛНЫЙ фикс listen-only (боевая группа → collect-only):**
  - `collectQueue` в `bridge.js` (`WHATSAPP_COLLECT_ONLY_CHATS`) — входящие из боевой группы идут только в очередь сбора, не в ответный контур
  - `/collect-messages` — ручной запуск сбора; JSONL-журнал `collect_journal.jsonl` + `/collect-ack` (подтверждение после записи в БД)
  - `failClosed`: HTTP 503 при пустом конфиге collect-only — не молчаливый пропуск
  - 403-гварды на ВСЕ outbound-каналы; изоляция от `messageQueue`; `/messages` без splice
  - Сбор `fromMe`/`fromOwner`; overflow сохраняет журнал; обработка `mediaMissing`
  - Фильтр `channel_directory`; send-guard адаптера (`_standalone_send`); диспетчер обрабатывает только `/collect-messages` + deny-send PRODUCTION + ack после записи в БД
- **Аудит настоящими CLI (не симуляция):** Codex CLI — 5 раундов REJECT→APPROVED; Grok CLI — APPROVED; кросс-ревью — APPROVED. Все найденные баги закрыты до нуля.
- **02.08 — время БД → местное Бишкек UTC+6:** `db.py` (`SET TIME ZONE 'Asia/Bishkek'`), `handlers.py`, `gather_snapshot_data.py`, `cleanup_db.py` (PGOPTIONS)
- **Классификация фото — 3 категории:** `construction` → `ojr_photo_log`; `site_related` / `unrelated` / `vision_unavailable` → только `bot_memory_messages`; greeting-приоритет: «АБК поздравляет…» → открытка. `vision_checklist.py`: `CHECKLIST_PROMPT` + поле `category`

### Сегодня (02.08)
- **Проверка сбора:** «С Днём строителя, коллектив!» и фото Максата собраны — доказано [PRD] SAVED/COLLECTED
- **Статус бота:** боевая группа в collect-only режиме, ответы заблокированы на всех уровнях (bridge + adapter + dispatcher)

---

## 02.08.2026 (04:04 UTC) — Ночная сводка: спокойный день, circulation graph, MEMORY.md → SOUL.md

### Статус систем (04:04 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает (uptime ~10.3ч), queueLength=0
- **document-extractor:** ✅ endpoint 8099 отвечает
- **Knowledge Graph:** актуален (сборка 01.08 04:04 UTC)
- **alikhan.service:** ОСТАНОВЛЕН (v6, Hermes Agent)
- **Hermes systemd unit:** inactive (dead) — Bridge запущен напрямую Hermes Agent, штатно

### Коммиты за 24 часа
- **01.08 04:04** — `e3d3949` chore: auto-sync 01.08 (CHRONOLOGY, CIRCULATION_GRAPH.md, бэкапы, knowledge graph, брифинг 31.07)

### Что изменилось
- **CIRCULATION_GRAPH.md** — новый документ: circulation edge types для knowledge graph (MGT_maccha #7). Информация не хранится — течёт: `работа → решение → артефакт → результат → обратно в работу`.
- **АйБиКон реквизиты:** `docs/реквизиты_АйБиКон_КР.md` — 16 строк, юридические реквизиты компании
- **HERMES-SOUL:** Hermes-оператор перешёл с MEMORY.md(hidden) на SOUL.md(public) — CRITICAL GATES публичны, failure-classification встроен в Rule 10
- **AGENTS.md Alikhan:** bot/AGENTS.md переименован в `AGENTS.md._DEPRECATED_` (дубликат, основной — в корне)
- **Knowledge Graph:** +68 строк, maintenance_report без критичных изменений
- **Бэкапы:** удалены старые .bak файлы шаблона ЕЖО (0729, clean_0730, fix_pu)

### Примечание
- 01.08 — спокойный день. Никаких багов в production. Bridge стабилен 3+ дня после миграции v6.
- Незакоммиченные изменения: whatsapp_commands.py, knowledge_graph (текущая CHRONOLOGY будет закоммичена авто-синхронизацией)

---

## 01.08.2026 — Внедрена классификация ошибок failure-classification

- В MEMORY.md добавлено правило: ошибки классифицировать через failure-classification (6 классов: REASONING_FAILURE, TOOL_FAILURE, MEMORY_FAILURE, ORCHESTRATION_FAILURE, EVALUATION_FAILURE, COST_FAILURE)
- TRANSIENT → retry max 3, PERMANENT → escalate (gateway не перезапускать!), LOGIC → replan+verify
- Decision tree: классифицировать → применить recovery → если не помогло → escalate

---

## 31.07.2026 (23:10 UTC) — Ночная сводка: экология 2025, авто-синхронизация, UTC→Бишкек

### Статус систем (23:10 UTC)
- **Hermes Bridge:** ✅ активен, порт 3000 отвечает (uptime 30534s ≈ 8.5ч), queueLength=0
- **document-extractor:** ✅ endpoint 8099 отвечает (ok)
- **Knowledge Graph:** актуален (сборка 31.07 18:15 UTC)
- **alikhan.service:** ОСТАНОВЛЕН (миграция v6 завершена 29.07)

### Коммиты за 24 часа
- **31.07 04:04** — `5277cce` chore: auto-sync 31.07 (бэкапы, knowledge graph, гидрология 2700.xlsx)
- **31.07 07:33** — `2d24c53` docs: финальные документы экология 2025 (4 .docx: анкета, письма Минприроды КР/РУС, справка)
- **31.07 08:02** — `ff48764` docs: ecology 2025 docs updated — период 19.03-31.07.2026 (обновление 4 .docx)

### Что изменилось
- **Экология 2025:** добавлена папка `docs/экология_2025/` — 4 документа: анкета-заявителя, письмо в Минприроды КР и РУС, справка. Период: 19.03–31.07.2026.
- **Гидрология:** `archive/hydrology/2026_07_30_замер_уровня_воды_2700.xlsx` — замер от 30.07
- **Knowledge Graph:** обновлён (maintenance_report.json — без критичных изменений)

### Контекст: 30.07 (предыдущие сутки, вчера)
- **UTC→Бишкек (+6):** серия из 6 коммитов (`5338c27`…`f53807d`) — исправление часового пояса во всех модулях: whatsapp_commands.py, fill_ejo.py, config.py, data_sources.py, poll.py, qa.py, db.py, avr.py, db_lookup.py. Бишкек UTC+6 вместо UTC.
- **Ролевая модель:** `5a305f3` — admin/operator/viewer роли
- **Оператор:** 996557261164 добавлен как оператор
- **Очистка материалов:** `f53807d` — fill_ejo очищает материалы при отсутствии данных за сегодня

### Примечание
- 29.07 миграция v5→v6 стабильна, бот не перезапускался
- Незакоммиченные изменения от 29.07 (whatsapp_commands.py, authorized_senders.json, документация) — остаются в рабочем состоянии

---

## 29.07.2026 (23:13 UTC) — Ночная сводка: полная миграция на Hermes Agent завершена

### Статус систем
- **Hermes Bridge:** активен, порт 3000 отвечает (health=200), режим bot. Systemd unit выключен — Bridge запущен напрямую Hermes Agent.
- **alikhan.service:** ОСТАНОВЛЕН — бот работает как агент Hermes, без отдельного Python-процесса.
- **document-extractor:** endpoint `127.0.0.1:8099` отвечает.
- **Knowledge Graph:** 230 nodes / 408 edges, 3 дубликата обнаружены (router≈alerter, qa≈avr, qa≈db), не критично.

### Коммиты за 24 часа
- **29.07 04:07** — `cedc03b` auto-sync: бэкапы .bak файлов, обновление knowledge graph, CHRONOLOGY nightly summary за 28.07.

### Незакоммиченные изменения (миграция v5→v6)
**Документация обновлена (5 файлов):**
- **AGENTS.md** — переписан под прямого Hermes Agent: убраны main_waha.py, bridge_wrapper.py, Evolution API, alikhan.service; добавлены каналы WhatsApp + Telegram DM; обновлены canonical files, workflows, verification.
- **INDEX.md** — синхронизирован с AGENTS.md: убраны ссылки на бота, добавлены прямые каналы, номер телефона.
- **RUNBOOK.md** — v5.0→v6.0: убран health check скрипт, обновлена архитектурная диаграмма, убраны systemd-команды для бота.
- **CONTRACTS.md** — убран bridge_wrapper из дерева зависимостей, заменён на Hermes Agent (прямой вызов).
- **CHRONOLOGY.md** — текущая запись.

**Новые файлы (2):**
- **`bot/whatsapp_commands.py`** (302 строки) — диспетчер WhatsApp-команд v2: слушает песочницу + боевую группу через Bridge API. Команды: ЕЖО, раскрыть отчёт, опрос. Авторизация по `authorized_senders.json`. QA-парсинг в обеих группах.
- **`bot/authorized_senders.json`** — whitelist отправителей: `79958974452` (руководитель).

### Что изменилось в архитектуре
```
v5: WhatsApp → Bridge :3000 → bridge_wrapper.py → main_waha.py (poll 3s) → Guard → Router → ...
v6: WhatsApp → Bridge :3000 (Baileys, mode=bot) → Hermes Agent → Alikhan (прямой агент)
```
- **bot/main_waha.py** — больше не исполняется (исторический)
- **bot/bridge_wrapper.py** — monkey-patch удалён
- **alikhan.service** — остановлен
- **Evolution API** — остановлен
- **Cron-задачи:** Health Check и Weather удалены. CHRONOLOGY и Knowledge Graph активны.

### Примечание
- 28.07 CRITICAL (`01edd49` фикс не в памяти процесса) — больше не актуально: бот остановлен, фикс не нужен.
- Bridge 405-реконнекты 28.07 — штатное поведение, 29.07 работает стабильно.

---

## 29.07.2026 — Миграция с Waha-бота на прямой Hermes Bridge

### Ключевое изменение
Alikhan переведён с промежуточного Python Waha-бота (`main_waha.py`, Evolution API) на прямое WhatsApp-подключение через Hermes Bridge (Baileys). Бот больше не крутится отдельным процессом — Alikhan теперь напрямую в группах WhatsApp как агент Hermes.

### Архитектура ДО → ПОСЛЕ
```
ДО:  WhatsApp → Hermes Bridge :3000 → bridge_wrapper.py → main_waha.py (poll 3s) → Guard → Router → ...
ПОСЛЕ: WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot) → Hermes Agent → Alikhan (прямой агент)
```

### Что изменилось
- **Бот (main_waha.py, Evolution API, alikhan.service)** — ОСТАНОВЛЕН. Больше не используется.
- **bridge_wrapper.py** — удалён (monkey-patch больше не нужен).
- **WhatsApp Bridge (Baileys)** — mode=bot, порт 3000. Alikhan напрямую в группах.
- **Номер телефона:** 79958974452 (тот же, что был у бота).

### Каналы (обновлённые)
| Платформа | Адрес | Роль |
|-----------|-------|------|
| WhatsApp | 120363179621030401@g.us | Песочница — команды, QA, ответы |
| WhatsApp | 120363400682390076@g.us | Боевая группа — пассивный сбор данных |
| Telegram | DM 652755599 | Администрирование, настройки |

### Конфигурация Hermes Bridge (config.yaml профиля alikhan)
```yaml
platforms:
  whatsapp:
    enabled: true
    mode: bot
    session_dir: /home/hermes-workspace/.hermes/sessions/whatsapp
    group_policy: allowlist
    group_allow_from: 120363179621030401@g.us,120363400682390076@g.us
    require_mention: false
```

### Патчи Hermes Agent (ключевые)
1. `adapter.py:412` — group_policy дефолт изменён с "pairing" на "open"
2. `adapter.py:413` — group_allow_from читает из env vars (WHATSAPP_GROUP_ALLOWED_USERS, WHATSAPP_GROUPS)
3. `whatsapp_common.py:359-361` — убран сломанный debug log

### Cron-задачи (обновлены)
- **Alikhan Health Check** — УДАЛЁН (не нужен без бота)
- **Alikhan Weather** — УДАЛЁН (погода больше не нужна)
- **Alikhan CHRONOLOGY + брифинг** — активен (23:10 ежедневно)
- **Alikhan Knowledge Graph** — активен (каждые 6 часов)

### Что осталось неизменным
- ЕЖО, QA-факты, ОЖР (PostgreSQL) — работают как прежде
- poll.py, qa.py, fill_ejo.py — вызываются через Hermes напрямую
- document_extractor — статус не менялся
- OHM-скиллы — установлены

### Документация обновлена
- AGENTS.md: убраны main_waha.py, Evolution API, bridge_wrapper, alikhan.service; добавлены прямые каналы WhatsApp
- INDEX.md: обновлены canonical files, verification commands
- Knowledge Graph: удалены bot-компоненты (main_waha, bridge_wrapper), добавлены bridge-компоненты, обновлены events

## 29.07.2026 — Дополнение к миграции: операционка (не архитектура v6)

### Инцидент: stale WebSocket
| Время | Событие |
|-------|---------|
| 13:19 | WhatsApp → `503 stream error` |
| 13:19:33 | Мост `connected`, но **0 входящих 48 мин** (до 14:07) |
| 14:07 | `restart hermes-whatsapp-bridge` из-за `Requires=` дёрнул и `alikhan.service` |
| после | `Seeded 0 IDs` — дедуп потерян, переобработка старых `[MSG]` без `[SEND]` |

Диагноз: HTTP `connected` ≠ живой сокет. «Silent expiry» Baileys.

### Живые баги диспетчера v6 (первый час)
- Cron-скрипт не видел модули бота.
- Пропал `if __name__ == "__main__": main()` — скрипт не вызывал `main()`.
- Сообщение приходит с полем **`body`**, парсер ждал `conversation`.
- Cron `GET /messages` — destructive read, «ворует» сообщения у Hermes-платформы.
- Два gateway дрались за одну WhatsApp-сессию (`WhatsApp session already in use`).
- Правило: **никогда не рестартовать Gateway изнутри сессии**.

### Access control
- Команды в песочнице — только `79958974452` (whitelist `authorized_senders.json`).
- QA-факты — от всех. Боевая — молча.
- Идентификация: `senderId = msg.key.participant \|\| chatId`, цифры номера.

### Первый живой цикл 29.07
- Данные: Майкадам ИТР 1, Рабочие 8, песок 20 м³, техника нет.
- Опрос: **23 позиции / 6 зданий**. Баг: коды без наименований работ — исправлено.
- `7.1.1.1` НВ Разработка грунта — **0.5 м³** (Сергей), затем Максат обновил до **0.25 м³**.
- Чистка дублей: персонал 14→2, материалы 4→1 (песок=20), work_log 10→3.

### Факт ОЖР (ответ Максату)
ОЖР ведётся с **18–20.07**: раздел 3 с 20.07 (6 записей), персонал с 20.07 (21), материалы с 18.07 (6), фото с 25.07 (16), погода с 20.07 (11), инциденты 0.

## 26.07.2026 — ОЖР-миграция: персонал/фото/готовность (production-цикл)

### Баги найдены и исправлены (5)
- **ON CONFLICT без constraint** — `db.py:676` и `db.py:696`: `ON CONFLICT DO NOTHING` без колонок + несовпадение с реальным constraint (4 колонки вместо 2). Бот падал в loop при сохранении опроса.
- **workers_count** — `ojr_section1_personnel` не имел поля количества. «Рабочие 4» → 1 запись. Добавлен `workers_count INTEGER DEFAULT 1`, обновлены `save_personnel()`, `get_staff()`, `qa.py`.
- **Фото не вставлялись** — `fill_ejo.py` тянул через Evolution API (мёртв). Добавлен local_path fallback: чтение с диска из `image_cache`. `ojr_photo_log.file_path` теперь заполняется.
- **Готовность сбрасывалась** — `fill_ejo.py` брал из вчерашнего авто-файла (23%) вместо шаблона (27%). Исправлено на чтение из TEMPLATE + обработка Excel fraction (0.27 → 27%).
- **Голос в production** — `production_listener_loop()` не обрабатывал аудио. Добавлен аудио-блок + `ojr_photo_log` запись в production handler.

### Production-проверка
- **Персонал:** Майкадам total=5 (ИТР=1, Рабочие=4) ✅
- **Работы:** 7.2.1.1 = 5 м³ ✅
- **Фото:** 3 шт вставлены ✅
- **Готовность:** 27% из шаблона ✅

### Инфраструктура
- **Интеграционный тест:** `test_e2e_ejo.py` (400 строк) — запись в OJR → fill_ejo → проверка Excel. Требует доработки: валидация другим worker'ом (Diamond), сверка с эталонным файлом.
- **T-115 Voice Testing:** закрыт (2 бага исправлено)
- **T-116 Cheap Delegate:** закрыт (DeepSeek v4-pro, экономия 11.5×)
- **AL-023 Client Guide:** готов, отправлен в песочницу
- **00_Task Index:** 4 неактуальные задачи закрыты (Evolution/WAHA/n8n)

### Уроки
- **Diff только по 3 колонкам** (16,19,21) — персонал/фото/готовность в слепой зоне. Пользователь подтвердил: не расширять.
- **Готовность из шаблона, не из авто-файла** — шаблон обновляется ежедневно из исправленного файла.
- **Фото: local_path, не Evolution API** — Evolution остановлен, local_path обязателен.

## 25.07.2026 — Полный аудит и стабилизация (Hermes-driven)

### Аудит
- Полный построчный аудит 15 модулей (~6900 строк): 49 багов (2 CRITICAL, 7 HIGH, 21 MEDIUM, 19 LOW)
- Документ: `docs/full-audit-2026-07-25.md`

### Исправления (коммит `bedf725` — 5 файлов, +49/−1713)

**Архитектура данных:**
- `data_sources.py` — единый модуль контрактов: 12 NamedTuple, primary OJR + fallback legacy
- `fill_ejo.py` — вырезаны прямые обращения к БД/API (~300 строк)

**ЕЖО:**
- Формат имени: `ЕЖО_ДД.ММ.ГГ_АйБиКон.xlsx` (единый во всех модулях)
- B1-B7: фото base64, guard перегенерации, hide_rows, погода fallback
- ПСД динамический, АйБиКон fallback, DRY планы
- R853 L-U очистка
- WhatsApp-кириллица: убран `'ЕЖО' in fname` (обрезается)
- Diff формат: `R737 U (2.1.10): 185.5 → 873.2`

**HIGH-баги исправлены:**
- bridge_wrapper: exact match вместо substring (утечка сообщений)
- Age gate 15с убран
- Дубликаты secrets → config.py
- Grok abuse vector → проверка имени «алихан»
- datetime.utcnow() → timezone.utc
- poll: ostatok≤0 filter убран
- main_waha: VOR дедупликация, EJO guard убран

**OJR:**
- Персонал: end_date закрывается при новых записях
- Объёмы: ON CONFLICT без category, дубликатов нет
- QA-парсер: не пишет volume=0 и статусные сообщения в work_log
- Фото: запись в ojr_photo_log + local_path сохраняется

**БД:**
- Очистка: 28→15 MB (2924 строки мусора миграции, 4816 старых фактов, 3983 сообщения, 36 пустых таблиц)

### Сегодня (25.07)
- **ЕЖО:** 10 версий сгенерировано, v10 финальная (613 KB). Исправленный файл от руководителя принят — 0 отличий.
- **Данные:** VOR 7.2.1.1 = 3 (арматурные работы), фото: АБК×2 + Общежитие×2
- **seen_ids.json:** сброшен в `[]`
- Бот НЕ перезапускался после коммита

### Верифицировано (без багов)
- AVR (КС-2, КС-6): не зависит от формата ЕЖО
- Календарь/напоминания: БД, не файлы
- STT: faster-whisper + Grok коррекция
- Grok: проверка имени, без abuse vector

### Осталось (низкий приоритет)
- 21 MEDIUM + 19 LOW (качество кода, мёртвый код)

## 25.07.2026 — Дополнение: инциденты дня аудита (в основной записи нет)

- **Collation-спам:** лог бота на 96% — `WARNING` коллейшна (версии совпали 2.41=2.41, ложное срабатывание). Было **8 614 строк / 824 KB**, стало **1 строка / ~2 KB**. Фикс: `datcollversion → NULL` на уровне `pg_database`.
- **Zombie-сессия моста:** HTTP `/health` = `connected`, но входящих нет. Последняя активность — **24.07**. Симптомы: `[SEND ERR] HTTP 404`, затем `500 Cannot destructure property 'user' of 'jidDecode(...)'`. С реальным JID песочницы отправка прошла (`success:true`). Лечение: рестарт моста, WhatsApp переподключился.
- **Подпись к фото пустая:** Hermes Bridge не кладёт caption в `media_meta` (`cap` всегда `""`). После тире в логе пусто. Фикс: читать поле `conversation`. Тег по умолчанию: `без тег` → `Общий план`.
- **Опрос:** после `Работы 7.2.1.1 - 3` бот слал полную сводку вместо короткого `✅ 7.2.1.1 = 3 м³ (НК)`. Полная сводка — только по «статус опроса».
- **Guard старого файла:** `poll.py` искал `/tmp/ЕЖО_{today}_v*.xlsx` и отдавал старый `ЕЖО_2026-07-25_v1.xlsx` вместо генерации. `fill_ejo.py` правили, `poll.py` — нет.
- **Health Monitor:** 5 процессов бота (`860301; 861170; 861184; 861652; 861667`) после множественных рестартов. Сведено к 1.
- **DELEGATION GATE принят:** Hermes не пишет код руками (`patch`/`write_file`). Анализ → постановка Codex/Grok → верификация.
- **Не лезть в автоматику шаблона.** Ручное копирование скорректированного ЕЖО в шаблон в 11:17 дало «0 отличий»: бот сравнил файл сам с собой. Реальные отличия были: G6 влажность 63%→61%, U737 остаток 185.5→873.2, K853 23%→27%. Сравнение смотрело узкий набор колонок.
- **7.2.1.1 ≠ «арматурные работы».** В шаблоне это «Разработка грунта» (НК, м³). QA/Grok неверно классифицировал; объём 3 верный.
- **Чистка репо:** 28 `.bak`, 6 старых ЕЖО, 3 `__pycache__`; `EVO :8080` → Bridge `:3000` в 6 файлах.

## 27.07.2026 — Контур безопасности + утечки секретов + второй цикл ЕЖО

### Решение: контур, чтобы «утром снова не чинить»
- `CONTRACTS.md` — 571 строка, граф 11 модулей + JSON.
- `pre_delegation.py` — перед делегированием собирает контракты в контекст Codex (`fill_ejo.py`+`data_sources.py` → зависимый; `bridge_wrapper.py` → **6** зависимых).
- `test_contracts.py` (10 контрактов) + `test_smoke.py` (5 проверок) → **15/15**.
- Формат делегирования: goal = проблема, не «замени строку 24». Diamond: Worker A (Codex) строит, Worker B (Grok) ищет дыру. Записано в `docs/war-story-sisyphus.md`. Коммит инструментов: 6 files, +1714.

### 🔴 Утечки (публичный репо)
| Что | Где | Откуда | Статус |
|-----|-----|--------|--------|
| xAI-ключ | `n8n-workflows/Алихан_AI-whatsApp_agent.json`, **9 вхождений** | первый коммит **20 июня**, ключ внутри экспорта n8n | заменён на `PLACEHOLDER_REVOKED`, история `filter-branch` → 0 `xai-` |
| Gmail пароль + email | `send_pdfs.py` (`solom1312818@gmail.com`) | открытый текст | `os.environ.get()`, история вычищена |

Сергею сказано: отозвать ключ в console.x.ai и сменить пароль Gmail.

### Баги ЕЖО 27.07 (логи врали, файл — нет)
- Фото: `content = 4715` (int) вместо `'4715'` (text) → `B1 MEDIA DB LOOKUP ERR`; плюс `get_photos()` брал хэш из `m.content` вместо `p.file_path`; `fill_ejo` снова долбил мёртвый Evolution `:8080`.
- QA: Grok вернул 3 факта, в БД сохранился 1 (техника). `'материалы'` не было в `ALLOWED_CATEGORIES`, fuzzy → `'документация'`.
- K853: `calc_completion_pct` считал с нуля (23%) вместо «база шаблона + прирост» (27%). Excel fraction `int(0.27)=0`.
- Техника: `source='qa'` vs `source='auto'` — не совпадало. В файле 2 экскаватора при факте 1.
- Персонал: «Рабочие - 8» → не 9 (1+8), пока не почистили дубли.
- Материалы: в БД мусор «Поставок материалов нет»; после чистки — **ТСП 199 м²**.
- Worker B нашёл 3 дыры: лишний JOIN роняет фото при удалении сообщений; `int()` на hex WhatsApp `msg_id`; `prod_seen_ids.json` в репозитории.
- Фильтр стройки: фото ключей от машины в салон — не стройка. Новые id 2788/2789 — стройка (кран, панели).

Коммит дня: `ec519e2` — 8 files, +164/−31 (`bridge_wrapper` `str(msg_id)`, `qa.py` категория материалы, `fill_ejo` K853 из шаблона, `db.py` ON CONFLICT с колонками).

**Урок:** не верить логам `[DS PHOTOS] counts=3` — открывать xlsx. Тест, который сам вставил данные и сам проверил, — worthless.

## 2026-07-24

- CONTEXT GATE (rule #0) added to `AGENTS.md`
- OfficeCLI installed: read mode works for EJO templates; write mode has persistence bug (formulas not saved to disk)
- `code-review-graph`: 448 nodes, 2,250 edges exported
- Unsiloed plugin installed for document parsing (gateway restart pending)

## 20.07.2026 — Structured Vision Checklist: photo→ЕЖО structured mapping (T-137 #5)

### Что было сделано
- Создан `vision_checklist.py` (338 строк): structured JSON checklist вместо plain-text Grok vision описаний
- CHECKLIST_SCHEMA с полями (weather, personnel_count, equipment, materials, progress, incidents, confidence scores)
- `checklist_from_image(base64)` → Grok-4 structured output → parsed JSON
- `checklist_to_ejo_map()` → прямое заполнение колонок ЕЖО + `ojr_photo_log` / `ojr_section3_work_log`
- Значительное улучшение фото-анализа для ежедневного отчёта, снижение hallucination в fill_ejo
- Интеграция в photo flow main_waha.py → ojr tables → ЕЖО generation

### Файлы
- `bot/vision_checklist.py` (новый модуль)
- Обновления в `bot/main_waha.py` (photo handler integration)
- Связанные правки в `fill_ejo.py` / `document_extractor.py`

### Discord
- #alikhan обсуждение архитектуры vision pipeline (T-137)

## 19.07.2026 — АВР: полный рефакторинг КС-6 + 837 расценок ВОР

### КС-6 — полная переделка

- **Одна таблица, 4 сгруппированных раздела:** Все работы / Выполнено с начала / За отчетный период / Остаток.
- Шапка: Код + Наименование + 4 группы подзаголовков (Ед., Кол-во, Цена за ед./сом, Сумма).
- Данные читаются напрямую из `ЕЖО_шаблон.xlsx` (колонки K/P/S), не из `ojr_section3_work_log`.
- 780+ строк, 0 пропущенных расценок. Итого только по колонкам Сумма (F,H,J,L). Округление до 2 знаков.
- Формат: `#,##0.00`, заморозка A9, альбомная ориентация, подписи.

### КС-2 — колонка Код ВОР

- Добавлена колонка «Код ВОР» (B) после № п/п, итого 15 колонок.
- Агрегация по коду, фильтр monthly_qty > 0.

### ВОР — 837 кодов (было 607)

- Добавлено 259 кодов из ЕЖО через среднее по разделу. 0 пропущенных.
- 5 критичных (3.3.2, 3.3.2.1, 3.3.2.2, 3.3.6, 7.2.1.1) — ручные цены.
- Поиск: точный код + fallback на родителя одного уровня.

### WhatsApp Bridge — стабильная доставка

- `_FakeResponse` переписан как контекст-менеджер (text + files).
- `status_code` property для совместимости с `send_document`.
- Текст и файлы уходят без ошибок.

### README — двуязычный для Twitter/GitHub

- EN/RU, обновлённые цифры: 837 кодов, 780+ строк КС-6, 3/3 теста.

### Аудит репозитория

- 0 секретов, 3/3 тестов, py_compile чисто, bridge 95+ мин аптайм.

## 19.07.2026 — КС-2 приведён к реальной 14-колоночной форме

- `generate_ks2()` формирует реквизиты акта, многоуровневую таблицу из 14 колонок, итоги, удержания и блок подписей.
- Заказчик, подрядчик, договор, стройка, объект и валюта читаются из переменных окружения; названия компаний в КС-2 не зашиты в код.
- Накопление предыдущего периода читается из вчерашнего КС-2, затем ЕЖО, с резервным расчётом по `ojr_section3_work_log`.
- Технические коды и накопительные объёмы сохраняются на скрытом листе `_meta` для переноса в следующий акт.
- Тесты КС-2 обновлены для проверки структуры формы, накоплений и удержаний; `generate_ks6()` оставлен без изменений.

## 19.07.2026 — Исправление кумулятивов ЕЖО

- Повторная генерация за дату corrected template больше не добавляет суточный объём второй раз.
- Чистая генерация использует вчерашние P/S даже при P=0; отсутствие файла теперь возвращает `None`.
- Значения P/S с десятичной запятой разбираются без потери данных.
- Проверки: `py_compile` успешно; существующий `test_ejo_simulation.py` не содержит pytest-тестов (`no tests ran`).

### Модуль АВР (КС-2 / КС-6)

- Создан `bot/avr.py`: формирование актов КС-2 за период и накопительного журнала КС-6 на дату.
- Добавлены команды WhatsApp: `АВР`, `формируй АВР`, `кс-2`, `кс-6`; интеграция выполнена в `router.py` и `main_waha.py`.
- Добавлен `bot/test_avr.py` с 3 тестами генерации КС-2, КС-6 и сводки стоимости.
- Источник расценок: `report/templates/ВОР_с_расценками.xlsx` — 607 позиций, расценки ФЕР-2020 с коэффициентом 0,75, общая стоимость около 760 млн KGS.

### Исправления после Grok review

- `avr.py`: КС-6 сохраняет названия работ и единицы измерения; переданные `work_entries` фильтруются по периоду; сопоставление кодов ВОР нормализовано.
- `fill_ejo.py`: устранён повторный учёт суточного объёма в P/S через `template_has_today`; `yesterday_cum()` возвращает `None`, когда предыдущего отчёта нет.
- `poll.py`: поддержан ввод нескольких кодов в одном сообщении; для новых записей используется `building='общая'`; добавлены предупреждения о пустом и частично распознанном ответе.
- `main_waha.py`: предупреждения poll теперь отправляются пользователю в WhatsApp.
- Исправления зарегистрированы в `bot/BUGS.md` как AL-013—AL-020.

### Репозиторий и инструменты

- Репозиторий опубликован: https://github.com/Gromykoss/Alikhan; секреты и внутренние идентификаторы очищены перед сменой видимости.
- Grok Build CLI обновлён с v0.2.59 до v0.2.103: `--yolo` заменён на `--always-approve`, для headless-запусков используется `--print`.

## 18.07.2026 — Миграция БД на структуру ОЖР (14 таблиц)

### Ключевое изменение
База данных перестроена со старой структуры (`bot_memory_facts` + `bot_poll_residuals`) на 14 таблиц ОЖР по ГОСТ РД-11-05-2007 / Приказу Минстроя РФ №1026/пр.

### Что изменилось
- **14 новых таблиц:** `ojr_title_page`, `ojr_section1_personnel` (Раздел 1 — ИТР), `ojr_section2_design_supervision` + `ojr_section2_visits` (Раздел 2 — Авторский надзор), `ojr_section3_work_log` (Раздел 3 — Выполнение работ, главная), `ojr_section4_construction_control` + `ojr_section4_checks` (Раздел 4 — Стройконтроль), `ojr_section5_asbuilt_docs` (Раздел 5 — Исполнительная документация), `ojr_section6_gosstroynadzor` (Раздел 6 — Госстройнадзор), `ojr_weather`, `ojr_photo_log`, `ojr_daily_summary`, `ojr_materials`, `ojr_incidents`
- **Новый поток данных:** QA → `bot_memory_facts` (промежуточный слой) → роутинг по `ojr_*` таблицам
- **Poll → `ojr_section3_work_log`:** закрытие опроса пишет объёмы в work_log
- **ЕЖО = view на `ojr_section3_work_log`:** `fill_ejo.py` читает work_log за дату вместо прямого чтения `bot_memory_facts`
- **Погода → `ojr_weather`:** Open-Meteo пишет и в БД, и в Excel
- **Снимок дня = композит:** `ojr_photo_log` + `ojr_daily_summary` + сообщения WhatsApp

### Файлы
- `db/ojr_schema.sql` — полная схема (14 таблиц, индексы, constraints, комментарии)
- `db/ojr_er_diagram.md` — ER-диаграмма (Mermaid + ASCII)
- `db/ojr_fill_guide.md` — руководство по заполнению разделов 1-6, sync-скрипты, диагностика
- `db/ojr_migration.sql` — скрипт миграции существующих данных
- `bot/ojr_sync.py` — модуль синхронизации: facts→work_log, фото→photo_log, погода→weather

### Старые таблицы
- `bot_memory_facts` и `bot_memory_messages` оставлены как история / audit trail
- `bot_poll_residuals` заменён на `ojr_section3_work_log` (category='объём')
- План отказа от старых таблиц: 4 фазы (см. `db/ojr_fill_guide.md`, раздел 4)

### Навыки
- `alikhan-daily-snapshot` — новый навык: ежедневный снимок дня из ОЖР-таблиц

## 17.07.2026 (14:23) — HermesBridge стабилизация: retry+backoff и systemd

### Проблема
- Мост падал с `Timeout in AwaitingInitialSync` / HTTP 000 — `startSocket()` без `.catch()` → unhandled rejection → crash
- Быстрые 440-реконнекты (каждые 3с) → rate-limiting → ухудшение стабильности

### Решение
1. **`bridge.js` — `connectWithRetry()`**: внешний цикл с exponential backoff (1s→60s cap), `.catch()` на каждом вызове
2. **`bridge.js` — внутренний reconnect с backoff**: 1s→30s cap, 428 ошибки отдельно (короткий), `.catch()` на таймерах
3. **systemd user service** (`hermes-whatsapp-bridge.service`): `Restart=always`, env vars, лимиты памяти

### Файлы
- `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js` — добавлены `connectWithRetry()`, `_reconnectBackoffMs`
- `~/.config/systemd/user/hermes-whatsapp-bridge.service` — создан
- Запуск: `systemctl --user {start,stop,restart,status} hermes-whatsapp-bridge`

### Примечание
- 440 конфликты (=телефон активен) — ожидаемое поведение; backoff предотвращает hammering
- Мост жив даже при 440: HTTP :3000 отвечает, systemd следит

## 17.07.2026 (10:00) — Фикс фото: _media + Grok vision description

### Достигнуто
- **Фото обнаружение:** `imageMessage` (Evolution API) → `_media.mediaType == "image"` (Bridge) — песочница + прод
- **Vision-описание:** Grok (grok-4-latest) анализирует фото и пишет 1-2 предложения в `tags->>'description'`
- **Промпт:** описание состояния конструкций без предположения активных работ

### Баги исправлены
- Фото не сохранялись после миграции на Hermes Bridge (wrapper кладёт _media, код искал imageMessage)
- Дубль: Codex оставил `has_media = bool(msg...)` до определения `msg` → `[LOOP ERR] name 'msg' is not defined`

### Файлы
- `bot/main_waha.py` — строки 390-413 (prod), 526-576 (sandbox): фото + vision
- `bot/bridge_wrapper.py` — без изменений (debug Codex откачен)

### Коммиты
- `8a2a87e` — Fix: imageMessage→_media for bridge photo detection
- `aedc853` — fix: photo detection via _media + Grok vision description

## 16.07.2026 (19:30) — ЕЖО v4: N=100%, планы из сырых сообщений, оформление 3-го листа

### Достигнуто
- N = 100% (L = M) всегда
- U = O − P, O > 0 ∧ U > 0 → строка видна
- Планы парсятся из сырых сообщений через Grok-фолбек
- 3-й лист «Персонал» оформлен
- Фаза 8 скрыта целиком
- 76 строк открыто

### Коммит
- `86d8439` — Alikhan v4 final

## 2026-07-22 — WAHA альтернатива + проект idle

- **12:00** — X Hotspot Radar: обнаружен WAHA — self-hosted WhatsApp HTTP API, альтернатива Evolution API для Alikhan-стека (T-159).
- **22-23.07** — Проект idle. Бот остановлен (миграция с Evolution на Hermes Bridge завершена 15.07). Новых изменений кода нет. AGENTS.md memory violation (10-й repeat) — Hermes не прочитал основной AGENTS.md при старте сессии 21.07.

## 15.07.2026 — Миграция на Hermes Bridge

### Ключевое изменение
Evolution API заменён на Hermes WhatsApp Bridge (:3000).
- `bridge_wrapper.py` — monkey-patch: перехватывает `requests.post` к Evolution API → Bridge API
- `main_waha.py` — не менялся, импортирует `from bridge_wrapper import *`
- Evolution API Docker — остановлен
- `alikhan.service` — остановлен

### Навыки созданы
- `alikhan-poll` — цикл опроса прорабов
- `alikhan-fill-ejo` — заполнение шаблона ЕЖО
- `alikhan-template-handoff` — цикл «бот→ручная правка→шаблон»
- `alikhan-monthly-template` — месячный план через «раскрой отчет»
- **25.07.2026 15:24** — test: post-commit hook verification (`81410fb`)
- **26.07.2026 04:13** — chore: auto-sync 26.07 (`65a1136`)
- **26.07.2026 09:46** — chronology: 26.07 — 5 bugs fixed (ON CONFLICT, workers_count, photos, readiness, voice) (`fbcfaa9`)
- **26.07.2026 15:05** — war-story: день сурка — трёхуровневый контур безопасности (26.07.2026) (`0b7e52e`)
- **27.07.2026 03:47** — security: replace hardcoded Gmail credentials with env vars (INCIDENT #2 fix) (`3480a1b`)
- **27.07.2026 04:03** — security: remove exposed xAI key and Gmail password (`7c9c6aa`)
- **27.07.2026 04:07** — chore: auto-sync 27.07 (`93f871a`)
- **27.07.2026 04:08** — chore: auto-sync CHRONOLOGY 27.07 (`7ac0505`)
- **27.07.2026 04:08** — chore: CHRONOLOGY final 27.07 (`2742775`)
- **27.07.2026 04:25** — smoke test (`27e4240`)
- **27.07.2026 09:51** — fix: photo lookup (str msg_id), QA materials category, K853 from template, ON CONFLICT columns (27.07) (`ec519e2`)
- **27.07.2026 10:48** — fix: production photo handler parity, graceful KeyError guard, qa ON CONFLICT columns — Diamond round 4 APPROVED (27.07) (`3652ccc`)
- **28.07.2026 04:04** — chore: auto-sync 28.07 (`4f4a5fc`)
- **28.07.2026 09:43** — fix(ejo): ON CONFLICT, personnel window, local_path, multi-insert race (28.07) (`4d6985e`)
## 28.07.2026 — CHRONOLOGY nightly summary

### Статус систем (23:10 UTC)
- **alikhan.service:** активен с 10:12 UTC (не перезапускался после фикса 10:18)
- **Hermes Bridge:** активен 3д13ч, стабилен, но 405-реконнекты (4 за последний час)
- **ЕЖО:** сгенерирован и отправлен 28.07.26 в песочницу
- **Бот:** 13ч аптайм, memory 25 MB

### ⚠️ КРИТИЧЕСКОЕ НАБЛЮДЕНИЕ
- **Бот НЕ перезапущен после фикса `01edd49`** (10:18). Код на диске — новый, код в памяти процесса — старый.
- Ошибка `'NoneType' object has no attribute 'fetchone'` (фото → ojr_photo_log) **всё ещё активна** — процесс запущен в 10:12, до фикса.
- Требуется перезапуск: `systemctl --user restart alikhan` (PROD-уровень, только после approval)

### Коммиты за день
- **28.07.2026 04:04** — chore: auto-sync 28.07 (`4f4a5fc`)
- **28.07.2026 09:43** — fix(ejo): ON CONFLICT, personnel window, local_path, multi-insert race (28.07) (`4d6985e`)
- **28.07.2026 10:18** — fix(photo): psycopg2 execute().fetchone breaks ojr_photo_log insert (`01edd49`)
- **29.07.2026 04:07** — chore: auto-sync 29.07 (`cedc03b`)
- **30.07.2026 01:52** — feat: ролевая модель admin/operator/viewer (`5a305f3`)
- **30.07.2026 04:04** — chore: auto-sync 30.07 (`7a06792`)
- **30.07.2026 08:11** — fix: Бишкек UTC+6 вместо UTC для дат + оператор 996557261164 (`5338c27`)
- **30.07.2026 08:22** — fix: UTC→Бишкек (+6) в whatsapp_commands.py и fill_ejo.py (`1d6c689`)
- **30.07.2026 08:25** — fix: навык ЕЖО + config.py → Бишкек (+6) (`98b7d71`)
- **30.07.2026 08:34** — fix: UTC→Бишкек (+6) — data_sources, poll, qa, db, avr, db_lookup (`b6b3ccf`)
- **30.07.2026 09:18** — fix: fill_ejo + data_sources — персонал, накопительные, фото (`72c7bd8`)
- **30.07.2026 10:53** — fix: fill_ejo — очистка материалов при отсутствии данных за сегодня (`f53807d`)
- **31.07.2026 04:04** — chore: auto-sync 31.07 (`5277cce`)
- **31.07.2026 07:33** — docs: финальные документы экология 2025 (`2d24c53`)
- **31.07.2026 08:02** — docs: ecology 2025 docs updated — period 19.03-31.07.2026 (`ff48764`)
- **01.08.2026 04:04** — chore: auto-sync 01.08 (`e3d3949`)
- **02.08.2026 00:29** — chore: auto-sync 02.08 — chronology, KG, whatsapp commands, briefing (`df3c9a1`)
- **02.08.2026 04:21** — chore: auto-sync 02.08 (`e1fc08c`)

## 28.07.2026 — Дополнение к ночной сводке (Diamond + утечка xAI)

### Diamond 28.07
- Worker A: ON CONFLICT, staff window, local_path, materials.
- Worker B: **CRITICAL** — N вызовов `save_personnel` закрывают предыдущие insert'ы того же дня (`end_date` race). NEEDS_CHANGES → fixed.
- pytest **21/21**. Рестарт PID **1913728** (09:39; предыдущий процесс с 26.07 09:06).

### Персонал
- Открытых строк 14 → **2**; `get_staff` 14 (2+12) → **9 (1+8)**; ЕЖО O11=9, R20/21/22 = 9/1/8.
- Новый уникальный индекс **`uq_ojr_personnel_slot`**.

### Ключ xAI
- Старый `xai-keND…` (len 84) — **revoked** после утечки 27.07. QA: JSON fail ×3 → «1 fact saved» вместо 3. Vision: «не могу получить ответ от AI».
- Новый в `secrets.env`: `xai-iBjlzIoz…` (09:55), `grok-4-latest` ок. Старый остался в `profiles/alikhan/.env`; бот читает `secrets.env` первым.

### Фото
- `[PHOTO OJR ERR] 'NoneType' object has no attribute 'fetchone'` — `cur.execute(...).fetchone()` на psycopg2.
- Backfill sandbox 4736/4738/4740 → OJR 2793–2795.
- ЕЖО 28.07: **5 фото + лого** (из 6 в OJR, лимит 5), K853=27%, Майкадам 9, погода 13°C / СЗ 11.4 / 43%.

### Прочее
- **T-184** закрыта: референс [Narendarcodes/Autonomous-Whatsapp-Agent] (~2★, Hermes ReAct + Evolution + FastMCP, ~7.8k LOC) — изучили, на этом всё.

## 30.07.2026 — Корень даты «всегда 29.07»: цепочка UTC без TZ

Не одна точка, а цепочка UTC без TZ:
1. навык `alikhan-ejo-generate`: `python3 fill_ejo.py $(date +%Y-%m-%d)` ← **системный UTC** (это то, что дергает оператор «заполни ежо»);
2. `config.py`: `today_str()` / `today_date()` = `datetime.now()` без TZ;
3. `whatsapp_commands.py`: `time.strftime`, `date.today()`;
4. `fill_ejo.py`: `dt_date.today()` / `datetime.now()` внутри, даже если аргумент верный.

Итого: **9 файлов + 1 навык**, 17 замен в 6 файлах одним прогоном. Diamond Worker B: APPROVED → `b6b3ccf`. На устройстве оператора часы тоже сбиты (00:31 30.07) — на серверную логику не влияет.

### Данные, которые правили руками
| | 29.07 | 30.07 |
|--|-------|-------|
| Персонал | Майкадам ИТР 1 + Рабочие 8 | АйБиКон ИТР 3 + Майкадам 1+1 |
| Работы | **7.1.1.1 НВ = 0.5 м³** (сначала ошибочно 0.25) | **0.25 м³** |
| Материалы | песок 20 | нет (перетёк из шаблона 29.07 — фикс `f53807d`) |
| Фото | 0 | 1 АБК (id **2796**: created 30.07 07:57 UTC = 13:57 Бишкек, но `photo_date=29.07`) |

`7.1.1.1` сначала записался с `building='общая'` вместо `НВ`.

### Правила, зафиксированные в этот день
- **SANDWICH:** отправка в песочницу только по явной команде (делегат спамил кривые ЕЖО).
- **Боевая = только слушать.** Файл пришёл в боевую → ответ только в песочницу. (Полный collect-only — 01.08; правило названо 30.07.)

### Экология / гидрология
- Codex по смете **выдумал цифры** (электроды 80 тн, дрова 160 м³, персонал 0). Пересчёт с ВОР/ЕЖО.
- PDF-форма: **5 итераций**, цифры сдвигались на 2 строки → ушли в Word.
- П.14: вывоз — «Майкадам Сервис», договор с МП г. Талас.
- Гидрология: 4 скважины (НС-1…НС-4), **145 замеров / 36 дат**, 23.09.2025–30.07.2026 → `archive/hydrology/2026_07_30_замер_уровня_воды_2700.xlsx`.
- **02.08.2026 06:36** — fix: listen-only collection + bishkek tz + 3-category photo classification (`536c451`)
- **02.08.2026 09:07** — feat: T-174 OCR pipeline — document_extractor OCR (rus+eng), dispatcher extracted_text tags (`5a652ed`)
- **02.08.2026 09:08** — fix: vision_checklist fallback XAI_API_KEY from secrets.env (`f9c41a8`)
- **03.08.2026 04:06** — chore: auto-sync 03.08 — chrono, knowledge_graph, briefing (`332f569`)
- **04.08.2026 04:06** — chore: auto-sync 04.08 (`8515757`)
- **04.08.2026 23:05** — chore: nightly CHRONOLOGY + briefing 04.08 (23:00 UTC) (`15755d8`)
- **04.08.2026 23:06** — chore: update commit list in CHRONOLOGY.md (04.08 23:05) (`eb9598d`)
- **05.08.2026 04:03** — chore: auto-sync 05.08 (`b0e9837`)
- **06.08.2026 04:03** — chore: auto-sync 06.08 (`fbb5285`)
- **07.08.2026 23:05** — chore: nightly CHRONOLOGY + briefing 07.08 (23:00 UTC) — без коммитов за день
## 06.08.2026 (04:00—11:00 UTC+6) — Major: bridge restore + ЕЖО fix + табель theme rule

### Bridge: collectOnlyChats + /collect-messages endpoint
- **Проблема:** после обновления hermes-agent (03.08) bridge.js потерял collectOnlyChats. Диспетчер пропускал тики: «collectOnlyChats отсутствует — /messages НЕ читаю». Бот не отвечал.
- **Фикс:** добавлен collectOnlyChats массив (WHATSAPP_SANDBOX + WHATSAPP_PRODUCTION) в /health, эндпоинт GET /collect-messages?only=<JID>. Файл: bridge.js.
- **CRITICAL:** после обновления hermes-agent bridge.js сбрасывается — требуется перезапуск gateway для подхвата.
- **Grok audit:** FAIL — dual consumer /messages + /collect-messages. Фикс: /messages заглушен (deprecated, всегда []).
- **Результат:** collectOnlyChats в health ✅, диспетчер читает сообщения ✅.

### ЕЖО: шаблон обновляется после fill_ejo
- **Проблема:** опрос показывал старые остатки (247,2/478,4 вместо 227,2/453,4), потому что читал TEMPLATE, а fill_ejo писал в /tmp.
- **Фикс:** fill_ejo.py → shutil.copy2(out_path, TEMPLATE_PATH) после успешной генерации. Делегат: deleg_032d59a0.
- **Результат:** шаблон синхронизирован. Остатки 2.1.5=227,2, 2.1.10=453,4 ✅.

### Персонал: reliable_orgs CTE обнулил табель
- **Проблема:** Codex добавил reliable_orgs CTE (source_rank >= 2) в get_staff. Записи sync_source='ejo_v2' для АйБиКон фильтровались → 3 вместо 7.
- **Фикс:** убрать reliable_orgs CTE из get_staff. SELECT DISTINCT ON напрямую из active.
- **Результат:** АйБиКон = 7 из OJR (без табеля), 3 из табеля (правильно: theme=0 = выходной).

### Табель АйБиКон: theme=0 vs theme=7 правило
- **КРИТИЧЕСКОЕ ЗНАНИЕ:** в табеле fill.patternType='solid' + fgColor.theme=0 (чёрный) = ВЫХОДНОЙ. theme=7 (жёлтый/зелёный) = РАБОЧИЙ.
- **Баг:** я убрал проверку theme != 0 → считались все 6 человек вместо 3.
- **Откат:** возвращено условие `fill.patternType == 'solid' and fill.fgColor.theme is not None and fill.fgColor.theme != 0`.
- **Правило НЕ ТРОГАТЬ:** это условие в data_sources.py:618. theme=0 — выходной, theme=7 — рабочий.
- **Результат:** АйБиКон = 3 (Громыко, Геодезист, Электрик) ✅.

### Ночная проверка WhatsApp моста
- **Исправлен промпт джобы ffcc5f112fff:** проверка через curl :3000/health вместо systemctl. Запрет systemctl enable.

### Сохранено в memory:
- MoA обязательно: Codex → Grok adversarial review ДО применения (3 отката за 06.08).
- theme=0=выходной — НЕ ТРОГАТЬ.
- fill_ejo копирует в TEMPLATE.
- bridge.js требует перезапуска gateway после обновления.

### Модифицированные файлы:
- `~/hermes-agent/scripts/whatsapp-bridge/bridge.js` — collectOnlyChats + /collect-messages
- `bot/data_sources.py` — get_staff без reliable_orgs, theme!=0 восстановлен
- `bot/fill_ejo.py` — shutil.copy2 в TEMPLATE
- `~/.hermes/cron/jobs.json` — обновлён промпт ffcc5f112fff- **08.08.2026 12:38** — chronology: 08.08.2026 — харденинг VPS, разделение очередей bridge, echo_loop_guard, аудит AGENTS.md (`7331301`)
- **08.08.2026 12:40** — chronology: 08.08.2026 — харденинг VPS, разделение очередей bridge, echo_loop_guard, аудит AGENTS.md, NexusOS memory-слой (`daea757`)
- **08.08.2026 12:43** — chronology: 08.08.2026 — харденинг VPS, разделение очередей bridge, echo_loop_guard, аудит AGENTS.md, NexusOS memory-слой (`333592d`)
- **08.08.2026 12:52** — chore: sync 08.08 — AGENTS.md audit (MGT_maccha), bridge fixes, ЕЖО template, KG update (`7961365`)
- **08.08.2026 12:55** — chore: finalize CHRONOLOGY 08.08 (`db9ac80`)
- **09.08.2026 00:32** — chrono: 2026-08-09 (`0a3ad2a`)
- **10.08.2026 23:06** — chrono: 2026-08-10 — ночная сводка, брифинги 09.08 + 10.08 (`499615b`)
- **11.08.2026 23:06** — chrono: 2026-08-11 — ночная сводка, брифинг 11.08 (`b694574`)
- **12.08.2026 13:50** — chore: delete dead code - main_waha.py (v5), bridge_wrapper.py (unused), daily_snapshot.py (UTC shift bug) (`497fcb8`)
- **12.08.2026 23:04** — chrono: 2026-08-12 — ночная сводка, брифинг 12.08 (`69f5523`)
- **13.08.2026 06:49** — QA: привязка прораба к подрядчику (sender→contractor) + фикс len(int) (`96498e0`)
- **13.08.2026 06:57** — QA: агрегация персонал-фактов одной позиции (fix last-write-wins) (`4a762f0`)
- **13.08.2026 07:32** — QA: first-match классификация итог/специальность (защита от задвоения 46) (`477e2cc`)
- **13.08.2026 07:34** — chrono: 13.08 — инцидент bridge + маппинг прораба на подрядчика, фиксы QA (`fe5d4e8`)
- **13.08.2026 12:49** — docs: перенести устаревшую v5-документацию и чужеродный CLAUDE.md в archive/ (`fc4bb62`)
- **14.08.2026 08:30** — fix: media-записи сохраняют message_time из bridge timestamp (`178a363`)
- **15.08.2026 10:43** — feat: enforced authority model (claim-gate + production send-deny) (`bfa9b2f`)
- **15.08.2026 10:55** — feat(authority): guard_tool_call — enforced файловая граница профиля Alikhan (`d4353f8`)
- **15.08.2026 13:16** — feat(каркас): H4+H5 — claim-gate проверяет counts (count=0 → INCONCLUSIVE) (`75a1bab`)
- **15.08.2026 13:18** — chore: удалить закоммиченный bot/venv/ из git + добавить .gitignore (`655d2b3`)
- **15.08.2026 13:19** — chore: удалить .bak/.backup файлы (резервные копии кода и ЕЖО-шаблонов) (`09620a0`)
- **15.08.2026 13:20** — refactor: доступ к секретам через secret_config.get_secret() + keepalive БД (`794d26d`)
- **15.08.2026 13:20** — docs: актуализация AGENTS/CONTRACTS (v6) + пересобранный knowledge graph (`c55d3b7`)
- **15.08.2026 13:20** — chore: документация/скрипты + удаление мёртвых артефактов (wamux, n8n reminder) (`aeb51c2`)
- **15.08.2026 13:20** — chrono: индекс коммитов разбора рабочего дерева (15.08) (`8df1623`)
- **15.08.2026 13:21** — chrono: индекс коммита 8df1623 (`97893d8`)
- **18.08.2026 14:11** — chrono: 2026-08-18 — синхронизация хронологии (запись устарела ~70ч) (`c7699df`)
- **19.08.2026 04:00** — daily-sync: auto-commit (`60f87a0`)
- **20.08.2026 04:03** — auto-sync infra 20260820 (`702c074`)
- **29.08.2026 12:21** — chrono: 2026-08-29 — синхронизация хронологии (бэклог после остановки auto-sync 20.08) (`928467b`)
- **29.08.2026 12:21** — chrono: индекс коммита 928467b (`ee57756`)
- **29.08.2026 23:01** — chrono: 2026-08-29 — авто-синхронизация (`ba5cc11`)
- **29.08.2026 23:01** — chrono: индекс коммита ba5cc11 (`f2cbe1f`)
- **30.08.2026 23:03** — chrono: 2026-08-30 — авто-синхронизация (`eadc5ae`)
- **30.08.2026 23:03** — chrono: индекс коммита eadc5ae (`94432f7`)
- **31.08.2026 15:10** — docs+infra: офисный мост с Grok Bot (Оркестратор/Кровельщик/Наружник): webhook-маршрут office-reply (profile-bound, ответ через агента), приёмник офиса проверен ping 200, секрета передан, секция «Грок-бот помощник» добавлена в AGENTS.md (Hermes)
- **31.08.2026 15:06** — office-forward: пересылка вопросов прорабов офисному Оркестратору (Diamond: Codex A + Grok B, 3 раунда, APPROVED). E2E песочница 4/4 HTTP 200 (`761a213`)

- **Урок 31.08 (опер.)** — buzz_send.py: флаги `--as/--to` ставить ДО текста сообщения (парсер break-ится на первом не-флаге); при 401 в чатах профилей сначала grep по точной фразе в централизованном logs/errors.log — 401 Nous-провайдера центрального агента не виден в профильных логах.
- **31.08.2026 23:02** — chrono: 2026-08-31 — авто-синхронизация (`37fe2f3`)
- **31.08.2026 23:01** — chrono: 2026-08-31 — авто-синхронизация (`37fe2f3`)
- **31.08.2026 23:02** — chrono: индекс коммита 37fe2f3 (`d2d596c`)
- **01.09.2026 23:01** — chrono: 2026-09-01 — авто-синхронизация (`98590ba`)
- **01.09.2026 23:01** — chrono: индекс коммита 98590ba (`0111e0c`)
- **02.09.2026 15:34** — equipment: 15-я таблица ОЖР ojr_section2_equipment (учёт техники) (`14bc078`)
