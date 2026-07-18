# ОЖР — Рекомендации по заполнению

> Для разработчиков Alikhan Bot и операторов ЕЖО
> Версия: 1.0.0 | 2026-07-18

---

## 1. ОБЩАЯ СТРАТЕГИЯ ЗАПОЛНЕНИЯ

### Приоритет источников данных

```
WhatsApp QA (прораб) ──→ bot_memory_facts ──→ ojr_section3_work_log
                                                         │
WhatsApp Photos ──→ bot_memory_messages ──→ ojr_photo_log
                                                         │
Open-Meteo API ──→ ojr_weather                           │
                                                         │
ЕЖО .xlsx ──→ _extract_ejo_volumes() ──→ ojr_section3_work_log
                                                         │
                                                         ▼
                                              ojr_daily_summary
```

### Золотое правило
**Данные пишутся в `ojr_*` таблицы только ПОСЛЕ проверки в `bot_memory_facts`.**
Не пиши напрямую в `ojr_*` — используй промежуточный слой через QA-парсер.

---

## 2. ПОШАГОВОЕ ЗАПОЛНЕНИЕ ПО РАЗДЕЛАМ

### 2.1 ТИТУЛЬНЫЙ ЛИСТ (`ojr_title_page`)

**Когда:** ОДИН раз при инициализации проекта.

```sql
-- Ручная вставка (заменить на реальные данные)
INSERT INTO ojr_title_page (
    customer_name,     contractor_name,    designer_name,
    object_name,       object_address,     object_type,
    contract_number,   contract_date,
    construction_permit_number, construction_permit_date,
    work_start_date,   work_end_date,
    gsn_body
) VALUES (
    'ОсОО «Альянс-Алтын»',
    'ОсОО «АйБиКон»',
    'ЗАО «Кыргызстройпроект»',   -- УТОЧНИТЬ
    'ТЗРК Джеруй',
    'Таласская область, Джеруй',
    'новое строительство',
    '№ ___ от ___.___.____',
    '____-__-__',
    '№ ___ от ___.___.____',
    '____-__-__',
    '2025-04-30',
    '2027-08-04',
    'Госстройнадзор при Минстрое КР'  -- УТОЧНИТЬ
);
```

**Рекомендации:**
- Только ОДНА активная запись (`is_active = TRUE`)
- Заполнить все поля с пометкой «УТОЧНИТЬ» из реальных документов
- `work_end_actual` обновлять при фактическом завершении

---

### 2.2 РАЗДЕЛ 1: ИТР-ПЕРСОНАЛ (`ojr_section1_personnel`)

**Источники данных:**
1. **QA-факты** (категория `персонал`) — автоматически из WhatsApp сообщений
2. **Табель** (Excel-файл) — `get_aibikon_headcount()` в `fill_ejo.py`
3. **Ручной ввод** через SQL / админ-панель

```sql
-- Пример: добавить ответственного производителя работ
INSERT INTO ojr_section1_personnel (
    title_id, organization_type, organization_name,
    full_name, position,
    start_date, is_responsible, sync_source
) VALUES (
    (SELECT id FROM ojr_title_page WHERE is_active = TRUE),
    'contractor',
    'ОсОО «АйБиКон»',
    'Иванов И.И.',          -- УТОЧНИТЬ
    'Руководитель проекта',
    '2025-04-30',
    TRUE,
    'manual'
);
```

**Автозаполнение из QA:**

`qa.py` уже парсит персонал в `bot_memory_facts` с категорией `персонал`. После каждой QA-сессии запускать:

```sql
-- Синхронизация персонала из QA-фактов (за сегодня)
INSERT INTO ojr_section1_personnel (
    title_id, organization_type, organization_name,
    full_name, position, start_date, sync_source
)
SELECT
    (SELECT id FROM ojr_title_page WHERE is_active = TRUE),
    CASE
        WHEN f.fact ILIKE '%айбикон%' THEN 'contractor'
        ELSE 'subcontractor'
    END,
    CASE
        WHEN f.fact ILIKE '%айбикон%' THEN 'ОсОО «АйБиКон»'
        WHEN f.fact ILIKE '%атантай%' THEN 'Атантай'
        WHEN f.fact ILIKE '%майкадам%' THEN 'Майкадам'
        WHEN f.fact ILIKE '%наватек%' THEN 'Наватек'
        ELSE 'Субподрядчик'
    END,
    substring(f.fact FROM '^([А-Я][а-я]+)'),
    CASE
        WHEN f.fact ILIKE '%итр%' THEN 'ИТР'
        WHEN f.fact ILIKE '%рабоч%' THEN 'Рабочий'
        WHEN f.fact ILIKE '%прораб%' THEN 'Прораб'
        ELSE 'Сотрудник'
    END,
    f.fact_date,
    'qa'
FROM bot_memory_facts f
WHERE f.category = 'персонал'
  AND f.source = 'qa'
  AND f.fact_date = CURRENT_DATE
ON CONFLICT DO NOTHING;
```

