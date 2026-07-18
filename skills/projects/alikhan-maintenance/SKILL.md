---
name: alikhan-maintenance
description: "Maintain and debug the Alikhan WhatsApp bot (ТЗРК Джеруй). Covers bot architecture, ЕЖО pipeline, common failure patterns, health checks, SIM_DATE workflow, and the golden rule: verify before reporting success."
version: 1.1.0
metadata:
  hermes:
    tags: [alikhan, whatsapp, ejo, debugging, health-check]
    category: projects
---

# Alikhan Maintenance

WhatsApp AI-агент для строительного проекта ТЗРК Джеруй. Бот: Python v5, Hermes Bridge (Baileys) + xAI/Grok. Evolution API заменён 15.07.2026.

> **⚠️ ОЖР Migration (2026-07-18):** `bot_memory_facts` → `ojr_section3_work_log` + `ojr_section1_personnel`. SQL-примеры ниже ссылаются на `bot_memory_facts` (legacy) — таблица пока существует (FK в OJR схеме). `bot_poll_residuals` заменён на `ojr_section3_work_log`. См. `/home/hermes-workspace/Alikhan-migration/db/ojr_schema.sql`.

## Quick Start

```bash
# Health check (run first)
python3 ~/.hermes/scripts/alikhan_health_check.py

# Bridge health + systemd status
curl -s http://127.0.0.1:3000/health
systemctl --user status hermes-whatsapp-bridge

# Live log
tail -30 /tmp/alikhan.log

# Restart bridge (systemd, auto-restart)
systemctl --user restart hermes-whatsapp-bridge

# Restart bot (approval required)
systemctl --user restart alikhan.service
```

## Architecture

```
WhatsApp → Hermes Bridge (:3000, Baileys v7) → bridge_wrapper.py → main_waha.py (poll 3s) → Guard → Router → [QA/DB/Weather/Grok/Schedule] → Reply
```

Key files:
- `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js` — Bridge (Node.js, Baileys), HTTP :3000, systemd-managed
- `~/.config/systemd/user/hermes-whatsapp-bridge.service` — systemd unit: Restart=always, backoff, env vars
- `~/Alikhan-migration/bot/bridge_wrapper.py` — monkey-patch: Evolution API calls → Bridge HTTP API
- `~/Alikhan-migration/bot/main_waha.py` — main loop, polling, command handlers, calendar reminders
- `~/Alikhan-migration/bot/poll.py` — poll/опрос module: residuals collection, EJO generation
- `~/Alikhan-migration/bot/router.py` — message routing (QA, DB, Grok fallback, CMD)
- `~/Alikhan-migration/bot/fill_ejo.py` — ЕЖО generation (weather + QA facts → Excel)
- `~/Alikhan-migration/bot/db.py` — PostgreSQL: memory, calendar, schedule, facts
- `~/Alikhan-migration/bot/verify.py` — Grok-powered reply verification (0-100 score)

Bridge session data: `~/.hermes/sessions/whatsapp/` (Baileys multi-file auth).
Bridge session owned by: `Алихан` (79958974452).

## Golden Rule: Verify Before Reporting

**Never report "done" until you've observed the fix working end-to-end.** A `patch` + `systemctl restart` is NOT a fix — the bot log must show the expected behavior. Common failure modes that hide behind a "looks good" report:

1. Ghost/zombie processes — old process survives restart, continues without fix
2. seen_ids blocking — restart adds messages to seen set, bot never processes them
3. 10-minute timeout — messages aged out during debugging
4. Word mismatches — command handler uses different words than router

Always run `tail -10 /tmp/alikhan.log` after restart to confirm the bot is processing.

## Schedule (bot_schedule_phases — 8 этапов)

Синхронизировано с PDF «ГРАФИК СМР.pdf» 01.07.2026. Полная таблица:

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

При обновлении графика пользователь присылает PDF-версию (не .mpp). .mpp требует JDK+MPXJ, не установлено на VPS.

**⚠️ ЕЖО ≠ график производства.** Данные для `bot_schedule_phases` берутся из «ГРАФИК СМР.pdf» (или таблицы в AGENTS.md, синхронизированной с ним). ЕЖО (ежедневный отчёт) — другой документ с другими данными (персонал, объёмы, погода). Никогда не извлекай этапы/даты/названия этапов из ЕЖО-файлов для графика производства. Если пользователь говорит «в песочнице график» — он про WhatsApp-сообщение с PDF, а не про данные ЕЖО.

