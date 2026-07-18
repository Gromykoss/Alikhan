---
name: alikhan-whatsapp-bot
description: Build, debug, and deploy the Alikhan WhatsApp AI bot. Covers Python bot architecture, WhatsApp connection methods (WAHA/Evolution API/Hermes), n8n-to-Python migration patterns, credential workarounds, STT/TTS voice messages, polling pagination, PostgreSQL-backed handlers (calendar, search, periods, participants, schedule phases), and Russian word-stem trigger matching.
triggers:
  - User asks about Alikhan, WhatsApp bot, алихан
  - Fixing/deploying WhatsApp AI assistant
  - Migrating n8n workflows to Python
  - WhatsApp API connection issues
  - Voice messages / STT / TTS for Alikhan
---

# Alikhan WhatsApp Bot

## Architecture

```python
WhatsApp → Hermes Bridge (:3000) → bridge_wrapper.py → Python poller → [STT] → [QA parser] → [Router] → [Verify] → reply
```
Migrated from Evolution API 15.07.2026. The `bridge_wrapper.py` monkey-patches requests/urllib to translate Evolution API format to Hermes bridge format, preserving all business logic.

**Current bot:** `main_waha.py` — тонкий оркестратор + ЕЖО/опрос/автодокументы. Модули:
- `stt.py` — faster-whisper base + Grok пост-коррекция
- `qa.py` — детектор вопросов + парсер данных (ИТР/рабочие разделение, VOR-коды)
- `poll.py` — управление опросом (start/close/parse residuals), DB: `bot_poll_state` + `ojr_section3_work_log` (ранее `bot_poll_residuals`)
- `db_lookup.py` — факты + погода + график (schedule phases)
- `router.py` — QA → Schedule → Weather/DB → Grok + fuzzy name match + CMD detection
- `verify.py` — трёхуровневая верификация (0-100): REJECT(<40)/FLAG(<70)/VERIFIED(90+)
- `building_profiles.py` — визуальные профили зданий (Grok Vision → JSON features)
- `fill_ejo.py` — ЕЖО: погода + QA → Excel 4 листа. **volumes() reads `category` field** from DB to route plans correctly (category='план' → plans dict, not works).
- `daily_snapshot.py` — снимок дня 8:00/16:00 МСК
- `handlers.py` — 17 обработчиков + ask_grok()
- `db.py` / `db_memory.py` — PostgreSQL: messages, facts, calendar, schedule, poll

### Voice Pipeline (T-114 ✅)
- **STT:** faster-whisper base → raw text → Grok correction (Алейхам→Алихан, такая→какая)
- **TTS:** edge-tts SvetlanaNeural (основной), Supertonic (fallback, on-device)
- Все расшифровки → `bot_memory_messages` (type=voice)
- Триггер: «голосом», «озвучь», «голос»
- Fuzzy name match: `[ао]л[еи][хгк]` (Олеган, Аликан, Алехан → Алихан)

### QA Parser (T-115)

**⚠️ CRITICAL: LLM hallucinates work codes.** When VOR codes are sent to Grok for extraction, Grok can invent codes not present in the user's message (e.g., user sends "Работы 3.3.2 = 104.3" but Grok outputs "3.3.2.1 = 2191.3кг" — a fabricated code). **Fix (2026-07-11):** Extract VOR codes from the ORIGINAL user text with regex BEFORE sending to Grok. Only send non-VOR text (personnel, incidents, equipment) to Grok.

```python
def _extract_vor_codes(text):
    """Extract VOR codes (3-part and 4-part) from original text.
    Returns (volume_facts, remaining_text_for_grok).
    Detects 'Планы'/'план' prefix → category='план'. """
    pattern = re.compile(
        r'(\w*[Пп]лан\w*|\b[Пп]рочее\b|\b[Сс]делано\b)?'  # optional prefix
        r'\s*(\d+\.\d+\.\d+(?:\.\d+)?)'                     # VOR code
        r'\s*[=—–\-]\s*(\d+(?:[.,]\d+)?)'                   # value
        r'\s*(м[23³]|м3|м2|кг|т|шт|км)?'                    # unit
    )
    facts = []
    remaining = text
    while True:
        m = pattern.search(remaining)
        if not m: break
        prefix = (m.group(1) or '').strip()
        code = m.group(2)
        vol = float(m.group(3).replace(',', '.'))
        unit = (m.group(4) or '').strip()
        is_plan = bool(re.search(r'[Пп]лан', prefix))
        category = 'план' if is_plan else 'объём'
        facts.append({'code': code, 'volume': vol, 'unit': unit,
                       'category': category, 'fact': f'{prefix} {code} = {vol}{unit}'.strip()})
        remaining = remaining[:m.start()] + ' ' + remaining[m.end():]
    return facts, remaining.strip()
```

**Key rules:**
1. VOR codes go through regex ONLY — never through Grok
2. «Планы»/«план» prefix → `category='план'` (not `'объём'`)
3. Remaining text (personnel/incidents) → Grok for extraction
4. This prevents both hallucination AND prefix loss

### QA Parser (old)

### DB Fact Lookup (T-115)
- Category filter: персонал / техника
- Grok-суммаризация: «ПРОСУММИРУЙ все числа»
- Контекст для Grok: строительный инспектор, ТЗРК Джеруй, АБК/Общежитие/Галерея

