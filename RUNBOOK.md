# 🔧 Алихан — Runbook оператора

**Дата:** 29 июля 2026 · **Проект:** ТЗРК Джеруй · **Версия:** v6.0 (прямой Hermes Bridge)

Быстрое руководство по эксплуатации, перезапуску и восстановлению WhatsApp-агента Алихан (Hermes Agent, прямой Bridge).

---

## 1. Быстрый статус

```bash
# WhatsApp Bridge (Hermes Bridge, Baileys, mode=bot)
curl -s http://127.0.0.1:3000/health
# (unit hermes-whatsapp-bridge НЕ существует — мост живёт в gateway)

# Document Extractor
curl -fsS http://127.0.0.1:8099/health
systemctl --user status alikhan-document-extractor

# PostgreSQL
docker ps --filter "name=evolution-postgres" --format "{{.Names}} {{.Status}}"
```

**Признаки работы:** Alikhan отвечает в WhatsApp группе напрямую через Hermes Agent (без отдельного Python-бота).

## 2. Архитектура (v6 — прямой Hermes Bridge, 29.07.2026)

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
   │ojr_section1  │ │ojr_section3│ │  ojr_    │
   │_personnel    │ │_work_log   │ │ weather  │
   └──────────────┘ └─────┬──────┘ └──────────┘
            │             │             │
                         ▼
                  ЕЖО (fill_ejo.py)
```

**Сервисы:**

| Сервис | Тип | Команда проверки |
|:-------|:----|:-----------------|
| `hermes-whatsapp-bridge` | внутри gateway | `curl -s http://127.0.0.1:3000/health` |
| `alikhan-document-extractor` | `systemctl --user` | `curl -fsS http://127.0.0.1:8099/health` |

**alikhan.service (Python-бот) — ОСТАНОВЛЕН 29.07.2026.** Alikhan работает как агент Hermes напрямую через Bridge.

**Ключевые файлы:**

| Файл | Назначение |
|:-----|:-----------|
| `bot/fill_ejo.py` | Генератор ЕЖО — view на `ojr_section3_work_log` |
| `bot/qa.py` | QA-парсер: извлечение фактов через Grok |
| `bot/poll.py` | Ежедневный опрос прорабов |
| `bot/db.py` | PostgreSQL: подключение, запросы |
| `bot/ojr_sync.py` | Синхронизация bot_memory_facts → OJR-таблицы |
| ~~bot/main_waha.py~~ | ИСТОРИЧЕСКИЙ — заменён прямым Hermes Agent (29.07.2026) |
| ~~bot/router.py~~ | ИСТОРИЧЕСКИЙ — маршрутизация теперь в Hermes Agent |
| ~~bot/bridge_wrapper.py~~ | ИСТОРИЧЕСКИЙ — monkey-patch удалён (29.07.2026) |
| `bot/watchdog_bridge.py` | Watchdog для Hermes Bridge |
| `bot/backup_db.py` | Бэкап/восстановление PostgreSQL |
| `bot/config.py` | Централизованный конфиг |
| `db/ojr_schema.sql` | Схема БД — 15 таблиц ОЖР |
| `db/ojr_er_diagram.md` | ER-диаграмма |
| `db/ojr_fill_guide.md` | Руководство по заполнению |

---

## 3. Перезапуск

### WhatsApp Bridge (Hermes Bridge)

> ⛔ **Unit `hermes-whatsapp-bridge` НЕ существует.** Мост (`bridge.js`) живёт внутри `hermes-gateway` (спавнится при connect профиля alikhan). Рестарт — только через gateway, а рестарт gateway запрещён (GATEWAY RESTART BAN) — только Сергей/оператор.

```bash
# Статус моста
curl -s http://127.0.0.1:3000/health
# → {"status":"connected", "queueLength":0, "uptime":..., "scriptHash":"..."}

# Если disconnected — НЕ рестартуй сам. Доложи Hermes в #infrastructure / Сергею.
```

### Python-бот (main_waha.py) — ⛔ БОЛЬШЕ НЕ ИСПОЛЬЗУЕТСЯ

Alikhan работает как агент Hermes напрямую через Bridge. Отдельный Python-процесс (`main_waha.py`) и `alikhan.service` остановлены 29.07.2026. Перезапуск не требуется — Hermes Agent сам обрабатывает сообщения.

### Document Extractor

```bash
systemctl --user restart alikhan-document-extractor
curl -fsS http://127.0.0.1:8099/health
```

