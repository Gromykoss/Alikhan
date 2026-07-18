# 🔧 Алихан — Runbook оператора

**Дата:** 17 июля 2026 · **Проект:** ТЗРК Джеруй · **Версия:** v3.1

Быстрое руководство по эксплуатации, перезапуску и восстановлению WhatsApp-бота Алихан.

---

## 1. Быстрый статус

```bash
# Все проверки одним скриптом
python3 /home/hermes-workspace/.hermes/scripts/alikhan_health_check.py

# Или вручную:
docker ps --filter "name=evolution" --format "{{.Names}} {{.Status}}"
ps aux | grep main_waha | grep -v grep
```

**Признаки работы:** бот отвечает в WhatsApp группе в течение 3-5 секунд.

---

## 2. Перезапуск

```bash
# Мягкий перезапуск (systemd)
sudo systemctl restart alikhan-bot

# Или вручную:
kill $(pgrep -f main_waha.py)
cd /home/hermes-workspace/Alikhan-migration/bot && python3 main_waha.py &
```

**⚠️ Убедись что старый процесс убит:** `pgrep -af main_waha` — должно быть ровно 1 PID.

---

## 3. Бот не отвечает — диагностика (5 шагов)

```
1. WhatsApp подключён?
   curl -s http://127.0.0.1:8080/instance/connectionState/alikhan \
     -H "apikey: <EVO_KEY>" | python3 -c "import sys,json; print(json.load(sys.stdin)['instance']['state'])"
   → "open" ✅ | "close"/"connecting" ❌ → шаг 4

2. Docker контейнеры работают?
   docker ps --filter "name=evolution" --filter "name=waha"
   → все Up ✅ | restart: docker start evolution-api evolution-postgres evolution-redis

3. Python бот запущен?
   pgrep -af main_waha.py → есть PID ✅ | ❌ → шаг «Перезапуск»

4. Переподключить WhatsApp (если disconnected):
   curl -s -X POST http://127.0.0.1:8080/instance/connect/alikhan \
     -H "apikey: <EVO_KEY>" | python3 -c "
   import sys,json,base64
   d=json.load(sys.stdin)
   b64=d['base64'].replace('data:image/png;base64,','')
   open('/tmp/alikhan_qr.png','wb').write(base64.b64decode(b64))
   print('QR сохранён в /tmp/alikhan_qr.png')"

5. Логи:
   tail -50 /home/hermes-workspace/Alikhan-migration/bot/bot.log
```

---

## 4. Восстановление базы данных

```bash
# Создать бэкап:
python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py

# Восстановить из последнего бэкапа:
ls -t /backups/alikhan_db_*.sql.gz | head -1 | xargs python3 /home/hermes-workspace/Alikhan-migration/bot/backup_db.py --restore

# Бэкапы хранятся в /backups/, ротация 30 дней.
# Cron: 0 3 * * * cd /home/hermes-workspace/Alikhan-migration/bot && python3 backup_db.py
```

---

## 5. Как обновить шаблон ЕЖО

1. Пришлите новый Excel-файл в WhatsApp группу
2. Бот сравнит с текущим шаблоном и покажет diff
3. Ответьте «применить шаблон» — бот обновит `/bot/templates/ЕЖО_шаблон.xlsx`
4. Кеш кодов обновится автоматически

---

## 6. Симуляция даты (тестирование)

```bash
# В config.py установи:
SIM_DATE = "2026-06-30"

# Перезапустить бота. Все операции будут использовать указанную дату.
# После тестирования: SIM_DATE = None → перезапустить.
```

---

## 7. Мониторинг и алерты

```bash
# Prometheus метрики:
curl http://localhost:9090/metrics

# Grafana: http://<ip>:3000 (source: Prometheus localhost:9090)

# Telegram алерты: настройте в secrets.env:
# ALERT_TELEGRAM_TOKEN=...
# ALERT_TELEGRAM_CHAT_ID=...
```

**Триггеры алертов:**
- Бот не отвечает > 10 минут
- Ошибок > 5 за 5 минут
- Grok API недоступен
- PostgreSQL не отвечает

---

## 8. Частые проблемы и решения

| Симптом | Причина | Решение |
|---------|---------|---------|
| Тройные ответы в WhatsApp | Зомби-процесс main_waha | `killall -9 python3; systemctl restart alikhan-bot` |
| Бот не видит сообщения | Bridge не запущен | Проверить `hermes bridge status` |
| ЕЖО пустой / нет данных | Неправильная категория фактов | Проверить `SELECT category, fact FROM bot_memory_facts WHERE fact_date = current_date` |
| Ошибка «табель не найден» | Файл табеля не загружен в WhatsApp | Прислать табель как документ в группу |
| Evolution API disconnected | Сессия WhatsApp истекла | Переподключить (шаг 4 диагностики) |

---

## 9. Контакты

| Роль | Контакт |
|------|---------|
| Разработчик | @gromykos |
| Поддержка | Hermes Agent (чат) |
| Алерты | Telegram |
| Wiki | Obsidian vault: `20_Projects/Hermes/Report - ЕЖО АйБиКон` |

---

## 10. Быстрые ссылки

- **Исходный код:** `/home/hermes-workspace/Alikhan-migration/bot/`
- **Шаблон ЕЖО:** `bot/templates/ЕЖО_шаблон.xlsx`
- **Логи:** `bot/bot.log`
- **Бэкапы:** `/backups/`
- **Systemd:** `sudo systemctl status alikhan-bot`
- **Health check:** `python3 ~/.hermes/scripts/alikhan_health_check.py`