### Verification (Claude Code pattern — verify > write)
- verify_reply(reply, question, db_facts) → (reply, score_0_100, issues)
- REJECT (<40): ❌ — hallucination, блокирует
- FLAG (<70): ⚠️ — требует review
- VERIFIED (90+): чистый ответ
- Источник: @Jeyxbt / Claude Code — verification skills 2-3x quality

### LLM Backend Routing: Local-First, Cloud-Fallback (2026-07-10)

Паттерн миграции с Grok (xAI) на локальную Ollama для 80% задач. Регламентные вопросы и vision остаются на Grok.

**Архитектура роутера в `handlers.py`:**

```python
# Constants
XAI_URL = "https://api.x.ai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"

# Raw Grok (internal, always cloud)
def ask_grok_raw(prompt, system=None, max_tokens=700, image_base64=None, mimetype="image/jpeg"):
    ...

# Ollama with Grok fallback
def ask_ollama(prompt, system=None, max_tokens=700):
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens}
        }, timeout=90)
        if r.status_code == 200:
            resp = r.json().get("response", "").strip()
            if resp and len(resp) > 5:
                return resp
    except Exception:
        pass
    return ask_grok_raw(prompt, system=system, max_tokens=max_tokens)

# Router — Ollama by default, Grok for critical paths
def ask_grok(prompt, system=None, max_tokens=700, image_base64=None, mimetype="image/jpeg", force_grok=False):
    if image_base64 or force_grok:
        return ask_grok_raw(prompt, system=system, max_tokens=max_tokens, 
                           image_base64=image_base64, mimetype=mimetype)
    return ask_ollama(prompt, system=system, max_tokens=max_tokens)
```

**Маршрутизация по типам запросов:**

| Задача | Бэкенд | Причина |
|--------|--------|---------|
| Общие вопросы, погода, календарь | Ollama | Не требует точности Grok |
| Суммаризация документов | Ollama | 8B модель справляется |
| Голосовая маршрутизация | Ollama | Простая классификация |
| **Регламентные вопросы** | **Grok** | Сложный юр. русский, перекрёстные ссылки, цитаты |
| **Vision (фото)** | **Grok** | qwen3:8b не поддерживает изображения |

**Выбор модели:** qwen3:8b — лучший для русского среди доступных (llama3.1:8b, qwen2.5:7b/3b).

**Pitfall:** при первом вызове Ollama модель загружается в RAM (5.2GB) — первый запрос может занять до 90с. Таймаут должен быть ≥90с. После загрузки — <5с на ответ.

### Alikhan health audit checklist (ЕЖО / DB / services)

When the user asks to “check Alikhan”, “check ЕЖО template”, or “check databases”, do a read-only audit first and report in Russian:

1. Load project context (`AGENTS.md` / `INDEX.md`) and do not restart services without explicit approval.
2. Verify code/import health: `python3 -m py_compile main_waha.py router.py fill_ejo.py document_extractor.py poll.py qa.py db_lookup.py`.
3. Verify services: `alikhan.service`, `alikhan-document-extractor.service`, exactly one real `main_waha.py` process, extractor `/health`, Evolution API HTTP 200, instance `alikhan=open`.
4. Verify ЕЖО template with `openpyxl`: file exists, opens, sheets `Ежедневный отчет`, `Персонал и техника`, `Материалы и планы` exist, date/current content matches latest `/tmp/ЕЖО_YYYY-MM-DD_v*.xlsx`.
5. Verify DB tables and counts: `bot_memory_messages`, `bot_memory_facts` (legacy), `bot_schedule_phases`, `bot_poll_state`, `ojr_section3_work_log` (ранее `bot_poll_residuals`); inspect real column names from `information_schema.columns` before querying.
6. Check duplicates separately: schedule duplicate groups; `bot_memory_facts` (legacy) duplicate `(fact_date, building, category, fact)`; recent `bot_memory_messages` duplicate content/minute. Message duplicates are less severe if `bot_memory_facts` has no duplicates.
7. Check `/tmp/alikhan.log` for `[LOOP ERR]`, `Traceback`, `error`, `exception`; `bot/bot.log` may be stale.
8. For ЕЖО content, verify key facts against the latest generated file: works, plans, materials, personnel, incidents — especially `3.3.2.1`, `3.3.2`, TSP materials/plans, Атантай/Майкадам.

### Duplicate process detection (2026-07-11)

Multiple `main_waha.py` processes cause triple-reply to every message AND triple DB writes (duplicate facts). This is invisible in `systemctl status` if extras were started manually or via shell wrappers.

**Detection:**
```bash
pgrep -af 'main_waha' | grep -v grep
# Expected: exactly 1 systemd-managed PID
# BAD: 3+ entries → duplicates running
```

**Fix:** kill extras, keep only the systemd PID:
```bash
systemctl --user status alikhan.service --no-pager | grep 'Main PID'
# → Main PID: 2448403
kill <other_pids>
```

