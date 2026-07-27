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