**Рекомендации:**
- Заводить запись на КАЖДОГО сотрудника (не агрегировать «Атантай ИТР 1, рабочих 6» в одну строку)
- `is_responsible = TRUE` только для ответственного производителя работ
- `end_date` заполнять при увольнении/замене (NULL = «работает»)

---

### 2.3 РАЗДЕЛ 3: ВЫПОЛНЕНИЕ РАБОТ (`ojr_section3_work_log`)

**Главная таблица.** Заполняется ежедневно.

**Источники:**
| Источник | created_by | Триггер |
|----------|-----------|---------|
| QA-парсер (WhatsApp) | `qa` | Каждое сообщение прораба с `код = объём` |
| Закрытие опроса | `poll` | `close_poll()` → `actual_today` |
| Извлечение из ЕЖО | `ejo_extraction` | `_extract_ejo_volumes()` при загрузке .xlsx |
| Ручная правка | `manual` | SQL / админка |

```sql
-- Запись дневного объёма (через QA-парсер)
INSERT INTO ojr_section3_work_log (
    title_id, work_date, vor_code, building,
    volume, unit, category, contractor,
    created_by, source_fact_id
) VALUES (
    (SELECT id FROM ojr_title_page WHERE is_active = TRUE),
    CURRENT_DATE,
    '3.3.2',           -- код ВОР
    'Общежитие',
    104.3,
    'м³',
    'объём',           -- или 'план'
    'Атантай',
    'qa',
    1234                -- id из bot_memory_facts
) ON CONFLICT (work_date, vor_code, building, category)
DO UPDATE SET volume = EXCLUDED.volume, updated_at = NOW();
```

**Правила заполнения:**
1. **UNIQUE на (work_date, vor_code, building, category):**
   - Один код = одна запись в день в одной категории
   - План и факт для одного кода — ДВЕ разные записи (category='план' и category='объём')
2. **Не заполнять `plan_volume`** — он импортируется из шаблона ЕЖО (столбец O)
3. **`building` всегда заполнен** — fallback на «Общее» если неизвестно
4. **`contractor` = `building` для АйБиКон** (основной подрядчик), для субподрядчиков — название организации
5. **Связь `schedule_phase_id`** заполнять при наличии соответствия код→этап графика

**Готовый скрипт синхронизации (после каждого poll close / QA):**

```python
# ojr_sync_works.py — вызывать после close_poll() и fill_ejo()
def sync_works_to_ojr():
    """Переносит объёмы из bot_memory_facts в ojr_section3_work_log"""
    facts = get_facts_for_today()  # ваш метод
    for f in facts:
        code = extract_vor_code(f['fact'])
        if not code: continue
        volume = extract_volume(f['fact'])
        building = f.get('building', 'Общее')
        category = 'план' if 'план' in f['fact'].lower() else 'объём'

        upsert_work_log(
            work_date=f['fact_date'],
            vor_code=code,
            building=building,
            volume=volume,
            category=category,
            source_fact_id=f['id']
        )
```

---

### 2.4 ПОГОДА (`ojr_weather`)

**Автоматически** через `fill_ejo.py` (Open-Meteo API, координаты 42.284, 72.765).

```python
# fill_ejo.py уже вызывает погоду. Добавить запись в ojr_weather:
def save_weather_to_ojr(date, weather_data):
    upsert_weather(
        weather_date=date,
        temp_max=weather_data['temp_max'],
        temp_min=weather_data['temp_min'],
        precipitation_mm=weather_data['precipitation'],
        wind_speed=weather_data['wind_speed'],
        phenomenon=map_phenomenon(weather_data),
        is_work_stopped=(weather_data['temp_min'] < -25)  # пример
    )
```

**Рекомендации:**
- Заполнять ОДИН раз в день (cron в 08:00 Бишкек / 02:00 UTC)
- `is_work_stopped` — пороговые значения: T° < −25°C или ветер > 25 м/с (уточнить у прораба)
- `raw_response` — сохранять полный JSON от Open-Meteo для отладки

---

### 2.5 ФОТО-ФИКСАЦИЯ (`ojr_photo_log`)

**Источник:** `bot_memory_messages` с `message_type = 'image'`.