## Common Failure Patterns

### 1. REJECT 35 (router sends commands through Grok)

**Symptom:** `[VERIFY] REJECT 35: Не сообщил об отсутствии данных в БД`
**Cause:** Router treats commands ("запускай опрос") as questions, sends to Grok, verify rejects reply
**Fix:** Add command words to `cmd_words` list in `router.py` → returns `CMD` action → `main_waha.py` skips Grok/verify

### 2. Bot not processing user messages

**Symptom:** Messages arrive in chat, log shows `[MSG]` but no `[REPLY]`
**Causes (check in order):**
- **Seen IDs swallowed message:** Seed adds user messages to `seen` set at boot. Fix: seed only `fromMe=true` messages.
- **10-minute timeout:** `if now_ts - msg_ts > 600: continue` — messages older than 10min skipped. Removed entirely; seen set handles dedup.
- **Ghost process:** Old PID survives restart, intercepts messages without fix. Fix: `kill` old PIDs before restart.
- **Command word mismatch:** Router uses "запускай опрос", handler uses "запустить опрос". Fix: align both lists.

### 3. psycopg2 not found

**Symptom:** `[LOOP ERR] No module named 'psycopg2'`
**Fix:** `pip install psycopg2-binary` in venv, then restart bot

### 4. Document extractor down

**Symptom:** `[DOC EXTRACT ERR] Connection refused`
**Fix:** Check `systemctl --user status alikhan-document-extractor.service`, restart if needed

### 5. Photo counter inflation after SIM_DATE flood / seen-clearing (2026-07-01)

**Symptom:** Опросник показывает «📸 Общежитие (21 из 3)» хотя реально прислали 5 фото.

**Root cause:** `main_waha.py:217` — SIM_DATE подменяет `created_at` на midnight указанной даты. При очистке seen_ids старые фото пересохраняются с той же датой → дубликаты в `bot_memory_messages`.

**Code fix (applied 2026-07-01):** `SELECT` проверка перед `INSERT` в `main_waha.py`:
```python
cur.execute("SELECT 1 FROM bot_memory_messages WHERE content = %s", (mid,))
if not cur.fetchone():
    cur.execute("INSERT INTO bot_memory_messages ...")
else:
    print(f"[PHOTO] Skip duplicate: {mid[:12]}...")
```
UNIQUE индекс на `content` невозможен (значения >8KB для file-path записей). Проверка существования — рабочий компромисс.

**Real photo sourcing:** когда DB содержит неверные ID, запросить реальные через Evolution API `findMessages` (пагинированный, `records` внутри `messages`). Фильтр: `imageMessage` в `message`, `fromMe=False`, caption содержит название здания. После нахождения реальных ID — обновить `bot_memory_messages.content` (это WA message ID) и пересобрать фото в ЕЖО через `fill_ejo.py`. См. `references/real-photo-sourcing.md`.

### 6. ЕЖО Diff limitation — only 3 columns compared (FIXED 2026-07-07)

**Symptom:** Пользователь исправляет заливку, фото и планы в ЕЖО. Бот отвечает «📎 Правки приняты (0 отличий)». Изменения не замечены.

**Root cause:** `main_waha.py:_update_template_from_correction()` сравнивал только 3 числовые колонки:
```python
for col, name in [(16, 'мес.факт'), (19, 'общ.факт'), (21, 'остаток')]:
```

**Status:** **Исправлено 07.07.2026.** Теперь сравниваются **все 7 колонок (O-U, 15-21)**: мес.план, мес.факт, мес.%, общ.план, общ.факт, общ.%, остаток. Заливка (cell fill), фото и планы всё ещё не проверяются — это выходит за рамки числового diff.

### 7. "Работы выполнены" IGNORED — name check blocks VOR codes (FIXED 2026-07-07)

**Symptom:** Прораб пишет «Работы выполнены 2.4.2 — 104.3», бот молчит. В логе `[MSG]` есть, но `[REPLY]` нет — сообщение уходит в IGNORE.

