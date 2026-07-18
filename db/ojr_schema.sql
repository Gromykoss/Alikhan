-- ============================================================================
-- ОЖР (Общий Журнал Работ) — Database Schema
-- ГОСТ: РД-11-05-2007 / Приказ Минстроя РФ №1026/пр от 02.12.2022
-- DB:    PostgreSQL (evolution_db)
-- Проект: ТЗРК Джеруй (Alikhan WhatsApp Bot)
-- ============================================================================

-- 1. ENUM-типы
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE ojr_supervision_status AS ENUM ('planned', 'conducted', 'violations_found', 'compliant');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ojr_inspection_result AS ENUM ('no_violations', 'violations_found', 'order_issued', 'resolved');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ojr_weather_phenomenon AS ENUM (
        'clear', 'cloudy', 'overcast', 'rain', 'snow', 'hail', 'fog', 'mixed'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- 2. ТИТУЛЬНЫЙ ЛИСТ
-- ============================================================================
-- Хранит метаданные строительного объекта — «шапка» ОЖР
CREATE TABLE IF NOT EXISTS ojr_title_page (
    id                  SERIAL PRIMARY KEY,
    -- Заказчик (ОсОО «Альянс-Алтын»)
    customer_name       TEXT NOT NULL,
    customer_address    TEXT,
    customer_ogrn       TEXT,                          -- ОГРН / ИНН
    customer_phone      TEXT,
    customer_email      TEXT,
    -- Застройщик (Технический заказчик)
    developer_name      TEXT,
    developer_address   TEXT,
    developer_ogrn      TEXT,
    -- Лицо, осуществляющее строительство (Подрядчик: ОсОО «АйБиКон»)
    contractor_name     TEXT NOT NULL,
    contractor_address  TEXT,
    contractor_ogrn     TEXT,
    contractor_phone    TEXT,
    -- Проектировщик (Генпроектировщик)
    designer_name       TEXT,
    designer_address    TEXT,
    designer_ogrn       TEXT,
    designer_sro        TEXT,                          -- № СРО
    -- Объект
    object_name         TEXT NOT NULL,                 -- «ТЗРК Джеруй»
    object_address      TEXT,
    object_type         TEXT,                          -- Тип: «новое строительство», «реконструкция», «кап.ремонт»
    -- Договор
    contract_number     TEXT,                          -- Номер договора подряда
    contract_date       DATE,
    -- Разрешительная документация
    construction_permit_number  TEXT,                  -- Разрешение на строительство
    construction_permit_date    DATE,
    construction_permit_issuer  TEXT,                  -- Кем выдано
    -- Сроки
    work_start_date     DATE,                          -- Начало работ
    work_end_date       DATE,                          -- Окончание работ (план)
    work_end_actual     DATE,                          -- Окончание работ (факт)
    -- Госстройнадзор
    gsn_body            TEXT,                          -- Орган госстройнадзора
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE,          -- Только один активный титул
    CONSTRAINT uq_ojr_title_active UNIQUE (is_active)  -- Не более 1 активного
        DEFERRABLE INITIALLY DEFERRED
);

COMMENT ON TABLE ojr_title_page IS 'Титульный лист ОЖР — заказчик, подрядчик, проектировщик, объект, договор, разрешения';


-- 3. РАЗДЕЛ 1: ИТР-ПЕРСОНАЛ
-- ============================================================================
-- Список инженерно-технического персонала всех организаций-участников
CREATE TABLE IF NOT EXISTS ojr_section1_personnel (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Организация
    organization_type   TEXT NOT NULL,                 -- 'customer' | 'developer' | 'contractor' | 'designer' | 'subcontractor'
    organization_name   TEXT NOT NULL,                 -- Наименование организации
    -- Сотрудник
    full_name           TEXT NOT NULL,                 -- Фамилия И.О.
    position            TEXT NOT NULL,                 -- Должность
    phone               TEXT,
    -- Период работы
    start_date          DATE NOT NULL,
    end_date            DATE,                          -- NULL = по настоящее время
    -- Основание
    order_number        TEXT,                          -- № приказа о назначении
    order_date          DATE,
    -- Статус
    is_responsible      BOOLEAN DEFAULT FALSE,         -- Ответственный производитель работ
    notes               TEXT,
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE,
    sync_source         TEXT                           -- источник данных: 'qa', 'manual', 'timesheet'
);

CREATE INDEX IF NOT EXISTS idx_ojr_personnel_title     ON ojr_section1_personnel(title_id);
CREATE INDEX IF NOT EXISTS idx_ojr_personnel_org       ON ojr_section1_personnel(organization_name);
CREATE INDEX IF NOT EXISTS idx_ojr_personnel_active    ON ojr_section1_personnel(is_active) WHERE is_active;

COMMENT ON TABLE ojr_section1_personnel IS 'Раздел 1 ОЖР — ИТР-персонал всех организаций (подрядчики, заказчик, проектировщик)';


-- 4. РАЗДЕЛ 2: АВТОРСКИЙ НАДЗОР
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_section2_design_supervision (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Организация
    organization_name   TEXT NOT NULL,                 -- Проектная организация
    -- Ответственный
    responsible_name    TEXT NOT NULL,                 -- ФИО ответственного
    responsible_position TEXT,
    certificate_number  TEXT,                          -- № квалификационного сертификата / приказа
    certificate_date    DATE,
    -- Заместители (JSON массив — на случай нескольких заместителей)
    deputies            JSONB DEFAULT '[]',            -- [{"name":"...", "position":"...", "order":"..."}]
    -- События надзора (связь с таблицей записей)
    notes               TEXT,
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_ojr_design_sv_title     ON ojr_section2_design_supervision(title_id);

COMMENT ON TABLE ojr_section2_design_supervision IS 'Раздел 2 ОЖР — Авторский надзор (ответственный, сертификаты, заместители)';

-- Журнал посещений авторского надзора
CREATE TABLE IF NOT EXISTS ojr_section2_visits (
    id                  SERIAL PRIMARY KEY,
    supervision_id      INTEGER NOT NULL REFERENCES ojr_section2_design_supervision(id) ON DELETE CASCADE,
    visit_date          DATE NOT NULL,
    inspector_name      TEXT NOT NULL,                 -- Кто проводил надзор
    findings            TEXT,                           -- Выявленные замечания
    recommendations     TEXT,                           -- Рекомендации / предписания
    resolution_date     DATE,                           -- Срок устранения
    is_resolved         BOOLEAN DEFAULT FALSE,
    act_number          TEXT,                           -- № акта/записи
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_design_visits_sv   ON ojr_section2_visits(supervision_id);
CREATE INDEX IF NOT EXISTS idx_ojr_design_visits_date  ON ojr_section2_visits(visit_date);

COMMENT ON TABLE ojr_section2_visits IS 'Журнал посещений авторского надзора — записи о выявленных замечаниях';


-- 5. РАЗДЕЛ 3: ВЫПОЛНЕНИЕ РАБОТ
-- ============================================================================
-- Ежедневный журнал выполнения строительно-монтажных работ
CREATE TABLE IF NOT EXISTS ojr_section3_work_log (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Дата
    work_date           DATE NOT NULL,
    -- Код и описание
    vor_code            TEXT NOT NULL,                 -- Код ВОР (напр. «3.3.2»)
    work_name           TEXT,                           -- Наименование работ по ВОР
    -- Здание / сооружение
    building            TEXT NOT NULL,                 -- «Общежитие», «АБК», «Галерея», «НВ», «НК», «НТ»
    -- Объём
    volume              NUMERIC(12,3),                 -- Объём работ за день
    unit                TEXT DEFAULT 'м³',              -- Единица измерения
    -- Подрядчик
    contractor          TEXT,                           -- Организация-исполнитель (субподрядчик)
    -- Условия
    work_conditions     TEXT,                           -- Условия производства работ
    shift               INTEGER DEFAULT 1,             -- Номер смены
    -- Связь с графиком
    schedule_phase_id   INTEGER,                        -- → bot_schedule_phases.id
    -- Статус / категория
    category            TEXT DEFAULT 'объём',           -- 'объём' | 'план' | 'корректировка'
    -- Связь с QA-фактами
    source_fact_id      INTEGER,                        -- → bot_memory_facts.id (если из QA)
    source_poll_id      INTEGER,                        -- → bot_poll_state.id
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    created_by          TEXT,                           -- 'qa', 'manual', 'ejo_extraction', 'bot'

    CONSTRAINT uq_ojr_work_log UNIQUE (work_date, vor_code, building, category)
);

CREATE INDEX IF NOT EXISTS idx_ojr_work_log_date       ON ojr_section3_work_log(work_date);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_code        ON ojr_section3_work_log(vor_code);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_building    ON ojr_section3_work_log(building);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_contractor  ON ojr_section3_work_log(contractor);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_schedule    ON ojr_section3_work_log(schedule_phase_id);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_fact        ON ojr_section3_work_log(source_fact_id);
CREATE INDEX IF NOT EXISTS idx_ojr_work_log_poll        ON ojr_section3_work_log(source_poll_id);

COMMENT ON TABLE ojr_section3_work_log IS 'Раздел 3 ОЖР — Выполнение работ (ежедневный журнал, код ВОР, объём, подрядчик, здание)';


-- 6. РАЗДЕЛ 4: СТРОИТЕЛЬНЫЙ КОНТРОЛЬ
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_section4_construction_control (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Организация, осуществляющая строительный контроль
    organization_name   TEXT NOT NULL,
    -- Ответственный
    responsible_name    TEXT NOT NULL,
    responsible_position TEXT,
    certificate_number  TEXT,                          -- № сертификата / приказа
    certificate_date    DATE,
    certificate_valid_until DATE,
    -- Контакты
    phone               TEXT,
    email               TEXT,
    -- Приказ о назначении
    order_number        TEXT,
    order_date          DATE,
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_ojr_ccontrol_title     ON ojr_section4_construction_control(title_id);

COMMENT ON TABLE ojr_section4_construction_control IS 'Раздел 4 ОЖР — Строительный контроль (ответственные, сертификаты)';

-- Записи строительного контроля (акты, проверки)
CREATE TABLE IF NOT EXISTS ojr_section4_checks (
    id                  SERIAL PRIMARY KEY,
    control_id          INTEGER NOT NULL REFERENCES ojr_section4_construction_control(id) ON DELETE CASCADE,
    check_date          DATE NOT NULL,
    check_type          TEXT,                          -- 'плановый', 'внеплановый', 'операционный'
    work_code           TEXT,                          -- Проверяемый вид работ (VOR-код)
    building            TEXT,
    description         TEXT,                          -- Описание проверки
    violations          TEXT,                          -- Выявленные нарушения
    required_actions    TEXT,                          -- Меры по устранению
    deadline            DATE,                          -- Срок устранения
    is_resolved         BOOLEAN DEFAULT FALSE,
    resolution_date     DATE,
    act_number          TEXT,                          -- Номер акта
    status              ojr_supervision_status DEFAULT 'planned',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_ccontrol_checks_cid ON ojr_section4_checks(control_id);
CREATE INDEX IF NOT EXISTS idx_ojr_ccontrol_checks_date ON ojr_section4_checks(check_date);

COMMENT ON TABLE ojr_section4_checks IS 'Записи строительного контроля — акты проверок, нарушения, предписания';


-- 7. РАЗДЕЛ 5: ИСПОЛНИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_section5_asbuilt_docs (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Тип документа
    doc_type            TEXT NOT NULL,                 -- 'акт', 'протокол', 'сертификат', 'журнал', 'схема', 'паспорт', 'иное'
    doc_subtype         TEXT,                          -- Уточнение: 'акт_освидетельствования_скрытых_работ', 'акт_приёмки', 'протокол_испытаний', ...
    -- Реквизиты
    doc_number          TEXT NOT NULL,
    doc_date            DATE NOT NULL,
    -- Содержание
    doc_name            TEXT,                          -- Наименование документа
    work_description    TEXT,                          -- Какие работы / конструкции
    vor_code            TEXT,                          -- Связанный код ВОР
    building            TEXT,
    contractor          TEXT,
    -- Подписи
    signed_by           JSONB DEFAULT '[]',            -- [{"name":"...", "org":"...", "role":"...", "signed":true}]
    -- Связь с файлами
    file_path           TEXT,                          -- Путь к файлу на диске / в облаке
    file_message_id     BIGINT,                        -- → bot_memory_messages.id (если документ пришёл в WhatsApp)
    -- Статус
    status              TEXT DEFAULT 'draft',          -- 'draft', 'signed', 'registered', 'archived'
    notes               TEXT,
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_asbuilt_title      ON ojr_section5_asbuilt_docs(title_id);
CREATE INDEX IF NOT EXISTS idx_ojr_asbuilt_date        ON ojr_section5_asbuilt_docs(doc_date);
CREATE INDEX IF NOT EXISTS idx_ojr_asbuilt_type        ON ojr_section5_asbuilt_docs(doc_type);
CREATE INDEX IF NOT EXISTS idx_ojr_asbuilt_code        ON ojr_section5_asbuilt_docs(vor_code);
CREATE INDEX IF NOT EXISTS idx_ojr_asbuilt_building    ON ojr_section5_asbuilt_docs(building);

COMMENT ON TABLE ojr_section5_asbuilt_docs IS 'Раздел 5 ОЖР — Исполнительная документация (акты, протоколы, сертификаты, журналы)';


-- 8. РАЗДЕЛ 6: ГОССТРОЙНАДЗОР
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_section6_gosstroynadzor (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Проверяющий орган
    authority_name      TEXT NOT NULL,                 -- Наименование органа ГСН
    inspector_name      TEXT,                          -- ФИО инспектора
    inspector_position  TEXT,
    -- Проверка
    inspection_date     DATE NOT NULL,
    inspection_type     TEXT DEFAULT 'выездная',       -- 'выездная', 'документарная', 'внеплановая'
    inspection_subject  TEXT,                          -- Предмет проверки
    -- Результаты
    result              ojr_inspection_result DEFAULT 'no_violations',
    violations_found    TEXT,                          -- Описание выявленных нарушений
    -- Предписание
    order_number        TEXT,                          -- Номер предписания
    order_date          DATE,
    order_deadline      DATE,                          -- Срок исполнения
    order_content       TEXT,                          -- Содержание предписания
    is_order_executed   BOOLEAN DEFAULT FALSE,
    order_execution_date DATE,
    -- Протокол / штраф
    protocol_number     TEXT,
    protocol_date       DATE,
    fine_amount         NUMERIC(12,2),                 -- Сумма штрафа
    -- Акт
    act_number          TEXT,                          -- Номер акта проверки
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_gsn_title          ON ojr_section6_gosstroynadzor(title_id);
CREATE INDEX IF NOT EXISTS idx_ojr_gsn_date            ON ojr_section6_gosstroynadzor(inspection_date);
CREATE INDEX IF NOT EXISTS idx_ojr_gsn_authority       ON ojr_section6_gosstroynadzor(authority_name);

COMMENT ON TABLE ojr_section6_gosstroynadzor IS 'Раздел 6 ОЖР — Госстройнадзор (проверки, предписания, протоколы)';


-- 9. ПОГОДА (ежедневно)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_weather (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    weather_date        DATE NOT NULL,
    -- Температура
    temp_max            NUMERIC(4,1),                  -- °C, максимум за день
    temp_min            NUMERIC(4,1),                  -- °C, минимум за день
    temp_avg            NUMERIC(4,1),                  -- °C, средняя
    temp_morning        NUMERIC(4,1),                  -- °C, утро (08:00)
    -- Осадки
    precipitation_mm    NUMERIC(5,1),                   -- мм
    precipitation_type  TEXT,                          -- 'none', 'rain', 'snow', 'hail'
    -- Ветер
    wind_speed          NUMERIC(4,1),                  -- м/с
    wind_direction      TEXT,                          -- Направление: 'С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'
    wind_gust           NUMERIC(4,1),                  -- Порывы, м/с
    -- Явления
    phenomenon          ojr_weather_phenomenon DEFAULT 'clear',
    cloud_cover_pct     INTEGER CHECK (cloud_cover_pct BETWEEN 0 AND 100),
    humidity_pct        INTEGER CHECK (humidity_pct BETWEEN 0 AND 100),
    pressure_hpa        NUMERIC(5,0),                   -- Атмосферное давление, гПа
    -- Источник
    source              TEXT DEFAULT 'open_meteo',     -- 'open_meteo', 'manual', 'gismeteo'
    raw_response        JSONB,                          -- Сырой ответ API
    -- Является ли день нерабочим по погодным условиям
    is_work_stopped     BOOLEAN DEFAULT FALSE,
    work_stop_reason    TEXT,                          -- Причина остановки
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_ojr_weather_date UNIQUE (weather_date)
);

COMMENT ON TABLE ojr_weather IS 'Погода — ежедневная метеосводка с привязкой к дате (Open-Meteo API)';


-- 10. ФОТО-ФИКСАЦИЯ
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_photo_log (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    -- Привязка к работе
    work_log_id         INTEGER,                        -- → ojr_section3_work_log.id (привязка к конкретной работе)
    photo_date          DATE NOT NULL,
    building            TEXT NOT NULL,                 -- «Общежитие», «АБК», «Галерея», «Общие планы»
    -- Файл
    file_path           TEXT,                          -- Путь к файлу на диске
    file_message_id     BIGINT,                        -- → bot_memory_messages.id (WhatsApp источник)
    file_name           TEXT,
    file_size_bytes     BIGINT,
    mime_type           TEXT DEFAULT 'image/jpeg',
    -- Описание
    caption             TEXT,                          -- Подпись к фото
    ai_description      TEXT,                          -- Авто-описание через Grok Vision
    description_json    JSONB,                         -- Структурированное описание
    -- Сетка ЕЖО
    ejo_sheet           TEXT DEFAULT 'Ежедневный отчет', -- Лист в ЕЖО
    ejo_column          INTEGER,                       -- Колонка в ЕЖО (3, 5, 10, 14, 17)
    ejo_photo_index     INTEGER,                       -- Индекс фото в здании (1-5)
    -- Технические поля
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    uploaded_by         TEXT                           -- 'production_listener', 'sandbox', 'manual'
);

CREATE INDEX IF NOT EXISTS idx_ojr_photo_date          ON ojr_photo_log(photo_date);
CREATE INDEX IF NOT EXISTS idx_ojr_photo_building      ON ojr_photo_log(building);
CREATE INDEX IF NOT EXISTS idx_ojr_photo_worklog       ON ojr_photo_log(work_log_id);
CREATE INDEX IF NOT EXISTS idx_ojr_photo_msg           ON ojr_photo_log(file_message_id);

COMMENT ON TABLE ojr_photo_log IS 'Фото-фиксация строительной площадки — привязка к датам, работам, зданиям';


-- 11. СВОДНЫЕ / КУМУЛЯТИВНЫЕ ПОКАЗАТЕЛИ
-- ============================================================================
-- Предрасчитанные агрегаты для быстрой отчётности
CREATE TABLE IF NOT EXISTS ojr_daily_summary (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    summary_date        DATE NOT NULL,

    -- Объёмы
    total_volume_today  NUMERIC(14,3),                 -- Всего за день (м³)
    total_volume_month  NUMERIC(14,3),                 -- С начала месяца
    total_volume_total  NUMERIC(14,3),                 -- С начала строительства

    -- Персонал
    total_workers       INTEGER,                       -- Всего рабочих
    total_itr           INTEGER,                       -- ИТР
    total_equipment     INTEGER,                       -- Единиц техники

    -- Инциденты
    incidents_count     INTEGER DEFAULT 0,
    tb_violations       INTEGER DEFAULT 0,

    -- Готовность
    completion_pct      NUMERIC(5,2),                  -- % общей готовности (формула calc_completion_pct)

    -- Метаданные
    ejo_file_path       TEXT,                          -- Путь к сгенерированному .xlsx
    ejo_version         INTEGER DEFAULT 1,
    is_corrected        BOOLEAN DEFAULT FALSE,

    created_at          TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_ojr_summary_date UNIQUE (summary_date)
);

CREATE INDEX IF NOT EXISTS idx_ojr_summary_date       ON ojr_daily_summary(summary_date);

COMMENT ON TABLE ojr_daily_summary IS 'Сводные дневные показатели: объёмы, персонал, готовность — быстрый доступ без пересчёта';


-- 12. МАТЕРИАЛЫ
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_materials (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    material_date       DATE NOT NULL,
    -- Материал
    material_name       TEXT NOT NULL,
    material_type       TEXT,                          -- 'бетон', 'арматура', 'кирпич', 'металл', и т.д.
    quantity            NUMERIC(12,3),
    unit                TEXT DEFAULT 'м³',
    -- Поставщик
    supplier            TEXT,
    -- Сертификат / паспорт
    certificate_number  TEXT,
    certificate_date    DATE,
    -- Привязка
    building            TEXT,
    vor_code            TEXT,
    -- Статус
    status              TEXT DEFAULT 'received',       -- 'ordered', 'shipped', 'received', 'used'
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_materials_date     ON ojr_materials(material_date);
CREATE INDEX IF NOT EXISTS idx_ojr_materials_building ON ojr_materials(building);
CREATE INDEX IF NOT EXISTS idx_ojr_materials_type     ON ojr_materials(material_type);

COMMENT ON TABLE ojr_materials IS 'Журнал поступления материалов — поставки, сертификаты, остатки';


-- 13. ИНЦИДЕНТЫ И ТБ
-- ============================================================================
CREATE TABLE IF NOT EXISTS ojr_incidents (
    id                  SERIAL PRIMARY KEY,
    title_id            INTEGER NOT NULL REFERENCES ojr_title_page(id) ON DELETE CASCADE,
    incident_date       DATE NOT NULL,
    incident_type       TEXT NOT NULL,                 -- 'accident', 'tb_violation', 'equipment_failure', 'weather_stop', 'other'
    severity            TEXT DEFAULT 'minor',          -- 'minor', 'major', 'critical', 'fatal'
    description         TEXT NOT NULL,
    location            TEXT,                          -- Место (building, участок)
    affected_persons    INTEGER DEFAULT 0,
    downtime_hours      NUMERIC(5,1),                   -- Время простоя
    actions_taken       TEXT,                          -- Принятые меры
    reported_by         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ojr_incidents_date     ON ojr_incidents(incident_date);
CREATE INDEX IF NOT EXISTS idx_ojr_incidents_type     ON ojr_incidents(incident_type);

COMMENT ON TABLE ojr_incidents IS 'Инциденты на площадке: происшествия, нарушения ТБ, отказы техники, погодные остановки';


-- ============================================================================
-- ВНЕШНИЕ КЛЮЧИ К СУЩЕСТВУЮЩИМ ТАБЛИЦАМ
-- ============================================================================

-- ojr_section3_work_log → bot_schedule_phases
DO $$ BEGIN
    ALTER TABLE ojr_section3_work_log
        ADD CONSTRAINT fk_worklog_schedule
        FOREIGN KEY (schedule_phase_id) REFERENCES bot_schedule_phases(id)
        ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ojr_section3_work_log → bot_memory_facts
DO $$ BEGIN
    ALTER TABLE ojr_section3_work_log
        ADD CONSTRAINT fk_worklog_fact
        FOREIGN KEY (source_fact_id) REFERENCES bot_memory_facts(id)
        ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ojr_section3_work_log → bot_poll_state
DO $$ BEGIN
    ALTER TABLE ojr_section3_work_log
        ADD CONSTRAINT fk_worklog_poll
        FOREIGN KEY (source_poll_id) REFERENCES bot_poll_state(id)
        ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ojr_photo_log → bot_memory_messages
DO $$ BEGIN
    ALTER TABLE ojr_photo_log
        ADD CONSTRAINT fk_photo_message
        FOREIGN KEY (file_message_id) REFERENCES bot_memory_messages(id)
        ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ojr_section5_asbuilt_docs → bot_memory_messages
DO $$ BEGIN
    ALTER TABLE ojr_section5_asbuilt_docs
        ADD CONSTRAINT fk_asbuilt_message
        FOREIGN KEY (file_message_id) REFERENCES bot_memory_messages(id)
        ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ojr_daily_summary → ojr_title_page (already via FK on title_id)


-- ============================================================================
-- ТРИГГЕР ДЛЯ АВТО-ОБНОВЛЕНИЯ updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION ojr_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Применяем триггер ко всем таблицам с updated_at
DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOR tbl IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tablename LIKE 'ojr_%'
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = tbl AND column_name = 'updated_at'
        ) THEN
            EXECUTE format('
                DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I;
                CREATE TRIGGER trg_%s_updated_at
                    BEFORE UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION ojr_update_timestamp();
            ', tbl, tbl, tbl, tbl);
        END IF;
    END LOOP;
END $$;


-- ============================================================================
-- ПРЕДСТАВЛЕНИЯ (VIEWS) ДЛЯ УДОБНОЙ ВЫБОРКИ
-- ============================================================================

-- 1. Сводка работ за день
CREATE OR REPLACE VIEW ojr_v_daily_works AS
SELECT
    w.work_date,
    w.building,
    w.vor_code,
    w.work_name,
    w.volume,
    w.unit,
    w.contractor,
    w.category,
    sp.phase_name AS schedule_phase,
    sp.status    AS schedule_status
FROM ojr_section3_work_log w
LEFT JOIN bot_schedule_phases sp ON w.schedule_phase_id = sp.id
ORDER BY w.work_date DESC, w.building, w.vor_code;

-- 2. Сводка персонала (активные)
CREATE OR REPLACE VIEW ojr_v_active_personnel AS
SELECT
    organization_name,
    organization_type,
    full_name,
    position,
    start_date,
    end_date,
    is_responsible
FROM ojr_section1_personnel
WHERE is_active
ORDER BY organization_type, organization_name, full_name;

-- 3. Незакрытые предписания ГСН
CREATE OR REPLACE VIEW ojr_v_open_gsn_orders AS
SELECT
    authority_name,
    inspection_date,
    order_number,
    order_deadline,
    order_content,
    order_deadline - CURRENT_DATE AS days_left
FROM ojr_section6_gosstroynadzor
WHERE is_order_executed = FALSE
  AND order_deadline IS NOT NULL
ORDER BY order_deadline;

-- 4. Незакрытые замечания строительного контроля
CREATE OR REPLACE VIEW ojr_v_open_cchecks AS
SELECT
    cc.organization_name,
    cc.responsible_name,
    ch.check_date,
    ch.violations,
    ch.required_actions,
    ch.deadline,
    ch.deadline - CURRENT_DATE AS days_left
FROM ojr_section4_checks ch
JOIN ojr_section4_construction_control cc ON ch.control_id = cc.id
WHERE ch.is_resolved = FALSE
ORDER BY ch.deadline;

-- 5. Погода за последние 30 дней
CREATE OR REPLACE VIEW ojr_v_recent_weather AS
SELECT
    weather_date,
    temp_max,
    temp_min,
    temp_avg,
    precipitation_mm,
    wind_speed,
    phenomenon,
    is_work_stopped
FROM ojr_weather
WHERE weather_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY weather_date DESC;


-- ============================================================================
-- PRINT SCHEMA SUMMARY
-- ============================================================================
DO $$
DECLARE
    r RECORD;
BEGIN
    RAISE NOTICE '========== OJR SCHEMA CREATED ==========';
    FOR r IN
        SELECT tablename, 
               (SELECT COUNT(*) FROM information_schema.columns c 
                WHERE c.table_schema='public' AND c.table_name=t.tablename) AS cols
        FROM pg_tables t
        WHERE schemaname = 'public' AND tablename LIKE 'ojr_%'
        ORDER BY tablename
    LOOP
        RAISE NOTICE '  Table: % (% columns)', r.tablename, r.cols;
    END LOOP;
    RAISE NOTICE '==========================================';
END $$;
