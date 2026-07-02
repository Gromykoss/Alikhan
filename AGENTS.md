# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент для ТЗРК Джеруй.
Бот: Python v5, Evolution API + xAI/Grok.
Путь: /home/hermes-workspace/Alikhan-migration/bot/

## Start here

Сначала читай этот файл, затем `/home/hermes-workspace/Alikhan-migration/INDEX.md`
если нужна карта проекта. Для кода бота начинай с
`/home/hermes-workspace/Alikhan-migration/bot/main_waha.py`, затем переходи в
`/home/hermes-workspace/Alikhan-migration/bot/router.py`.

## Canonical files

- Live bot: `/home/hermes-workspace/Alikhan-migration/bot/main_waha.py`
- Router: `/home/hermes-workspace/Alikhan-migration/bot/router.py`
- EJO generator: `/home/hermes-workspace/Alikhan-migration/bot/fill_ejo.py`
- Local extractor: `/home/hermes-workspace/Alikhan-migration/bot/document_extractor.py`
- Extractor service unit: `/home/hermes-workspace/Alikhan-migration/bot/alikhan-document-extractor.service`
- Live user services: `alikhan.service`, `alikhan-document-extractor.service`
- Extractor endpoint: `127.0.0.1:8099`
- Runtime log: `/tmp/alikhan.log` for the current user-systemd service; `bot/bot.log` may be stale.

## Active workflows

- Bot behavior: edit/read `bot/main_waha.py`, `bot/router.py`, and related
  helpers in `bot/`.
- EJO work: use `bot/fill_ejo.py` and `bot/templates/ЕЖО_шаблон.xlsx`.
- Document extraction: use `bot/document_extractor.py`; verify against local
  service `127.0.0.1:8099`.
- WhatsApp validation: use sandbox group `120363179621030401@g.us`.
- Production WhatsApp group `120363400682390076@g.us`: never send here without
  explicit approval.

## Archive / do not use by default

- Avoid old/deprecated WAHA and n8n paths unless historical context is
  explicitly requested.
- Treat `/home/hermes-workspace/Alikhan-migration/n8n-workflows/` as historical
  unless the task says otherwise.

## Do not touch without explicit approval

- Do not restart `alikhan.service`, `alikhan-document-extractor.service`, or
  Evolution API unless explicitly approved.
- Do not send to the production WhatsApp group
  `120363400682390076@g.us` without explicit approval.
- Do not change secrets, credentials, database connection settings, or
  production service units without explicit approval.

## Verification commands

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m py_compile main_waha.py router.py fill_ejo.py document_extractor.py
python3 -m pytest test_ejo_simulation.py -q
curl -fsS http://127.0.0.1:8099/health
tail -30 /tmp/alikhan.log
```

## Принцип

**Надёжность и работоспособность всей системы — приоритет №1.** Фиксы и костыли переписываются в надёжный код. Каждое изменение тестируется в песочнице до боевой группы.

## Архитектура

WhatsApp → Evolution API :8080 → main_waha.py (poll 3s) → Guard → Router → [QA/DB/Weather/Grok/Schedule] → Reply

## Быстрые команды

```bash
# Статус контейнеров
docker ps --filter "name=evolution"

# Логи бота
tail -30 /tmp/alikhan.log

# Перезапуск бота (только после явного approval)
systemctl --user restart alikhan.service
systemctl --user status alikhan.service --no-pager
pgrep -af 'python3 .*main_waha.py'

# Рестарт document extractor (только после явного approval)
systemctl --user restart alikhan-document-extractor.service
curl -fsS http://127.0.0.1:8099/health

# Рестарт Evolution API (только после явного approval)
docker restart evolution-api
```

## Память проекта (PostgreSQL)

Хост: `DB_HOST`/`EVO_DB_HOST` при наличии; иначе авто-обнаружение IP контейнера `evolution-postgres` через `docker inspect`, порт 5432. База: evolution_db, пользователь: evolution.
Таблицы: bot_memory_messages, bot_memory_facts, bot_building_profiles, bot_schedule_phases.

## ЕЖО

- `fill_ejo.py` — погода (Open-Meteo 42.284,72.765) + QA-факты → Excel 4 листа
- Шаблон: bot/templates/ЕЖО_шаблон.xlsx
- SIM_DATE: None в продакшене (симуляция 30.06 закрыта 01.07.2026)
- **Цикл:** авто-заполнение → ручная правка → diff по кодам → шаблон + `ЕЖО_{date}_v1.xlsx`
- **Накопленные:** `yesterday_cum()` из v1-файла, защита от удвоения (v>0 → yesterday)
- **Персонал:** из табеля по профессиям (колонка C), лист «Персонал и техника» строки 9-13
- **Дата:** извлекается из имени файла (`27.06.2026`), сохраняется как `ЕЖО_{YYYY-MM-DD}_v1.xlsx`
- **Шаблон:** `data_only=True` при загрузке (формулы → значения, нет потерь)

## График производства

- Таблица bot_schedule_phases — **8 записей** (8 этапов из ГРАФИК СМР.pdf)
- Даты синхронизированы с PDF 01.07.2026
- lookup_schedule() в db_lookup.py — триггеры: график, этап, отставание, срок
- check_delays() — проверка просроченных этапов
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

## Последняя сессия (02.07.2026) — контекст восстановления

### Что сделано
- ЕЖО 02.07.2026 (v1): персонал, объёмы, планы, фото — без замечаний
- **QA parser fix:** убран pre-parse в `qa.py` (дублировал факты: голый код + labelled)
- **Дубликаты в БД:** 4 записи за 02.07 удалены, больше не появятся
- **Авто-шаблон:** cron `7adc37a6efc5` ежедневно 8:00 Бишкек (02:00 UTC) — нет правки → v1 → шаблон
- **Скрипт:** `/home/hermes-workspace/.hermes/scripts/ejo_auto_template.py`
- Шаблон обновлён из ЕЖО_2026-07-02_v1.xlsx (backup сохранён)
- SIM_DATE = None, бот в реальном времени

### Известные баги / ограничения
- Diff в `_update_template_from_correction()` проверяет только 3 колонки (16, 19, 21) — заливку/фото/планы НЕ сравнивает
- Удаление через WhatsApp API не работает в группах (bug #885)
- .mpp файлы не читаются (нужен JDK + MPXJ) — пользователь присылает PDF версию графика

### БД
- PostgreSQL в Docker: `evolution-postgres` (172.22.0.3:5432)
- База: evolution_db, пользователь: evolution, пароль: pass123
- bot_memory_messages.content — не UNIQUE (слишком длинные значения), защита через SELECT

### Ключевые файлы сессии
- `/tmp/ЕЖО_2026-06-30_v2.xlsx` — финальный ЕЖО
- `/tmp/corrected_ЕЖО_30.06.2026 АйБиКон.xlsx` — пользовательская правка
- `bot/main_waha.py` L214 — защита фото
- `bot/main_waha.py` L15 — SIM_DATE = None

## Группы WhatsApp

| Группа | ID | Режим |
|--------|-----|-------|
| Песочница | 120363179621030401@g.us | Полный доступ, отвечает |
| Боевая | 120363400682390076@g.us | Только слушает + погода |

## Погода

- API: Open-Meteo (42.284, 72.765)
- Cron: 1:30 и 10:30 UTC → боевая группа
- Формат: °C, м/с, %, мм рт.ст.
