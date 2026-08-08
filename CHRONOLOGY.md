# CHRONOLOGY — Хронология изменений Алихан бота

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
