-- ============================================================================
-- ОЖР — Migration Script (bot_memory_facts + bot_poll_residuals → ojr_*)
-- ============================================================================
-- Версия: 1.0.0
-- Дата: 2026-07-18
-- Назначение: перенос данных из текущих таблиц в новую структурированную схему ОЖР
-- Стратегия: неразрушающая — старые таблицы НЕ удаляются, только создаются новые + миграция
-- ============================================================================

BEGIN;

-- =====================================================================
-- ШАГ 0: Проверка окружения
-- =====================================================================
DO $$
DECLARE
    v_facts_count   INTEGER;
    v_residuals_count INTEGER;
    v_title_count   INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_facts_count FROM bot_memory_facts;
    SELECT COUNT(*) INTO v_residuals_count FROM bot_poll_residuals;
    SELECT COUNT(*) INTO v_title_count FROM ojr_title_page;

    RAISE NOTICE '=== MIGRATION PRE-CHECK ===';
    RAISE NOTICE 'bot_memory_facts:     % rows', v_facts_count;
    RAISE NOTICE 'bot_poll_residuals:   % rows', v_residuals_count;
    RAISE NOTICE 'ojr_title_page:       % rows (existing)', v_title_count;
    RAISE NOTICE '============================';
END $$;


-- =====================================================================
-- ШАГ 1: Создание титульного листа (если нет)
-- =====================================================================
INSERT INTO ojr_title_page (
    customer_name,     contractor_name,    object_name,
    object_type,       work_start_date,    is_active
)
SELECT
    'ОсОО «Альянс-Алтын»',               -- Заказчик (известно из проекта)
    'ОсОО «АйБиКон»',                     -- Подрядчик
    'ТЗРК Джеруй',                        -- Объект
    'новое строительство',
    MIN(start_date),                       -- Начало = min из schedule_phases
    TRUE
FROM bot_schedule_phases
WHERE NOT EXISTS (SELECT 1 FROM ojr_title_page WHERE is_active = TRUE)
  AND start_date IS NOT NULL;

-- Выводим id созданного титула
DO $$
DECLARE
    v_tid INTEGER;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN
        RAISE NOTICE '⚠️ Титульный лист НЕ создан — нужны данные в bot_schedule_phases';
    ELSE
        RAISE NOTICE '✅ Титульный лист создан: id=%', v_tid;
    END IF;
END $$;


-- =====================================================================
-- ШАГ 2: Миграция персонала из bot_memory_facts (Раздел 1)
-- =====================================================================
-- Извлекаем факты с категорией «персонал» в ojr_section1_personnel
DO $$
DECLARE
    v_tid       INTEGER;
    v_fact      RECORD;
    v_org       TEXT;
    v_name      TEXT;
    v_role      TEXT;
    v_count     INTEGER;
    v_inserted  INTEGER := 0;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN RETURN; END IF;

    FOR v_fact IN
        SELECT DISTINCT fact, fact_date, building
        FROM bot_memory_facts
        WHERE category = 'персонал'
          AND source = 'qa'
        ORDER BY fact_date DESC
    LOOP
        -- Парсинг: формат «Организация Роль N» или «Имя ИТР N, рабочих M»
        v_org := CASE
            WHEN v_fact.fact ILIKE '%айбикон%' THEN 'ОсОО «АйБиКон»'
            WHEN v_fact.fact ILIKE '%атантай%' THEN 'Атантай'
            WHEN v_fact.fact ILIKE '%майкадам%' THEN 'Майкадам'
            WHEN v_fact.fact ILIKE '%наватек%' THEN 'Наватек'
            ELSE 'Субподрядчик'
        END;

        v_name := COALESCE(
            substring(v_fact.fact FROM '^([А-Я][а-я]+)'),
            'Не указано'
        );

        v_role := CASE
            WHEN v_fact.fact ILIKE '%итр%' THEN 'ИТР'
            WHEN v_fact.fact ILIKE '%рабоч%' THEN 'Рабочий'
            WHEN v_fact.fact ILIKE '%водител%' THEN 'Водитель'
            WHEN v_fact.fact ILIKE '%прораб%' THEN 'Прораб'
            WHEN v_fact.fact ILIKE '%геодезист%' THEN 'Геодезист'
            WHEN v_fact.fact ILIKE '%пто%' THEN 'ПТО'
            WHEN v_fact.fact ILIKE '%тб%' THEN 'Инженер ТБ'
            WHEN v_fact.fact ILIKE '%электрик%' THEN 'Электрик'
            ELSE 'Сотрудник'
        END;

        INSERT INTO ojr_section1_personnel (
            title_id, organization_type, organization_name,
            full_name, position,
            start_date, sync_source, is_active
        ) VALUES (
            v_tid,
            CASE WHEN v_org = 'ОсОО «АйБиКон»' THEN 'contractor' ELSE 'subcontractor' END,
            v_org, v_name, v_role,
            v_fact.fact_date, 'qa', TRUE
        ) ON CONFLICT DO NOTHING;

        v_inserted := v_inserted + 1;
    END LOOP;

    RAISE NOTICE '✅ Раздел 1 (Персонал): перенесено % записей из bot_memory_facts', v_inserted;
