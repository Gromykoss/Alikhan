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
- Local extractor: `/home/hermes-workspace/Alikhan-migration/bot/document_extractor.py`
- Extractor service unit: `/home/hermes-workspace/Alikhan-migration/bot/alikhan-document-extractor.service`
- Live services: `alikhan.service`, `alikhan-document-extractor.service`
- Extractor endpoint: `127.0.0.1:8099`
- Runtime log: `/tmp/alikhan.log` for the current user-systemd service; `bot/bot.log` may be stale.

## Active workflows

- Bot routing and replies: `bot/main_waha.py`, `bot/router.py`, then helper
  modules in `bot/`.
- EJO generation: `bot/fill_ejo.py` plus `bot/templates/ЕЖО_шаблон.xlsx`.
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
