# CHRONOLOGY — Хронология изменений Алихан бота

## 26.07.2026 — ОЖР-миграция: персонал/фото/готовность (production-цикл)

### Баги найдены и исправлены (5)
- **ON CONFLICT без constraint** — `db.py:676` и `db.py:696`: `ON CONFLICT DO NOTHING` без колонок + несовпадение с реальным constraint (4 колонки вместо 2). Бот падал в loop при сохранении опроса.
- **workers_count** — `ojr_section1_personnel` не имел поля количества. «Рабочие 4» → 1 запись. Добавлен `workers_count INTEGER DEFAULT 1`, обновлены `save_personnel()`, `get_staff()`, `qa.py`.
- **Фото не вставлялись** — `fill_ejo.py` тянул через Evolution API (мёртв). Добавлен local_path fallback: чтение с диска из `image_cache`. `ojr_photo_log.file_path` теперь заполняется.
- **Готовность сбрасывалась** — `fill_ejo.py` брал из вчерашнего авто-файла (23%) вместо шаблона (27%). Исправлено на чтение из TEMPLATE + обработка Excel fraction (0.27 → 27%).
- **Голос в production** — `production_listener_loop()` не обрабатывал аудио. Добавлен аудио-блок + `ojr_photo_log` запись в production handler.

### Production-проверка
- **Персонал:** Майкадам total=5 (ИТР=1, Рабочие=4) ✅
- **Работы:** 7.2.1.1 = 5 м³ ✅
- **Фото:** 3 шт вставлены ✅
- **Готовность:** 27% из шаблона ✅

### Инфраструктура
- **Интеграционный тест:** `test_e2e_ejo.py` (400 строк) — запись в OJR → fill_ejo → проверка Excel. Требует доработки: валидация другим worker'ом (Diamond), сверка с эталонным файлом.
- **T-115 Voice Testing:** закрыт (2 бага исправлено)
- **T-116 Cheap Delegate:** закрыт (DeepSeek v4-pro, экономия 11.5×)
- **AL-023 Client Guide:** готов, отправлен в песочницу
- **00_Task Index:** 4 неактуальные задачи закрыты (Evolution/WAHA/n8n)

### Уроки
- **Diff только по 3 колонкам** (16,19,21) — персонал/фото/готовность в слепой зоне. Пользователь подтвердил: не расширять.
- **Готовность из шаблона, не из авто-файла** — шаблон обновляется ежедневно из исправленного файла.
- **Фото: local_path, не Evolution API** — Evolution остановлен, local_path обязателен.

## 25.07.2026 — Полный аудит и стабилизация (Hermes-driven)

### Аудит
- Полный построчный аудит 15 модулей (~6900 строк): 49 багов (2 CRITICAL, 7 HIGH, 21 MEDIUM, 19 LOW)
- Документ: `docs/full-audit-2026-07-25.md`

### Исправления (коммит `bedf725` — 5 файлов, +49/−1713)

**Архитектура данных:**
- `data_sources.py` — единый модуль контрактов: 12 NamedTuple, primary OJR + fallback legacy
- `fill_ejo.py` — вырезаны прямые обращения к БД/API (~300 строк)

**ЕЖО:**
- Формат имени: `ЕЖО_ДД.ММ.ГГ_АйБиКон.xlsx` (единый во всех модулях)
- B1-B7: фото base64, guard перегенерации, hide_rows, погода fallback
- ПСД динамический, АйБиКон fallback, DRY планы
- R853 L-U очистка
- WhatsApp-кириллица: убран `'ЕЖО' in fname` (обрезается)
- Diff формат: `R737 U (2.1.10): 185.5 → 873.2`

**HIGH-баги исправлены:**
- bridge_wrapper: exact match вместо substring (утечка сообщений)
- Age gate 15с убран
- Дубликаты secrets → config.py
- Grok abuse vector → проверка имени «алихан»
- datetime.utcnow() → timezone.utc
- poll: ostatok≤0 filter убран
- main_waha: VOR дедупликация, EJO guard убран