END $$;


-- =====================================================================
-- ШАГ 3: Миграция выполнения работ — VOR-коды с объёмами (Раздел 3)
-- =====================================================================
DO $$
DECLARE
    v_tid       INTEGER;
    v_fact      RECORD;
    v_code      TEXT;
    v_volume    NUMERIC;
    v_unit      TEXT;
    v_bld       TEXT;
    v_cat       TEXT;
    v_inserted  INTEGER := 0;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN RETURN; END IF;

    FOR v_fact IN
        SELECT id, fact, category, building, fact_date
        FROM bot_memory_facts
        WHERE (category IN ('объём', 'бетонирование', 'монтаж', 'земляные работы', 'план')
               OR fact ~ '[0-9]+\.[0-9]+\.[0-9]+')
          AND source = 'qa'
        ORDER BY fact_date
    LOOP
        -- Извлекаем код ВОР
        v_code := substring(v_fact.fact FROM '([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?)');

        IF v_code IS NULL THEN CONTINUE; END IF;

        -- Извлекаем объём (русский разделитель ',' → '.')
        BEGIN
            v_volume := REPLACE(substring(v_fact.fact FROM '=\s*([0-9]+[.,]?[0-9]*)'), ',', '.')::NUMERIC;
        EXCEPTION WHEN OTHERS THEN
            v_volume := NULL;
        END;

        -- Единица измерения
        v_unit := CASE
            WHEN v_fact.fact ILIKE '%м³%' OR v_fact.fact ILIKE '%м3%' THEN 'м³'
            WHEN v_fact.fact ILIKE '%м²%' OR v_fact.fact ILIKE '%м2%' THEN 'м²'
            WHEN v_fact.fact ILIKE '%пог\.м%' OR v_fact.fact ILIKE '%п\.м%' THEN 'пог.м'
            WHEN v_fact.fact ILIKE '%кг%' THEN 'кг'
            WHEN v_fact.fact ILIKE '%т%' THEN 'т'
            WHEN v_fact.fact ILIKE '%шт%' THEN 'шт'
            ELSE 'м³'
        END;

        -- Здание
        v_bld := COALESCE(
            NULLIF(v_fact.building, ''),
            CASE
                WHEN v_fact.fact ILIKE '%общежит%' THEN 'Общежитие'
                WHEN v_fact.fact ILIKE '%абк%' THEN 'АБК'
                WHEN v_fact.fact ILIKE '%галере%' THEN 'Галерея'
                WHEN v_fact.fact ILIKE '%нв%' THEN 'НВ'
                WHEN v_fact.fact ILIKE '%нк%' THEN 'НК'
                WHEN v_fact.fact ILIKE '%нт%' THEN 'НТ'
                ELSE 'Общее'
            END
        );

        -- Категория
        v_cat := CASE
            WHEN v_fact.fact ILIKE '%план%' OR v_fact.category = 'план' THEN 'план'
            ELSE 'объём'
        END;

        INSERT INTO ojr_section3_work_log (
            title_id, work_date, vor_code, building,
            volume, unit, category, contractor,
            source_fact_id, created_by
        ) VALUES (
            v_tid, v_fact.fact_date, v_code, v_bld,
            v_volume, v_unit, v_cat,
            v_bld, v_fact.id, 'qa'
        ) ON CONFLICT (work_date, vor_code, building, category) DO UPDATE SET
            volume = EXCLUDED.volume,
            source_fact_id = COALESCE(ojr_section3_work_log.source_fact_id, EXCLUDED.source_fact_id),
            updated_at = NOW();

        v_inserted := v_inserted + 1;
    END LOOP;

    RAISE NOTICE '✅ Раздел 3 (Работы): перенесено % записей из bot_memory_facts', v_inserted;