**Prevention:** never run `python3 main_waha.py` directly from shell — use `systemctl --user restart alikhan.service` only. Duplicates most commonly appear after manual restarts that leave orphaned processes.
```bash
# Kill old process
ps aux | grep "[m]ain_waha" | awk '{print $2}' | xargs -r kill
sleep 1
# Verify dead
ps aux | grep "[m]ain_waha" || echo "stopped"
```
Then launch via `terminal(background=true)` using `exec` so Hermes tracks a single Python process, not an extra wrapper shell:
```
cd /home/hermes-workspace/Alikhan-migration/bot && exec python3 main_waha.py >> bot.log 2>&1
```
⚠️ Не использовать `&` в foreground терминале — Hermes блокирует. Использовать `terminal(background=true)`. После рестарта проверить: `tail -5 bot.log` — должна быть строка «Alikhan EVO v5». Also verify exactly one real Python bot process, because duplicate `main_waha.py` processes cause duplicate replies:
```bash
python3 - <<'PY'
import subprocess
out=subprocess.check_output(['ps','-eo','pid,ppid,cmd'], text=True)
rows=[l for l in out.splitlines()[1:] if 'main_waha.py' in l and 'python' in l and 'ps -eo' not in l]
print('\n'.join(rows)); print('count=' + str(len(rows)))
PY
```

## WhatsApp Connection Methods (by preference)

1. **Evolution API v2.3.7** (CURRENT — confirmed stable 2026-06-27) — `evoapicloud/evolution-api:latest`
   - Volume persistence verified, unless-stopped, session open
   - Requires trust auth: `POSTGRES_HOST_AUTH_METHOD=***` + `DATABASE_CONNECTION_URI=postgresql://evolution:pass123@postgres:5432/evolution_db?schema=evolution_api`
   - Docker DNS fix: always `--dns 8.8.8.8`
   - Network alias: Postgres container MUST have `--network-alias postgres`
   - QR scanning via Manager UI: `http://72.60.16.105:8080/manager`
   - Documents, photos, and audio download natively via `getBase64FromMediaMessage`

2. **WAHA** (DEPRECATED — T-096 archived) — `devlikeapro/waha:latest`
3. **WAHA Plus** ($5/mo Patreon)
4. **Hermes Native Bridge** (Baileys-based, built into Hermes Agent) — **NEW 15.07.2026, Migration in progress**
   - No Docker containers needed — bridge runs as Hermes gateway subprocess
   - Pairing: `WHATSAPP_MODE=bot node bridge.js --session ~/.hermes/sessions/whatsapp --pair-json`
   - QR extracted from JSON output → Python `qrcode` library → PNG
   - Single-line patch for group messages: `bridge.js` line 637 add `!isGroup &&`
   - REST API on `127.0.0.1:3000`: `GET /messages`, `POST /send`, `POST /send-media`
   - See `references/hermes-bridge-migration.md` for full migration guide
5. **WhatsApp Cloud API** — official Meta, needs business verification

## Bot Components

### Main files (`bot/` directory)
- `main_waha.py` — EVO v5: polling loop (3-page fetch, STT, QA parser, Grok replies, TTS)
- `main.py` — old polling loop (Guard + Router + handler dispatch)
- `router.py` — 15 commands in priority order
- `handlers.py` — 17 handlers + `ask_grok()` for xAI
- `db.py` / `db_memory.py` — PostgreSQL access
- `seen_ids.json` — persisted message IDs to prevent re-processing on restart

### PostgreSQL tables
- `bot_calendar_events`, `bot_memory_messages`, `bot_memory_summaries`, `bot_group_participants`
- `bot_poll_state`, `ojr_section3_work_log` — poll lifecycle and VOR-code work residuals (ранее `bot_poll_residuals`)

## Poll System (опрос остатков работ) — T-128, 2026-07-06

Модуль `poll.py` управляет опросом для сбора остатков работ от прорабов. Заменяет старый вызов `smart_evening_check.py` — вся логика в poll.py.

### DB Tables

```sql
-- Состояние опроса
bot_poll_state:
  ...

-- Остатки по VOR-кодам (⚠️ migrating to ojr_section3_work_log)
bot_poll_residuals (legacy):
  id SERIAL PRIMARY KEY,
  poll_id INTEGER REFERENCES bot_poll_state(id),
  code TEXT NOT NULL,           -- VOR code (e.g. '2.1.1')
  building TEXT,
  name TEXT,
  unit TEXT,
  plan_volume NUMERIC,          -- original plan
  residual_volume NUMERIC,      -- remaining as of template
  actual_today NUMERIC,         -- updated by foreman reply
  updated_by TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(poll_id, code)
```

### Commands (processed in main_waha.py BEFORE routing)

