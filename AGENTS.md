# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент для ТЗРК Джеруй. Подключение: Hermes Bridge (Baileys, mode=bot). Путь: /home/hermes-workspace/Alikhan-migration/

---

## ⛔ CRITICAL GATES — ЧИТАЙ ПЕРВЫМ

### ⛔ DELEGATION GATE — ПРАВИЛО №0 (25.07.2026)

**Alikhan = ОРКЕСТРАТОР, не исполнитель.** MoA Auto: `skill_view('moa-auto')`.
**⛔ НИКОГДА `delegate_task` без `acp_command`.**

**SELF-CHECK перед каждым tool call:**
> «Пишет код / патчит / мутирует?» → ДА → `delegate_task`.

**Разрешено:** read_file, search_files, grep, session_search, delegate_task, vision_analyze, terminal (read-only), systemctl status/logs, curl health-checks.
**Запрещено:** patch(), write_file(), terminal с sed/awk/python/git commit/push/cp/mv/rm, pkill, systemctl restart.
**Почему:** Codex/Grok = $0. DeepSeek = $0.87/M. ⛔ Нарушение = откат.

### 🗣️ Buzz-общение (multi-agent)

Отвечай **только** на прямое `@ТвойПрофиль`. Без `@` — молчи (кроме `default_profile`).
Не лезь в чужую зону. Не дублируй. ⛔ Запрещено слово «тишина» (эхо-петля).

---

## 🚀 Start here

1. `skill_view("hermes-self-knowledge")` + этот файл + `INDEX.md`
2. **Knowledge Graph:** `python3 ~/Alikhan-migration/knowledge_graph/query_tool.py grounded_answer "recurring bugs and API quirks?"` — обновляется cron каждые 6 часов.

---

## 📊 Метрики — KPI стройплощадки ТЗРК Джеруй

### Операционные (ежедневно)

| KPI | Цель | Источник / формула |
|-----|------|--------------------|
| ЕЖО — отправка | 100% дней (30/30) | Файл отправлен в WA песочницу → SEND OK в логе |
| QA-сбор из боевой | ≥90% дней с ≥1 фактом | `bot_memory_messages WHERE chat_id LIKE '120363400682390076%' AND date=today` |
| Персонал ИТР | ≥90% дней | `ojr_section1_personnel WHERE report_date=today` |
| Персонал рабочие | ≥80% дней | `ojr_section1_personnel WHERE role='worker' AND report_date=today` |
| Техника | ≥80% дней | `ojr_section3_work_log WHERE date=today AND equipment IS NOT NULL` |
| Фото-фиксация | ≥1/день | `COUNT ojr_photo_log WHERE photo_date=today` |
| OJR-записи (section3) | ≥3/день (раб. дни) | `COUNT ojr_section3_work_log WHERE date=today` |

### Качество

| KPI | Цель | Измерение |
|-----|------|-----------|
| ЕЖО — точность | ≤10% правок | v2 существует → были правки прорабов |
| ЕЖО — время генерации | ≤3 мин | От команды «ежо» до SEND OK |
| Время ответа на «ежо» | ≤30 сек | От сообщения до reply |

### Надёжность

| KPI | Цель | Измерение |
|-----|------|-----------|
| Bridge uptime | ≥99% (≤7ч downtime/мес) | `curl :3000/health` → `status=connected` |
| Потеря сообщений | 0 | `collect_journal.jsonl` после ACK = 0 строк |
| Баги/неделя | N+1 < N (тренд вниз) | `CHRONOLOGY.md` → `grep '🐛'` |

### Бизнес (график СМР)

| KPI | Цель | Измерение |
|-----|------|-----------|
| График — отклонение | ≤5 дней | Текущий этап: дата ГРАФИК СМР.pdf vs факт |
| Персонал — укомплектованность | ≥85% от плана | План СМР vs факт `ojr_section1_personnel` |
| Техника — укомплектованность | ≥90% от плана | План vs факт equipment в section3 |