**Root cause:** `router.py:26` — regex `[ао]л[еи][хгк]` не находит «алихан» в сообщении → `return "IGNORE"`. Сообщения с VOR-кодами, но без «алихан», молча отбрасываются.

**Fix (двухфайловый):**
1. **router.py** (line 25-27): Добавлен `re.search(r'\d+\.\d+\.\d+(?:\.\d+)?\s*[=—–\-:\s]+\s*\d+', text)` **до** name check. Если совпадает → `return "RESIDUAL", "", False`.
2. **main_waha.py** (lines 527-536): Обработчик `action == "RESIDUAL"` после `route()` — вызывает `parse_poll_reply()` напрямую.

**Диагностика:** Если видишь `action == "IGNORE"` для сообщения с VOR-кодами, проверь regex — возможно, формат не совпадает (пробелы, разделители).

### 8. `int(None)` crash in poll.py format strings (FIXED 2026-07-07)

**Symptom:** `build_poll_message()` или `build_poll_summary()` вызывает `TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`. Краш в середине опроса.

**Root cause:** Три места в `poll.py` вызывали `int()` на значениях из БД, которые могут быть `None`:
- L280: `item['ostatok'] == int(item['ostatok'])` — хотя `_safe_float` возвращает 0, это место в `build_poll_message` могло получить None от template
- L470: `r['residual_volume'] == int(r['residual_volume'])` — DB residual_volume может быть NULL
- L471: `r['actual_today'] == int(r['actual_today'])` — actual_today может быть NULL (не обновлён)

**Fix:** Добавлены `is not None` guards перед каждым `int()` с `else '0'` fallback.

### 9. Section 3.1 missing from ACTIVE_SECTIONS (OBSOLETE — replaced by column O filter v3, 16.07.2026)

**Symptom (historical):** Работы из раздела 3.1 не появлялись в опросе.

**Root cause (historical):** `poll.py:88` — `ACTIVE_SECTIONS` не включал `"3.1"`.

**Current approach (v3):** Фильтр опроса — только столбец O (колонка 15) > 0. Никаких ACTIVE_SECTIONS. Пользователь сам определяет активные работы через месячный план в шаблоне. `_get_work_items_from_template()` читает col 15, единственное условие: `monthly_plan > 0`.

### 10. `_safe_message_ts()` returning 0 silently breaks 5-minute filter (FIXED 2026-07-13)

**Symptom:** Бот видит сообщения (`[MSG]`), но молча пропускает — ни `[QA]`, ни `[REPLY]`. Пользователь: «почему он не принимает данные из песочницы?»

**Root cause:** `_safe_message_ts()` (L42-46) возвращает `0` для `messageTimestamp=None`. Главный цикл (L498) проверяет `now_ts - msg_ts > 300` — когда `msg_ts=0`, условие ВСЕГДА истинно → сообщение пропускается. Фикс от 12.07 исправил краш `int(None)` но не проверил вторую точку использования.

**Fix:** `_safe_message_ts()` возвращает `int(time.time())` вместо `0` для None. Это гарантирует прохождение 5-минутного фильтра.

### 11. Bridge crash: "Timeout in AwaitingInitialSync" / HTTP 000 (FIXED 2026-07-17)

**Symptom:** Bridge process dies shortly after starting. `systemctl status` shows `inactive (dead)`. HTTP health check at :3000 unavailable. Logs show unhandled promise rejection from `startSocket()`.

**Root cause:** `bridge.js` called `startSocket()` without `.catch()` on the main code path (line 1118). When Baileys initial sync timed out (network hiccup, WhatsApp server unresponsive, rate-limiting after rapid 440 reconnects), the promise rejected → unhandled rejection → Node.js process crash.

**Compound factor:** Inner reconnect on `connection === 'close'` used a flat 3-second retry. Rapid 440 conflicts (phone active) triggered dozens of reconnect attempts per minute → WhatsApp rate-limiting → initial sync timeouts on subsequent attempts.

**Fix (three-part, applied 2026-07-17):**

1. **`connectWithRetry()` wrapper** — external retry loop with exponential backoff (1s→60s cap), catches ALL rejections. Replaces bare `startSocket()` call.

2. **Inner reconnect backoff** — per-session reconnects use exponential backoff (1s→30s cap). 428 errors get short backoff (1s). 440 conflicts get longer, growing backoff. All `setTimeout(startSocket, ...)` calls wrapped in `.catch()`.