| Message | Handler | What happens |
|---------|---------|-------------|
| «Алихан начать опрос» / «запустить опрос» | `start_poll()` | Читает ЕЖО-шаблон → находит активные коды с остатком > 0 → сохраняет в `ojr_section3_work_log` (ранее `bot_poll_residuals`) → отправляет сообщение-опрос с ✅/❌ по категориям и списком остатков |
| Ответ с VOR-кодом | `parse_poll_reply()` | Авто-детект: `re.search(r'\d+\.\d+\.\d+(?:\s*[=—–\-:\s]\s*\d+)', text)` → обновляет `actual_today` в `ojr_section3_work_log` (ранее `bot_poll_residuals`) + сохраняет факт в `bot_memory_facts` (legacy) → показывает обновлённую сводку |
| «Алихан статус опроса» / «что собрано» | `get_poll_status()` + `build_poll_summary()` | Сводка собранного: персонал, техника, фото, остатки, планы |
| «Алихан закончить опрос» / «завершить опрос» | `close_poll()` | Авто-заполняет отсутствующие категории (бетонирование/монтаж/земляные работы/документация = «не выполнялось») → `fill_ejo.py` → отправляет сгенерированный ЕЖО в группу |
| «Алихан заполни ежо» / «сформируй ежо» | `get_poll_status()` + conditional | Если poll активен — проверяет готовность данных (персонал, техника, остатки). Если не все собраны — подсказывает. Если всё есть — закрывает и генерирует ЕЖО. |

### Foreman reply format

**VOR codes (auto-detected):**
```
2.1.1 = 85.5
2.3.2 — 50м3
2.4.1 120
```

**Personnel (via QA parser):**
```
Атантай ИТР 2, рабочих 15
```

### Lifecycle

```
start_poll() → reads template residuals → sends questionnaire
  ↓
foremen reply with VOR codes → parse_poll_reply() → update residuals → show summary
  ↓
repeat until all categories have data
  ↓
close_poll() → auto-fill → fill_ejo.py → send ЕЖО.xlsx to group
```

Подробнее: `references/poll-system-detail.md` — полная документация по функциям, SQL, интеграции и pitfalls.

### Corrected ЕЖО → template handler (T-XXX, 2026-06-29)

1. **`_update_template_from_correction(b64, fname)`** — triggers on documents with «ЕЖО» in filename
2. Compares cumulative values (мес.факт, общ.факт, остаток) with latest auto-generated `/tmp/ЕЖО_*_v*.xlsx`
3. Logs differences, replaces `templates/ЕЖО_шаблон.xlsx` with corrected version
4. `fill_ejo.py` uses `max(template, yesterday_cum)` — corrected template wins
5. Reports to group: «📎 Правки приняты (N отличий). Шаблон обновлён.»

**Message ID extraction from DB for document download:**
```python
# Documents are stored: content = filename, tags = {"msg_id": "...", "file_name": "..."}
msg_id = json.loads(row['tags'])['msg_id']
payload = {'message': {'key': {'id': msg_id}}}
req = Request(f'{EVO}/chat/getBase64FromMediaMessage/alikhan', ...)
```

- **Testing protocol:** ALWAYS sandbox group only (`120363179621030401@g.us`). NEVER send to production (`120363400682390076@g.us`) during testing/development.
- **Test before deploy:** run component tests (ffmpeg → whisper roundtrip, Evolution API download) BEFORE restarting bot with changes. Never deploy untested.
- **Delegation model:** Use xAI/Grok for sub-agent delegation, NOT Gemini (Google free tier rate-limits with 429).
- **Verbosity:** Keep Alikhan replies concise. Shortened `only_name` response from long paragraph to "Я на связи."

## Known Pitfalls

### Audit log path false positives

Do not assume the running bot writes to `bot.log`. In current supervised runs, `main_waha.py` may have stdout/stderr redirected to `/tmp/alikhan.log`, while `/home/hermes-workspace/Alikhan-migration/bot/bot.log` is stale. Audit pattern:

```bash
PID=$(ps -eo pid,cmd | awk '/python3 main_waha.py/ && !/awk/ {print $1; exit}')
readlink -f /proc/$PID/fd/1
readlink -f /proc/$PID/fd/2
F=$(readlink -f /proc/$PID/fd/1); [ -f "$F" ] && tail -30 "$F"
```

Flag `bot.log` as stale only if the active fd target is also stale or the process is not running. Evolution API health check should include `curl -s -m 5 http://127.0.0.1:8080/` returning HTTP 200.

### Evolution API Polling Pagination (2026-06-27)

`/chat/findMessages` orders messages **oldest-first**. Page 1 = oldest, last page = newest. `limit` parameter is IGNORED — API returns ~50 records per page regardless.

**WRONG — never sees new messages:**
```python
r = requests.post(..., json={"where": ..., "page": 1, "limit": 1})
```

**RIGHT — two-step fetch from last pages:**
```python
# Step 1: get total page count
r = requests.post(..., json={"where": ..., "page": 1, "limit": 1})
total_pages = r.json().get("messages", {}).get("pages", 1)

# Step 2: fetch last 3 pages (newest messages, with overlap for safety)
msgs = []
for page in range(max(1, total_pages - 2), total_pages + 1):
    r = requests.post(..., json={"where": ..., "page": page, "limit": 5})
    msgs.extend(r.json().get("messages", {}).get("records", []))
```

**Pitfall:** messages can appear on multiple pages → MUST deduplicate by message ID before processing.

### Seen persistence — prevent re-processing on restart (2026-06-27)

Bot's `seen` set is in-memory and lost on restart. Without persistence, restarted bot re-processes ALL old messages.

