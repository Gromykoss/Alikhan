---
name: alikhan-operations
description: Operational patterns for the Alikhan WhatsApp bot — DB migrations, schedule management, data extraction, and project conventions.
metadata:
  tags: [alikhan, whatsapp, db, schedule, operations]
  category: operations
  phase: maintenance
  quality_tier: evidence-gated
---

# Alikhan Operations

Operational patterns for maintaining the Alikhan WhatsApp bot (ТЗРК Джеруй, Evolution API + PostgreSQL).

## ⛔ WORKFLOW DISCIPLINE — READ BEFORE ANY ACTION

**Эти правила существуют потому что агент их систематически нарушал. Каждое = реальный провал.**

### SANDWICH RULE
- Отправка ЛЮБОГО сообщения/файла в sandbox требует явной команды: «отправь», «пошли», «шлём»
- Никогда не отправлять автоматически после генерации ЕЖО
- Не принимать «ок» как разрешение на отправку
- Не слать v2, потом v3, потом v4 — один файл, один раз, после подтверждения

### CODE CHANGES
- PRE-PATCH GATE: `grep -rn "имя" bot/` → показать → дождаться «да» → патч
- **⛔ READ ALL FILES FIRST (2026-07-17):** Не трогать код пока не прочитан ВЕСЬ проект: `bridge_wrapper.py` (184 строки полностью), `bridge_helpers.js` (extractBridgeEvent), `main_waha.py` (poll + оба listener'а), `fill_ejo.py`, `db.py`, `poll.py`, `router.py`. Wrapper переводит bridge→Evolution формат — нельзя править main_waha не понимая что wrapper делает. См. `references/bridge-media-flow.md`.
- **⛔ FIX → PROGRAMMATIC VERIFY → USER TEST (2026-07-17):** Никогда не просить пользователя тестировать сырой результат. Сначала починить код, потом проверить E2E тестом (симуляция bridge→wrapper→bot), только потом просить пользователя подтвердить. Пользователь не тестировщик. См. `references/bridge-media-flow.md#debugging-pitfalls`.
- Бизнес-логика (`calc_completion_pct`, `staff`, `volumes`) — НИКОГДА не менять без явного «да»
- Даже если «очевидно неправильно» — сначала спросить, потом править

### PROJECT SCOPE
- Не переходить к другому проекту пока пользователь не сказал «переходим к»
- Не говорить «всё, закончили» пока пользователь не подтвердил
- Read-only режим («только проверять») = НИКАКИХ изменений

### VERIFICATION BEFORE SENDING
1. QA-факты за сегодня — соответствуют ли тому что пользователь подавал
2. Если пользователь говорит «я не подавал X» — удалить из БД, не включать в ЕЖО
3. Персонал — все подрядчики корректны
4. Готовность — формула не менялась без approval
5. Показать сводку → ждать «отправляй»

### ANTI-PATTERNS (реальные провалы 14.07.2026)
- ❌ Спамить v2, v3, v4 в песочницу без спроса
- ❌ Менять формулу готовности (26%→94%) потому что «кажется правильнее»
- ❌ Слать текст с неверными данными, потом слать исправление
- ❌ Считать что «ок» = «отправляй файл»
- ❌ Менять данные в БД и сразу генерировать/слать ЕЖО без проверки
- ❌ Запускать бота/опрос/ЕЖО вручную в обход основного цикла — ломает seen-ID трекинг, создаёт дубликаты poll'ов, перехватывает сообщения у sandbox-цикла. Бот должен работать через WhatsApp-команды.

### ⛔ NO MANUAL EXECUTION (16.07.2026)
- Агент НИКОГДА не запускает `start_poll()`, `close_poll()`, `fill_ejo.py` напрямую через терминал
- Агент НИКОГДА не шлёт опрос/ЕЖО в обход бота через `send_msg()` или `bridge/send`
- Единственный способ запустить опрос/ЕЖО — пользователь отправляет команду в WhatsApp-песочницу
- Нарушение: ручной `start_poll()` → poll #9 создан с неправильными секциями → дубликаты → сломанный flow
- Если бот не отвечает на команду — чинить бота, а не обходить его вручную

## Quick Reference

- **Bot path:** `/home/hermes-workspace/Alikhan-migration/bot/`
- **DB:** Docker `evolution-postgres`, port 5432, db `evolution_db`, user `evolution`, password `pass123`
- **Transport:** Hermes WhatsApp bridge on `:3000` (migrated from Evolution API 15.07.2026). Wrapper: `bridge_wrapper.py` monkey-patches requests/urllib.
- **Bridge startup (v2 — 16.07.2026):** `WHATSAPP_ALLOWED_USERS="*" node bridge.js --mode bot --session ~/.hermes/sessions/whatsapp`. MUST use `--mode bot` (NOT default self-chat) to receive group messages. `WHATSAPP_ALLOWED_USERS="*"` is required in bot mode. See `references/hermes-bridge-pairing.md`.
- **Sandbox group:** `120363179621030401@g.us` (full access)
- **Production group:** `120363400682390076@g.us` (listen-only: photos, documents, text → DB; no replies except weather cron)
- **Production listener:** background thread `production_listener_loop()` in `main_waha.py`. First run: 4 pages × 50 messages, 24h window. Subsequent: page 1 × 5, no window. Persists seen IDs to `prod_seen_ids.json`. Captures: `imageMessage` → `bot_memory_messages`, `documentMessage` → download+save, `conversation` → QA parse via `parse_qa()`.
- **EJO volume extraction:** `_extract_ejo_volumes()` in `main_waha.py` — reads VOR codes with non-zero volumes from uploaded ЕЖО .xlsx. **As of 2026-07-18, dual-writes:** `save_work_log()` → `ojr_section3_work_log` (primary) + `bot_memory_facts` (legacy compat). See `references/ejo-volume-extraction.md` and `references/ojr-migration-routing.md`.
- **Architecture doc:** `/home/hermes-workspace/Alikhan-migration/architecture.md` — полный функционал, cross-reference n8n→EVO v5, техдолг
- **Bridge migration:** `references/hermes-bridge-migration.md` — Evolution → Hermes bridge (15.07.2026), pairing, wrapper pattern, pitfalls
- **Key modules:** `main_waha.py` (оркестратор), `poll.py` (опрос), `fill_ejo.py` (ЕЖО), `db.py` (PostgreSQL), `router.py` (роутинг)
- **Poll reference:** `references/poll-module.md` — полный цикл опроса остатков работ
- **Poll business logic:** `references/poll-business-logic.md` — как опрос выбирает коды (активные + просроченные, v2 16.07.2026)
- **Poll message splitting:** `references/poll-message-splitting.md` — WhatsApp limit workaround (header + residuals, 16.07.2026)
- **Bridge wrapper buffer:** `references/bridge-wrapper-buffer.md` — race condition fix (v2 16.07.2026)
- **Bridge media flow:** `references/bridge-media-flow.md` — bridge→wrapper→bot media mapping, imageMessage→_media fix (17.07.2026)
- **Live debug trace:** `references/bridge-live-debug-trace.md` — minimal temp prints + restart + curl test for 3EB0* messages (17.07.2026)
- **EJO fill reference:** `references/ejo-fill-logic.md` — полный разбор: yesterday_cum, цепочка накопов, guard logic, колонки
- **sendMedia pattern:** `references/evo-sendmedia-pattern.md` — отправка файлов через Evolution API (JSON+base64, не multipart)
- **NEVER restart:** `alikhan.service`, `alikhan-document-extractor.service`, or Evolution API without explicit approval

## DB Operations

Connect via Docker:
```bash
docker exec evolution-postgres psql -U evolution -d evolution_db -c "SELECT ..."
```

Key tables:
- `bot_memory_messages` — raw WhatsApp messages and extracted document text
- `bot_memory_facts` — legacy facts table (⚠️ **2026-07-18: OJR migration complete** — qa.py/poll.py/fill_ejo.py/main_waha.py now write to and read from `ojr_section3_work_log` + `ojr_section1_personnel` + `ojr_incidents` + `ojr_materials`. `bot_memory_facts` retained as fallback on error.)
- `bot_schedule_phases` — production schedule (phases + sub-tasks)
- `bot_building_profiles` — building metadata
- **`ojr_*` tables** (14 tables) — structured ОЖР schema (ГОСТ РД-11-05-2007 / Приказ 1026/пр). Replaces `bot_memory_facts` (category fields) + `bot_poll_residuals`. See `references/ojr-schema.md`.

### ОЖР Schema (2026-07-18)

Full schema reference: `references/ojr-schema.md`.
SQL files: `/home/hermes-workspace/Alikhan-migration/db/ojr_schema.sql` (CREATE), `/home/hermes-workspace/Alikhan-migration/db/ojr_migration.sql` (data migration).

**Quick inspection:**
```bash
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
  SELECT tablename FROM pg_tables
  WHERE schemaname='public' AND tablename LIKE 'ojr_%'
  ORDER BY tablename;
"
```

**Key views:**
- `ojr_v_daily_works` — daily work log with schedule phase names
- `ojr_v_active_personnel` — active ITR staff
- `ojr_v_open_gsn_orders` — unresolved GSN orders with days_left
- `ojr_v_open_cchecks` — unresolved construction control checks
- `ojr_v_recent_weather` — weather for last 30 days

**Migration pitfalls (SQL):**
- Russian decimal separator: facts contain `113,56` → use `REPLACE(..., ',', '.')::NUMERIC`
- Wrap unparseable volumes in `BEGIN/EXCEPTION WHEN OTHERS THEN v_volume := NULL; END`
- Must SELECT `id` explicitly in cursor loops that reference it

### Schema migrations

When adding columns, use `IF NOT EXISTS`:
```sql
ALTER TABLE bot_schedule_phases ADD COLUMN IF NOT EXISTS code VARCHAR(20);
ALTER TABLE bot_schedule_phases ADD COLUMN IF NOT EXISTS responsible VARCHAR(100);
```

After migration, update `seed_schedule()` in `db.py` to match the new schema.

## Schedule Management

### Data sources

The canonical schedule source is **ГРАФИК СМР.pdf** — a 2-page PDF from the project management team. 

Full extracted schedule data: `references/schedule-grafik-smr.md` (53 tasks, last synced 02.07.2026). 

**Правило источников:**
- **ГРАФИК СМР.pdf** → плановые даты и структура этапов. Это «что должно быть».
- **ЕЖО (Ежедневный отчет)** → фактическое выполнение. Это «что сделано на самом деле».
- **Не путать:** PDF = план, ЕЖО = факт. Никогда не делай выводов о завершении только по PDF.

### Verifying completion status via ЕЖО

To check if work is actually complete, read the ЕЖО file for the relevant date:

```python
import openpyxl
wb = openpyxl.load_workbook('/tmp/ЕЖО_YYYY-MM-DD_v1.xlsx', data_only=True)
ws = wb['Ежедневный отчет']
```

**Key columns (data rows 24+, header row 20):**
| Col | Letter | Name | Written by | Notes |
|-----|--------|------|-----------|-------|
| 11 | K | Кол-во | template | Contract volume |
| 12 | L | План сут | fill_ejo | = today's v |
| 13 | M | Факт сут | fill_ejo | = today's v |
| 14 | N | % сут | fill_ejo | = v/O*100 |
| 15 | O | План мес | template | Poll filter |
| 16 | P | Накоп мес | fill_ejo | = prev_p + v |
| 17 | Q | % мес | fill_ejo | = P/O |
| 18 | R | План общ | template | **Preserved** |
| 19 | S | Накоп общ | fill_ejo | = prev_s + v |
| 20 | T | % общ | fill_ejo | = S/R |
| 21 | U | Остаток | fill_ejo | = O − P (пересчитывается при M>0) |

**PITFALL: Headers occupy merged cells (15, 18) while values are in the right-side sub-columns (16, 19).** Row 20 shows headers in 15 and 18; actual values are written to 16 and 19. Always use the column NUMBERS from `fill_ejo.py`, not the header labels alone.

**Completion check pattern:**
```python
plan = ws.cell(row, 11).value       # K — контрактный план
cum_smr = ws.cell(row, 19).value    # S — накоп с начала СМР
pct = ws.cell(row, 20).value        # T — %
is_done = (cum_smr is not None and cum_smr == plan and pct == 1)
```

**PITFALL: Daily columns (12-13) are often empty even for completed work.** Always check Col 19 (SMR cumulative) and Col 20 (%), not daily columns.

**PITFALL: Monthly cumulative (Col 16) is NOT reliable for completion.** Always use Col 19 (SMR cumulative). The user may correct monthly cumulative independently of SMR cumulative.

**PITFALL: Auto-formula in raw v1 ЕЖО.** In uncorrected v1, Col 19 = Col 11 and Col 20 = 1 for ALL rows — this is an auto-formula, not real completion. After user correction (v2+), Col 16 gets emptied for rows without actual work, while Col 19+20 are filled only for rows with real completion. **If Col 16 is empty AND Col 19 = plan AND Col 20 = 1 → real completion. If Col 16 = plan AND Col 19 = plan → auto-formula, ignore.**

**PITFALL: Corrected files may arrive with different filenames.** Look for `/tmp/corrected_ЕЖО_*.xlsx` and `/tmp/ЕЖО_YYYY-MM-DD_v2.xlsx` (or v3, v4). The user uploads corrections via sandbox WhatsApp group.

### Cross-validation workflow

After loading PDF schedule data into DB:
1. Run `check_delays()` to find overdue tasks
2. For each overdue task, cross-reference with ЕЖО:
   - Find matching rows by work code or description
   - Check Col 19 (cumulative SMR) and Col 20 (percentage)
   - If Col 19 == Col 11 and Col 20 == 1 → mark `completed`
3. **Never report delays without cross-validating against ЕЖО first**

### Extracting schedule from PDF

Use `pdfplumber`:
```python
import pdfplumber
pdf = pdfplumber.open('ГРАФИК СМР.pdf')
for page in pdf.pages:
    text = page.extract_text()
    # Parse lines: "N TaskName Duration Start End Responsible"
```

PDF structure:
- 2 pages, ~53 tasks
- Top-level phases: «Этап 1» through «Этап 8»
- Sub-tasks with codes like 2.1, 3.5, 4.1
- Date format: Russian abbreviated weekday + DD.MM.YY (e.g., «Сб 23.05.26»)
- Responsible: Заказчик, Подрядчик, Стороны

### DB structure for schedule

```sql
bot_schedule_phases:
  id, building, code, phase_num, phase_name, description,
  start_date, end_date, duration_days, status, responsible, parent_phase_id
```

- `phase_num`: 1-8 for top-level phases, same number for sub-tasks under that phase
- `parent_phase_id`: sub-tasks link to their parent phase row
- `code`: e.g., '2.1', '3.5' — null for phase headers
- `status`: 'completed', 'active', 'planned'

### Query functions (in db.py)

- `get_schedule()` — all rows, ordered by start_date
- `get_active_phases()` — where start ≤ today ≤ end AND status ≠ completed
- `check_delays()` — where end < today AND status ≠ completed
- `get_upcoming_phases(days=30)` — upcoming within N days

`check_delays()` is used by `db_lookup.py` for the «отставания» trigger. **Verify end dates are correct before marking as delays** — the PDF may be outdated and actual completion may differ.

## ЕЖО Workflow (v3 — 10.07.2026)

**Формат:** 3 листа: «Ежедневный отчет», «Персонал и техника», «Материалы и планы». Лист «Фототчет» удалён.

### Ключевые изменения v3

1. **Фотоотчёт** — строки 856-859 основного листа (не отдельный лист):
   - A856=Общежитие, A857=АБК, A858=Галерея, A859=Общие планы
   - **Перед вставкой ОБЯЗАТЕЛЬНО:** `ws._images.clear()` + снять объединение ячеек в строках 856-859 (`ws.unmerge_cells()`)
   - **Сетка фото:** фиксированные колонки C(3), E(5), J(10), N(14), Q(17) — по индексу фото в здании
   - Фото 1→C, Фото 2→E, Фото 3→J, Фото 4→N, Фото 5→Q. Максимум 5 фото на здание.
   - **НИКОГДА не использовать `col + offset*2`** — фото будут наслаиваться. Только фиксированные колонки.
   
2. **Жёлтая заливка** — ТОЛЬКО строки с объёмами за сегодня (L>0 или M>0). НЕ все активные фазы.

3. **Готовность объекта** — K853 = `{pct}%` с жёлтой заливкой (FFFF00). J853 — очистить (был «x%»).
   - Формула: `base = sum(plan × min(fact/plan, 1.0)) / sum(plan) × 100` по всем строкам с K>0
   - Итог: `round(base × (1 - 0.06) + 6)` — где 6% = раздел 1 (ПСД, всегда 100%)
   - `calc_completion_pct(ws)` в `fill_ejo.py` реализует эту логику

4. **Активные фазы** — из `bot_schedule_phases` (status='active', start_date ≤ today). Строки активных фаз НЕ удаляются из отчёта даже без объёмов.

5. **Извлечение из .xlsx** — `_extract_ejo_volumes()` в `main_waha.py`. При загрузке ЕЖО бот парсит коды и объёмы в QA-факты.

Детали: `references/ejo-fill-logic.md`.

See `fill_ejo.py` and AGENTS.md for the full ЕЖО cycle:
- Auto-fill → manual correction → diff by codes → template + `ЕЖО_{date}_v1.xlsx`
- **Cron `7adc37a6efc5`:** daily 8:00 Bishkek (02:00 UTC) — updates template from the **latest** version (highest v number) of yesterday's EJO. Script: `/home/hermes-workspace/.hermes/scripts/ejo_auto_template.py`
- Corrected files arrive via sandbox (document_extractor → `/tmp/corrected_ЕЖО_*.xlsx`)
- `SIM_DATE = None` in production

### Corrected EJO → template update

When user sends a corrected `.xlsx` file to WhatsApp:
1. Bot receives document → extracts base64 → saves to `/tmp/corrected_{fname}`
2. `_update_template_from_correction()` in `main_waha.py`:
   - Compares corrected file with latest auto-generated ЕЖО
   - Builds code→value maps for **all 7 numeric columns (col 15-21)**: мес.план, мес.факт, мес.%, общ.план, общ.факт, общ.%, остаток
   - Reports diffs to sandbox group
   - Copies corrected file as new template + saves dated copy to `/tmp/ЕЖО_{date}_v1.xlsx`
3. Template now has corrected факт values → poll correctly filters by O>0 and U>0.
   **⚠️ AL-015 (16.07.2026):** `_update_template_from_correction()` больше НЕ закрывает опрос автоматически. Шаблон обновляется, опрос продолжается.

### Force EJO generation

**«Алихан ежо принудительно»** — generates EJO without data completeness checks.

Triggers: `ежо принудительно`, `ежо все равно`, `ежо несмотря`, `заполни ежо принудительно`, `отчет принудительно`.

Flow:
1. If poll active → closes poll (fills missing with defaults)
2. Generates EJO via `fill_ejo.py` (or `close_poll()`)
3. Sends `.xlsx` file to group
4. No warnings about missing data — use when data is knowingly incomplete

### Row hiding (активно с 16.07.2026)

В сгенерированном ЕЖО скрываются строки без работ сегодня И без остатка (U≤0):
- Есть работа сегодня (L или M) → видна
- O > 0 И U > 0 (план + остаток) → видна
- Заголовки секций/подсекций → видны
- Фаза 8 → скрыта полностью (нет подуровней, нет работ)
- Остальное → скрыто

### Template update logic (ejo_auto_template.py)

```python
# Find all EJO files for yesterday, sorted by modification time (newest last)
all_files = sorted(glob.glob(f"/tmp/ЕЖО_{date_str}*.xlsx"), key=os.path.getmtime)
latest = all_files[-1]  # most recently modified wins

# Skip if template already matches or is newer
if os.path.exists(TEMPLATE) and os.path.getmtime(TEMPLATE) >= os.path.getmtime(latest):
    return  # [SKIP]

# Backup old, copy latest as new template
shutil.copy2(latest, TEMPLATE)
```

**Sort by mtime, not filename.** Filename patterns (v1, v2) are unreliable — corrected files may use different naming. Always sort by modification time.

## QA Parser Architecture (v4 — 11.07.2026)

**File:** `bot/qa.py`

The QA parser receives raw WhatsApp text from the production-listener or sandbox and extracts structured facts. **As of 2026-07-18, routes directly to OJR tables** with per-category targeting (see `references/ojr-migration-routing.md`): персонал → `ojr_section1_personnel`, work volumes → `ojr_section3_work_log`, инцидент → `ojr_incidents`, документация/материалы → `ojr_materials. All OJR writes have graceful fallback to `bot_memory_facts` on error.

### Two-stage extraction

```
User text → _extract_vor_codes()  → VOR codes saved directly (no LLM)
          → remaining text         → Grok for personnel/incidents/equipment
```

**Stage 1 — VOR code extraction (pure regex, no LLM):**

`_extract_vor_codes()` uses a regex to find ALL VOR code segments from the original user text before anything reaches Grok. This eliminates two bugs:
1. **LLM hallucination of fake codes** — Grok never sees VOR codes, so it can't invent `3.3.2.1 = 2191.3`
2. **Планы prefix stripped** — regex detects `Планы`/`план` before the code and saves with category=`'план'` instead of `'объём'`

**Pattern matched:** `[prefix] CODE = VOLUME [unit]`
- Code: 3-part (`3.3.2`) or 4-part (`7.2.1.1`)
- Separator: `=`, `—`, `–`, `-`
- Volume: integer or decimal (`.` or `,` as decimal separator)
- Unit: explicit match against known measurement units (`м3`, `м2`, `кг`, `т`, `шт`, `км`, `пог.м`, etc.) — prevents eating Russian words like `Планы` that follow immediately (e.g. `1.5 м3Планы 3.3.2 = 104.3`)
- Prefix gap: `[\w\s]*?` (lazy, v15.07.2026) — allows text like «на завтра» between prefix and code. Old `\s*` only matched whitespace.
- Prefix detection: `is_plan = re.search(r'[Пп]лан|завтра', prefix)` with fallback to full_match `m.group(0)` when prefix group is empty (fixes «Работы ... Планы на завтра 3.1.1» — where «Работы» gets eaten by the gap)
- Plan/Work coexistence: `pn[cd] = vl` always (no `cd not in dn` guard) — same code can have both work and plan values

**Stage 2 — Grok extraction (structured JSON, v5 — 14.07.2026):**
Only text that didn't match any VOR code pattern is sent to Grok. The prompt requests structured JSON array: `[{"building","category","fact"}]`. Parser uses `json.loads()` with fallback to old pipe-delimited format. **Neil XBT pattern:** «natural language handoffs drift by week 3, structured handoffs don't.» Grok output is now a typed contract, not free text.

**Fact text for VOR codes** preserves the original prefix (e.g. `"Планы 3.3.2 = 104.3м3"` not `"3.3.2 = 104.3м3"`) so downstream `fill_ejo.py`'s `volumes()` function correctly detects `'план' in txt.lower()` and routes to plans dict.

### Downstream routing in fill_ejo.py

`volumes(date)` queries ALL QA facts (no category filter), then parses each fact text with regex:
- `is_plan = 'план' in txt.lower() or x.get('category') == 'план'` — detects plans from BOTH text prefix AND DB category field
- Plans → `pn[cd] = vl` (always added, even if same code has work fact — v15.07.2026)
- Works → `dn[cd] = vl`
- Returns `(r, pn, dn)` — 3-tuple: combined all codes, plans-only, works-only (v15.07.2026)
- `fill()`: `vols = {k:v for k,v in r.items() if k in dn}` — cleanly separates works from plans

The «Материалы и планы» sheet also searches for `'план' in fact.lower()` across all facts for its own plan table — this also works because the prefix is preserved.

### Test patterns

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m pytest test_qa_parser.py -v  # 6 tests, all must pass
python3 verify_ejo.py 2026-07-15         # compare v1 vs corrected EJO
python3 -c "from qa import _extract_vor_codes; print(_extract_vor_codes('7.2.1.1 = 1.5 м3Планы 3.3.2 = 104.3 м3'))"
# Expects: ([{code:'7.2.1.1', category:'объём'}, {code:'3.3.2', category:'план'}], '')
```

Full test patterns: `references/qa-parser-test-patterns.md`.

### Pitfalls

- **Unit regex must be explicit, not `\S*` or `\w*`.** Russian Unicode letters like `П` are `\w` in Python's `re` module — a catch-all `\w*` would eat `м3Планы` as a single unit token. Use an explicit measurement unit pattern instead.
- **Preserve prefix in fact text.** The fact text `"Планы 3.3.2 = 104.3м3"` enables both `volumes()` and the plans sheet to detect plans by text search. Stripping the prefix breaks downstream routing.
- **Remove matched segments from remaining text.** Use `remove_first_match()` that preserves characters before/after the match but cleans up surrounding whitespace and punctuation artifacts (leading `. ` etc).

## Calendar Reminders

Restored 06.07.2026 from n8n workflow `nsox5DrKIF1KLUYi` (Calendar Reminders). Runs as a background daemon thread in `main_waha.py`.

### How it works

1. **Background thread** (`calendar_reminder_loop`) runs every 60 seconds
2. Queries `bot_calendar_events` WHERE `status='active'` AND `reminder_sent=FALSE` AND `remind_at <= NOW()`
3. Formats reminder message with title, description, location, time, timezone
4. Sends to WhatsApp group via `send_msg()`
5. Marks `reminder_sent = TRUE`

### DB functions (in db.py)

| Function | Purpose |
|----------|---------|
| `get_due_reminders()` | Returns all unsent reminders where `remind_at <= NOW()` |
| `mark_reminder_sent(event_id)` | Sets `reminder_sent = TRUE` |
| `create_calendar_event(chat_id, title, event_start, remind_minutes_before, ...)` | Creates new event with computed `remind_at` |
| `get_calendar_events(chat_id, range)` | Lists events (today/week/all) |

### Commands

| Trigger | Action |
|---------|--------|
| `Алихан напомни <текст> <дата> <время>` | Creates calendar event (e.g., `Алихан напомни совещание 15.07 14:00`) |
| `Алихан календарь` / `события` / `ивенты` | Lists upcoming events for the week |

### Table schema

```sql
bot_calendar_events:
  id, chat_id, title, description, location, timezone,
  event_start, event_end, remind_at, remind_minutes_before,
  reminder_sent BOOLEAN, status, created_at, updated_at
```

Default timezone: `Asia/Bishkek` (UTC+6). Default remind: 30 minutes before.

### Pitfall

- **Reminders are NOT sent to production group.** The calendar thread sends to whatever `SANDBOX` is set to in `main_waha.py`. Production reminders require a separate thread or explicit approval.
- **Events persist after sending** — `reminder_sent = TRUE` prevents re-sending but the row stays for history.

## Verification

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile main_waha.py router.py fill_ejo.py db.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
tail -30 /tmp/alikhan.log
```

### Verification Tools (15.07.2026)

Three new scripts added after the 31-bug session:

| Tool | Purpose | Command |
|------|---------|---------|
| `verify_ejo.py` | Compare v1 EJO vs corrected | `python3 verify_ejo.py 2026-07-15` |
| `test_qa_parser.py` | 6 parser test cases | `python3 -m pytest test_qa_parser.py -v` |
| `health_check.sh` | 8 infrastructure checks | `bash health_check.sh` |

**verify_ejo.py** exits 0 if all P/Q/U values match corrected EJO (±0.5 tolerance), exits 1 with diff output otherwise. Run after every EJO generation.

**health_check.sh** checks: bot pid, Evolution API, PostgreSQL, DB connection, template, document extractor, last EJO, bot log errors. All 8 must pass.

### Pre-commit Hook (.git/hooks/pre-commit)

Catches before commit:
- `py_compile` errors in fill_ejo.py, qa.py, main_waha.py
- `range(2)` hardcoded limits (warns)
- `continue` before `save_message` (warns)

## Pitfalls

1. **Не делай выводов о просрочках только по PDF.** ГРАФИК СМР.pdf даёт плановые даты. Фактическое завершение подтверждай через ЕЖО (Col 19 + Col 20).
2. **ЕЖО дневные колонки (12-13) часто пустые — это нормально.** Смотри накопительные: Col 19 «с начала СМР» и Col 20 «%».
3. **Шаблон ЕЖО и последний сгенерированный ЕЖО — часто один и тот же файл.** `_update_template_from_correction()` копирует corrected файл и как шаблон, и как `/tmp/ЕЖО_{date}_v1.xlsx`. Проверяй `md5sum` перед тем как утверждать что шаблон «не обновился».
4. **Never restart services without approval** — alikhan.service, alikhan-document-extractor.service, Evolution API.
5. **Production group is read-only** — never send to `120363400682390076@g.us` without explicit approval.
6. **psql is not on PATH** — always use `docker exec evolution-postgres psql`.
7. **READ architecture.md first** for any architecture question. It contains the full n8n→EVO v5 cross-reference (15 живых функций, 1 утрачена, 2 частично) and is the single source of truth for what works and what doesn't.
8. **🐉 Poll: O>0 ∧ U>0 → в опрос (2026-07-16).** Столбцы O (план) и U (остаток) — фильтр опроса. Пользователь заполняет вручную. В ЕЖО U пересчитывается: `U = O − P`. В шаблоне U — остаток на начало месяца.

45. **🐉 N column — НЕ хардкодить 1 (2026-07-16).** `sw(ws, r, 14, 1)` ставит 100% для всех строк. Правильно: `round(v / mp * 100, 1)` — реальный % за сутки от месячного плана. Формат: `0.0"%"`.

46. **🐉 P/S cumulative — prev + v (2026-07-16).** `cum_p = round(prev_p + v, 2)` — вчерашний накоп + сегодня. Старая версия писала `round(prev_p, 2)` без добавления v (рассчитывала что corrected EJO уже включает сегодня).

47. **🐉 Row hiding: O>0 И U>0 → строка видна (2026-07-16).** Скрываются только строки без работ сегодня И без остатка (U≤0). Фаза 8 скрыта (нет подуровней, нет работ). Заголовки секций (2, 3.1) видны. Правило: есть работа ИЛИ есть план+остаток → видна.

48. **🐉 Bridge media send: requests.post handler (2026-07-16).** `_send_document()` использует `requests.post` → `bridge_wrapper.py` нужен handler для `/message/sendMedia/`. Без него: 404 Cannot POST. Express body limit: `{limit: '50mb'}`.

49. **🐉 Timesheet (табель) — из локального кеша (2026-07-16).** `get_aibikon_headcount()` читает табель из `/tmp/hermes-media-cache/` через `local_path` в DB tags. Старый вызов Evolution API `/chat/getBase64FromMediaMessage/` заменён. При отсутствии файла: default total=5, by_prof={}.

50. **🐉 Три этапа — не мешать (2026-07-16).** Месячный план (шаблон, O/U руками) ≠ Опрос (O>0∧U>0) ≠ ЕЖО (формулы, скрытие). Не применять правила одного этапа к другому.
9. **🐉 Дублирование процессов main_waha.py (2026-07-11).** Каждый лишний процесс = N× ответов + N× записей в БД. Три процесса — тройные сообщения, 38 дубликатов фактов за день. **Диагностика:** `pgrep -af 'main_waha' | grep -v grep`. Должен быть ровно 1 процесс (systemd-юнит). **Фикс:** `kill PID1 PID2` — убить лишние, оставить systemd. **Как отличить:** systemd процесс выглядит как `/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3 /home/hermes-workspace/Alikhan-migration/bot/main_waha.py`; лишние — `python3 main_waha.py` без полного пути или через `/bin/bash -lic`. **Предотвращение:** `systemctl --user status alikhan.service` убедиться что нет ручных запусков.
10. **🐉 Grok hallucinates VOR codes (2026-07-11).** LLM выдумывает коды работ. Пользователь пишет `«7.2.1.1 = 1.5 м3 Планы 3.3.2 = 104.3»`, Grok генерирует `«3.3.2.1 = 2191.3кг»` — несуществующий код. **Корень:** VOR-коды отправляются в LLM, LLM фабрикует значения из контекста. **Фикс:** извлекать VOR-коды regex'ом из оригинального текста ДО отправки в LLM (см. QA Parser Architecture). **Восстановление после бага:** `DELETE FROM bot_memory_facts WHERE fact_date='YYYY-MM-DD' AND fact LIKE '%<hallucinated_code>%'`. **Диагностика:** `SELECT category, fact FROM bot_memory_facts WHERE fact_date='2026-07-11' AND source='qa'` — искать коды, которых нет в оригинальных сообщениях пользователя.
11. **🐉 Plans routing: qa() не читала category из БД (2026-07-11).** `qa()` в fill_ejo.py выбирала `SELECT fact` без `category` → `x.get('category')` всегда None → `volumes()` не могла отличить планы от работ. **Фикс:** `SELECT fact, category FROM bot_memory_facts` + `is_plan = 'план' in txt.lower() or x.get('category') == 'план'`. **DB cleanup после дублирования процессов:** `DELETE FROM bot_memory_facts a USING bot_memory_facts b WHERE a.id > b.id AND a.fact_date = b.fact_date AND a.fact = b.fact AND a.category = b.category`.
12. **🐉 Жёлтая заливка — только строки с объёмами, НЕ все активные фазы.** Пользовательская правка 10.07.2026: Codex подсветил ВСЕ строки активных фаз 3,4,7,8 жёлтым (183 строки). Правило: жёлтый ТОЛЬКО если L(12) > 0 или M(13) > 0. Проверка: `has_volume = plan_val > 0 or fact_val > 0`.
13. **🐉 volumes() в fill_ejo.py не находит данные: проверь категории QA.** Когда пользователь пишет «данные по работам не заполнены» (work data not filled), а бот отвечает «данные приняты» — первым делом проверь категории QA-фактов. `volumes()` (line 267) ищет только категории: `бетонирование`, `монтаж`, `земляные работы`, `объём`. Если QA использует другую категорию (например, пользователь скомандовал «алихан объём 2.2.3.3 = 125» — это сохраняется с категорией `объём`, не `бетонирование`), `volumes()` вернёт `{}` и ЕЖО останется пустым. **Диагностика:** `python3 -c "from fill_ejo import volumes; from datetime import datetime; v = volumes(datetime.now()); print(v)"` + проверка `SELECT category, fact FROM bot_memory_facts WHERE fact_date=CURRENT_DATE AND source='qa'` в БД. **Если категория не совпадает** — расширь список категорий в `volumes()` или измени парсер QA, чтобы он использовал ожидаемую категорию.
14. **🐉 Материалы и планы — реализация парсинга не завершена.** В `fill_ejo.py` секция `if name == "Материалы и планы"` (line 715) имела `pass # TODO` — парсинг материалов из QA не был реализован. Вместо этого код **безусловно очищал** старые значения в шаблоне (строки 8-24, колонки 2-8), затирая пользовательские правки даже когда новых данных не было. **Фикс (10.07.2026):** (1) реализован парсинг материалов: ищет факты с ключевым словом `материал` в любой категории, парсит по шаблону `"Материал X - YYYм2"` → заполняет строки 14-23. (2) Добавлен guard: если новых данных нет — удаляем только жёлтые ячейки (автозаполненные старые значения), сохраняя не-жёлтые (пользовательские правки). **Если правишь этот код:** не ставь `pass` без логирования; всегда проверяй `if mat_facts` перед очисткой; используй `yellow(cell)` чтобы отличить автозаполненные ячейки от ручных правок.

15. **🐉 Табель АйБиКон = только ИТР (2026-07-12).** В табеле нет каменщиков/бетонщиков — только ИТР-персонал: рук.проекта, геодезист, ТБ, ПТО, электрик. Поэтому M17 (чел.-часы всего) = M18 (ИТР-часы) = `aibikon['total'] * 8`. Это НЕ баг — все сотрудники АйБиКон в табеле являются ИТР. Число подрядчиков (Атантай, Майкадам) берётся из QA-фактов (WhatsApp → БД), не из табеля. **При проверке ЕЖО:** если M17 = M18 для АйБиКон — это корректно.

21. **🐉 Structured QA Parser — Neil XBT pattern (2026-07-14).** `qa.py` Grok-промпт переведён с pipe-delimited текста (`building | category | fact_text`) на structured JSON (`[{"building","category","fact"}]`). Парсинг: `json.loads()` с fallback на старый `split("|")`. Причина: «natural language handoffs drift by week 3» (Neil XBT). Если Grok меняет формат вывода — старый парсинг теряет данные молча. Structured JSON + field validation предотвращает дрифт.

22. **🐉 Personnel regex — формат «Имя ИТР N» не парсился (2026-07-14).** `staff()` в `fill_ejo.py`: regex `m4` ловил `(name)\s+(\d+)\s*итр` (число ДО «ИТР»), но QA-парсер возвращает «Атантай ИТР 1» (число ПОСЛЕ). Добавлен `m6`: `(name)\s+итр\s+(\d+)` — «Атантай ИТР 1». **Диагностика:** EJO показывает общее число (6) без ИТР → проверить QA-факты: есть ли отдельные строки «ИТР N» → добавить regex если число после «ИТР».

23. **🐉 Completion % — НЕ менять формулу без approval (2026-07-14).** Агент посчитал 26% «неправильным» и изменил `calc_completion_pct()` чтобы исключать будущие фазы → получил 94%. **Пользователь откатил:** «Готовность проекта в процентах старая формула верная 26% правильно». Старая формула считает % от ВСЕГО проекта (включая будущие фазы 5 и 6 с нулевым выполнением). 26% = корректный процент общей готовности. **Правило:** `calc_completion_pct()` — бизнес-логика, НЕ менять без явного «да» от пользователя. Даже если число «кажется неправильным» — сначала спросить. Формула: `base = sum(plan × min(fact/plan, 1.0)) / sum(plan) × 100` по ВСЕМ строкам с K>0, затем `round(base × 0.94 + 6)`. 26% — корректно, НЕ «исправлять».

24. **🐉 НИКОГДА не отправляй ЕЖО не проверив источник данных (2026-07-14).** Пользователь: «Атантай я не подавал, ты снова не разобрался а уже шлешь мне ЕЖО». Перед генерацией/отправкой ЕЖО всегда проверяй: (1) какие QA-факты за сегодня, (2) кто их источник (пользователь или production-listener), (3) соответствуют ли они тому что пользователь реально подавал. **Диагностика:** `SELECT fact, category, to_char(created_at, 'HH24:MI') FROM bot_memory_facts WHERE fact_date=CURRENT_DATE AND source='qa'`. Если есть сомнительные факты (production-listener поймал старые данные) — удалить перед ЕЖО. **Антипаттерн:** увидел баг в коде → исправил код → сразу перегенерировал и отправил ЕЖО. Правильно: исправил код → проверил данные → показал пользователю → получил «ок» → отправил.

25. **🐉 Логотип теряется при вставке фото (2026-07-14).** `ws._images.clear()` на строке 772 `fill_ejo.py` удаляет ВСЕ изображения включая логотип компании в верхней части листа. **Фикс:** перед `clear()` сохранить non-photo images (строки НЕ 856-859) в `saved_images`, после вставки фото восстановить через `ws._images.append(img)`. **Проверка:** `len(ws._images)` должно быть ≥ 10 (9 фото + логотип). Если = 9 — логотип потерян.

27. **🐉 Bridge sendMedia: через bridge_wrapper, не напрямую (2026-07-16).** `_send_document()` использует `requests.post` → bridge_wrapper перехватывает `/message/sendMedia/` → b64decode → tempfile → bridge `/send-media`. Express body limit: `{limit: '50mb'}` (413 PayloadTooLargeError для ЕЖО >100KB). См. `references/evo-sendmedia-pattern.md`.

28. **🐉 EJO Debugging Flow — НЕ начинай с ЕЖО (2026-07-15).** Когда пользователь говорит «отчёт неправильно заполнен» — сначала WhatsApp (какие данные подал), потом БД (какие факты сохранил бот), потом ЕЖО (как легло). Агент систематически начинал с ЕЖО и пропускал отсутствующие данные. Пользователь: «сначала в песочницу посмотри, ты еще до боевой не дорос». Полный workflow: `references/ejo-debugging-flow.md`.

29. **🐉 Поиск персонала в ЕЖО — колонки N-P, не строки 9-13 (2026-07-15).** Персонал (Атантай, Майкадам) в колонках N-P строки 10-12. Строки 9-13 колонок B-D — статистика ТБ, не персонал. Искать по ВСЕМУ листу, не предполагать зону.

30. **🐉 QA regex \s* не матчит текст между префиксом и VOR-кодом (2026-07-15).** `_extract_vor_codes()` в `qa.py`: `\s*` между префиксом (Group 1) и кодом (Group 2) матчит ТОЛЬКО пробелы. Строка «Планы на завтра  3.1.1» — « на завтра  » содержит буквы → regex ломается, код матчится без префикса → category='объём'. **Фикс:** `\s*` → `[\w\s]*?` (lazy match word+whitespace). Добавить `завтра` в `is_plan` detection: `re.search(r'[Пп]лан|завтра', prefix)`. **Диагностика:** `python3 -c "from qa import _extract_vor_codes; f,r = _extract_vor_codes('Планы на завтра 3.1.5 = 142,66'); print(f)"` — должен показать `is_plan=True`.

31. **🐉 save_message() вызывается ПОСЛЕ age gate — старые сообщения не в БД (2026-07-15).** `main_waha.py`: age gate (L517-522, `now_ts - msg_ts > 300`) выполняется ДО `_log_msg()` (L868). Старые сообщения → `seen.add(mid); continue` → никогда не доходят до сохранения. Симптом: Evolution API показывает N сообщений, `bot_memory_messages` — меньше. **Фикс:** `_log_msg(SANDBOX, sender, "user", text)` сразу после извлечения текста (L529), до всех `continue`-ов. **НЕ удалять** старый вызов на L868 — дублирующий вызов безопасен (save_message проверяет дубликаты).

32. **🐉 Планы и работы для одного кода: `cd not in dn` блокировало планы (2026-07-15).** `volumes()` в `fill_ejo.py`: когда один код (напр. 3.1.1) имеет И работу (50м2) И план (41.8м2), условие `if cd not in dn and cd not in pn` для планов блокировало добавление (работа уже в dn). **Фикс:** `pn[cd] = vl` без проверки dn — планы всегда добавляются независимо от работ. **Возвращаемое значение:** `volumes()` теперь возвращает 3 значения: `(r, pn, dn)` — combined, plans-only, works-only. `fill()` использует `vols = {... if k in dn}` для отделения работ.

33. **🐉 volumes() подбирает факты из не-рабочих категорий — Grok hallucination pollutes EJO (2026-07-15).** `volumes()` запрашивает ВСЕ категории QA-фактов и парсит regex'ом любые строки с VOR-кодами. Если Grok галлюцинирует код в категории `[монтаж]` (напр. `3.1.3 = 105.0`), он попадает в works-dict и перезаписывает правильное значение из `[объём]`. **Симптом:** в ЕЖО факт = 105 вместо 150. **Диагностика:** `SELECT category, fact FROM bot_memory_facts WHERE fact_date=CURRENT_DATE AND fact LIKE '3.1.3%'` — если видишь тот же код в нескольких категориях, лишняя — галлюцинация. **Фикс:** в `volumes()` добавлен guard: `cat = x.get('category', ''); if cat and cat not in ('объём', 'план'): continue` — пропускает факты из категорий вроде `монтаж`, `земляные работы`, оставляя только объём и план. **DB cleanup:** `DELETE FROM bot_memory_facts WHERE fact_date='...' AND category NOT IN ('объём','план') AND fact ~ '^\\d+\\.\\d+\\.\\d+'` — удалить галлюцинации с VOR-кодами в не-рабочих категориях.

34. **🐉 Plans table: жёсткий лимит 2 строки на здание (2026-07-15).** Лист «Материалы и планы» — таблица «Планируемые работы на следующий день» имела `for i in range(2)` — максимум 2 пункта на здание. Общежитие имело 3 плана (3.1.1, 3.1.2, 3.1.3) → 3.1.3 не помещался. **Пользователь:** «Нет лимита такого, сколько нужно строчек столько и добавляй». **Фикс:** `range(2)` → `enumerate(items)`, пересчёт `start_row` динамически: `start_row = start_row + max(len(items), 1) + 2`. Здания идут последовательно, каждый со своим количеством строк. **Очистка:** перед записью нового здания очищаются 5 строк (старые leftovers) в колонках 1-4,6.

35. **🐉 Кумулятив: НЕ очищать колонки P/S/U (2026-07-16).** `fill_ejo.py` очищает только дневные колонки (12, 13, 14). Кумулятивные (16, 19) и U (21) — из шаблона. Пишутся как: `cum_p = prev_p + v` (вчера + сегодня), `cum_s = prev_s + v`. `yesterday_cum()` — только если есть чистый вчерашний v1-файл (yp > 0).

36. **🐉 Кумулятив: prev_p + v — корректно (2026-07-16).** `cum_p = round(prev_p + v, 2)` — вчерашний накоп + сегодня. Старая версия писала `round(prev_p, 2)` без v (шаблон из corrected EJO уже включал сегодня) → теперь corrected EJO не включает сегодня как кумулятив, поэтому добавление v корректно. **N (col 14):** `round(v / mp * 100, 1)` — реальный % выполнения за день. Было хардкодом 1.

37. **🐉 Verify before claim — SHOW the verification (2026-07-15, кросспроект).** Агент 7 раз за сессию утверждал факты без проверки: «погода пустая» (смотрел не те ячейки), «персонал пуст» (смотрел не те колонки), «бот не запущен» (не проверил pgrep), «DB IP 172.22.0.3» (не проверил docker inspect). **Правило:** каждое утверждение о данных должно сопровождаться output'ом инструмента проверки в ответе. «Значение = N» → показать `grep`/`python3 -c openpyxl`/`pgrep`. Если не можешь проверить — сказать «не могу проверить». Молчание лучше фабрикации. **SOUL.md:** правило «Show Your Work — MANDATORY».

38. **🐉 Bridge /messages — destructive read (splice) вызывает race condition (2026-07-16).** `app.get('/messages')` делает `messageQueue.splice(0)` — удаляет ВСЕ сообщения при первом чтении. Если PROD-поток (10s poll) читает раньше sandbox-цикла (3s poll), команды песочницы теряются. Бот не отвечает на «Алихан запускай опрос». **Фикс:** bridge_wrapper.py v2 — локальный буфер `_BUFFER`. Каждый `findMessages` вызов: `_fetch_and_buffer()` → `_drain_buffer(remoteJid)`. PROD получает только `PRODUCTION`-сообщения, sandbox — только `SANDBOX`. См. `references/bridge-wrapper-buffer.md`.

39. **🐉 Poll _get_work_items_from_template — v3 (16.07.2026).** Единственный фильтр: столбец O (колонка 15, месячный план) > 0 И столбец U (колонка 21, остаток) > 0. Никаких schedule-based догадок, никаких запасных формул расчёта остатка (plan_cum - fact_cum). Пользователь заполняет O и U в начале месяца через «Алихан раскрой отчет». Здания выводятся динамически (for bld in by_bld), включая НВ/НК/НТ/Благоустройство фазы 7. **Питфол:** если данные не соответствуют фильтру — сказать пользователю что заполнить, НЕ менять код.

40. **🐉 Poll message too long — WhatsApp обрезает (2026-07-16).** При 37+ позициях остатков опрос превышает лимит WhatsApp (~4096 символов). `send_msg()` режет на 3800. **Фикс:** `build_poll_message()` возвращает tuple `(header, residuals)` — заголовок (QA-сводка) и остатки отдельными сообщениями с задержкой 1с. См. `references/poll-message-splitting.md`.

41. **🐉 WhatsApp Bridge НЕ принимает групповые сообщения без --mode bot (2026-07-16).** По умолчанию мост стартует в `self-chat` режиме. В этом режиме ВСЕ входящие из групп дропаются. Бот не видит сообщения 3 дня. **Диагностика:** в логе моста `🔒 Self-chat mode`. **Фикс:** `WHATSAPP_ALLOWED_USERS="*" node bridge.js --mode bot --session ...`. После миграции с Evolution API ОБЯЗАТЕЛЬНО проверить что мост принимает групповые сообщения.

42. **🐉 Не менять логику опроса без ТЗ (2026-07-16).** Агент 4 раза менял фильтр опроса за одну сессию (schedule → O+U → O+план_кум → O). Пользователь: «я понял, мне нужно заполнить остаток, а ты должен сказать о том что я нарушил логику а не менять логику каждый раз». **Правило:** если данные в шаблоне не соответствуют фильтру — сказать пользователю что заполнить, а не менять код.

43. **🐉 Документы через Hermes Bridge — кеш и загрузка (2026-07-16).** Мост скачивает входящие документы в `/tmp/hermes-media-cache/`. `bridge_wrapper.py` передаёт `_media.mediaUrls`. Бот читает локальные файлы, не дёргает Evolution API. Кеш-директории задаются через `HERMES_DOCUMENT_CACHE_DIR`.

44. **🐉 Здания в опросе — хардкод-список (2026-07-16).** `build_poll_message()` использовал `for bld in ['Общежитие','АБК','Галерея']` — здания фазы 7 (Благоустройство, НК, НТ) молча пропускались. **Фикс:** `for bld in by_bld` — динамический вывод всех зданий из данных.

27. **🐉 WAHA и n8n — висящие контейнеры (2026-07-14).** VPS 15GB RAM не хватает для локальной LLM. 540MB заняты: n8n+n8n-msf (~400MB, не используются), WAHA (~137MB, legacy — Alikhan переехал на Evolution API). Безопасно остановить: `docker stop n8n n8n-msf waha`. WAHA больше не нужен. Диагностика: `docker stats --no-stream` → `free -h`. После остановки: `sudo sync && echo 3 | sudo tee /proc/sys/vm/drop_caches` для page cache. Очистка Docker: `docker rmi $(docker images ghcr.io/openclaw/openclaw -q)` — образы ~17GB не используются.

17. **🐉 Evolution API sendMedia возвращает 201 но файл не доходит до WhatsApp (2026-07-13).** Бот отправлял документы без проверки ответа. Evolution API принимает запрос (HTTP 201, status=PENDING), но WhatsApp-клиент файл не получает. **Фикс:** `_send_document()` хелпер с проверкой статуса и логированием в `main_waha.py`.

18. **🐉 Evolution API Redis replica — read-only (2026-07-13).** `evolution-redis` был slave внешнего сервера `175.24.232.83:26619`. Внешний мастер недоступен → Redis read-only → документы висят в PENDING. **Диагностика:** `docker exec evolution-redis redis-cli INFO replication | grep role` → `role:slave`. **Фикс:** `docker exec evolution-redis redis-cli SLAVEOF NO ONE` + `docker restart evolution-api`.

19. **🐉 Перезапуск Evolution API ломает WhatsApp-сессию (2026-07-13).** После `docker restart` сообщения не доходят несмотря на `state: open` и HTTP 201. **Фикс:** полный logout (`DELETE /instance/logout/alikhan`) + connect (`GET /instance/connect/alikhan`) + отсканировать QR.

20. **🐉 WhatsApp блокирует QR через API, но Manager UI работает (2026-07-13).** Когда WhatsApp rate-limit'ит привязку устройств («Невозможно связать новые устройства»), API-QR не принимается. **Решение:** Evolution Manager UI — http://72.60.16.105:8080/manager → инстанс alikhan → кнопка Connecting → QR принимается. Manager UI использует другой механизм подключения. **Порядок:** (1) `docker restart evolution-api`, (2) открыть Manager UI в браузере, (3) нажать Connecting, (4) отсканировать QR. **Не делать** `DELETE /instance/delete` + recreate — теряется API-ключ.

16. **🐉 Планы (category='план') НЕ попадают в ежедневные колонки L/M (2026-07-12).** Бот отправлял документы через `requests.post(f"…/sendMedia/alikhan")` без проверки ответа. Evolution API принимает запрос (HTTP 201, status=PENDING), но WhatsApp-клиент файл не получает — особенно .xlsx. Текстовые сообщения и фото доходят, документы — нет. **Фикс:** добавить `_send_document(chat_id, filepath, filename)` в `main_waha.py` — хелпер с проверкой статуса, логированием результата и возвратом True/False. Бот теперь пишет `[SEND OK]` или `[SEND FAIL] HTTP NNN` вместо молчаливого «📊 отправлен». **Проверка:** не доверять логу, проверять факт доставки через WhatsApp-клиент. Если файл не виден — пересохранить через openpyxl и отправить заново. **Причина:** Evolution API bug — не все типы документов корректно передаются в WhatsApp через медиа-эндпоинт.\n\n16. **🐉 Планы (category='план') НЕ попадают в ежедневные колонки L/M (2026-07-12).** `fill_ejo.py` пишет планы только в накопительные колонки (P, S), а L(12)/M(13) остаются пустыми. Это корректное поведение: планы на завтра идут на лист 3 «Материалы и планы», а не в ежедневные колонки листа 1. **При проверке ЕЖО:** если L76/M76 для 3.3.2 пустые, а в БД есть `3.3.2 = 104.3 (план)` — это НЕ баг. Проверь лист 3 — план должен быть там.