3. **systemd user service** — `Restart=always`, `RestartSec=10`, memory cap (512M), env vars pre-configured. Located at `~/.config/systemd/user/hermes-whatsapp-bridge.service`.

**440 conflict note:** When the phone actively uses WhatsApp, the bridge receives 440 "replaced" disconnects. This is expected — a single WhatsApp account cannot have two active Web sessions. The exponential backoff prevents rate-limiting during these conflict periods. Once the phone is idle, the bridge reconnects automatically.

**Verification:**
```bash
systemctl --user status hermes-whatsapp-bridge   # active (running)
curl -s http://127.0.0.1:3000/health             # {"status":"connected",...}
journalctl --user -u hermes-whatsapp-bridge -n 20 # check for crash/backoff
```

See `references/hermes-bridge-stability.md` for full fix recipe and systemd unit template.

### 12. Photo vision silently broken — import `ask_ollama_raw` doesn't exist (FIXED 2026-07-18)

**Symptom:** Фото приходят, сохраняются в БД, но vision-описание не генерируется. Лог: `[PROD PHOTO DESC ERR]` / `[PHOTO DESC ERR]`.

**Root cause:** `main_waha.py` импортировал `from handlers import ask_ollama_raw` (строка 607 — prod, строка 764 — sandbox), но в `handlers.py` существует только `ask_grok_raw` (строка 117). Импорт внутри `try/except` → `NameError` молча глотается → фото обрабатываются без vision.

**Fix:** `from handlers import ask_ollama_raw` → `from handlers import ask_grok_raw` в ОБОИХ местах. **Pitfall:** в main_waha.py два независимых пути обработки фото (sandbox + production) — исправлять нужно ОБА. Проверка: `grep -c ask_ollama_raw main_waha.py` → `0`.

### 13. Age gate 300s silently drops real messages (FIXED 2026-07-18)

**Symptom:** Бот видит сообщения (`[MSG]`), но молча пропускает — объёмы и QA-факты теряются. Сообщение старше 5 минут игнорируется.

**Root cause:** `main_waha.py:714` — `if now_ts - msg_ts > 300: continue`. При любом перерыве >5 минут (gateway restart, отладка) все накопленные сообщения дропаются без следа.

**Fix:** 300s → **15s**. Это третий инцидент с age gate (600s 12.07, 300s 13.07, 300s 18.07). **Правило:** age gate НИКОГДА не должен быть >15s. seen set уже обрабатывает дедупликацию — большие окна только теряют данные.


## ЕЖО Workflow (⚠️ SQL-примеры используют legacy `bot_memory_facts` — миграция в OJR в процессе)

```bash
# Set simulation date in main_waha.py and router.py:
SIM_DATE = "2026-06-30"  # None for production

# Move data between dates (legacy bot_memory_facts):
UPDATE bot_memory_facts SET fact_date='2026-06-30' WHERE fact_date='2026-06-29';
UPDATE bot_memory_messages SET created_at = created_at + INTERVAL '1 day' WHERE DATE(created_at)='2026-06-29';

# Remove duplicate facts (same date/category/fact):
DELETE FROM bot_memory_facts WHERE id IN (
    SELECT id FROM (
        SELECT id, ROW_NUMBER() OVER (PARTITION BY fact_date, category, fact ORDER BY id) as rn
        FROM bot_memory_facts WHERE fact_date='YYYY-MM-DD'
    ) t WHERE t.rn > 1
);

# Generate ЕЖО:
cd ~/Alikhan-migration/bot && python3 fill_ejo.py 2026-06-30

# Check personnel from timesheet:
python3 -c "from fill_ejo import get_aibikon_headcount; from datetime import datetime; print(get_aibikon_headcount(datetime(2026,6,30)))"
```

## Health Check

```bash
python3 ~/.hermes/scripts/alikhan_health_check.py
```

Checks: bot process (single, no zombies), psycopg2, DB connection, document extractor :8099, Hermes Bridge :3000, REJECT errors in logs, recent activity.

Manual bridge checks:
```bash
curl -s http://127.0.0.1:3000/health              # {"status":"connected/disconnected",...}
systemctl --user status hermes-whatsapp-bridge     # active (running)
journalctl --user -u hermes-whatsapp-bridge -n 20  # recent log
```