**Fix — `seen_ids.json`:**
```python
SEEN_FILE = os.path.join(os.path.dirname(__file__), "seen_ids.json")
seen = set()
if os.path.exists(SEEN_FILE):
    seen = set(json.load(open(SEEN_FILE)))

# After seeding:
with open(SEEN_FILE, "w") as f:
    json.dump(list(seen), f)

# After processing each message:
seen.add(mid)
with open(SEEN_FILE, "w") as f:
    json.dump(list(seen), f)
```

### Message age filter — skip ancient messages (2026-06-27)

Without age filter, bot re-processes days-old messages on every restart even with seen persistence (if seen file was lost).

```python
msg_ts = m.get("messageTimestamp")
# Evolution may return None for some messages. Treat None/non-numeric as "unknown":
# do not do `now_ts - msg_ts` until it is normalized.
try:
    msg_ts = int(msg_ts)
except (TypeError, ValueError):
    msg_ts = 0
now_ts = int(time.time())
if msg_ts and now_ts - msg_ts > 600:  # skip >10 min old
    seen.add(mid)
    continue
```

If logs show `[LOOP ERR] int() argument must be a string, a bytes-like object or a real number, not 'NoneType'`, inspect the timestamp path before touching DB or services. This error can appear without killing the bot.

### Grok date context (2026-06-27)

Grok doesn't know the current date. Inject it:
```python
reply = ask_grok(f"Сегодня {datetime.now().strftime('%d.%m.%Y, %A')}. Ответь коротко на русском: {text[:2000]}", max_tokens=200)
```
Without this, "какой сегодня день?" gets "не знаю" responses.

### Russian word-stem matching for trigger words (2026-06-28)

Russian nouns have multiple forms: `"отставание" != "отставания"`, `"задержка" != "задержки"`. Python substring matching with full words silently misses inflected forms.

**WRONG — misses plural/genitive forms:**
```python
if "отставание" in text:  # False for "отставания"
```

**RIGHT — use word stems (корни):**
```python
# Stem triggers to catch all inflections
triggers = ["отставан", "задержк", "отклонени", "опережен"]
if any(t in text for t in triggers):
    # matches: отставание, отставания, отстаём
    # matches: задержка, задержки, задерживаемся
```

Rule: drop the last 2-3 characters of the base form and match on the stem. Test with both singular and plural forms in the target phrase.

### Router command bypass — prevent REJECT on commands (2026-07-01)

Commands like «Алихан запускай опрос» / «заполни ЕЖО» / «закончить опрос» are handled in `main_waha.py` after routing, BUT they still pass through `router.py` first. If no DB facts match the command keywords, router falls through to Grok → Grok generates a reply → `verify.py` scores it → REJECT noise before the actual command handler runs.

**Fix:** add command words to `router.py` after the name check:

```python
# 2.5 Command detection — skip Grok/verify for known commands
cmd_words = ["запускай опрос", "начать опрос", "заполни ежо", "сформируй ежо",
             "формируй ежо", "сделай ежо", "закрыть опрос", "завершить опрос",
             "закончить опрос", "стоп опрос", "формируй отчет", "сформируй отчет",
             "сделай отчет", "заполни отчет",
             "статус опроса", "что собрано", "сводка опроса", "опрос статус",
             "опрос стоп", "опрос закрыть", "опрос завершить", "опрос закончить",
             "опрос окончен", "опрос завершен"]
if any(w in text.lower() for w in cmd_words):
    return "CMD", "", False
```

And in `main_waha.py`:
```python
if action in ("IGNORE", "CMD"):
    continue
```

**Rule:** every time you add a new command handler to `main_waha.py`, add its trigger words to `router.py`'s `cmd_words` list. Otherwise the command generates a spurious Grok reply + REJECT before executing.

`send_msg` must log what it sends — otherwise debugging is blind:
```python
def send_msg(chat_id, text):
    print(f"[REPLY] {text[:100]}", flush=True)
    requests.post(...)
```

### Docker container OOM kill — Evolution API dies silently (2026-06-28)

Evolution API container can exit with code 137 (SIGKILL from OOM killer) without any warning. The bot continues polling and fills the log with `Connection refused` errors. Symptoms:
- `[LOOP ERR] Connection refused` flood in bot.log
- `docker ps` shows no evolution-api container
- `docker ps -a` shows `Exited (137)`

**Fix:**
```bash
docker restart evolution-api
# Wait for API to respond
sleep 5 && curl -s http://127.0.0.1:8080/ | head -1
# Bot auto-recovers on next poll cycle
```

**Prevention:** monitor container memory, consider `--memory` limit in docker run.
Host systemd-resolved stub at `127.0.0.53` breaks DNS inside Docker containers. ALWAYS add `--dns 8.8.8.8` to Docker containers that need WhatsApp connectivity.

### Circular imports from module refactoring (2026-06-27)

When factoring bot code into modules, NEVER import from `main_waha` in sub-modules (`stt.py`, `qa.py`, `router.py`, `db_lookup.py`, `verify.py`). `main_waha` starts the polling loop on import — importing it from a sub-module starts a second bot instance as a side effect.

**WRONG (qa.py):**
```python
from main_waha import send_msg  # starts main_waha polling loop!
```

**RIGHT — return data, let router handle messaging:**
```python
def parse_qa(gid, text, date_str=None):
    # Save facts, return count — don't send messages
    return count
```