**Пороги:** 🔴 3 дня подряд ниже цели → эскалация Сергею. 🟡 2 дня. 🟢 В норме.

---

## 🏗️ Архитектура (v6 — прямой Hermes Bridge)

```
WhatsApp → Hermes Bridge :3000 (Baileys, mode=bot) → Hermes Agent (Alikhan)
           │
           ├── QA-парсер (qa.py) → bot_memory_facts → ojr_section1/3/weather
           ├── ЕЖО (fill_ejo.py) — view на ojr_section3 за дату
           ├── poll.py — опросы персонала
           └── document_extractor.py → :8099
```

**Ключевые отличия от v5:** нет main_waha.py, bridge_wrapper.py, alikhan.service, Evolution API.
Alikhan работает напрямую как агент Hermes.

---

## ⛔ PRE-COMMIT / PRE-FIX GATE (MANDATORY)

### Автоматический хук (`.git/hooks/pre-commit`)

| Фаза | Команда | Блокирует? |
|------|---------|-----------|
| 1. py_compile | `python3 -m py_compile bot/*.py` | ✅ |
| 2. codex:review | `codex review --uncommitted` | ✅ |
| 3. codex:adversarial-review | `codex exec review --uncommitted` | ✅ CRITICAL / ⚠️ HIGH |
| 4. codex:rescue | `codex exec` — автофикс MEDIUM/LOW | Нет |

### Ручная проверка перед правкой

1. `grep -rn "имя" bot/` — все использования. Показать пользователю.
2. CHRONOLOGY.md — последние 50 строк (что менялось).
3. Knowledge Graph: `python3 knowledge_graph/query_tool.py grounded_answer "bugs for <component>?"`
4. ALIKHAN_ARCHITECTURE.md — секция компонента.
5. MoA: Codex (Maker) → Grok (Checker) → применять после PASS.
Если grep не показан / шаг пропущен → правка не принята. Откат.

---

## 🤖 Agent-Driven Development (Codex / Grok Build)

`skill_view('codex-grok-delegation')` перед делегированием.

1. Read docs: AGENTS.md + INDEX.md + CHRONOLOGY.md
2. Build plan (Goal Mode) для задач >20 строк
3. Preserve security: НЕ в боевую группу, НЕ менять secrets/DB
4. Verification: `py_compile` → `pytest test_ejo_simulation.py` → sandbox → CHRONOLOGY.md
5. No production restart без approval
6. `git status` перед работой — не перезаписывать чужие правки

---

## 📁 Канонические файлы

- Venv: `/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3`
- Env vars: `WHATSAPP_SANDBOX`, `WHATSAPP_PRODUCTION`, `DB_PASS`
- Bridge: `systemctl --user start hermes-whatsapp-bridge` (port 3000, mode=bot)
- Session: `~/.hermes/sessions/whatsapp/` | Номер: 79958974452
- poll.py, qa.py, fill_ejo.py, document_extractor.py — в `bot/`
- Extractor: `127.0.0.1:8099` | alikhan-document-extractor.service
- main_waha.py, bridge_wrapper.py, Evolution API, alikhan.service — ОСТАНОВЛЕНЫ

---

## 🔄 Активные workflows

- WhatsApp сообщения → Hermes Bridge :3000 → Hermes Agent → reply
- ЕЖО: `fill_ejo.py` + `templates/ЕЖО_шаблон.xlsx`
- Poll: `poll.py` | QA: `qa.py` | Extractor: `document_extractor.py` + :8099
- Sandbox: `120363179621030401@g.us` | Production: `120363400682390076@g.us` (read-only)
- Telegram DM: 652755599

---

## 📱 Группы WhatsApp / Telegram

| Платформа | Адрес | Роль |
|-----------|-------|------|
| WhatsApp | 120363179621030401@g.us | Песочница |
| WhatsApp | 120363400682390076@g.us | Боевая (read-only) |
| Telegram | DM 652755599 | Администрирование |

---