Cron: daily at 5:00 and 20:00 UTC (job `95d3c7d7fe16`).

## Commands Reference

| Command | Handler | Action |
|---------|---------|--------|
| Алихан начать/запустить/запускай опрос | Poll trigger | `poll.py` → `start_poll()` → questionnaire with residuals |
| Алихан заполни/сформируй/сделай/формируй ежо/отчет | EJO trigger | Check poll → `close_poll()` or direct `fill_ejo.py` |
| Алихан закрыть/завершить/закончить опрос | Close survey | `poll.py` → `close_poll()` → auto-fill + `fill_ejo.py` → send Excel |
| Алихан статус опроса / что собрано | Poll status | `poll.py` → `get_poll_status()` → summary |
| Алихан напомни _текст_ _дата_ _время_ | Calendar | `db.py` → `create_calendar_event()` (e.g., `напомни совещание 15.07 14:00`) |
| Алихан календарь / события / ивенты | Calendar list | `db.py` → `get_calendar_events('week')` |

**Pitfall:** command words in `router.py:30-34` must match what users actually type. Users type «формируй отчет» and «сформируй отчет» — these MUST be in `cmd_words` list alongside «ежо» variants. Missing command words cause the router to send the command through Grok instead of the CMD handler → REJECT or wrong reply.

