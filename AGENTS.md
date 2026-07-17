# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент для ТЗРК Джеруй.
Бот: Python v5, Hermes WhatsApp bridge + xAI/Grok.
Путь: /home/hermes-workspace/Alikhan-migration/bot/

## Start here

1. `skill_view("hermes-self-knowledge")` — 14 паттернов харнеса
2. Прочитай `~/hermes-vault/30_Logs/Арсенал Hermes.md`
3. Затем этот файл, потом `/home/hermes-workspace/Alikhan-migration/INDEX.md`

## Правила строительства

**Общие правила (все проекты):** `skill_view('build')`

### ⛔ PRE-PATCH GATE (MANDATORY — все проекты)

Перед любым изменением кода:
1. `grep -rn "имя" bot/` — все места использования функции/переменной
2. Показать grep в ответе пользователю
3. Проследить логику в КАЖДОМ найденном месте
4. Только потом патч

Если grep не показан — патч не принят. Откат.

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

- Live bot: `/home/hermes-workspace/Alikhan-migration/bot/main_waha.py` (запуск: `python3 main_waha.py &`)
- Bridge wrapper: `/home/hermes-workspace/Alikhan-migration/bot/bridge_wrapper.py` (monkey-patch Evolution→Bridge)
- Hermes Bridge: `cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge && WHATSAPP_ALLOWED_USERS="*" node bridge.js --mode bot --session ~/.hermes/sessions/whatsapp &`
- Evolution API: остановлен (миграция на Hermes Bridge)
- alikhan.service: остановлен (бот запускается напрямую)
- Router: `/home/hermes-workspace/Alikhan-migration/bot/router.py`
- Poll module: `/home/hermes-workspace/Alikhan-migration/bot/poll.py`
- QA parser: `/home/hermes-workspace/Alikhan-migration/bot/qa.py`
- EJO generator: `/home/hermes-workspace/Alikhan-migration/bot/fill_ejo.py`
- Local extractor: `/home/hermes-workspace/Alikhan-migration/bot/document_extractor.py`
- Extractor service unit: `/home/hermes-workspace/Alikhan-migration/bot/alikhan-document-extractor.service`
- Live user services: `alikhan.service`, `alikhan-document-extractor.service`
- Extractor endpoint: `127.0.0.1:8099`
- Runtime log: `/tmp/alikhan.log`

## Active workflows

- Bot behavior: edit/read `bot/main_waha.py`, `bot/router.py`
- EJO work: `bot/fill_ejo.py` + `bot/templates/ЕЖО_шаблон.xlsx`
- Document extraction: `bot/document_extractor.py`; verify `127.0.0.1:8099`
- WhatsApp validation: sandbox group `120363179621030401@g.us`
- Production group `120363400682390076@g.us`: never send without explicit approval

## Archive / do not use by default

- Old/deprecated WAHA and n8n paths — only if explicitly requested
- `/home/hermes-workspace/Alikhan-migration/n8n-workflows/` — historical

## Do not touch without explicit approval

- Do not restart `alikhan.service`, `alikhan-document-extractor.service`, or Evolution API
- Do not send to production WhatsApp group `120363400682390076@g.us`
- Do not change secrets, credentials, DB connection, production service units