## ⚙️ Конфигурация Bridge (профиль alikhan)

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

---

## 🗄️ ОЖР (PostgreSQL)

Хост: `DB_HOST`, порт 5432. База: evolution_db, пользователь: evolution.
14 таблиц ГОСТ РД-11-05-2007. Схема: `db/ojr_schema.sql`.

Поток: QA → `bot_memory_facts` → роутинг по `ojr_section1_personnel`, `ojr_section3_work_log`, `ojr_weather`, `ojr_photo_log`, `ojr_daily_summary`, `ojr_materials`, `ojr_incidents`.

Устаревшие (заменены ОЖР): `bot_poll_residuals` → `ojr_section3_work_log`; ручная погода → `ojr_weather`; фото → `ojr_photo_log`.

Существующие legacy: `bot_memory_messages`, `bot_schedule_phases`, `bot_building_profiles`, `bot_poll_state`, `bot_calendar_events`.

---

## 📋 ЕЖО (v5 — миграция на ОЖР)

`fill_ejo.py` → Excel 4 листа из `ojr_section3_work_log` (фильтр `work_date`). Шаблон: `templates/ЕЖО_шаблон.xlsx`.
Цикл: QA → `bot_memory_facts` → `ojr_section3` → `fill_ejo.py` → .xlsx.
Суточный цикл: v1 → правки → v2 (или авто 8:00 cron). Месячный: «раскрой отчет» → O+U → шаблон.
Погода: Open-Meteo (42.284,72.765). Отправка: bridge 50mb, `requests.post`.
Навыки: `alikhan-fill-ejo`, `alikhan-template-handoff`, `alikhan-monthly-template`, `alikhan-poll`, `alikhan-photo-vision`, `alikhan-daily-snapshot`.

---

## 📅 График производства (8 этапов, bot_schedule_phases)

827 дней (30.04.2025–04.08.2027). `lookup_schedule()` / `check_delays()` в `db_lookup.py`.

| # | Название | Начало | Конец | Дни | Статус |
|---|----------|--------|-------|-----|--------|
| 1 | ПСД, подготовка | 30.04.25 | 26.06.26 | 423 | ✅ |
| 2 | Фундаменты, МК | 05.01.26 | 30.06.26 | 177 | 🔄 |
| 3 | М/каркас, перекрытия | 23.05.26 | 31.07.26 | 70 | 🔄 |
| 4 | Ограждающие, кровля | 15.06.26 | 30.10.26 | 138 | 🔄 |
| 5 | Внутренние системы | 01.11.26 | 01.07.27 | 243 | 🔄 |
| 6 | СКС, безопасность | 15.01.27 | 10.07.27 | 177 | 🔄 |
| 7 | Внутриплощадочные сети | 01.07.26 | 01.10.26 | 93 | 🔄 |
| 8 | Благоустройство, сдача | 01.07.26 | 31.07.27 | 396 | 🔄 |

---

## ⏰ Cron-задачи

- CHRONOLOGY + брифинг — 23:10 ежедневно
- Knowledge Graph — каждые 6 часов

---

## ✅ Верификация

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile poll.py qa.py fill_ejo.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
curl -s http://127.0.0.1:3000/health
```

---

## 📝 Последняя сессия (29.07.2026) — миграция на Hermes Agent

Alikhan переведён с Waha-бота на прямое WhatsApp-подключение через Hermes Bridge (Baileys).

**ДО:** WhatsApp → Bridge :3000 → bridge_wrapper.py → main_waha.py → Guard → Router → Reply
**ПОСЛЕ:** WhatsApp → Bridge :3000 (mode=bot) → Hermes Agent → Reply

**Остановлено:** alikhan.service, main_waha.py, bridge_wrapper.py, Evolution API.
**Активно:** ЕЖО, QA, ОЖР (PostgreSQL), poll.py, qa.py, fill_ejo.py, document_extractor.
**Каналы:** WhatsApp sandbox + production + Telegram DM 652755599.
