# Alikhan — рабочая среда Hermes

Проект: WhatsApp AI-агент для ТЗРК Джеруй.
Бот: Python v5, Evolution API + xAI/Grok.
Путь: /home/hermes-workspace/Alikhan-migration/bot/

## Принцип

**Надёжность и работоспособность всей системы — приоритет №1.** Фиксы и костыли переписываются в надёжный код. Каждое изменение тестируется в песочнице до боевой группы.

## Архитектура

WhatsApp → Evolution API :8080 → main_waha.py (poll 3s) → Guard → Router → [QA/DB/Weather/Grok/Schedule] → Reply

## Быстрые команды

```bash
# Статус контейнеров
docker ps --filter "name=evolution"

# Логи бота
tail -30 /home/hermes-workspace/Alikhan-migration/bot/bot.log

# Перезапуск бота (после правок кода)
pkill -f "main_waha.py"
cd /home/hermes-workspace/Alikhan-migration/bot
python3 main_waha.py >> bot.log 2>&1 &

# Рестарт Evolution API
docker restart evolution-api
```

## Память проекта (PostgreSQL)

Хост: `DB_HOST`/`EVO_DB_HOST` при наличии; иначе авто-обнаружение IP контейнера `evolution-postgres` через `docker inspect`, порт 5432. База: evolution_db, пользователь: evolution.
Таблицы: bot_memory_messages, bot_memory_facts, bot_building_profiles, bot_schedule_phases.

## ЕЖО

- `fill_ejo.py` — погода (Open-Meteo 42.284,72.765) + QA-факты → Excel 4 листа
- Шаблон: bot/templates/ЕЖО_шаблон.xlsx
- SIM_DATE: "2026-06-27" в main_waha.py и router.py (None в продакшене)
- **Цикл:** авто-заполнение → ручная правка → diff по кодам → шаблон + `ЕЖО_{date}_v1.xlsx`
- **Накопленные:** `yesterday_cum()` из v1-файла, защита от удвоения (v>0 → yesterday)
- **Персонал:** из табеля по профессиям (колонка C), лист «Персонал и техника» строки 9-13
- **Дата:** извлекается из имени файла (`27.06.2026`), сохраняется как `ЕЖО_{YYYY-MM-DD}_v1.xlsx`
- **Шаблон:** `data_only=True` при загрузке (формулы → значения, нет потерь)

## График производства

- Таблица bot_schedule_phases — 7 записей (4 этапа + 3 milestones)
- lookup_schedule() в db_lookup.py — триггеры: график, этап, отставание, срок
- check_delays() — проверка просроченных этапов
- 827 дней (30.04.2025–04.08.2027)

## Группы WhatsApp

| Группа | ID | Режим |
|--------|-----|-------|
| Песочница | 120363179621030401@g.us | Полный доступ, отвечает |
| Боевая | 120363400682390076@g.us | Только слушает + погода |

## Погода

- API: Open-Meteo (42.284, 72.765)
- Cron: 1:30 и 10:30 UTC → боевая группа
- Формат: °C, м/с, %, мм рт.ст.