---

## 4. Бот не отвечает — диагностика (6 шагов)

```
1. WhatsApp Bridge жив?
   curl -s http://127.0.0.1:3000/health
   → {"status":"connected"} ✅ | ошибка ❌ → шаг 5 (перезапуск моста)

2. Docker контейнеры работают?
   docker ps --filter "name=evolution-postgres"
   → evolution-postgres Up ✅ | ❌ → sudo systemctl restart docker

3. Hermes Agent получает сообщения?
   grep "platform=whatsapp" gateway.log → есть inbound ✅ | ❌ → проверить мост

4. Бот получает сообщения?
   grep "platform=whatsapp" gateway.log | tail
   → есть активность ✅ | ❌ → проверить мост + агента

5. Если bridge disconnected — НЕ рестартуй сам (GATEWAY RESTART BAN):
   доложи Hermes в #infrastructure / Сергею.
   Проверка: curl -s http://127.0.0.1:3000/health

6. Логи:
   journalctl --user -u hermes-gateway --since "30 minutes ago" | tail -30
```

---

## 5. Восстановление базы данных

```bash
# Создать бэкап:
python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py

# Восстановить из последнего бэкапа:
ls -t /backups/alikhan_db_*.sql.gz | head -1 | xargs python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py --restore

# Бэкапы хранятся в /backups/, ротация 30 дней
# Cron: ежедневно в 03:00 UTC (backup_db.py)
```

### Проверка целостности БД ОЖР

```bash
# Проверить все 14 таблиц
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
SELECT tablename FROM pg_tables
WHERE schemaname='public' AND tablename LIKE 'ojr_%'
ORDER BY tablename;
"

# Проверить данные за сегодня
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
SELECT work_date, building, vor_code, volume
FROM ojr_section3_work_log
WHERE work_date = CURRENT_DATE
ORDER BY building, vor_code;
"

# Погода за сегодня
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
SELECT weather_date, temp_max, temp_min, wind_speed, phenomenon
FROM ojr_weather
WHERE weather_date = CURRENT_DATE;
"

# Фото за сегодня
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
SELECT photo_date, building, file_name, ai_description
FROM ojr_photo_log
WHERE photo_date = CURRENT_DATE;
"
```

---

## 6. ЕЖО — формирование и отладка

### Генерация ЕЖО

```bash
# По команде в WhatsApp: «Алихан формируй ЕЖО»
# Или вручную:
cd /home/hermes-workspace/Alikhan-migration/bot
python3 fill_ejo.py $(date +%Y-%m-%d)
# Результат: /tmp/ЕЖО_YYYY-MM-DD_vN.xlsx
```

### Проверка ЕЖО перед отправкой

```bash
# Проверить что все факты из БД попали в шаблон
docker exec evolution-postgres psql -U evolution -d evolution_db -c "
SELECT vor_code, building, volume, category
FROM ojr_section3_work_log
WHERE work_date = CURRENT_DATE
ORDER BY building, vor_code;
"

# Сравнить с шаблоном (data_only=True — читает формулы как значения)
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('/home/hermes-workspace/Alikhan-migration/bot/templates/ЕЖО_шаблон.xlsx', data_only=True)
ws = wb['Ежедневный отчет']
print(f'Строк: {ws.max_row}, Колонок: {ws.max_column}')
"
```

### Симуляция даты (тестирование)

```bash
# В config.py установи:
SIM_DATE = "2026-06-30"

# Перезапустить бота. Все операции будут использовать указанную дату.
# После тестирования: SIM_DATE = None → перезапустить.
```

---

## 7. Мониторинг и алерты

### Проверка систем мониторинга

```bash
# Мост (health)
curl -s http://127.0.0.1:3000/health

# Document Extractor
curl -fsS http://127.0.0.1:8099/health

# PostgreSQL
docker ps --filter "name=evolution-postgres"

# Telegram-алерты (cron-страж, ежедневно 02:00 UTC)
#   scripts/daily_health_check.py + scripts/daily_data_liveness.py
```

**Триггеры алертов:**
- Hermes Bridge `status != connected` → доложить Hermes/Сергею (не рестартить самому)
- Cron-страж `f7025391a89a` (02:00 UTC) — pytest + живость → Telegram
- Grok API недоступен
- PostgreSQL не отвечает

---

## 8. Частые проблемы и решения