## References
- `references/2026-07-01-bugs.md` — Transcript of four bugs found and fixed (REJECT 35, 10min timeout, seen seed, command mismatch)
- `references/2026-07-07-bugs.md` — Four bugs fixed this session (RESIDUAL bypass, section 3.1, template comparison 7 columns, int(None) crash)
- `references/mpp-extraction.md` — Complete MPP extraction workflow (what works, what doesn't, full stack requirements)
- `scripts/health_check.py` — Comprehensive health check script (8 checks: process, psycopg2, DB, extractor, Evolution API, REJECT errors, activity, collation spam)

## SIM_DATE Closure (конец симуляции)

When closing a simulation day:

1. **Fix and finalize ЕЖО**: correct fills, photos, plans → save as `ЕЖО_{date}_v2.xlsx`
2. **Copy v2 to template**: `cp /tmp/ЕЖО_{date}_v2.xlsx templates/ЕЖО_шаблон.xlsx`
3. **Disable SIM_DATE in BOTH files**: `SIM_DATE = None` in `main_waha.py:15` AND `router.py:9`. **Pitfall:** router.py has its own independent `SIM_DATE` variable — if you only disable it in main_waha.py, QA facts will still be saved with the old simulation date because `parse_qa()` reads `date_str=SIM_DATE` from router.py.
4. **Restart bot**: `systemctl --user restart alikhan.service`
5. **Verify**: `tail -5 /tmp/alikhan.log` — bot should show real date, not SIM_DATE
6. **Verify facts date**: `SELECT fact_date, created_at FROM bot_memory_facts WHERE source='qa' ORDER BY created_at DESC LIMIT 5` — fact_date must match the real date, not any old SIM_DATE

The v2 becomes the authoritative template for the next cycle. ЕЖО_шаблон.xlsx grows from ~300KB to ~1.3MB (with embedded photos).

## Duplicate EJO Prevention (2026-07-08)

**Problem:** Multiple code paths (`poll close`, `forced EJO`, `fill EJO trigger` in `main_waha.py`, plus `close_poll()` in `poll.py`) all call `fill_ejo.py` without checking if a report already exists. Result: 2+ identical Excel files per day.

**Root cause:** Guards at the message-routing level in `main_waha.py` were unreliable — too many paths, race conditions possible, the `close_poll()` function itself calls `fill_ejo.py` unconditionally.

**Triple-guard solution (all three levels must be in place):**

1. **`main_waha.py`** — guard at ALL THREE paths (poll close, forced EJO, fill EJO trigger):
   ```python
   existing = sorted(glob.glob(f"/tmp/ЕЖО_{today_str}_v*.xlsx"))
   if existing:
       send_msg(SANDBOX, f"📊 ЕЖО за {today_str} уже существует (v{len(existing)}). Отправляю существующий.")
       # Send existing file, then continue
   ```

2. **`poll.py` `close_poll()`** — guard BEFORE `subprocess.run(["fill_ejo.py", ...])`:
   ```python
   existing = sorted(glob.glob(f"/tmp/ЕЖО_{today}_v*.xlsx"))
   if existing:
       print(f"[POLL] EJO already exists. Skipping generation.")
       return poll_id, existing[-1]
   ```

3. **`fill_ejo.py` `__main__`** — final line of defense, exits early:
   ```python
   existing = sorted(glob.glob(f"/tmp/ЕЖО_{ds}_v*.xlsx"))
   if existing:
       print(f"⚠️ ЕЖО за {ds} уже существует. Пропускаю.", file=sys.stderr)
       sys.exit(0)
   ```

**Verification:** `python3 fill_ejo.py 2026-07-08` with existing files → "⚠️ Пропускаю" → exit 0, no new file.

**⚠️ TOCTOU race with two bot instances (2026-07-08):** Even the triple guard fails when TWO instances of `main_waha.py` run simultaneously. Both check for existing files → both see none → both proceed to `fill_ejo.py`. By the time instance B's `fill_ejo` guard runs, instance A's file may not be flushed to disk yet → v1 AND v2 created in the same second (identical timestamps, identical file sizes). **Diagnose:** `ls -la /tmp/ЕЖО_{date}_v*.xlsx` — if 2+ files have identical timestamps → TOCTOU race. **Fix:** `pgrep -cf main_waha.py` must return 1. If >1, kill all (`pkill -f main_waha.py`) and restart cleanly. **Verify:** `ps aux | grep main_waha | grep -v grep` — exactly one process.

**⚠️ Zombie bot instances from different launch mechanisms (2026-07-08):** A bot instance launched manually via bash wrapper (`bash -lic 'cd .../bot && python3 main_waha.py'`) can survive for days alongside the systemd service. `pgrep -cf` counts both, but they use different Python interpreters (system python3 vs Hermes venv). **Symptoms:** duplicate EJO files, duplicate QA facts, doubled personnel counts. **Diagnose:** `ps aux | grep main_waha | grep -v grep` — look for different Python paths (`/usr/bin/python3` vs `/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3`). **Fix:** identify the non-systemd instance by its parent process (bash, not systemd) and `kill <PID> <parent_PID>`. **Prevention:** verify single instance after every restart: `systemctl --user status alikhan.service` + `ps aux` — the systemd service is the sole authoritative runner. Never manually launch the bot with `python3 main_waha.py` while the service is running.

**⚠️ Personnel doubled in EJO → check QA facts first:** When personnel counts are 2× expected in the generated ЕЖО, the root cause is almost always duplicate QA facts in `bot_memory_facts`. Two bot instances process the same message → duplicate facts → `staff()` double-counts. **Quick check:** `SELECT category, fact, COUNT(*) FROM bot_memory_facts WHERE DATE(created_at)='YYYY-MM-DD' AND category='персонал' GROUP BY category, fact HAVING COUNT(*) > 1`. **Fix:** dedup with `ROW_NUMBER() OVER (PARTITION BY category, fact ORDER BY id)` — then delete rn>1 rows and regenerate EJO. Always fix the root cause (zombie instances) before cleaning data.



## Production Group Listener (2026-07-08)

**Problem:** Photos and documents sent to the production group (`120363400682390076@g.us`) were invisible to the bot — only the sandbox group was polled. Result: ЕЖО photos empty, personnel data from production group not captured.

**Solution:** Background daemon thread that polls the production group every 10 seconds, saves photos/documents/text to DB, runs QA parser on text — but NEVER replies.

### Architecture

```
main_waha.py main loop (sandbox, replies)  ←  existing
production_listener_loop() daemon thread  ←  NEW, no replies
  → poll PRODUCTION group every 10s
  → save photos → bot_memory_messages (type='image')
  → save documents → bot_memory_messages (type='document')
  → save text → bot_memory_messages (type='text') → parse_qa(PRODUCTION, text)
  → skip fromMe, skip >10min old, dedup by seen set
```

### Key rules

- **10-second poll interval** (not 3s like sandbox — production is passive)
- **PERSISTED seen IDs** (`prod_seen_ids.json`) — survives restarts, prevents re-processing old messages
- **First-run seed (24h window, limit 20)** — captures recent messages on startup, not just messages arriving within the last 10 minutes
- **Subsequent runs: no time window** — all new (unseen) messages are processed regardless of age
- **Separate seen set** (`prod_seen`) — does NOT mix with sandbox `seen`
- **QA parser called with `parse_qa(PRODUCTION, text)`** — facts stored with correct chat_id
- **Photos get building tag** from caption: check for `['АБК', 'Общежитие', 'Галерея', 'Общий план']`
- **No reply code path exists** — the thread has no `send_msg` calls

### Production listener 10-minute window pitfall (fixed 2026-07-08)

**Problem:** Initial implementation used `if int(time.time()) - msg_ts > 600: skip` — a hard 10-minute age filter on every poll cycle. Since production group messages trickle in over hours, by the time the listener polls, all messages are >10 minutes old → zero captures. Log showed only `[PROD] Listener started` with no `[PROD PHOTO]` lines.

**Fix:**
1. Persist seen IDs to `prod_seen_ids.json` (load on startup)
2. First run: 24-hour window with limit=20 (seeds recent state)
3. Subsequent runs: no time window — process any unseen message
4. `first_run` flag toggled after first iteration completes
5. Result: 5 photos captured immediately on restart, 32 IDs seeded

### Verification

```bash
# Check production messages in DB
docker exec evolution-postgres psql -U evolution -d evolution_db -c \
  "SELECT message_type, LEFT(content,40), created_at FROM bot_memory_messages WHERE chat_id='120363400682390076@g.us' ORDER BY created_at DESC LIMIT 10"

# Check production QA facts
docker exec evolution-postgres psql -U evolution -d evolution_db -c \
  "SELECT category, fact FROM bot_memory_facts WHERE chat_id='120363400682390076@g.us' AND DATE(fact_date)='2026-07-08'"
```

## Poll/EJO Interaction — Auto-Close + Missing Data Fix (2026-07-09)

**Symptom:** After user uploads corrected ЕЖО, bot writes «📋 Не хватает данных для ЕЖО: Что сделано? Что не успели?» even though the report is ready for the next day's template.

**Root cause:** Two interacting bugs:
1. Uploading a corrected ЕЖО didn't close the active poll → poll stays open after report is accepted
2. `build_poll_summary()` didn't check whether an ЕЖО already exists for today → shows «не хватает данных» even when report is ready

**Fix (two-file):**
1. **`main_waha.py`** — after accepting corrected ЕЖО, call `close_poll()` to auto-close the active poll
2. **`poll.py`** — `build_poll_summary()` now checks `glob.glob(f"/tmp/ЕЖО_{today}_v*.xlsx")` before showing «не хватает данных». If ЕЖО exists → «📊 ЕЖО готов», not «не хватает»

**Verification:** After uploading corrected EJO → poll auto-closes → «статус опроса» shows «ЕЖО готов» instead of data request.

## Pitfalls

- **`sendMedia` без проверки ответа → «отправлен» ≠ отправлен (FIXED 2026-07-13).** Все 8 вызовов `requests.post(...sendMedia...)` в `main_waha.py` не проверяли HTTP-статус. Бот писал «📊 ЕЖО отправлен» даже при 401/403/таймауте — файл не доходил до WhatsApp. **Fix:** обёртка `_send_document(chat_id, filepath, filename)` которая проверяет `r.status_code in (200, 201)` и логирует `[SEND OK]` / `[SEND FAIL]`. При ошибке бот пишет «❌ Ошибка отправки» вместо «📊 отправлен».

- **Evolution API документы не доходят — Redis в read-only slave режиме (FIXED 2026-07-13).** Симптом: `sendMedia` возвращает HTTP 201, текстовые сообщения и картинки доходят, но документы (.xlsx, .xls, .zip) не появляются в WhatsApp. Evolution API пишет ошибки `[RedisCache] READONLY You can't write against a read only replica` и `[WebhookController] AxiosError: timeout of 60000ms exceeded`. Причина: `evolution-redis` контейнер настроен как slave с `slaveof 175.24.232.83 26619`, внешний мастер недоступен → Redis в read-only → медиа-сессии не сохраняются → документы висят в PENDING. Диагностика: `docker exec evolution-redis redis-cli INFO replication | grep role` — если `role:slave` — проблема подтверждена. Fix: `docker exec evolution-redis redis-cli SLAVEOF NO ONE`. Проверка: `role:master` + `PING` → `PONG`. После fix нужно перезапустить `evolution-api` для сброса connection pool'а (`docker restart evolution-api`).
- **Duplicate EJO: guard at routing level is NOT enough.** Multiple code paths call `close_poll()`/`fill_ejo.py` — guard must be at ALL THREE levels: `main_waha.py` message routing, `poll.py` `close_poll()`, and `fill_ejo.py` `__main__`. See Duplicate EJO Prevention above.
- **Duplicate EJO: triple guard still fails with two bot instances (TOCTOU race).** When `pgrep -cf main_waha.py` > 1, both instances execute fill_ejo.py in the same second — the file-existence check passes for both before either writes to disk. Always check for ghost processes before debugging duplicates. See TOCTOU section in Duplicate EJO Prevention above.
- **RESIDUAL bypass: «Работы выполнены 2.4.2 — 104.3» ignored if format doesn't match regex.** The router checks `\d+\.\d+\.\d+(?:\.\d+)?\s*[=—–\-:\s]+\s*\d+`. If the foreman writes without a number after the code, the bypass doesn't fire and the message still requires «алихан».
- **Never restart bot without checking for ghost processes:** `pgrep -af main_waha` — if >1, kill old ones first
- **Never clear seen_ids.json without understanding flood risk:** bot will re-process ALL un-seen messages. Always pair with the 5-minute age filter.
- **QA extractor adds ИТР to worker count:** "Атантай ИТР 1, рабочих 6" → stored as "Атантай 7 рабочих" (ИТР + рабочих = 7)
- **Timesheet auto-pull works but needs correct date:** `get_aibikon_headcount()` uses `date.day` to find the right column (col 5 = day 1)
- **15-second dedup window (was 300s, fixed 2026-07-18):** `if now_ts - msg_ts > 15: skip` — brief dedup on restart, does NOT lose real volumes/QA facts. Verify: `grep 'msg_ts >' main_waha.py` → `> 15`. **History:** was 300s (lost 5-min-old messages silently), then 600s (lost 10-min-old). **Rule:** any age gate ≥30s WILL cause data loss in WhatsApp polling — keep it ≤15s or remove entirely.
- **Seed only own messages:** `if m["key"].get("fromMe"): seen.add(id)` — user messages must be processed, not seeded
- **Poll residual fallback:** шаблон ЕЖО может не иметь кэшированных значений в столбце «Остаток» (col 21) — `openpyxl(data_only=True)` возвращает `None`. `poll.py:_get_work_items_from_template()` имеет fallback: если col 21 пуст → остаток = план (col 18) − факт (col 19). Не ломай этот fallback.
- **deleteMessageForEveryone fails silently in groups:** Evolution API v2.3.7 on Baileys returns PENDING/REVOKE but doesn't actually delete group messages (GitHub issue #885). Only `fromMe=true` messages are affected. User must delete manually from phone.
- **Template contamination: old daily values survive in ЕЖО (fixed 2026-07-08).** `_update_template_from_correction` copies corrected ЕЖО as template. The corrected file contains daily values (e.g., 798 in L/M for code 3.1.4). On the next day, if no work for that code, the old daily value remains visible — looks like «работы выполнены» when they weren't. **Fix:** `fill_ejo.py` now clears daily columns (L=12, M=13, N=14) for ALL VOR-coded rows, not just active ones. Cumulative columns (P=16, S=19) are preserved across days via `yesterday_cum()`.

## Message Deletion

When bot floods the group (e.g., after a seen_ids clear), delete messages via Evolution API:

```bash
# Find spam message IDs (fromMe=true, recent):
curl -s -X POST http://127.0.0.1:8080/chat/findMessages/alikhan \
  -H "apikey: <key>" -H "Content-Type: application/json" \
  -d '{"where": {"key": {"remoteJid": "120363179621030401@g.us", "fromMe": true}}, "page": 1, "limit": 40}'

# Delete each message:
curl -s -X DELETE "http://127.0.0.1:8080/chat/deleteMessageForEveryone/alikhan" \
  -H "apikey: <key>" -H "Content-Type: application/json" \
  -d '{"id": "<MSG_ID>", "remoteJid": "120363179621030401@g.us", "fromMe": true}'
```
