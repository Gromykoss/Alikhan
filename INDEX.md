# Alikhan Index

Concise routing map for `/home/hermes-workspace/Alikhan-migration`.

## Start here

Read `/home/hermes-workspace/Alikhan-migration/AGENTS.md` first. For active bot
behavior, start at `/home/hermes-workspace/Alikhan-migration/bot/main_waha.py`
and then `/home/hermes-workspace/Alikhan-migration/bot/router.py`.

## Canonical files

- Bot dir: `/home/hermes-workspace/Alikhan-migration/bot/`
- Live bot: `/home/hermes-workspace/Alikhan-migration/bot/main_waha.py`
- Router: `/home/hermes-workspace/Alikhan-migration/bot/router.py`
- EJO generator: `/home/hermes-workspace/Alikhan-migration/bot/fill_ejo.py`
- OJR sync module: `/home/hermes-workspace/Alikhan-migration/bot/ojr_sync.py`
- OJR schema: `/home/hermes-workspace/Alikhan-migration/db/ojr_schema.sql` (14 таблиц ОЖР)
- OJR ER diagram: `/home/hermes-workspace/Alikhan-migration/db/ojr_er_diagram.md`
- OJR fill guide: `/home/hermes-workspace/Alikhan-migration/db/ojr_fill_guide.md`
- Local extractor: `/home/hermes-workspace/Alikhan-migration/bot/document_extractor.py`
- Extractor service unit: `/home/hermes-workspace/Alikhan-migration/bot/alikhan-document-extractor.service`
- Live services: `alikhan.service`, `alikhan-document-extractor.service`
- Extractor endpoint: `127.0.0.1:8099`
- Runtime log: `/tmp/alikhan.log` for the current user-systemd service; `bot/bot.log` may be stale.

## Active workflows

- Bot routing and replies: `bot/main_waha.py`, `bot/router.py`, then helper
  modules in `bot/`.
- EJO generation: `bot/fill_ejo.py` plus `bot/templates/ЕЖО_шаблон.xlsx`.
  - **v5 (18.07.2026):** ЕЖО = view на `ojr_section3_work_log` за дату.
  - Auto-hide rows: `_hide_rows()` — скрывает завершённые/будущие строки по графику (`bot_schedule_phases`).
  - Personnel parsing: `staff()` — из `ojr_section1_personnel` + табель.
  - Logo preservation: логотип сохраняется при очистке фото-строк.
- OJR data flow: QA (`qa.py`) → `bot_memory_facts` → роутинг по `ojr_*` таблицам (schema: `db/ojr_schema.sql`).
- OJR sync: `bot/ojr_sync.py` — функции синхронизации facts→OJR, фото→`ojr_photo_log`, погода→`ojr_weather`.
- Daily snapshot: композит из `ojr_photo_log` + `ojr_daily_summary` + сообщений.
- Document extraction: `bot/document_extractor.py` and the local extractor
  service on `127.0.0.1:8099`.
- Sandbox WhatsApp validation: `120363179621030401@g.us`.
- Production WhatsApp group: `120363400682390076@g.us`; approval required
  before sending.

## Archive / do not use by default

- Old WAHA and n8n paths are deprecated context, not default implementation
  targets.
- `/home/hermes-workspace/Alikhan-migration/n8n-workflows/` is historical unless
  the task explicitly asks for it.

## Do not touch without explicit approval

- Production WhatsApp sends to `120363400682390076@g.us`.
- Service restarts for `alikhan.service`, `alikhan-document-extractor.service`,
  or Evolution API.
- Secrets, credentials, DB connection settings, and production service units.

## Verification commands

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile main_waha.py router.py fill_ejo.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
tail -30 /tmp/alikhan.log
```