| Симптом | Причина | Решение |
|:--------|:--------|:--------|
| Тройные ответы в WhatsApp | Зомби-процесс/дубль gateway | Доложить Hermes (рестарт gateway — только оператор) |
| Бот не видит сообщения | Bridge не запущен | `curl -s http://127.0.0.1:3000/health`; disconnected → доложить Hermes |
| Bridge health = disconnected | Сессия WhatsApp истекла | Доложить Hermes (релинк/рестарт — только оператор), заново привязать QR |
| ЕЖО пустой / нет данных | Данные не попали в `ojr_section3_work_log` | `SELECT * FROM ojr_section3_work_log WHERE work_date = CURRENT_DATE` |
| Фото не обрабатываются | Document extractor упал | `systemctl --user restart alikhan-document-extractor` |
| Ошибка «табель не найден» | Файл табеля не загружен | Прислать табель как документ в WhatsApp |
| Watchdog не алертит | Не настроен DISCORD_WEBHOOK_URL | Добавить webhook в `~/.hermes/secrets.env` |
| Бэкапы не создаются | Нет прав на `/backups/` | `sudo chown $(whoami):$(whoami) /backups` |
| Двойное накопление дат в планах | Перезапись без проверки | `fill_ejo.py` — проверка `old_v == new_label` |
| Погода не обновляется | Open-Meteo / wttr.in недоступен | Ручной ввод через `ojr_weather` |

---

## 9. Как обновить шаблон ЕЖО

1. Пришлите новый Excel-файл в WhatsApp группу
2. Бот сравнит с текущим шаблоном и покажет diff
3. Ответьте «применить шаблон» — бот обновит `bot/templates/ЕЖО_шаблон.xlsx`
4. Кеш кодов обновится автоматически

---

## 10. Восстановление после сбоя — полный цикл

### Полный сбой (VPS перезагружен / всё упало)

```bash
# 1. Проверить Docker
sudo systemctl status docker
docker ps --filter "name=evolution-postgres"

# 2. Запустить PostgreSQL если упал
docker start evolution-postgres 2>/dev/null || true

# 3. Запустить WhatsApp Bridge (внутри gateway)
#    ⛔ НЕ рестартить gateway самому — доложить Hermes/Сергею
sleep 10
curl -s http://127.0.0.1:3000/health

# 4. Hermes Agent (Alikhan) — работает как агент, отдельного процесса нет

# 5. Запустить Document Extractor
sudo systemctl start alikhan-document-extractor

# 6. Проверить всё
curl -s http://127.0.0.1:3000/health
curl -fsS http://127.0.0.1:8099/health
```

### Только WhatsApp Bridge упал (бот жив, БД жива)

```bash
# ⛔ НЕ рестартить gateway самому — GATEWAY RESTART BAN.
# Доложить Hermes в #infrastructure / Сергею, оператор перезапустит.
curl -s http://127.0.0.1:3000/health
```

### Повреждена БД ОЖР

```bash
# Восстановить из последнего бэкапа
ls -t /backups/alikhan_db_*.sql.gz | head -1 | xargs python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py --restore

# Проверить что таблицы восстановились
docker exec evolution-postgres psql -U evolution -d evolution_db -c "\dt ojr_*"
```

---

## 11. Быстрые ссылки

| Ресурс | Команда / Путь |
|:-------|:---------------|
| Исходный код | `/home/hermes-workspace/Alikhan-migration/bot/` |
| Шаблон ЕЖО | `bot/templates/ЕЖО_шаблон.xlsx` |
| Схема БД | `db/ojr_schema.sql` (15 таблиц) |
| Логи агента | Hermes session logs (не `/tmp/alikhan.log` — бот остановлен) |
| Логи моста | `journalctl --user -u hermes-gateway` |
| Бэкапы | `/backups/` (ежедневно, ротация 30 дней) |
| Health check | `curl :3000/health` + `curl :8099/health` |
| Песочница WhatsApp | `120363179621030401@g.us` |
| Боевая группа | `120363400682390076@g.us` (только с approval!) |

---

## 12. Контакты

| Роль | Контакт |
|:-----|:--------|
| Разработчик | @gromykos |
| Поддержка | Hermes Agent (чат) |
| Алерты | Discord / Telegram |
| Wiki | Obsidian vault: `20_Projects/Hermes/Report - ЕЖО АйБиКон` |

---

*Alikhan v6.0 — прямой Hermes Bridge · ТЗРК Джеруй · обновлено 05.09.2026*