END $$;


-- =====================================================================
-- ШАГ 4: Миграция остатков из bot_poll_residuals → work_log (Раздел 3)
-- =====================================================================
DO $$
DECLARE
    v_tid       INTEGER;
    v_r         RECORD;
    v_inserted  INTEGER := 0;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN RETURN; END IF;

    FOR v_r IN
        SELECT r.code, r.building, r.name, r.unit,
               r.residual_volume, r.actual_today, r.plan_volume,
               s.poll_date
        FROM bot_poll_residuals r
        JOIN bot_poll_state s ON r.poll_id = s.id
        WHERE r.code IS NOT NULL
        ORDER BY s.poll_date
    LOOP
        -- Остаток → запись в work_log (если сегодня был факт)
        IF v_r.actual_today IS NOT NULL AND v_r.actual_today > 0 THEN
            INSERT INTO ojr_section3_work_log (
                title_id, work_date, vor_code, building,
                volume, unit, category
            ) VALUES (
                v_tid, v_r.poll_date, v_r.code,
                COALESCE(v_r.building, 'Общее'),
                v_r.actual_today,
                COALESCE(v_r.unit, 'м³'),
                'объём'
            ) ON CONFLICT (work_date, vor_code, building, category) DO UPDATE SET
                volume = EXCLUDED.volume,
                updated_at = NOW();

            v_inserted := v_inserted + 1;
        END IF;
    END LOOP;

    RAISE NOTICE '✅ Раздел 3 (из остатков): перенесено % записей из bot_poll_residuals', v_inserted;
END $$;


-- =====================================================================
-- ШАГ 5: Миграция фото из bot_memory_messages (Фото-фиксация)
-- =====================================================================
DO $$
DECLARE
    v_tid       INTEGER;
    v_msg       RECORD;
    v_bld       TEXT;
    v_inserted  INTEGER := 0;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN RETURN; END IF;

    FOR v_msg IN
        SELECT id, tags, created_at, file_name
        FROM bot_memory_messages
        WHERE message_type = 'image'
          AND tags IS NOT NULL
        ORDER BY created_at
    LOOP
        -- Извлекаем building из JSONB-тегов
        v_bld := COALESCE(
            v_msg.tags->>'building',
            'Общие планы'
        );

        -- Нормализуем «без тег» → «Общие планы»
        IF v_bld IN ('без тег', 'без тега', 'не указано') THEN
            v_bld := 'Общие планы';
        END IF;

        INSERT INTO ojr_photo_log (
            title_id, photo_date, building,
            file_message_id, file_name,
            caption, ai_description,
            uploaded_by
        ) VALUES (
            v_tid,
            v_msg.created_at::DATE,
            v_bld,
            v_msg.id, v_msg.file_name,
            v_msg.tags->>'caption',
            CASE WHEN v_msg.tags ? 'description'
                THEN v_msg.tags->>'description'
                ELSE NULL
            END,
            CASE WHEN v_msg.tags->>'source' = 'production_listener'
                THEN 'production_listener'
                ELSE 'sandbox'
            END
        ) ON CONFLICT DO NOTHING;

        v_inserted := v_inserted + 1;
    END LOOP;

    RAISE NOTICE '✅ Фото-фиксация: перенесено % записей из bot_memory_messages', v_inserted;