**OJR:**
- Персонал: end_date закрывается при новых записях
- Объёмы: ON CONFLICT без category, дубликатов нет
- QA-парсер: не пишет volume=0 и статусные сообщения в work_log
- Фото: запись в ojr_photo_log + local_path сохраняется

**БД:**
- Очистка: 28→15 MB (2924 строки мусора миграции, 4816 старых фактов, 3983 сообщения, 36 пустых таблиц)

### Сегодня (25.07)
- **ЕЖО:** 10 версий сгенерировано, v10 финальная (613 KB). Исправленный файл от руководителя принят — 0 отличий.
- **Данные:** VOR 7.2.1.1 = 3 (арматурные работы), фото: АБК×2 + Общежитие×2
- **seen_ids.json:** сброшен в `[]`
- Бот НЕ перезапускался после коммита

### Верифицировано (без багов)
- AVR (КС-2, КС-6): не зависит от формата ЕЖО
- Календарь/напоминания: БД, не файлы
- STT: faster-whisper + Grok коррекция
- Grok: проверка имени, без abuse vector

### Осталось (низкий приоритет)
- 21 MEDIUM + 19 LOW (качество кода, мёртвый код)

## 2026-07-24

- CONTEXT GATE (rule #0) added to `AGENTS.md`
- OfficeCLI installed: read mode works for EJO templates; write mode has persistence bug (formulas not saved to disk)
- `code-review-graph`: 448 nodes, 2,250 edges exported
- Unsiloed plugin installed for document parsing (gateway restart pending)

## 20.07.2026 — Structured Vision Checklist: photo→ЕЖО structured mapping (T-137 #5)

### Что было сделано
- Создан `vision_checklist.py` (338 строк): structured JSON checklist вместо plain-text Grok vision описаний
- CHECKLIST_SCHEMA с полями (weather, personnel_count, equipment, materials, progress, incidents, confidence scores)
- `checklist_from_image(base64)` → Grok-4 structured output → parsed JSON
- `checklist_to_ejo_map()` → прямое заполнение колонок ЕЖО + `ojr_photo_log` / `ojr_section3_work_log`
- Значительное улучшение фото-анализа для ежедневного отчёта, снижение hallucination в fill_ejo
- Интеграция в photo flow main_waha.py → ojr tables → ЕЖО generation

### Файлы
- `bot/vision_checklist.py` (новый модуль)
- Обновления в `bot/main_waha.py` (photo handler integration)
- Связанные правки в `fill_ejo.py` / `document_extractor.py`

### Discord
- #alikhan обсуждение архитектуры vision pipeline (T-137)

## 19.07.2026 — АВР: полный рефакторинг КС-6 + 837 расценок ВОР

### КС-6 — полная переделка

- **Одна таблица, 4 сгруппированных раздела:** Все работы / Выполнено с начала / За отчетный период / Остаток.
- Шапка: Код + Наименование + 4 группы подзаголовков (Ед., Кол-во, Цена за ед./сом, Сумма).
- Данные читаются напрямую из `ЕЖО_шаблон.xlsx` (колонки K/P/S), не из `ojr_section3_work_log`.
- 780+ строк, 0 пропущенных расценок. Итого только по колонкам Сумма (F,H,J,L). Округление до 2 знаков.
- Формат: `#,##0.00`, заморозка A9, альбомная ориентация, подписи.

### КС-2 — колонка Код ВОР

- Добавлена колонка «Код ВОР» (B) после № п/п, итого 15 колонок.
- Агрегация по коду, фильтр monthly_qty > 0.

### ВОР — 837 кодов (было 607)

- Добавлено 259 кодов из ЕЖО через среднее по разделу. 0 пропущенных.
- 5 критичных (3.3.2, 3.3.2.1, 3.3.2.2, 3.3.6, 7.2.1.1) — ручные цены.
- Поиск: точный код + fallback на родителя одного уровня.

### WhatsApp Bridge — стабильная доставка

- `_FakeResponse` переписан как контекст-менеджер (text + files).
- `status_code` property для совместимости с `send_document`.
- Текст и файлы уходят без ошибок.

### README — двуязычный для Twitter/GitHub

- EN/RU, обновлённые цифры: 837 кодов, 780+ строк КС-6, 3/3 теста.

### Аудит репозитория

- 0 секретов, 3/3 тестов, py_compile чисто, bridge 95+ мин аптайм.

## 19.07.2026 — КС-2 приведён к реальной 14-колоночной форме

- `generate_ks2()` формирует реквизиты акта, многоуровневую таблицу из 14 колонок, итоги, удержания и блок подписей.
- Заказчик, подрядчик, договор, стройка, объект и валюта читаются из переменных окружения; названия компаний в КС-2 не зашиты в код.
- Накопление предыдущего периода читается из вчерашнего КС-2, затем ЕЖО, с резервным расчётом по `ojr_section3_work_log`.
- Технические коды и накопительные объёмы сохраняются на скрытом листе `_meta` для переноса в следующий акт.
- Тесты КС-2 обновлены для проверки структуры формы, накоплений и удержаний; `generate_ks6()` оставлен без изменений.

## 19.07.2026 — Исправление кумулятивов ЕЖО

- Повторная генерация за дату corrected template больше не добавляет суточный объём второй раз.
- Чистая генерация использует вчерашние P/S даже при P=0; отсутствие файла теперь возвращает `None`.
- Значения P/S с десятичной запятой разбираются без потери данных.
- Проверки: `py_compile` успешно; существующий `test_ejo_simulation.py` не содержит pytest-тестов (`no tests ran`).

### Модуль АВР (КС-2 / КС-6)

- Создан `bot/avr.py`: формирование актов КС-2 за период и накопительного журнала КС-6 на дату.
- Добавлены команды WhatsApp: `АВР`, `формируй АВР`, `кс-2`, `кс-6`; интеграция выполнена в `router.py` и `main_waha.py`.
- Добавлен `bot/test_avr.py` с 3 тестами генерации КС-2, КС-6 и сводки стоимости.
- Источник расценок: `report/templates/ВОР_с_расценками.xlsx` — 607 позиций, расценки ФЕР-2020 с коэффициентом 0,75, общая стоимость около 760 млн KGS.

### Исправления после Grok review

- `avr.py`: КС-6 сохраняет названия работ и единицы измерения; переданные `work_entries` фильтруются по периоду; сопоставление кодов ВОР нормализовано.
- `fill_ejo.py`: устранён повторный учёт суточного объёма в P/S через `template_has_today`; `yesterday_cum()` возвращает `None`, когда предыдущего отчёта нет.
- `poll.py`: поддержан ввод нескольких кодов в одном сообщении; для новых записей используется `building='общая'`; добавлены предупреждения о пустом и частично распознанном ответе.
- `main_waha.py`: предупреждения poll теперь отправляются пользователю в WhatsApp.
- Исправления зарегистрированы в `bot/BUGS.md` как AL-013—AL-020.

### Репозиторий и инструменты

- Репозиторий опубликован: https://github.com/Gromykoss/Alikhan; секреты и внутренние идентификаторы очищены перед сменой видимости.
- Grok Build CLI обновлён с v0.2.59 до v0.2.103: `--yolo` заменён на `--always-approve`, для headless-запусков используется `--print`.

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

## 2026-07-22 — WAHA альтернатива + проект idle

- **12:00** — X Hotspot Radar: обнаружен WAHA — self-hosted WhatsApp HTTP API, альтернатива Evolution API для Alikhan-стека (T-159).
- **22-23.07** — Проект idle. Бот остановлен (миграция с Evolution на Hermes Bridge завершена 15.07). Новых изменений кода нет. AGENTS.md memory violation (10-й repeat) — Hermes не прочитал основной AGENTS.md при старте сессии 21.07.

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
- **25.07.2026 15:24** — test: post-commit hook verification (`81410fb`)
- **26.07.2026 04:13** — chore: auto-sync 26.07 (`65a1136`)
- **26.07.2026 09:46** — chronology: 26.07 — 5 bugs fixed (ON CONFLICT, workers_count, photos, readiness, voice) (`fbcfaa9`)