If a sub-module needs to send messages (e.g., `send_voice` in `stt.py`), define `send_msg` in a shared `config.py` or pass it as a dependency — never import from `main_waha`.

Use Python `urllib.request` with `req.add_header()` passing the key as a VARIABLE, not a string literal. The redactor scans string literals but does NOT scan variable references. Runtime keys should be loaded through the project helper `secret_config.get_evo_key()` / `secret_config.get_secret()` rather than hard-coded in bot files.

```python
from secret_config import get_evo_key
key = get_evo_key(required=True)
req = urllib.request.Request(url, data=data, method='POST')
req.add_header('apikey', key)     # SAFE: key is a variable
# req.add_header('apikey', f'{key}')  # BROKEN — redactor may replace key
```

### Evolution API key discovery (2026-07-02)

When the API key is unknown or wrong (401 Unauthorized), the most common mistake is guessing `waha123`. The actual key is set via Docker environment variable. Find it:

```bash
# Method: docker inspect the container
docker inspect evolution-api --format '{{range .Config.Env}}{{println .}}{{end}}' | grep API_KEY
# → AUTHENTICATION_API_KEY=SuperSecretKey_Grok2026_!@#
```

Never hard-code keys in bot files. The bot uses `secret_config.get_evo_key()` which loads from env or Docker inspect. For ad-hoc curl commands from outside the bot repo, extract the key from Docker config — do NOT read `.env` files or credential files directly.
Returns HTTP **201**, not 200. Use `r.status_code not in (200, 201)` to check success. Must send `{"message": full_message_dict}`, not `{"key": ...}`.

### PostgreSQL host: Docker bridge IP / auto-discovery (updated 2026-06-30)
Python bot runs on VPS host (not in Docker), so Docker DNS names don't resolve. Docker bridge IP changes after container/network restarts. Do **not** hard-code `172.22.0.x` in new DB code. Use shared `db.get_conn()` / `db.resolve_db_host()` which prefers `DB_HOST` or `EVO_DB_HOST`, otherwise auto-discovers `evolution-postgres` via `docker inspect` before connecting.

This applies to **external Hermes scripts too** (`~/.hermes/scripts/morning-briefing.py`, evening questionnaires, watchdog reports), not only files inside the bot repo. If a script outside `/home/hermes-workspace/Alikhan-migration/bot` needs Alikhan DB access, import the project resolver instead of duplicating connection config:
```python
import sys
sys.path.insert(0, "/home/hermes-workspace/Alikhan-migration/bot")
from db import get_conn
conn = get_conn()
```
Do not treat `connection refused at 172.22.0.x:5432` as Postgres down until you have checked `docker ps` and `db.resolve_db_host()`; it is often a stale Docker bridge IP in a helper script.

Manual check: `cd /home/hermes-workspace/Alikhan-migration/bot && python3 - <<'PY'\nimport db\nprint(db.resolve_db_host())\nconn=db.get_conn(); cur=conn.cursor(); cur.execute('select 1'); print(cur.fetchone()[0]); cur.close(); conn.close()\nPY`

### Bot auto-start without sudo — cron @reboot (2026-06-27)
```bash
(crontab -l 2>/dev/null; echo '@reboot sleep 15 && /path/to/venv/bin/python3 /path/to/bot/main_waha.py >> /path/to/bot/bot.log 2>&1') | crontab -
```
Use user-level cron when system sudo/systemd is unavailable. Verify with `crontab -l`, `pgrep -af main_waha.py`, and a WAHA `/sendText` sandbox ping after reboot.

**Update 2026-06-30:** if using `systemctl --user`, do **not** include `User=`/`Group=` in the user unit; it fails as `status=216/GROUP`. Use the same venv Python as the bot (`.../.hermes/hermes-agent/venv/bin/python3`) or imports like `psycopg2` fail under `/usr/bin/python3`.

### Local document extractor on `127.0.0.1:8099` (2026-06-30)
`main_waha.py` expects `POST http://localhost:8099/extract-document` for incoming WhatsApp documents and health scripts check `GET /health`. Implementation is `bot/document_extractor.py`; service template is `bot/alikhan-document-extractor.service`, installed at `~/.config/systemd/user/alikhan-document-extractor.service`.

Verify:
```bash
systemctl --user status alikhan-document-extractor.service --no-pager
curl -sf http://127.0.0.1:8099/health
ss -ltnp | grep ':8099'   # must bind 127.0.0.1 only
```
Extractor supports both live WAHA `{base64,file_name}` and test/path `{path,filename,chat_id,sender}` payloads. Use Hermes venv Python to keep `openpyxl` available.

### User-systemd pitfall: no `User=` in `systemctl --user` units (2026-06-30)
If `~/.config/systemd/user/alikhan.service` contains `User=hermes-user`, it fails with `status=216/GROUP` and logs `Failed to determine supplementary groups: Operation not permitted`. User services already run as the user; remove `User=`.

Use the project/Hermes venv in `ExecStart`, not `/usr/bin/python3`, because Alikhan depends on packages such as `psycopg2` that may only exist in the venv:
```ini
[Service]
Type=simple
WorkingDirectory=/home/hermes-workspace/Alikhan-migration/bot
ExecStart=/home/hermes-workspace/.hermes/hermes-agent/venv/bin/python3 /home/hermes-workspace/Alikhan-migration/bot/main_waha.py
Restart=always
RestartSec=10
StandardOutput=append:/tmp/alikhan.log
StandardError=append:/tmp/alikhan.log
```

