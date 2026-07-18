# CHRONOLOGY — Хронология изменений Алихан бота

## 18.07.2026 — Миграция БД на структуру ОЖР (14 таблиц)

### Ключевое изменение
База данных перестроена со старой структуры (`bot_memory_facts` + `bot_poll_residuals`) на 14 таблиц ОЖР по ГОСТ РД-11-05-2007 / Приказу Минстроя РФ №1026/пр.

### Что изменилось
- **14 новых таблиц:** `ojr_title_page`, `ojr_section1_personnel` (Раздел 1 — ИТР), `ojr_section2_design_supervision` + `ojr_section2_visits` (Раздел 2 — Авторский надзор), `ojr_section3_work_log` (Раздел 3 — Выполнение работ, главная), `ojr_section4_construction_control` + `ojr_section4_checks` (Раздел 4 — Стройконтроль), `ojr_section5_asbuilt_docs` (Раздел 5 — Исполнительная документация), `ojr_section6_gosstroynadzor` (Раздел 6 — Госстройнадзор), `ojr_weather`, `ojr_photo_log`, `ojr_daily_summary`, `ojr_materials`, `ojr_incidents`
- **Новый поток данных:** QA → `bot_memory_facts` (промежуточный слой) → роутинг по `ojr_*` таблицам
- **Poll → `ojr_section3_work_log`:** закрытие опроса пишет объёмы в work_log
- **ЕЖО = view на `ojr_section3_work_log`:** `fill_ejo.py` читает work_log за дату вместо прямого чтения `bot_memory_facts`
- **Погода → `ojr_weather`:** Open-Meteo пишет и в БД, и в Excel
- **Снимок дня = композит:** `ojr_photo_log` + `ojr_daily_summary` + сообщения WhatsApp

### Файлы
- `db/ojr_schema.sql` — полная схема (14 таблиц, индексы, constraints, комментарии)
- `db/ojr_er_diagram.md` — ER-диаграмма (Mermaid + ASCII)
- `db/ojr_fill_guide.md` — руководство по заполнению разделов 1-6, sync-скрипты, диагностика
- `db/ojr_migration.sql` — скрипт миграции существующих данных
- `bot/ojr_sync.py` — модуль синхронизации: facts→work_log, фото→photo_log, погода→weather

### Старые таблицы
- `bot_memory_facts` и `bot_memory_messages` оставлены как история / audit trail
- `bot_poll_residuals` заменён на `ojr_section3_work_log` (category='объём')
- План отказа от старых таблиц: 4 фазы (см. `db/ojr_fill_guide.md`, раздел 4)

### Навыки
- `alikhan-daily-snapshot` — новый навык: ежедневный снимок дня из ОЖР-таблиц

## 17.07.2026 (14:23) — HermesBridge стабилизация: retry+backoff и systemd

### Проблема
- Мост падал с `Timeout in AwaitingInitialSync` / HTTP 000 — `startSocket()` без `.catch()` → unhandled rejection → crash
- Быстрые 440-реконнекты (каждые 3с) → rate-limiting → ухудшение стабильности

### Решение
1. **`bridge.js` — `connectWithRetry()`**: внешний цикл с exponential backoff (1s→60s cap), `.catch()` на каждом вызове
2. **`bridge.js` — внутренний reconnect с backoff**: 1s→30s cap, 428 ошибки отдельно (короткий), `.catch()` на таймерах
3. **systemd user service** (`hermes-whatsapp-bridge.service`): `Restart=always`, env vars, лимиты памяти

### Файлы
- `~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js` — добавлены `connectWithRetry()`, `_reconnectBackoffMs`
- `~/.config/systemd/user/hermes-whatsapp-bridge.service` — создан
- Запуск: `systemctl --user {start,stop,restart,status} hermes-whatsapp-bridge`

### Примечание
- 440 конфликты (=телефон активен) — ожидаемое поведение; backoff предотвращает hammering
- Мост жив даже при 440: HTTP :3000 отвечает, systemd следит

## 17.07.2026 (10:00) — Фикс фото: _media + Grok vision description

### Достигнуто
- **Фото обнаружение:** `imageMessage` (Evolution API) → `_media.mediaType == "image"` (Bridge) — песочница + прод
- **Vision-описание:** Grok (grok-4-latest) анализирует фото и пишет 1-2 предложения в `tags->>'description'`
- **Промпт:** описание состояния конструкций без предположения активных работ

### Баги исправлены
- Фото не сохранялись после миграции на Hermes Bridge (wrapper кладёт _media, код искал imageMessage)
- Дубль: Codex оставил `has_media = bool(msg...)` до определения `msg` → `[LOOP ERR] name 'msg' is not defined`

### Файлы
- `bot/main_waha.py` — строки 390-413 (prod), 526-576 (sandbox): фото + vision
- `bot/bridge_wrapper.py` — без изменений (debug Codex откачен)

### Коммиты
- `8a2a87e` — Fix: imageMessage→_media for bridge photo detection
- `aedc853` — fix: photo detection via _media + Grok vision description

## 16.07.2026 (19:30) — ЕЖО v4: N=100%, планы из сырых сообщений, оформление 3-го листа

### Достигнуто
- N = 100% (L = M) всегда
- U = O − P, O > 0 ∧ U > 0 → строка видна
- Планы парсятся из сырых сообщений через Grok-фолбек
- 3-й лист «Персонал» оформлен
- Фаза 8 скрыта целиком
- 76 строк открыто

### Коммит
- `86d8439` — Alikhan v4 final

## 15.07.2026 — Миграция на Hermes Bridge

### Ключевое изменение
Evolution API заменён на Hermes WhatsApp Bridge (:3000).
- `bridge_wrapper.py` — monkey-patch: перехватывает `requests.post` к Evolution API → Bridge API
- `main_waha.py` — не менялся, импортирует `from bridge_wrapper import *`
- Evolution API Docker — остановлен
- `alikhan.service` — остановлен

### Навыки созданы
- `alikhan-poll` — цикл опроса прорабов
- `alikhan-fill-ejo` — заполнение шаблона ЕЖО
- `alikhan-template-handoff` — цикл «бот→ручная правка→шаблон»
- `alikhan-monthly-template` — месячный план через «раскрой отчет»
