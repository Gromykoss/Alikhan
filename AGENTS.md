# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент для ТЗРК Джеруй.
Подключение: прямой Hermes Bridge (Baileys, mode=bot) + xAI/Grok.
Режим: агент Hermes напрямую в группах WhatsApp.
Путь: /home/hermes-workspace/Alikhan-migration/

---

# ⛔ CRITICAL GATES — ЧИТАЙ ПЕРВЫМ, ДО ЛЮБОГО ДЕЙСТВИЯ

⚠️ DO NOT SKIP: read ALL rules in this file before acting. Самые нарушаемые правила — здесь, наверху.

### ⛔ DELEGATION GATE — ПРАВИЛО №0 (MANDATORY — 25.07.2026, усилено 26.07)

**Alikhan на DeepSeek v4 Pro — ОРКЕСТРАТОР, не исполнитель кода. Никаких исключений.**
**MoA Auto:** `skill_view('moa-auto')` — автоматический Codex Maker + Grok Checker.
**⛔ НИКОГДА `delegate_task` без `acp_command`** — spawn default-сабагента (DeepSeek-клон), пустая трата токенов.

**SELF-CHECK перед КАЖДЫМ tool call:**
> «Этот вызов: пишет код, патчит файл, или делает что-то что Codex/Grok Build может сделать?»
> Если ДА → остановись. Делегируй через `delegate_task`.

**Разрешено Alikhan напрямую (read-only + оркестрация):**
- read_file, search_files, grep, session_search — анализ
- delegate_task → Codex/Grok Build — исполнение
- vision_analyze, terminal (только read-only: cat, ls, git status, grep)
- systemctl status/logs, curl health-checks

**⛔ Запрещено Alikhan напрямую (любой код/мутация):**
- patch(), write_file() — ЗАПРЕЩЕНЫ
- terminal с sed/awk/python/git commit/push/cp/mv/rm — ЗАПРЕЩЕНЫ
- «мелкий патч», «хирургическая правка», «проверю сам» — не оправдания
- pkill, systemctl restart, любые мутации процессов

**Почему:** Codex/Grok Build включены в подписку → $0. DeepSeek output = $0.87/M. Каждый ручной patch — платные токены за работу, которую Codex делает бесплатно.

**⛔ Нарушение = откат. Без предупреждений.**

---

## Start here

1. `skill_view("hermes-self-knowledge")` — 14 паттернов харнеса
2. Прочитай `~/hermes-vault/30_Logs/Арсенал Hermes.md`
3. Затем этот файл, потом `/home/hermes-workspace/Alikhan-migration/INDEX.md`
4. **Запроси Knowledge Graph:** `python3 ~/Alikhan-migration/knowledge_graph/query_tool.py` — recurring bugs, quirks, architecture

## 🧠 Knowledge Graph — shared memory (Anthropic Graph Engineering, 25.07.2026)

**Проблема:** память агентов умирает с контекстным окном. Knowledge Graph — постоянная structured память по домену Alikhan (WhatsApp bot, PostgreSQL/ОЖР, Hermes Bridge, ЕЖО, poll/QA).

**Файлы:**
- `knowledge_graph/schema.py` — Pydantic-модели (Triple, Entity, Edge; типы: bugs, fixes, api_quirks, db_tables, bot_components, events)
- `knowledge_graph/query_tool.py` — запросы к графу + `grounded_answer` (DeepSeek)
- `knowledge_graph/maintenance.py` — Step 5: stale/duplicates/contradictions/decay → maintenance_report.json
- `knowledge_graph/graph.json` — сам граф (seeded from MEMORY.md + AGENTS.md + CHRONOLOGY.md + BUGS.md)
- `scripts/knowledge_graph.py` — пайплайн Extract → Resolve → Assemble (+ maintenance после rebuild)

**Правила для всех агентов Alikhan:**

1. **Session start / bug triage** — ПЕРЕД диагнозом запроси граф:
   ```bash
   python3 ~/Alikhan-migration/knowledge_graph/query_tool.py grounded_answer \
     "What recurring bugs and API quirks affect the bot right now?"
   ```