END $$;


-- =====================================================================
-- ШАГ 6: Заполнение сводных дневных показателей (ojr_daily_summary)
-- =====================================================================
DO $$
DECLARE
    v_tid       INTEGER;
    v_d         RECORD;
    v_inserted  INTEGER := 0;
BEGIN
    SELECT id INTO v_tid FROM ojr_title_page WHERE is_active = TRUE;
    IF v_tid IS NULL THEN RETURN; END IF;

    -- Для каждой даты, где есть записи о работах
    FOR v_d IN
        SELECT
            work_date,
            SUM(volume) AS total_vol,
            COUNT(DISTINCT vor_code) AS code_count
        FROM ojr_section3_work_log
        WHERE category = 'объём'
        GROUP BY work_date
        ORDER BY work_date
    LOOP
        INSERT INTO ojr_daily_summary (
            title_id, summary_date,
            total_volume_today
        ) VALUES (
            v_tid, v_d.work_date,
            v_d.total_vol
        ) ON CONFLICT (summary_date) DO UPDATE SET
            total_volume_today = EXCLUDED.total_volume_today;

        v_inserted := v_inserted + 1;
    END LOOP;

    RAISE NOTICE '✅ Сводные показатели: перенесено % записей', v_inserted;
END $$;


-- =====================================================================
-- ШАГ 7: Погода — backfill из Open-Meteo за последние 90 дней
-- =====================================================================
-- (Заполняется извне через fill_ejo.py / weather cron — здесь только структура)
DO $$
BEGIN
    RAISE NOTICE 'ℹ️ Погода: заполняется через fill_ejo.py (Open-Meteo API 42.284,72.765) — не в миграции';
END $$;


-- =====================================================================
-- ШАГ 8: Верификация результатов миграции
-- =====================================================================
DO $$
DECLARE
    r RECORD;
    v_total INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========== MIGRATION VERIFICATION ==========';
    FOR r IN
        VALUES
            ('ojr_title_page',                    (SELECT COUNT(*) FROM ojr_title_page)),
            ('ojr_section1_personnel',            (SELECT COUNT(*) FROM ojr_section1_personnel)),
            ('ojr_section3_work_log',             (SELECT COUNT(*) FROM ojr_section3_work_log)),
            ('ojr_photo_log',                     (SELECT COUNT(*) FROM ojr_photo_log)),
            ('ojr_daily_summary',                 (SELECT COUNT(*) FROM ojr_daily_summary)),
            ('ojr_weather',                       (SELECT COUNT(*) FROM ojr_weather))
    LOOP
        RAISE NOTICE '  %: % rows', r.column1, r.column2;
        v_total := v_total + COALESCE(r.column2, 0);
    END LOOP;
    RAISE NOTICE '------------------------------------------';
    RAISE NOTICE '  TOTAL migrated: % rows', v_total;

    -- Сравнение с исходными таблицами
    RAISE NOTICE '';
    RAISE NOTICE '  bot_memory_facts (исходник):  % rows',
        (SELECT COUNT(*) FROM bot_memory_facts WHERE source='qa');
    RAISE NOTICE '  bot_poll_residuals (исходник): % rows',
        (SELECT COUNT(*) FROM bot_poll_residuals);
    RAISE NOTICE '==========================================';
END $$;


COMMIT;

-- =====================================================================
-- ROLLBACK INSTRUCTIONS (если что-то пошло не так):
--   DROP TABLE IF EXISTS ojr_daily_summary, ojr_incidents, ojr_materials,
--     ojr_photo_log, ojr_weather, ojr_section6_gosstroynadzor,
--     ojr_section5_asbuilt_docs, ojr_section4_checks,
--     ojr_section4_construction_control, ojr_section3_work_log,
--     ojr_section2_visits, ojr_section2_design_supervision,
--     ojr_section1_personnel, ojr_title_page CASCADE;
--   DROP TYPE IF EXISTS ojr_supervision_status, ojr_inspection_result,
--     ojr_weather_phenomenon;
-- =====================================================================