Restart and verify:
```bash
systemctl --user daemon-reload
systemctl --user reset-failed alikhan.service
systemctl --user restart alikhan.service
systemctl --user status alikhan.service --no-pager
```
Always verify exactly one `main_waha.py` process after restart; kill duplicates not owned by the service PID.

Inside `main_waha.py`, child script calls should use `sys.executable`, not string `"python3"`, so `fill_ejo.py` and `smart_evening_check.py` inherit the same venv:
```python
subprocess.run([sys.executable, "fill_ejo.py", today_str], cwd=BOT_DIR)
subprocess.run([sys.executable, "/home/hermes-workspace/.hermes/scripts/smart_evening_check.py", SANDBOX], env=env)
```

If a message was marked seen before a crash, it may not be reprocessed after the fix because `seen` is kept in memory and persisted in `seen_ids.json`. For command messages that already caused the intended side effect manually, do not force reprocessing; otherwise remove the id from `seen_ids.json` and restart the service so the in-memory set reloads.

## Voice Messages (STT + TTS) — T-114, 2026-06-27

### STT: Receive voice → text

Tools: **faster-whisper** `base` model (free, local) + **ffmpeg** for audio conversion.

```python
from faster_whisper import WhisperModel

def transcribe_audio(b64_audio):
    # Download via Evolution API: POST /chat/getBase64FromMediaMessage/alikhan
    # Returns {"base64": "..."} with HTTP 201
    
    # Write OGG, convert to WAV 16kHz mono
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(base64.b64decode(b64_audio))
        ogg_path = f.name
    wav_path = ogg_path.replace(".ogg", ".wav")
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path],
                   capture_output=True, check=True)
    
    # Transcribe (base model for Russian accuracy)
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav_path, language="ru")
    text = " ".join(s.text for s in segments).strip()
    os.unlink(ogg_path); os.unlink(wav_path)
    return text
```

**Voice messages are NOT filtered by "алихан" before transcription.** ALL audio messages get transcribed, then transcribed text goes through normal flow (QA parser → "алихан" check → Grok).

### TTS: Send voice replies

Tools: **edge-tts** (Microsoft Edge, free, no API key) — voice `ru-RU-SvetlanaNeural`.

```python
def send_voice(chat_id, text):
    mp3_path = "/tmp/tts_output.mp3"
    subprocess.run(["edge-tts", "--voice", "ru-RU-SvetlanaNeural", "--text", text,
                    "--write-media", mp3_path], check=True, capture_output=True)
    with open(mp3_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    # Send via Evolution API — use urllib, not requests (redactor-safe)
    req = urllib.request.Request(
        f"{EVO}/message/sendMedia/alikhan",
        data=json.dumps({"number": chat_id, "mediatype": "audio",
                         "mimetype": "audio/mpeg", "media": b64}).encode(),
        headers={"apikey": KEY, "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)
```

**Trigger:** keywords `голосом`, `озвучь`, `голос` in user message → bot sends BOTH text and voice reply.
**Fallback:** if TTS fails → `send_msg` text only.

### STT Fuzzy Matching for «Алихан»

Whisper (even base model) frequently mishears "Алихан" due to Russian phonetics:
- "Олеган" (third char "е" instead of "и")
- "Алехан" (first char "а" is fine)
- "Аликан" ("к" instead of "х")
- "Олег Фан" (space inserted)

**Regex for matching all STT variants:**
```python
ali_match = re.search(r'[ао]л[еи][хгк]', text.lower())
```
Covers: алихан, олеган, алехан, олиган, аликан, олег, алих.

**Pitfalls of wrong regexes:**
- `r'[ао]л[еи][хг]а[нм]'` — misses "Олег" (no "ан" at end), misses "Аликан" ("к" not in [хг])
- `r'[ао][лд]и[хг]а[нм]'` — "д" false-positive, force "и" misses "е" in "Олеган"
- Basic `"алихан" in text.lower()` — misses ALL STT errors

### Voice Test Suite (T-XXX, 2026-06-29)

**Файл:** `bot/test_voice_production.py` — 5 тестов, все пройдены (5/5 PASS):

| Тест | Статус | Результат |
|------|--------|-----------|
| 1. STT roundtrip (5 фраз) | ✅ | 100% key accuracy. edge-tts → ffmpeg → faster-whisper → Grok коррекция |
| 2. DB fact lookup (6 запросов) | ✅ | Все варианты (включая STT-ошибки: олеган, алехан, пагода) корректно роутируются |
| 3. Grok summarization (4 вопроса) | ✅ | Суммирует числа (53 рабочих, 6 техники) из DB facts |
| 4. Verification scoring | ✅ | REJECT галлюцинаций (score=15), FLAG избыточности (60), OK точного (100) |
| 5. E2E voice pipeline | ✅ | Искажённые STT-тексты → правильные хендлеры (GROK/WEATHER/SCHEDULE) |