```sql
-- Синхронизация фото (автоматически при получении в production_listener)
INSERT INTO ojr_photo_log (
    title_id, photo_date, building,
    file_message_id, file_name,
    caption, ai_description, uploaded_by
)
SELECT
    (SELECT id FROM ojr_title_page WHERE is_active = TRUE),
    m.created_at::DATE,
    COALESCE(
        NULLIF(m.tags->>'building', ''),
        'Общие планы'
    ),
    m.id, m.file_name,
    m.tags->>'caption',
    m.tags->>'description',
    CASE WHEN m.chat_id = '120363400682390076@g.us'
        THEN 'production_listener' ELSE 'sandbox' END
FROM bot_memory_messages m
WHERE m.message_type = 'image'
  AND m.created_at::DATE = CURRENT_DATE
  AND NOT EXISTS (
    SELECT 1 FROM ojr_photo_log pl
    WHERE pl.file_message_id = m.id
);
```

**Привязка к работам:**
```python
# После заполнения work_log — привязать фото к ближайшей работе
def link_photos_to_works(date):
    photos = get_photos_for_date(date)
    works = get_works_for_date(date)
    for photo in photos:
        # Найти работу в том же здании
        matching_work = find_work_by_building(works, photo['building'])
        if matching_work:
            update_photo_work_link(photo['id'], matching_work['id'])
```

**Сетка ЕЖО:**
- Колонки C(3), E(5), J(10), N(14), Q(17)
- Максимум 5 фото на здание
- Заполнять `ejo_column` и `ejo_photo_index` в `fill_ejo.py` при вставке фото

---

### 2.6 СВОДНЫЕ ПОКАЗАТЕЛИ (`ojr_daily_summary`)

**Заполняется после `fill_ejo.py`:**

```python
def save_daily_summary(date, ejo_path, ejo_version):
    summary = {
        'total_volume_today': get_total_volume(date),
        'total_workers': get_total_workers(date),
        'total_itr': get_total_itr(date),
        'completion_pct': calc_completion_pct(ws),
        'ejo_file_path': ejo_path,
        'ejo_version': ejo_version,
        'is_corrected': 'corrected' in ejo_path
    }
    upsert_daily_summary(date, summary)
```

---

## 3. АВТОМАТИЗАЦИЯ (ДОБАВИТЬ В КОД)

### 3.1 В `main_waha.py` — после `close_poll()`:

```python
# В конце close_poll():
from ojr_sync import sync_works_to_ojr, sync_personnel_to_ojr, sync_photos_to_ojr
sync_works_to_ojr()
```

### 3.2 В `fill_ejo.py` — после генерации:

```python
# В конце fill_ejo():
from ojr_sync import save_daily_summary, save_weather_to_ojr
save_daily_summary(date, ejo_path, version)
```

### 3.3 В `production_listener_loop()` — при получении фото:

```python
# После save_message():
from ojr_sync import sync_single_photo
if message_type == 'image':
    sync_single_photo(msg_id)
```

### 3.4 Новый скрипт `bot/ojr_sync.py`:

Создать модуль с функциями:
- `sync_works_to_ojr()` — bot_memory_facts → ojr_section3_work_log
- `sync_personnel_to_ojr()` — QA персонал → ojr_section1_personnel
- `sync_photos_to_ojr()` — bot_memory_messages (image) → ojr_photo_log
- `sync_single_photo(msg_id)` — одно фото
- `save_daily_summary(date, ejo_path, v)` — сводка дня
- `save_weather_to_ojr(date, weather_data)` — погода

---

## 4. СВЯЗЬ С СУЩЕСТВУЮЩИМИ ТАБЛИЦАМИ

### Что НЕ менять

| Таблица | Почему |
|---------|--------|
| `bot_memory_messages` | Исходные WhatsApp-сообщения — первичный источник |
| `bot_schedule_phases` | График производства — эталонные даты и статусы |
| `bot_building_profiles` | Профили зданий — визуальные признаки |
| `bot_poll_state` | Активные опросы — ссылка из work_log |
| `bot_calendar_events` | Календарь — напоминания |

### Что ЗАМЕНЯЕТСЯ (постепенно)

| Старая таблица | Новая таблица | Когда |
|----------------|---------------|-------|
| `bot_memory_facts` (категория `объём`) | `ojr_section3_work_log` | Сразу |
| `bot_memory_facts` (категория `персонал`) | `ojr_section1_personnel` | Сразу |
| `bot_poll_residuals` | `ojr_section3_work_log` + остаток в шаблоне | После верификации |
| Ручной учёт погоды | `ojr_weather` | Сразу |
| Разрозненные фото | `ojr_photo_log` | Сразу |

### План отказа от старых таблиц

1. **Фаза 1 (неделя 1):** Параллельная запись — данные пишутся И в `bot_memory_facts`, И в `ojr_*`
2. **Фаза 2 (неделя 2):** Верификация — сверка `ojr_*` с ЕЖО за 5+ дней
3. **Фаза 3 (неделя 3):** Переключение — `fill_ejo.py` читает из `ojr_*`, не из `bot_memory_facts`
4. **Фаза 4 (месяц 2):** Архивация `bot_memory_facts` и `bot_poll_residuals` (оставить как историю)

