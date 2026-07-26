#!/usr/bin/env python3
"""
pre_delegation.py — сборщик контрактов для делегирования задач в Codex/Grok Build.

Принимает список файлов, которые будут изменены, находит ВСЕ зависимые модули
и выводит их контракты + предупреждения в формате, готовом для вставки в context
делегирования.

Источник данных: bot/CONTRACTS.md (машиночитаемая JSON-секция).

Пример:
    python3 scripts/pre_delegation.py --files fill_ejo.py data_sources.py
    python3 scripts/pre_delegation.py --files bridge_wrapper.py --all
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import deque

# ── Константы ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_PATH = PROJECT_ROOT / "bot" / "CONTRACTS.md"

# Цвета для терминала
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def colorize(text: str, color: str) -> str:
    """Оборачивает текст в ANSI-цвета, если вывод — терминал."""
    if sys.stdout.isatty():
        return f"{color}{text}{COLOR_RESET}"
    return text


# ── Парсинг CONTRACTS.md ───────────────────────────────────────────────────

def parse_contracts(contracts_path: Path) -> dict:
    """
    Извлекает машиночитаемую JSON-секцию из CONTRACTS.md.

    Ищет блок ```json ... ``` внутри файла и парсит его.
    Ожидаемая структура:
        {
            "dependency_graph": { "module.py": ["dep1.py", ...], ... },
            "modules": { "module.py": { ... }, ... }
        }
    """
    text = contracts_path.read_text(encoding="utf-8")

    # Ищем JSON-блок между ```json и ```
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        print(
            colorize(
                f"❌ ОШИБКА: не найден JSON-блок в {contracts_path}",
                COLOR_RED,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(
            colorize(
                f"❌ ОШИБКА: некорректный JSON в {contracts_path}: {e}",
                COLOR_RED,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    if "dependency_graph" not in data or "modules" not in data:
        print(
            colorize(
                f"❌ ОШИБКА: JSON в {contracts_path} не содержит"
                f" 'dependency_graph' и/или 'modules'",
                COLOR_RED,
            ),
            file=sys.stderr,
        )
        sys.exit(1)

    return data


# ── Построение обратного графа зависимостей ────────────────────────────────

def build_reverse_graph(dep_graph: dict[str, list[str]]) -> dict[str, set[str]]:
    """
    Строит обратный граф: для каждого модуля — множество модулей,
    которые от него зависят.

    Из:
        {"a.py": ["b.py", "c.py"]}
    Получаем:
        {"b.py": {"a.py"}, "c.py": {"a.py"}}
    """
    reverse: dict[str, set[str]] = {}
    for module, deps in dep_graph.items():
        for dep in deps:
            if dep not in reverse:
                reverse[dep] = set()
            reverse[dep].add(module)
    return reverse


def find_all_dependents(
    changed_files: list[str], reverse_graph: dict[str, set[str]]
) -> dict[str, int]:
    """
    Находит все модули, которые (транзитивно) зависят от изменяемых файлов.

    Возвращает словарь {module: distance}, где distance — минимальное
    расстояние в графе зависимостей (0 = прямой dependant, 1 = зависит
    через один модуль, и т.д.).

    Использует BFS для обхода графа.
    """
    # Нормализуем имена файлов
    normalized = []
    for f in changed_files:
        f = f.strip()
        if "/" in f:
            f = Path(f).name  # берём только имя файла
        if not f.endswith(".py"):
            f = f + ".py" if "." not in f else f
        normalized.append(f)

    visited: dict[str, int] = {}
    queue = deque()

    # Начальные узлы — прямые dependants изменяемых файлов
    for f in normalized:
        if f in reverse_graph:
            for dep in reverse_graph[f]:
                if dep not in visited:
                    visited[dep] = 0
                    queue.append((dep, 0))

    # BFS для транзитивных зависимостей
    while queue:
        current, dist = queue.popleft()
        if current in reverse_graph:
            for dep in reverse_graph[current]:
                if dep not in visited:
                    visited[dep] = dist + 1
                    queue.append((dep, dist + 1))

    return visited


# ── Форматирование вывода ──────────────────────────────────────────────────

def format_contract_context(
    changed_files: list[str],
    dependents: dict[str, int],
    modules_info: dict,
    dep_graph: dict[str, list[str]],
) -> str:
    """
    Формирует текст контекста для вставки в задание Codex/Grok Build.

    Структура вывода:
    1. Заголовок: какие файлы меняются
    2. Список зависимых модулей с указанием расстояния
    3. Для каждого зависимого модуля — контракт (exports, critical rules)
    4. Предупреждения: «меняешь X → проверь Y, Z»
    """
    lines = []

    # ── Заголовок ──
    lines.append("=" * 72)
    lines.append(
        colorize(
            "⚡ КОНТЕКСТ ДЕЛЕГИРОВАНИЯ — КОНТРАКТЫ ЗАТРОНУТЫХ МОДУЛЕЙ",
            COLOR_BOLD + COLOR_CYAN,
        )
    )
    lines.append("=" * 72)
    lines.append("")
    lines.append(
        f"📝 Изменяемые файлы: {colorize(', '.join(changed_files), COLOR_YELLOW)}"
    )
    lines.append("")

    if not dependents:
        lines.append(
            colorize(
                "✅ Ни один модуль не зависит от изменяемых файлов. Можно менять безопасно.",
                COLOR_GREEN,
            )
        )
        return "\n".join(lines)

    # ── Список зависимых модулей ──
    lines.append("─" * 72)
    lines.append(
        colorize("📊 ЗАТРОНУТЫЕ МОДУЛИ (транзитивное замыкание):", COLOR_BOLD)
    )
    lines.append("─" * 72)

    # Сортируем по приоритету (P0 > P1 > P2 > P3) и расстоянию
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

    def sort_key(item):
        module, dist = item
        info = modules_info.get(module, {})
        prio = priority_order.get(info.get("priority", "P3"), 4)
        return (prio, dist, module)

    for module, dist in sorted(dependents.items(), key=sort_key):
        info = modules_info.get(module, {})
        prio = info.get("priority", "P3")
        prio_color = {
            "P0": COLOR_RED,
            "P1": COLOR_YELLOW,
            "P2": COLOR_GREEN,
            "P3": COLOR_RESET,
        }.get(prio, COLOR_RESET)

        dist_label = (
            f"(прямая зависимость)"
            if dist == 0
            else f"(через {dist} модулей)"
        )
        lines.append(
            f"  [{colorize(prio, prio_color)}] {colorize(module, COLOR_BOLD)} {dist_label}"
        )

    lines.append("")

    # ── Контракты для каждого зависимого модуля ──
    lines.append("─" * 72)
    lines.append(colorize("📋 КОНТРАКТЫ МОДУЛЕЙ:", COLOR_BOLD))
    lines.append("─" * 72)

    for module, dist in sorted(dependents.items(), key=sort_key):
        info = modules_info.get(module, {})
        if not info:
            continue

        lines.append("")
        lines.append(
            f"### {colorize(module, COLOR_BOLD + COLOR_CYAN)} "
            f"[{colorize(info.get('priority', '?'), COLOR_YELLOW)}] "
            f"Уровень {info.get('level', '?')}"
        )
        lines.append(f"    {info.get('description', 'Нет описания')}")

        deps = info.get("deps", dep_graph.get(module, []))
        if deps:
            lines.append(f"    Зависит от: {', '.join(deps)}")

        exports = info.get("exports", [])
        if exports:
            lines.append(f"    Экспортирует: {', '.join(exports)}")

        rules = info.get("critical_rules", [])
        if rules:
            lines.append(f"    ⛔ Критические правила:")
            for rule in rules:
                lines.append(f"       • {rule}")

    lines.append("")

    # ── Предупреждения ──
    lines.append("─" * 72)
    lines.append(colorize("⚠️  ПРЕДУПРЕЖДЕНИЯ:", COLOR_BOLD + COLOR_RED))
    lines.append("─" * 72)
    lines.append("")

    # Собираем нормализованные имена изменяемых файлов
    changed_norm = set()
    for cf in changed_files:
        cf_name = cf.strip()
        if "/" in cf_name:
            cf_name = Path(cf_name).name
        if not cf_name.endswith(".py"):
            cf_name = cf_name + ".py" if "." not in cf_name else cf_name
        changed_norm.add(cf_name)

    for cf_name in sorted(changed_norm):
        # Находим все модули, которые зависят от cf (прямо или транзитивно),
        # исключая сам изменяемый файл
        all_affected = set()
        for module, dist in dependents.items():
            all_affected.add(module)

        # Убираем сам изменяемый файл из списка (его и так меняем)
        affected_filtered = all_affected - changed_norm

        if affected_filtered:
            affected_list = ", ".join(sorted(affected_filtered))
            lines.append(
                f"  {colorize('Меняешь', COLOR_YELLOW)} "
                f"{colorize(cf_name, COLOR_BOLD)} "
                f"{colorize('→ проверь', COLOR_YELLOW)} "
                f"{colorize(affected_list, COLOR_CYAN)}"
            )
        else:
            lines.append(
                f"  {colorize('✅', COLOR_GREEN)} "
                f"{cf_name} — нет зависимых модулей (или только сам файл)"
            )

    lines.append("")
    lines.append("─" * 72)
    lines.append(
        colorize(
            "🔧 ДЕЙСТВИЯ ПОСЛЕ ИЗМЕНЕНИЙ (verification ladder):",
            COLOR_BOLD + COLOR_GREEN,
        )
    )
    lines.append("─" * 72)
    lines.append("  1. python3 -m py_compile bot/*.py")
    lines.append("  2. Проверить логи: tail -30 /tmp/alikhan.log")
    lines.append("  3. Тест в песочнице: запустить опрос → ответ → ЕЖО")
    lines.append("  4. Обновить CHRONOLOGY.md с описанием изменений")
    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="pre_delegation.py — сборщик контрактов"
        " для делегирования задач в Codex/Grok Build",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 scripts/pre_delegation.py --files fill_ejo.py data_sources.py
  python3 scripts/pre_delegation.py --files bridge_wrapper.py
  python3 scripts/pre_delegation.py --files messaging.py --plain
        """,
    )
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Список файлов, которые будут изменены (например: fill_ejo.py data_sources.py)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Показать контракты ВСЕХ модулей (не только затронутых)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Вывод без ANSI-цветов (для вставки в промпт)",
    )
    parser.add_argument(
        "--contracts",
        default=str(CONTRACTS_PATH),
        help=f"Путь к CONTRACTS.md (по умолчанию: {CONTRACTS_PATH})",
    )

    args = parser.parse_args()

    # Если --plain, отключаем цвета
    if args.plain:
        global COLOR_RED, COLOR_YELLOW, COLOR_GREEN, COLOR_CYAN, COLOR_BOLD, COLOR_RESET
        COLOR_RED = COLOR_YELLOW = COLOR_GREEN = COLOR_CYAN = COLOR_BOLD = COLOR_RESET = ""

    # Проверяем существование CONTRACTS.md
    contracts_path = Path(args.contracts)
    if not contracts_path.exists():
        print(
            colorize(
                f"❌ ОШИБКА: {contracts_path} не найден",
                COLOR_RED,
            ),
            file=sys.stderr,
        )
        print(
            "   Убедитесь, что CONTRACTS.md существует в bot/",
            file=sys.stderr,
        )
        sys.exit(1)

    # Парсим контракты
    data = parse_contracts(contracts_path)
    dep_graph = data["dependency_graph"]
    modules_info = data["modules"]

    # Строим обратный граф
    reverse_graph = build_reverse_graph(dep_graph)

    # Находим зависимые модули
    if args.all:
        # Все модули, включая изменяемые
        changed = set(args.files)
        dependents = {}
        for module in dep_graph:
            if module not in changed:
                dependents[module] = 0
    else:
        dependents = find_all_dependents(args.files, reverse_graph)

    # Формируем вывод
    output = format_contract_context(
        args.files, dependents, modules_info, dep_graph
    )
    print(output)

    # Краткая справка
    print(
        colorize(
            f"\n💡 Совет: скопируйте вывод выше в поле 'context' при делегировании в Codex/Grok Build.",
            COLOR_GREEN,
        ),
        file=sys.stderr,
    )
    print(
        colorize(
            f"   Используйте --plain для вывода без цветов, --all для полного списка модулей.",
            COLOR_GREEN,
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
