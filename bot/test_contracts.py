#!/usr/bin/env python3
"""
test_contracts.py — Diamond-верификация контрактов проекта Alikhan.

10 независимых проверок. Каждый тест = одна функция.
Провал любого теста = контракт нарушен → изменения должны быть заблокированы.

Запуск:
    pytest test_contracts.py -v
    pytest test_contracts.py::test_contract_bridge_wrapper_import -v  # один тест
"""

import ast
import os
import sys


# Добавляем bot/ в путь для импорта модулей проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════════════════════════════════════
# Утилиты
# ═══════════════════════════════════════════════════════════════════════════

def _top_level_imports(filepath):
    """Возвращает список строк: ('from', 'module', 'name') или ('import', None, 'name')
    только для импортов на верхнем уровне модуля (не внутри функций)."""
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read(), filename=filepath)
    imports = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                imports.append(('from', module, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(('import', None, alias.name))
    return imports


# ═══════════════════════════════════════════════════════════════════════════
# Тест 1: bridge_wrapper — fill_ejo.py должен импортировать EVO, KEY
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_bridge_wrapper_import():
    """Контракт: fill_ejo.py НЕ импортирует EVO/KEY из bridge_wrapper — фото читаются с диска напрямую (Evolution API мёртв)."""
    fill_ejo_path = os.path.join(os.path.dirname(__file__), 'fill_ejo.py')
    imports = _top_level_imports(fill_ejo_path)

    evo_imported = False
    key_imported = False

    for kind, mod, name in imports:
        if kind == 'from' and mod == 'bridge_wrapper':
            if name == 'EVO':
                evo_imported = True
            if name == 'KEY':
                key_imported = True

    assert not evo_imported, (
        "КОНТРАКТ НАРУШЕН: fill_ejo.py импортирует EVO из bridge_wrapper. "
        "Evolution API (getBase64FromMediaMessage) мёртв — фото должны читаться с диска через pf.local_path."
    )
    assert not key_imported, (
        "КОНТРАКТ НАРУШЕН: fill_ejo.py импортирует KEY из bridge_wrapper. "
        "Evolution API (getBase64FromMediaMessage) мёртв — фото должны читаться с диска через pf.local_path."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 2: data_sources — все NamedTuple доступны для импорта
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_NAMEDTUPLES = [
    'WeatherData',
    'IncidentCount',
    'StaffOrg',
    'StaffData',
    'VolumeData',
    'PhotoFile',
    'PhotoData',
    'AIBHeadcount',
    'EquipmentData',
    'MaterialItem',
    'MaterialData',
    'ActivePhases',
    'PlanData',
    'CodeSource',
]


def test_contract_data_sources_namedtuples():
    """Контракт: все 14 NamedTuple доступны для импорта из data_sources."""
    import data_sources

    missing = []
    for name in EXPECTED_NAMEDTUPLES:
        if not hasattr(data_sources, name):
            missing.append(name)

    assert not missing, (
        f"КОНТРАКТ НАРУШЕН: отсутствуют NamedTuple в data_sources: {missing}. "
        "Все контрактные NamedTuple должны быть доступны для импорта."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 3: data_sources — все функции-источники доступны
# ═══════════════════════════════════════════════════════════════════════════

EXPECTED_FUNCTIONS = [
    'get_weather',
    'get_incidents',
    'get_staff',
    'get_volumes',
    'get_photos',
    'get_aibikon_headcount',
    'get_equipment',
    'get_materials',
    'get_active_phases',
    'get_plans_from_messages',
    'get_code_source',
    'get_phase_end_dates',
]


def test_contract_data_sources_functions():
    """Контракт: все 12 функций-источников доступны для импорта из data_sources."""
    import data_sources

    missing = []
    for name in EXPECTED_FUNCTIONS:
        if not hasattr(data_sources, name):
            missing.append(name)
        elif not callable(getattr(data_sources, name)):
            missing.append(f"{name} (не функция)")

    assert not missing, (
        f"КОНТРАКТ НАРУШЕН: отсутствуют функции в data_sources: {missing}. "
        "Все функции-источники должны быть доступны для импорта."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 4: fill_ejo.py НЕ импортирует db.get_conn напрямую (на уровне модуля)
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_fill_ejo_no_direct_db():
    """Контракт: fill_ejo.py НЕ импортирует get_conn из db на уровне модуля.

    fill_ejo.py должен использовать data_sources.py для всех запросов к БД.
    Прямой импорт db.get_conn на уровне модуля = нарушение архитектурной границы.
    (Импорты внутри функций допустимы как временная мера, но не поощряются.)
    """
    fill_ejo_path = os.path.join(os.path.dirname(__file__), 'fill_ejo.py')
    imports = _top_level_imports(fill_ejo_path)

    for kind, mod, name in imports:
        if kind == 'from' and mod == 'db' and name == 'get_conn':
            assert False, (
                "КОНТРАКТ НАРУШЕН: fill_ejo.py импортирует get_conn из db на уровне модуля. "
                "Все обращения к БД должны идти через data_sources.py."
            )
        if kind == 'import' and name == 'db':
            assert False, (
                "КОНТРАКТ НАРУШЕН: fill_ejo.py импортирует модуль db на уровне модуля. "
                "Все обращения к БД должны идти через data_sources.py."
            )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 5: messaging.py импортирует EVO, KEY из bridge_wrapper
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_messaging_imports_bridge():
    """Контракт: messaging.py импортирует EVO, KEY из bridge_wrapper."""
    messaging_path = os.path.join(os.path.dirname(__file__), 'messaging.py')
    imports = _top_level_imports(messaging_path)

    evo_imported = False
    key_imported = False

    for kind, mod, name in imports:
        if kind == 'from' and mod == 'bridge_wrapper':
            if name == 'EVO':
                evo_imported = True
            if name == 'KEY':
                key_imported = True

    assert evo_imported, (
        "КОНТРАКТ НАРУШЕН: messaging.py не импортирует EVO из bridge_wrapper."
    )
    assert key_imported, (
        "КОНТРАКТ НАРУШЕН: messaging.py не импортирует KEY из bridge_wrapper."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 6: poll.py импортирует get_conn из db
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_poll_imports_db():
    """Контракт: poll.py импортирует get_conn из db."""
    poll_path = os.path.join(os.path.dirname(__file__), 'poll.py')
    imports = _top_level_imports(poll_path)

    get_conn_imported = False
    for kind, mod, name in imports:
        if kind == 'from' and mod == 'db' and name == 'get_conn':
            get_conn_imported = True
            break

    assert get_conn_imported, (
        "КОНТРАКТ НАРУШЕН: poll.py не импортирует get_conn из db. "
        "poll.py должен иметь доступ к БД через db.get_conn."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 7: qa.py импортирует EVO, KEY из bridge_wrapper
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_qa_imports_bridge():
    """Контракт: qa.py импортирует EVO, KEY из bridge_wrapper."""
    qa_path = os.path.join(os.path.dirname(__file__), 'qa.py')
    imports = _top_level_imports(qa_path)

    evo_imported = False
    key_imported = False

    for kind, mod, name in imports:
        if kind == 'from' and mod == 'bridge_wrapper':
            if name == 'EVO':
                evo_imported = True
            if name == 'KEY':
                key_imported = True

    assert evo_imported, (
        "КОНТРАКТ НАРУШЕН: qa.py не импортирует EVO из bridge_wrapper."
    )
    assert key_imported, (
        "КОНТРАКТ НАРУШЕН: qa.py не импортирует KEY из bridge_wrapper."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 8: PhotoFile содержит поле local_path
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_photo_local_path():
    """Контракт: PhotoFile NamedTuple содержит поле local_path."""
    from data_sources import PhotoFile

    # Получаем поля NamedTuple
    fields = PhotoFile._fields

    assert 'local_path' in fields, (
        f"КОНТРАКТ НАРУШЕН: PhotoFile не содержит поле 'local_path'. "
        f"Текущие поля: {fields}. "
        "Поле local_path обязательно для отслеживания пути к файлу фото в кеше."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 9: StaffOrg использует workers (не count)
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_staff_org_workers_count():
    """Контракт: StaffOrg использует поле workers, а не count."""
    from data_sources import StaffOrg

    fields = StaffOrg._fields

    assert 'workers' in fields, (
        f"КОНТРАКТ НАРУШЕН: StaffOrg не содержит поле 'workers'. "
        f"Текущие поля: {fields}. "
        "Поле 'workers' обязательно для подсчёта рабочих."
    )

    # Убеждаемся, что нет поля 'count' (его не должно быть)
    assert 'count' not in fields, (
        f"КОНТРАКТ НАРУШЕН: StaffOrg содержит поле 'count' вместо 'workers'. "
        f"Текущие поля: {fields}. "
        "Должно использоваться поле 'workers' для подсчёта рабочих, а не 'count'."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 10: SQL в db.py использует ON CONFLICT с явными колонками
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_on_conflict_columns():
    """Контракт: все ON CONFLICT в db.py указывают явные колонки.

    ON CONFLICT без указания колонок (или с ON CONFLICT DO NOTHING без колонок)
    может привести к неожиданному поведению при изменении схемы.
    """
    db_path = os.path.join(os.path.dirname(__file__), 'db.py')

    with open(db_path, 'r') as f:
        source = f.read()

    # Ищем все вхождения ON CONFLICT
    import re
    conflicts = list(re.finditer(r'ON\s+CONFLICT\s*(\([^)]+\))?', source, re.IGNORECASE))

    assert len(conflicts) > 0, (
        "КОНТРАКТ НАРУШЕН: в db.py не найдено ни одного ON CONFLICT. "
        "Ожидается использование ON CONFLICT с явными колонками."
    )

    violations = []
    for m in conflicts:
        match_text = m.group(0)
        # Если после ON CONFLICT нет скобок с колонками — нарушение
        if '(' not in match_text:
            line_num = source[:m.start()].count('\n') + 1
            violations.append(f"строка {line_num}: {match_text.strip()}")

    assert not violations, (
        f"КОНТРАКТ НАРУШЕН: найдены ON CONFLICT без явных колонок в db.py:\n"
        + '\n'.join(violations) + "\n"
        "Каждый ON CONFLICT должен указывать целевые колонки, например: "
        "ON CONFLICT (col1, col2)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 11: save_work_log ON CONFLICT = uq_ojr_work_log
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_work_log_on_conflict_matches_unique():
    """Контракт: ON CONFLICT work_log = (work_date, vor_code, building, category)."""
    db_path = os.path.join(os.path.dirname(__file__), 'db.py')
    with open(db_path, 'r') as f:
        source = f.read()
    assert 'ON CONFLICT (work_date, vor_code, building, category)' in source, (
        "КОНТРАКТ НАРУШЕН: save_work_log ON CONFLICT должен совпадать с "
        "uq_ojr_work_log (work_date, vor_code, building, category)."
    )
    assert 'ON CONFLICT (work_date, vor_code) DO UPDATE' not in source, (
        "КОНТРАКТ НАРУШЕН: старый ON CONFLICT (work_date, vor_code) всё ещё в db.py."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 12: get_staff uses start_date/end_date window
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_get_staff_active_window():
    """Контракт: get_staff primary query — start_date/end_date window, не created_at."""
    ds_path = os.path.join(os.path.dirname(__file__), 'data_sources.py')
    with open(ds_path, 'r') as f:
        source = f.read()
    # Extract get_staff function body (rough)
    start = source.find('def get_staff')
    end = source.find('\ndef get_volumes', start)
    body = source[start:end] if end > start else source[start:start+3000]
    assert 'start_date <=' in body or 'start_date<=' in body, (
        "КОНТРАКТ НАРУШЕН: get_staff должен фильтровать по start_date <= d."
    )
    assert 'end_date IS NULL' in body, (
        "КОНТРАКТ НАРУШЕН: get_staff должен учитывать end_date IS NULL."
    )
    # Primary must NOT use DATE(created_at) as the only window
    primary_chunk = body.split('Fallback')[0] if 'Fallback' in body else body
    assert 'DATE(created_at)' not in primary_chunk, (
        "КОНТРАКТ НАРУШЕН: primary get_staff всё ещё использует DATE(created_at)."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 13: materials category not remapped to documentation
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_materials_category():
    """Контракт: ALLOWED_CATEGORIES has материалы; validate_category keeps it."""
    from qa import ALLOWED_CATEGORIES, validate_category
    assert 'материалы' in ALLOWED_CATEGORIES
    assert validate_category('материалы') == 'материалы'
    assert validate_category('материал') == 'материалы'
    assert validate_category('поставки') == 'материалы'
    # documentation stays documentation
    assert validate_category('документация') == 'документация'
    assert validate_category('документы') == 'документация'


# ═══════════════════════════════════════════════════════════════════════════
# Тест 14: normalize_org_name + save_personnel workers_count signature
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_normalize_org_and_personnel_api():
    """Контракт: canonical org names + save_personnel accepts workers_count."""
    import inspect
    from db import normalize_org_name, save_personnel
    assert normalize_org_name('майкадам') == 'Майкадам'
    assert normalize_org_name('Майкадам') == 'Майкадам'
    assert normalize_org_name('атантай') == 'Атантай'
    assert normalize_org_name('наватек') == 'Наватек'
    assert normalize_org_name('алтын-тас') == 'Алтын-Тас'
    assert normalize_org_name('айбикон') == 'АйБиКон'
    sig = inspect.signature(save_personnel)
    assert 'workers_count' in sig.parameters, (
        "КОНТРАКТ НАРУШЕН: save_personnel должен принимать workers_count."
    )


# ═══════════════════════════════════════════════════════════════════════════
# Тест 15: photo handlers write local_path into tags
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_photo_tags_local_path_written():
    """Контракт: main_waha photo paths always set tags.local_path from media."""
    path = os.path.join(os.path.dirname(__file__), 'main_waha.py')
    with open(path, 'r') as f:
        source = f.read()
    assert '_resolve_media_local_path' in source, (
        "КОНТРАКТ НАРУШЕН: нужен _resolve_media_local_path helper."
    )
    assert source.count('tags_photo["local_path"]') >= 2 or source.count("tags_photo['local_path']") >= 2 or \
           'tags_photo["local_path"]' in source or 'if local_path:' in source, (
        "КОНТРАКТ НАРУШЕН: local_path должен писаться в tags_photo."
    )
    # Both sandbox and prod should reference helper
    assert source.count('_resolve_media_local_path') >= 3


# ═══════════════════════════════════════════════════════════════════════════
# Тест 16: personnel multi-insert end_date race guard
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_personnel_no_multi_insert_close_race():
    """Контракт: QA must not multi-insert N workers; save_personnel must exclude same-day slot on close.

    Race (Worker A hole): for i in range(n): save_personnel(...) closed ALL open
    org+position rows before each insert → only last of N survived end_date IS NULL.
    """
    import re
    qa_path = os.path.join(os.path.dirname(__file__), 'qa.py')
    db_path = os.path.join(os.path.dirname(__file__), 'db.py')
    with open(qa_path, 'r') as f:
        qa = f.read()
    with open(db_path, 'r') as f:
        db = f.read()

    # parse_qa personnel path must use workers_count=N, not for i in range(n)
    # Find the main save_personnel call site after num_match
    assert 'workers_count=max(1, n)' in qa or 'workers_count=max(1,n)' in qa, (
        "КОНТРАКТ НАРУШЕН: parse_qa должен писать workers_count=max(1, n) одной строкой."
    )
    # Forbid the old multi-insert pattern near save_personnel
    assert 'for i in range(n):' not in qa and 'for i in range(max(1, n))' not in qa, (
        "КОНТРАКТ НАРУШЕН: multi-insert for i in range(n) save_personnel всё ещё в qa.py."
    )

    # save_personnel close must exclude the same full_name + start_date slot
    start = db.find('def save_personnel')
    end = db.find('\ndef save_work_log', start)
    body = db[start:end] if end > start else db[start:start + 4000]
    assert 'start_date = %s::date' in body or "start_date = %s::date" in body, (
        "КОНТРАКТ НАРУШЕН: close UPDATE должен исключать same-day slot."
    )
    assert 'AND NOT (' in body or 'AND NOT(' in body, (
        "КОНТРАКТ НАРУШЕН: close UPDATE должен иметь NOT (same full_name + start_date)."
    )
    assert 'full_name' in body and 'end_date' in body