---

## 5. ДИАГНОСТИКА И ОТЛАДКА

### Проверка целостности

```sql
-- Сверка: объёмы в work_log vs bot_memory_facts
SELECT
    w.work_date,
    COUNT(w.id) AS in_ojr,
    (SELECT COUNT(*) FROM bot_memory_facts f
     WHERE f.fact_date = w.work_date
       AND f.source = 'qa'
       AND f.category IN ('объём','план','бетонирование','монтаж'))
    AS in_facts
FROM ojr_section3_work_log w
GROUP BY w.work_date
ORDER BY w.work_date DESC
LIMIT 7;
```

```sql
-- Пропущенные даты (нет записей в work_log)
SELECT d::date
FROM generate_series(
    (SELECT MIN(work_date) FROM ojr_section3_work_log),
    CURRENT_DATE,
    '1 day'::interval
) d
WHERE d::date NOT IN (SELECT DISTINCT work_date FROM ojr_section3_work_log)
  AND d::date NOT IN (SELECT DISTINCT fact_date FROM bot_memory_facts WHERE source='qa');
```

```sql
-- Здания без фото за последние 3 дня
SELECT DISTINCT w.building
FROM ojr_section3_work_log w
WHERE w.work_date >= CURRENT_DATE - 3
  AND w.building NOT IN (
    SELECT p.building FROM ojr_photo_log p
    WHERE p.photo_date >= CURRENT_DATE - 3
);
```

### Типовые ошибки

| Симптом | Причина | Диагностика |
|---------|---------|-------------|
| Пустой work_log | QA не сохранил факты | `SELECT * FROM bot_memory_facts WHERE fact_date=CURRENT_DATE AND source='qa'` |
| Дубликаты объёмов | Один код пришёл дважды | `SELECT vor_code, COUNT(*) FROM ojr_section3_work_log WHERE work_date=CURRENT_DATE GROUP BY vor_code HAVING COUNT(*)>1` |
| Фото без building | Нет тега в сообщении | `SELECT id, tags FROM bot_memory_messages WHERE message_type='image' AND tags->>'building' IS NULL` |
| Погода не обновилась | Cron не отработал | `SELECT weather_date FROM ojr_weather ORDER BY weather_date DESC LIMIT 1` |
| % готовности = 0 | Нет К-значений в шаблоне | Проверить `bot/templates/ЕЖО_шаблон.xlsx` колонку K |

---

## 6. ПЛАН ВНЕДРЕНИЯ

| Шаг | Действие | Ответственный | Срок |
|-----|----------|---------------|------|
| 1 | Применить `ojr_schema.sql` к evolution_db | DBA | День 0 |
| 2 | Заполнить `ojr_title_page` реальными данными | Менеджер проекта | День 0 |
| 3 | Применить `ojr_migration.sql` (перенос существующих данных) | DBA | День 1 |
| 4 | Создать `bot/ojr_sync.py` с функциями синхронизации | Разработчик | День 1-2 |
| 5 | Интегрировать вызовы `ojr_sync` в `main_waha.py` + `fill_ejo.py` | Разработчик | День 2-3 |
| 6 | Тестирование в песочнице (5 дней данных) | QA | День 3-7 |
| 7 | Переключить `fill_ejo.py` на чтение из `ojr_*` | Разработчик | День 8 |
| 8 | Мониторинг в проде (1 неделя) | Все | День 8-15 |

---

## 7. ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ

**В: Нужно ли удалять `bot_memory_facts`?**
О: НЕТ. Оставить как историю и audit trail. Переключить `fill_ejo.py` на чтение из `ojr_section3_work_log`, а `bot_memory_facts` использовать только для QA-парсинга.

**В: Что делать если `title_id` не 1?**
О: Всегда использовать `(SELECT id FROM ojr_title_page WHERE is_active = TRUE)` вместо хардкода.

**В: Как обрабатывать план (category='план') vs факт (category='объём')?**
О: Один код ВОР может иметь ДВЕ записи в один день — одну с `category='план'` и одну с `category='объём'`. UNIQUE-ключ это учитывает.

**В: Где хранить остаток (столбец U из ЕЖО)?**
О: Остаток = часть шаблона ЕЖО (столбец U). Он динамический: `U = O − P`. В БД его хранить не нужно — он пересчитывается при каждой генерации ЕЖО. Если нужен для опроса — читать из шаблона .xlsx.

**В: Как связать инцидент с конкретной работой?**
О: Пока прямой связи нет. Использовать `location` (building + описание). При необходимости добавить `work_log_id` в `ojr_incidents`.