2. **Перед фиксом в bot/** — проверь, что уже известно:
   ```python
   from knowledge_graph.query_tool import query_knowledge_graph
   print(query_knowledge_graph("What fixes exist for poll / photo / QA?", center_entity="bot_component/poll"))
   print(query_knowledge_graph("PostgreSQL and Bridge quirks", center_entity="api_quirk/postgres-collation-warning"))
   ```

3. **Любой агент** может вызвать:
   ```bash
   python3 ~/Alikhan-migration/knowledge_graph/query_tool.py query "..." [entity]
   python3 ~/Alikhan-migration/knowledge_graph/query_tool.py grounded_answer "..." [entity]
   ```

4. **Rebuild:** cron каждые 6 часов (`311003b953c6`, `15 */6 * * *`, script `alikhan_knowledge_graph.py`, no_agent). Граф всегда свежий.
   ```bash
   python3 ~/Alikhan-migration/scripts/knowledge_graph.py
   ```

**Entity types (Alikhan domain — no X/Twitter):**
`bug`, `fix`, `api_quirk`, `db_table`, `bot_component`, `event`, `service`, `decision`, `template`, `group`, `project`

**Pipeline:**
Extract (regex + curated seed from CHRONOLOGY + MEMORY + AGENTS + BUGS) → Resolve (aliases) → Assemble (NetworkX) → Query (subgraph serialization) → Grounded Answer (DeepSeek, every claim cites an edge) → Maintain (`maintenance.py` after each rebuild)

## Правила строительства

### ⛔ PRE-COMMIT GATE (MANDATORY — все проекты)

**Общие правила (все проекты):** `skill_view('build')`

### ⛔ PRE-COMMIT GATE (MANDATORY — все проекты)

**Автоматический хук** (`.git/hooks/pre-commit`) — 4 фазы:

| Фаза | Команда | Блокирует commit? |
|------|---------|-------------------|
| 1. py_compile | `python3 -m py_compile` всех .py | ✅ Да |
| 2. `/codex:review` | `codex review --uncommitted` — correctness, security, quality | ✅ Да |
| 3. `/codex:adversarial-review` | `codex exec review --uncommitted` — агрессивный поиск багов | ✅ Да (CRITICAL) / ⚠️ (HIGH) |
| 4. `/codex:rescue` | `codex exec` — авто-фикс MEDIUM/LOW предупреждений | Нет |

**Перед любым изменением кода (ручная проверка):**
1. `grep -rn "имя" bot/` — все места использования функции/переменной
2. Показать grep в ответе пользователю
3. Проследить логику в КАЖДОМ найденном месте
4. Только потом патч

Если grep не показан — патч не принят. Откат.

**Обход pre-commit gate:** `git commit --no-verify` (только для некритичных правок).

## Agent-Driven Development Rules (Codex CLI / Grok Build)

**Загрузить перед делегированием:** `skill_view('codex-grok-delegation')`

При делегировании задач в Codex CLI или Grok Build:

1. **Read docs first** — прочитать этот AGENTS.md + `INDEX.md` + `CHRONOLOGY.md` перед любым изменением
2. **Use build plan** — для задач >20 строк кода: Шаблон 1 из `codex-grok-delegation` (Goal Mode)
3. **Preserve security** — НЕ слать в боевую группу `120363400682390076@g.us`. НЕ менять secrets/DB connection
4. **Verification ladder** — `python3 -m py_compile bot/*.py` → `pytest test_ejo_simulation.py -q` → WhatsApp sandbox test → `tail -30 /tmp/alikhan.log` → CHRONOLOGY.md
5. **Reproducible setup** — `pip install -r requirements.txt`, Evolution API через Docker Compose (остановлен, миграция на Hermes Bridge)
6. **No production without approval** — НЕ рестартить `alikhan.service`, `alikhan-document-extractor.service`, Evolution API
7. **Never expose credentials** — Evolution API ключи, WhatsApp токены, DB connection — не коммитить
8. **Preserve user changes** — `git status` перед работой, не перезаписывать чужие правки

### Alikhan-специфичные

### Canonical files

- **Alikhan работает как агент Hermes** (прямой Bridge, без отдельного бота)
- Venv python: `/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3`
- Env vars в конфигурации Hermes: `WHATSAPP_SANDBOX`, `WHATSAPP_PRODUCTION`, `DB_PASS`
- Hermes Bridge: `systemctl --user start hermes-whatsapp-bridge` (systemd, Restart=always, port 3000, mode=bot)
- Bridge session: `~/.hermes/sessions/whatsapp/`
- Номер телефона: 79958974452
- **alikhan.service — ОСТАНОВЛЕН** (29.07.2026, полная миграция на Hermes Agent)
- **main_waha.py — НЕ ИСПОЛЬЗУЕТСЯ** (заменён прямым подключением Hermes)
- **bridge_wrapper.py — НЕ ИСПОЛЬЗУЕТСЯ** (monkey-patch удалён, Hermes напрямую)
- **Evolution API — ОСТАНОВЛЕН**
- Poll module: `/home/hermes-workspace/Alikhan-migration/bot/poll.py`
- QA parser: `/home/hermes-workspace/Alikhan-migration/bot/qa.py`
- EJO generator: `/home/hermes-workspace/Alikhan-migration/bot/fill_ejo.py`
- Local extractor: `/home/hermes-workspace/Alikhan-migration/bot/document_extractor.py`
- Extractor service unit: `/home/hermes-workspace/Alikhan-migration/bot/alikhan-document-extractor.service`
- Extractor endpoint: `127.0.0.1:8099`
- Runtime log: Hermes session logs (не `/tmp/alikhan.log` — бот остановлен)

## Active workflows

- **Alikhan теперь работает как агент Hermes** — без отдельного бота. Сообщения WhatsApp приходят напрямую через Hermes Bridge (Baileys, mode=bot) в Hermes Agent, который обрабатывает их и отвечает.
- EJO work: `bot/fill_ejo.py` + `bot/templates/ЕЖО_шаблон.xlsx`
- Poll module: `bot/poll.py` — вызывается напрямую
- QA parser: `bot/qa.py` — вызывается напрямую
- Document extraction: `bot/document_extractor.py`; verify `127.0.0.1:8099`
- WhatsApp sandbox: `120363179621030401@g.us` — полный доступ
- WhatsApp production: `120363400682390076@g.us` — пассивный сбор данных
- Telegram DM: 652755599 — администрирование

## Archive / do not use by default

- Old/deprecated WAHA and n8n paths — only if explicitly requested
- `/home/hermes-workspace/Alikhan-migration/n8n-workflows/` — historical

## Do not touch without explicit approval

- Do not restart `alikhan-document-extractor.service`
- Do not send to production WhatsApp group `120363400682390076@g.us` без approval
- Do not change secrets, credentials, DB connection
- alikhan.service и main_waha.py — исторический код, не изменять

## Verification commands

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile poll.py qa.py fill_ejo.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
curl -s http://127.0.0.1:3000/health
```

## Принцип

**Надёжность и работоспособность всей системы — приоритет №1.** Фиксы и костыли переписываются в надёжный код. Каждое изменение тестируется в песочнице до боевой группы.

## Архитектура

### Поток данных (v6 — 29.07.2026, прямой Hermes Bridge)

```
WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot) → Hermes Agent (Alikhan)
  → QA/DB/Weather/Grok/Schedule/Poll → Reply напрямую в WhatsApp
                          │
                          ▼
                    QA-парсер (qa.py)
                          │
                    bot_memory_facts (промежуточный слой)
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
   ┌──────────────┐ ┌────────────┐ ┌──────────┐
   │ ojr_section1 │ │ojr_section3│ │  ojr_    │
   │ _personnel   │ │_work_log   │ │ weather  │
   │ (ИТР)        │ │ (объёмы)   │ │ (погода) │
   └──────────────┘ └─────┬──────┘ └──────────┘
            │             │             │
            │    ┌────────┼────────┐    │
            │    ▼        ▼        ▼    │
            │ ┌──────┐┌──────┐┌──────┐ │
            │ │photo ││daily ││mater-│ │
            │ │_log  ││_summ ││ials  │ │
            │ └──────┘└──┬───┘└──────┘ │
            │            │             │
            └────────────┼─────────────┘
                         ▼
                  ЕЖО (fill_ejo.py)
             = view на ojr_section3_work_log
               + ojr_weather + ojr_photo_log
               + ojr_daily_summary
```

**WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot) → Hermes Agent (Alikhan) → Reply напрямую в WhatsApp**

### Ключевые отличия от v5 (18.07.2026)

- **Нет бота (main_waha.py)** — Alikhan работает как агент Hermes, напрямую получает и отправляет сообщения
- **Нет bridge_wrapper.py** — нет monkey-patch слоя, Hermes использует Bridge нативно
- **Нет alikhan.service** — системный сервис бота остановлен 29.07.2026
- **ЕЖО, QA, ОЖР** — вызываются напрямую из Hermes, без промежуточного Python-процесса

## Быстрые команды

```bash
curl -s http://127.0.0.1:3000/health              # Hermes Bridge health
systemctl --user status hermes-whatsapp-bridge     # bridge systemd status
# alikhan.service ОСТАНОВЛЕН — бот работает как агент Hermes
```

## Группы WhatsApp и Telegram

| Платформа | Адрес | Роль |
|-----------|-------|------|
| WhatsApp | 120363179621030401@g.us | Песочница — команды, QA, ответы |
| WhatsApp | 120363400682390076@g.us | Боевая группа — пассивный сбор данных |
| Telegram | DM 652755599 | Администрирование, настройки |

## Конфигурация Hermes Bridge (профиль alikhan)

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

## Cron-задачи (обновлено 29.07.2026)

- **Alikhan CHRONOLOGY + брифинг** — 23:10 ежедневно
- **Alikhan Knowledge Graph** — каждые 6 часов
- ~~Alikhan Health Check~~ — УДАЛЁН (бот остановлен)
- ~~Alikhan Weather~~ — УДАЛЁН (погода больше не нужна)

## Память проекта (PostgreSQL) — миграция на ОЖР (18.07.2026)

Хост: `DB_HOST`/`EVO_DB_HOST` или авто-обнаружение `evolution-postgres` (docker inspect), порт 5432. База: evolution_db, пользователь: evolution.

### Структура ОЖР (14 таблиц, ГОСТ РД-11-05-2007)

| # | Таблица | Раздел ГОСТ | Назначение |
|---|---------|-------------|------------|
| 1 | `ojr_title_page` | Титульный лист | Заказчик, подрядчик, объект, договор, разрешения |
| 2 | `ojr_section1_personnel` | Раздел 1 | ИТР-персонал всех организаций (АйБиКон, субподрядчики) |
| 3 | `ojr_section2_design_supervision` | Раздел 2 | Авторский надзор: ответственный, сертификаты |
| 4 | `ojr_section2_visits` | Раздел 2 | Журнал посещений авторского надзора |
| 5 | `ojr_section3_work_log` | Раздел 3 | **Главная таблица** — выполнение работ (код ВОР, объём, здание) |
| 6 | `ojr_section4_construction_control` | Раздел 4 | Строительный контроль: ответственные |
| 7 | `ojr_section4_checks` | Раздел 4 | Акты проверок строительного контроля |
| 8 | `ojr_section5_asbuilt_docs` | Раздел 5 | Исполнительная документация (акты, протоколы, сертификаты) |
| 9 | `ojr_section6_gosstroynadzor` | Раздел 6 | Госстройнадзор: проверки, предписания, протоколы |
| 10 | `ojr_weather` | Погода | Ежедневная метеосводка (Open-Meteo API) |
| 11 | `ojr_photo_log` | Фото-фиксация | Фото стройплощадки с привязкой к датам и работам |
| 12 | `ojr_daily_summary` | Сводные | Предрасчитанные агрегаты за день (объёмы, персонал, %) |
| 13 | `ojr_materials` | Материалы | Журнал поступления материалов, сертификаты |
| 14 | `ojr_incidents` | Инциденты и ТБ | Происшествия, нарушения ТБ, простои |

### Существующие таблицы (оставлены как история / промежуточный слой)

- `bot_memory_messages` — исходные WhatsApp-сообщения (первичный источник)
- `bot_memory_facts` — QA-факты (промежуточный слой перед ОЖР)
- `bot_schedule_phases` — график производства (8 этапов)
- `bot_building_profiles` — профили зданий
- `bot_poll_state` — активные опросы (ссылка из work_log)
- `bot_calendar_events` — календарь

**Устаревшие таблицы (заменены ОЖР):** `bot_poll_residuals` → `ojr_section3_work_log` (category='объём'); ручной учёт погоды → `ojr_weather`; разрозненные фото → `ojr_photo_log`.

**Поток данных:** QA → `bot_memory_facts` (промежуточный) → роутинг по `ojr_*` таблицам. Полная документация: `db/ojr_schema.sql`, `db/ojr_er_diagram.md`, `db/ojr_fill_guide.md`.

## ЕЖО (v5 — 18.07.2026, миграция на ОЖР)

- `fill_ejo.py` — читает `ojr_section3_work_log` (объёмы) + `ojr_weather` (погода) + `ojr_photo_log` (фото) → Excel 4 листа
- **ЕЖО = view на `ojr_section3_work_log` за конкретную дату** (фильтр по `work_date`)
- Шаблон: `bot/templates/ЕЖО_шаблон.xlsx`
- SIM_DATE: None в продакшене
- **Цикл:** QA → `bot_memory_facts` → `ojr_section3_work_log` → `fill_ejo.py` → ЕЖО .xlsx
- **Суточный цикл:** ЕЖО v1 → правки → шаблон (или авто 8:00 через cron)
- **Месячный план:** «раскрой отчет» → заполнить O+U → шаблон на месяц
- **Колонки:** N=100% (0%), U=O−P, P/S=prev+v, всего 76 строк открыто
- **Скрытие:** O>0 ∧ U>0 видно, фаза 8 скрыта
- **Заполнение разделов ГОСТ:**
  - Раздел 1 (ИТР): `ojr_section1_personnel` → из QA + табель
  - Раздел 3 (Работы): `ojr_section3_work_log` → из QA-фактов + poll
  - Раздел 4 (СК): `ojr_section4_construction_control` + `ojr_section4_checks`
  - Раздел 5 (ИД): `ojr_section5_asbuilt_docs`
  - Раздел 6 (ГСН): `ojr_section6_gosstroynadzor`
- **Погода:** Open-Meteo (42.284,72.765) → `ojr_weather` + Excel
- **Планы:** парсинг из сырых сообщений (Grok-фолбек)
- **Табель:** локальный кеш `/tmp/hermes-media-cache/`
- **Отправка:** bridge 50mb, `_send_document` через `requests.post`
- Навыки: `alikhan-fill-ejo`, `alikhan-template-handoff`, `alikhan-monthly-template`, `alikhan-poll`, `alikhan-photo-vision`, `alikhan-daily-snapshot`

## График производства

- Таблица bot_schedule_phases — **8 записей** (из ГРАФИК СМР.pdf)
- Даты синхронизированы с PDF 01.07.2026
- lookup_schedule() / check_delays() в db_lookup.py
- 827 дней (30.04.2025–04.08.2027)

### Этапы (актуально на 01.07.2026)

| # | Название | Начало | Конец | Дни | Статус |
|---|----------|--------|-------|-----|--------|
| 1 | ПСД, подготовка | 30.04.25 | 26.06.26 | 423 | ✅ completed |
| 2 | Фундаменты, МК | 05.01.26 | 30.06.26 | 177 | 🔄 active |
| 3 | М/каркас, перекрытия | 23.05.26 | 31.07.26 | 70 | 🔄 active |
| 4 | Ограждающие, кровля | 15.06.26 | 30.10.26 | 138 | 🔄 active |
| 5 | Внутренние системы | 01.11.26 | 01.07.27 | 243 | 🔄 active |
| 6 | СКС, безопасность | 15.01.27 | 10.07.27 | 177 | 🔄 active |
| 7 | Внутриплощадочные сети | 01.07.26 | 01.10.26 | 93 | 🔄 active |
| 8 | Благоустройство, сдача | 01.07.26 | 31.07.27 | 396 | 🔄 active |

## Последняя сессия (29.07.2026) — полная миграция на Hermes Agent

**Ключевое изменение:** Alikhan переведён с промежуточного Python Waha-бота на прямое WhatsApp-подключение через Hermes Bridge (Baileys).

**Архитектура:**
```
ДО:  WhatsApp → Hermes Bridge :3000 → bridge_wrapper.py → main_waha.py → Guard → Router → Reply
ПОСЛЕ: WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot) → Hermes Agent (Alikhan) → Reply напрямую
```

**Что изменилось:**
- **alikhan.service — ОСТАНОВЛЕН** (29.07.2026)
- **main_waha.py** — больше не используется (заменён прямым подключением Hermes)
- **bridge_wrapper.py** — не нужен (Hermes использует Bridge нативно)
- **Evolution API** — остановлен
- **Cron-задачи:** Health Check и Weather удалены. CHRONOLOGY и Knowledge Graph активны.
- **Каналы:** WhatsApp песочница + боевая + Telegram DM 652755599
- **Номер телефона:** 79958974452

**Что осталось:**
- ЕЖО, QA-факты, ОЖР (PostgreSQL) — работают как прежде
- poll.py, qa.py, fill_ejo.py — вызываются напрямую через Hermes
- document_extractor — без изменений