## Verification commands

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile main_waha.py bridge_wrapper.py router.py fill_ejo.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
curl -s http://127.0.0.1:3000/health
tail -30 /tmp/alikhan.log
```

## Принцип

**Надёжность и работоспособность всей системы — приоритет №1.** Фиксы и костыли переписываются в надёжный код. Каждое изменение тестируется в песочнице до боевой группы.

## Архитектура

WhatsApp → Hermes bridge :3000 → bridge_wrapper.py → main_waha.py (poll 3s) → Guard → Router → [QA/DB/Weather/Grok/Schedule] → Reply

## Быстрые команды

```bash
curl -s http://127.0.0.1:3000/health    # Hermes bridge
pgrep -af 'bridge.js\|main_waha'        # процессы
tail -30 /tmp/alikhan.log               # логи
# Перезапуск бота
pkill -f main_waha.py; cd /home/hermes-workspace/Alikhan-migration/bot && python3 main_waha.py &
# Мост WhatsApp
cd ~/.hermes/hermes-agent/scripts/whatsapp-bridge && WHATSAPP_ALLOWED_USERS="*" node bridge.js --mode bot --session ~/.hermes/sessions/whatsapp &
```

## Память проекта (PostgreSQL)

Хост: `DB_HOST`/`EVO_DB_HOST` или авто-обнаружение `evolution-postgres` (docker inspect), порт 5432. База: evolution_db, пользователь: evolution.
Таблицы: bot_memory_messages, bot_memory_facts, bot_building_profiles, bot_schedule_phases, bot_poll_state, bot_poll_residuals.

## ЕЖО (v4 — 16.07.2026)

- `fill_ejo.py` — погода (Open-Meteo 42.284,72.765) + QA-факты → Excel 4 листа
- Шаблон: `bot/templates/ЕЖО_шаблон.xlsx`
- SIM_DATE: None в продакшене
- **Цикл:** авто-заполнение → ручная правка → шаблон обновлён → следующий день
- **Суточный цикл:** ЕЖО v1 → правки → шаблон (или авто 8:00 через cron)
- **Месячный план:** «раскрой отчет» → заполнить O+U → шаблон на месяц
- **Колонки:** N=100% (0%), U=O−P, P/S=prev+v, всего 76 строк открыто
- **Скрытие:** O>0 ∧ U>0 видно, фаза 8 скрыта
- **Планы:** парсинг из сырых сообщений (Grok-фолбек)
- **Табель:** локальный кеш `/tmp/hermes-media-cache/`
- **Отправка:** bridge 50mb, `_send_document` через `requests.post`
- Навыки: `alikhan-fill-ejo`, `alikhan-template-handoff`, `alikhan-monthly-template`, `alikhan-poll`, `alikhan-photo-vision`

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

## Последняя сессия (15.07.2026) — миграция на Hermes Bridge

**Ключевое изменение:** Evolution API заменён на Hermes WhatsApp Bridge (:3000).
- `bridge_wrapper.py` — monkey-patch слой: перехватывает `requests.post` к Evolution API, транслирует в Bridge API
- `main_waha.py` — не менялся, просто импортирует `from bridge_wrapper import *`
- Evolution API Docker — остановлен
- `alikhan.service` — остановлен (заменён прямым запуском `python3 main_waha.py`)
- Hermes Bridge: `node bridge.js --mode bot --session ~/.hermes/sessions/whatsapp &`

**Что сделано:**
- ЕЖО 02.07.2026 (v1): без замечаний
- QA parser fix: убран pre-parse в `qa.py`
- Дубликаты в БД: 4 записи за 02.07 удалены
- Авто-шаблон: cron `7adc37a6efc5` ежедневно 8:00 Бишкек
- Шаблон обновлён из ЕЖО_2026-07-02_v1.xlsx (backup сохранён)
- SIM_DATE = None

**Известные баги / ограничения:**
- Diff в `_update_template_from_correction()` проверяет только 3 колонки (16, 19, 21)
- Удаление через WhatsApp API не работает в группах (bug #885)
- .mpp файлы не читаются (нужен JDK + MPXJ) — только PDF
- Poll: smart_evening_check.py — резервный, poll.py — основной

**БД:**
- PostgreSQL: `evolution-postgres` (172.22.0.3:5432)
- База: evolution_db, пользователь: evolution, пароль: pass123
- bot_memory_messages.content — не UNIQUE (защита через SELECT)

**Ключевые файлы сессии:**
- `/tmp/ЕЖО_2026-06-30_v2.xlsx`
- `/tmp/corrected_ЕЖО_30.06.2026 АйБиКон.xlsx`
- `bot/main_waha.py` L214 (защита фото), L15 (SIM_DATE = None)

## Группы WhatsApp

| Группа | ID | Режим |
|--------|-----|-------|
| Песочница | 120363179621030401@g.us | Полный доступ, отвечает |
| Боевая | 120363400682390076@g.us | Только слушает + погода |

## Погода

- API: Open-Meteo (42.284, 72.765)
- Cron: 1:30 и 10:30 UTC → боевая группа
- Формат: °C, м/с, %, мм рт.ст.