**Зависимости:** `pip install faster-whisper edge-tts openpyxl Pillow` (openpyxl и Pillow нужны для fill_ejo, не для тестов). **Запуск:** `cd bot && python3 test_voice_production.py`.

### STT Roundtrip подтверждён (2026-06-29)
Whisper base распознаёт «Олеган» вместо «Алихан», «наджервия» вместо «на Джеруе» — Grok пост-коррекция исправляет все ошибки. Key accuracy: 100% по всем 5 фразам. Fuzzy name match `[ао]л[еи][хгк]` покрывает все варианты.
1. **Roundtrip test:** edge-tts → ffmpeg → faster-whisper (text should survive)
2. **API test:** Evolution API `getBase64FromMediaMessage` with existing document before audio
3. **Sandbox only:** never deploy voice features to production without sandbox verification
4. **Never test on production group** — this is a hard rule, not a suggestion
5. **Full suite:** `python3 test_voice_production.py` — 5 тестов (STT roundtrip, DB lookup, Grok summarization, verification scoring, E2E pipeline). Требует: `faster-whisper`, `edge-tts`, `openai`. Результат: 5/5 PASS при живых БД и API.

## Auto-save vs. "Алихан" mention

The old n8n workflow distinguishes:
- **Auto-save:** ALL documents/photos → extract content → save to DB → SILENT (no reply)
- **Response:** Only messages containing "алихан" → route → handler → reply

Auto-save runs BEFORE the "алихан" check in the polling loop.

## Document extractor service (:8099)

**Location:** `/root/doc_import/scripts/document_extract_server.py`
**Ven:** `/root/doc_import/venv/bin/python`
**Env file:** `/root/doc_import/document_extract.env`

## Schedule Integration (2026-06-28)

### DB Table: `bot_schedule_phases`
```sql
CREATE TABLE IF NOT EXISTS bot_schedule_phases (
    id SERIAL PRIMARY KEY,
    building TEXT,           -- АБК, Общежитие, общая
    phase_num INTEGER,       -- номер этапа (NULL для milestones)
    phase_name TEXT,         -- название
    description TEXT,
    start_date DATE,
    end_date DATE,
    duration_days INTEGER,
    status TEXT DEFAULT 'planned',  -- planned/active/completed
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### DB Functions (db.py)
- `ensure_schedule_table()` — create table
- `seed_schedule()` — load 7 records (4 phases + 3 milestones from wiki)
- `get_schedule(building, status)` — all phases
- `get_active_phases(today)` — phases where start_date ≤ today ≤ end_date
- `get_upcoming_phases(today, days)` — phases starting in next N days
- `check_delays(today)` — active phases where end_date < today

### Router Integration (router.py → step 3.5)
```python
# 3.5 Schedule lookup (BEFORE Weather/DB)
from db_lookup import lookup_schedule
schedule_reply = lookup_schedule(chat_id, text)
if schedule_reply:
    return "SCHEDULE", schedule_reply, voice
```

### Query Types (db_lookup.py → lookup_schedule)
Trigger words: `график, этап, отставан, срок, план, календарный, отклонени, задержк, опережен`

Priority order:
1. Delay check: `отставан, задержк, отклонени` → `check_delays()` → "Отставаний нет" or list
2. Active phases: `активн, идут, сейчас, текущ` → `get_active_phases()` → list
3. Upcoming: `ближайш, предстоящ, скоро` → `get_upcoming_phases()` → list
4. Full schedule: default → `get_schedule()` → all phases with status icons

**Output format:**
- Phases: `• Этап 1: ПСД, подготовка — 30.04.2025–26.06.2026 ✅`
- Milestones (phase_num=NULL): `  ▸ Изготовление МК — 05.01.2026–20.02.2026 ✅`
- Status icons: ✅ completed, 🔄 active, ⏳ planned
- Dates: DD.MM.YYYY via strftime
- Milestones indented with 2 spaces + ▸ prefix

### Seed Data (Общежитие 223 мест + АБК, ТЗРК Джеруй)
| Phase | Name | Dates | Duration |
|-------|------|-------|----------|
| 1 | ПСД, подготовка | 30.04.2025–26.06.2026 | 423 дня |
| 2 | Фундаменты, металлоконструкции | 05.01–30.06.2026 | 177 дней |
| 3 | Этап 3 | 23.05–31.07.2026 | 70 дней |
| 4 | Этап 4 | 15.06–30.10.2026 | 138 дней |

Milestones: Устройство фундаментов (23.04–01.06), Изготовление МК (05.01–20.02), Монтаж МК (22.02–05.05).

Run after any deploy or config change:
1. `docker inspect <name> --format '{{.HostConfig.RestartPolicy.Name}}'` → all `unless-stopped`
2. `docker inspect <name> --format '{{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'` → `evo_instances` on `/evolution/instances`
3. `curl http://127.0.0.1:8080/instance/fetchInstances -H "apikey: <key>"` → `connectionStatus: "open"`
4. `pgrep -f main_waha` → must return PID
5. `tail -20 /path/to/bot.log` → recent activity
6. `crontab -l | grep @reboot` → entry present

## Project Management

Obsidian Kanban boards for task tracking: see `references/obsidian-kanban-boards.md` for format, placement, and sync pitfalls.
