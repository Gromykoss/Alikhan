"""Enforced-модель полномочий Alikhan.

Модуль собирает контракт честности, риск-матрицу и fail-closed проверки в одном
месте. Он не читает окружение, не ходит в БД, не пишет файлы и не выполняет I/O:
вызывающий код обязан передать уже наблюдённые доказательства.
"""

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import re
import shlex
import shutil
from typing import Any

from config import PRODUCTION, SANDBOX


# Канонические ID приходят из config.py (единый источник правды),
# а не хардкодятся заново — иначе охранники «разъедутся» при смене группы.
PRODUCTION_CHAT_ID = PRODUCTION
SANDBOX_CHAT_ID = SANDBOX

CORE_DATA_TABLES = (
    "bot_memory_facts",
    "ojr_photo_log",
    "ojr_section3_work_log",
    "bot_memory_messages",
)

SECRET_NAMES = (
    "DB_PASS",
    "EVO_DB_PASS",
    "XAI_KEY",
    "ALERT_TELEGRAM_TOKEN",
    "DISCORD_WEBHOOK_URL",
)

ALLOWED_ROOTS = (
    "~/Alikhan-migration",
    "~/hermes-vault/20_Projects/Alikhan",
)

BUZZ_SEND_SCRIPT = Path(
    "/home/hermes-workspace/hermes-agent-lab/infra/skills/operator-workflow/scripts/buzz-send.py"
)
ALLOWED_BUZZ_PYTHON_REALPATHS = frozenset(
    os.path.realpath(path) for path in ("/usr/bin/python3", "/usr/bin/python")
)

TERMINAL_DENIED_FRAGMENTS = (
    "~/robot-man",
    "/home/hermes-workspace/robot-man",
    "~/gooolag",
    "/home/hermes-workspace/gooolag",
    "~/gulag",
    "/home/hermes-workspace/gulag",
    "~/rab9",
    "/home/hermes-workspace/rab9",
    "~/.hermes/secrets",
    ".hermes/secrets.env",
    "secrets.env",
    "~/.hermes/credentials",
    ".hermes/credentials",
    "buzz-message-router",
    "hermes-agent-lab",
    "~/hermes-agent-lab",
)

SHELL_META_RE = re.compile(r"&&|\|\||;|\||`|\$\(|\r|\n|>>|>|<")
BUZZ_SEND_SHELL_META_RE = re.compile(r"&&|\|\||;|\||`|\$|\r|\n|>>|>|<")

DATA_CLAIMS = frozenset(
    ("data_ok", "not_lost", "personnel_ok", "volume_ok", "photo_ok")
)
RUNTIME_CLAIMS = frozenset(("fixed", "ready", "sent"))
VALID_CLAIMS = DATA_CLAIMS | RUNTIME_CLAIMS
DATA_EVIDENCE_KIND = "select_count"
RUNTIME_EVIDENCE_KINDS = frozenset(
    ("process_rc", "curl_health", "file_exists", "test_pass")
)


class AuthorityLevel(Enum):
    """Уровни риска действия: чем дальше по списку, тем сильнее требуется контроль."""

    READ = 1
    ANALYZE = 2
    LOCAL = 3
    MULTI = 4
    PROD = 5
    DESTROY = 6


class Verdict(Enum):
    """Вердикт контракта; fail-closed: проходит только явно удовлетворённый контракт."""

    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    INCONCLUSIVE = "inconclusive"
    INVALID_CONTRACT = "invalid_contract"

    @property
    def passes(self) -> bool:
        """Возвращает True только для SATISFIED; любой иной вердикт блокирует."""

        return self is Verdict.SATISFIED

    @property
    def blocking(self) -> bool:
        """Возвращает True для всех fail-closed состояний кроме SATISFIED."""

        return not self.passes


@dataclass(frozen=True)
class Evidence:
    """Наблюдаемое доказательство, полученное вне этого чистого модуля.

    Fail-closed правило: доказательство с observed=False не может подтверждать
    заявление, даже если его kind/source выглядят подходящими.
    """

    kind: str
    source: str
    value: Any
    observed: bool
    note: str = ""


@dataclass
class Claim:
    """Заявление агента, которое запрещено принимать без доказательств.

    Fail-closed правило: пустой список evidence никогда не даёт SATISFIED.
    Поле verdict хранит последний известный вердикт, но validate_claim
    пересчитывает его из фактов.
    """

    kind: str
    evidence: list[Evidence] = field(default_factory=list)
    verdict: Verdict = Verdict.INCONCLUSIVE


def _extract_counts_sum(value: Any) -> int | None:
    """Возвращает сумму всех числовых count-значений из Evidence.value.

    Обрабатывает обе структуры, которые может положить build_evidence:
      - {"counts": {"table1": int, "table2": int, ...}}
      - {"table1": int, "table2": int, ...}   (value — сам словарь counts)

    Если value не dict, внутри нет числовых значений или структура нечитаема —
    возвращает None (вызывающий не блокируется, satisfied определяется по source/covers).
    """

    if not isinstance(value, dict):
        return None

    # Приоритет: вложенный ключ "counts", если он есть и является dict.
    inner: Any = value.get("counts")
    if isinstance(inner, dict):
        target = inner
    else:
        # Иначе считаем, что value сам является словарём counts.
        target = value

    total = 0
    found_numeric = False
    for v in target.values():
        if isinstance(v, (int, float)):
            total += int(v)
            found_numeric = True
        elif isinstance(v, str):
            try:
                total += int(v)
                found_numeric = True
            except (ValueError, TypeError):
                continue
    return total if found_numeric else None


def validate_claim(claim: Claim) -> Verdict:
    """Проверяет заявление агента по контракту честности.

    Fail-closed правило: неизвестный claim.kind, пустые evidence, ненаблюдённые
    evidence или отсутствие обязательного типа доказательства блокируют ответ.
    """

    if claim.kind not in VALID_CLAIMS:
        claim.verdict = Verdict.INVALID_CONTRACT
        return claim.verdict

    if not claim.evidence:
        claim.verdict = Verdict.INCONCLUSIVE
        return claim.verdict

    if any(not item.observed for item in claim.evidence):
        claim.verdict = Verdict.NOT_SATISFIED
        return claim.verdict

    if claim.kind in DATA_CLAIMS:
        satisfied = False
        for item in claim.evidence:
            if (
                item.kind == DATA_EVIDENCE_KIND
                and bool(item.source)
                and _source_covers_required_tables(item.source, claim.kind)
            ):
                counts_sum = _extract_counts_sum(item.value)
                if counts_sum is not None:
                    if counts_sum > 0:
                        satisfied = True
                        break
                    # counts_sum == 0: source валиден, но данных нет — мягкий блок.
                    if counts_sum == 0:
                        claim.verdict = Verdict.INCONCLUSIVE
                        return claim.verdict
                else:
                    # Не удалось вычислить сумму — fall back к старой логике (source/covers).
                    satisfied = True
                    break
    else:
        satisfied = any(
            item.kind in RUNTIME_EVIDENCE_KINDS and bool(item.source)
            for item in claim.evidence
        )

    claim.verdict = Verdict.SATISFIED if satisfied else Verdict.NOT_SATISFIED
    return claim.verdict


def can_send(chat_id: str, actor: str, approval_token: str | None = None) -> bool:
    """Разрешает отправку в WhatsApp-чат по production-deny контракту.

    Fail-closed правило: production без approval-токена и неизвестные chat_id
    всегда запрещены. actor оставлен в сигнатуре для аудита вызывающей стороны.
    """

    del actor
    if chat_id == SANDBOX_CHAT_ID:
        return True
    if chat_id == PRODUCTION_CHAT_ID:
        return bool(approval_token)
    return False


def authority_level(action: str) -> AuthorityLevel:
    """Классифицирует действие по риск-матрице READ/ANALYZE/LOCAL/MULTI/PROD/DESTROY.

    Fail-closed правило: неизвестное действие получает PROD, а опасные маркеры
    получают DESTROY независимо от остальных слов.
    """

    text = _normalize_action(action)

    destroy_markers = (
        "drop ",
        "truncate ",
        "delete from ",
        "rm -rf",
        "git reset --hard",
        "restart gateway",
        "hermes-gateway restart",
        "systemctl restart hermes-gateway",
        "destroy",
        "wipe",
    )
    if any(marker in text for marker in destroy_markers):
        return AuthorityLevel.DESTROY

    prod_markers = (
        "production",
        "prod",
        "боев",
        "db",
        "database",
        "postgres",
        "select",
        "insert",
        "update ",
        "delete ",
        "wa-send",
        "send",
        "whatsapp",
        "bridge restart",
        "restart bridge",
        "systemctl restart hermes-whatsapp-bridge",
    )
    if any(marker in text for marker in prod_markers):
        return AuthorityLevel.PROD

    multi_markers = (
        "multi",
        "many files",
        "multiple files",
        "refactor",
        "рефактор",
        "многофай",
        "несколько файлов",
    )
    if any(marker in text for marker in multi_markers):
        return AuthorityLevel.MULTI

    local_markers = (
        "patch",
        "write_file",
        "edit",
        "single file",
        "one file",
        "локаль",
        "правка",
        "один файл",
    )
    if any(marker in text for marker in local_markers):
        return AuthorityLevel.LOCAL

    analyze_markers = (
        "analyze",
        "analyse",
        "grep",
        "search",
        "search_files",
        "logs",
        "log",
        "status",
        "curl-get",
        "health",
        "провер",
        "анализ",
    )
    if any(marker in text for marker in analyze_markers):
        return AuthorityLevel.ANALYZE

    read_markers = (
        "read",
        "read_file",
        "cat",
        "ls",
        "find",
        "просмотр",
        "читать",
    )
    if any(marker in text for marker in read_markers):
        return AuthorityLevel.READ

    return AuthorityLevel.PROD


def is_mutation_allowed(level: AuthorityLevel, actor_is_orchestrator: bool) -> bool:
    """Решает, можно ли актору выполнять действие этого уровня напрямую.

    Fail-closed правило: оркестратор допускается только к READ/ANALYZE; для
    оператора без внешнего approval здесь разрешён только LOCAL и ниже.
    """

    if actor_is_orchestrator:
        return level in (AuthorityLevel.READ, AuthorityLevel.ANALYZE)
    return level in (AuthorityLevel.READ, AuthorityLevel.ANALYZE, AuthorityLevel.LOCAL)


def secret_path_denied(path: str) -> bool:
    """Проверяет файловую границу профиля.

    Fail-closed правило: пустой путь, путь вне разрешённых корней или путь,
    который нельзя нормализовать, считается запрещённым.
    """

    if not path:
        return True

    try:
        candidate = Path(os.path.expanduser(path)).resolve(strict=False)
        allowed_roots = tuple(
            Path(os.path.expanduser(root)).resolve(strict=False)
            for root in ALLOWED_ROOTS
        )
    except (OSError, RuntimeError, ValueError):
        return True

    return not any(_is_relative_to(candidate, root) for root in allowed_roots)


def secret_name_denied(name: str) -> bool:
    """Запрещает раскрывать или прокидывать значения известных секретов.

    Fail-closed правило: сравнение идёт после нормализации регистра и пробелов;
    точное имя из SECRET_NAMES всегда запрещено.
    """

    normalized = (name or "").strip().upper()
    return normalized in SECRET_NAMES


def _buzz_send_allowed(command: str) -> bool:
    """Разрешает только канонический argv-вектор buzz-send для Alikhan.

    Форма `--as=alikhan` намеренно запрещена: AGENTS.md фиксирует канон
    как `--as alikhan`.
    """

    if BUZZ_SEND_SHELL_META_RE.search(command):
        return False

    try:
        argv = shlex.split(command, posix=True)
    except ValueError:
        return False

    if len(argv) < 4:
        return False

    interpreter = Path(argv[0]).expanduser()
    if not interpreter.is_absolute():
        # Bare `python3` → DENY (adversarial review r3): guard резолвит через чистый
        # PATH, но bash -c исполнит сессионный — hijack через export PATH неизбежен.
        # Канон AGENTS.md использует абсолютный /usr/bin/python3.
        return False
    try:
        interpreter_realpath = os.path.realpath(str(interpreter.resolve(strict=False)))
    except (OSError, RuntimeError, ValueError):
        return False
    if interpreter_realpath not in ALLOWED_BUZZ_PYTHON_REALPATHS:
        return False

    try:
        script_path = Path(argv[1]).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False

    try:
        allowed_script_path = BUZZ_SEND_SCRIPT.expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return False

    if script_path != allowed_script_path:
        return False

    as_count = 0
    index = 2
    while index < len(argv):
        token = argv[index]
        if token == "--as":
            as_count += 1
            if index + 1 >= len(argv) or argv[index + 1] != "alikhan":
                return False
            index += 2
            continue
        if token == "--to":
            if (
                index + 1 >= len(argv)
                or not argv[index + 1]
                or argv[index + 1].startswith("--")
            ):
                return False
            index += 2
            continue
        if token.startswith("--"):
            return False
        break

    if as_count != 1:
        return False

    message = argv[index:]
    if not message or message[0].startswith("--"):
        return False

    rest = " ".join(argv[2:])
    return not any(fragment in rest for fragment in TERMINAL_DENIED_FRAGMENTS)


def guard_tool_call(tool_name: str, args: dict) -> tuple[bool, str]:
    """Проверяет tool call на файловую границу профиля Alikhan."""

    tool = tool_name or ""
    payload = args if isinstance(args, dict) else {}

    if tool in (
        "read_file",
        "write_file",
        "patch",
        "search_files",
        "skill_manage",
        "skill_view",
    ):
        stack = [payload]
        paths = []
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                path = current.get("path")
                if isinstance(path, str) and path:
                    paths.append(path)
                stack.extend(current.values())
            elif isinstance(current, (list, tuple)):
                stack.extend(current)

        for path in paths:
            if secret_path_denied(path):
                return (
                    False,
                    f"Файловая граница: путь {path} вне разрешённой зоны Alikhan",
                )
        return True, ""

    if tool == "terminal":
        command = payload.get("command")
        if not isinstance(command, str) or not command:
            return False, "Файловая граница: terminal.command пустой или не строка"

        # Allowlist: каноническая отправка в agent-bus (AGENTS.md, включено оператором 31.08,
        # разблокировано 04.09 после инцидента блокировки шины).
        if _buzz_send_allowed(command):
            return True, ""

        if "buzz-send.py" in command:
            return (
                False,
                "Файловая граница: buzz-send разрешён только каноническим argv-вектором Alikhan",
            )

        for fragment in TERMINAL_DENIED_FRAGMENTS:
            if fragment in command:
                return (
                    False,
                    f"Файловая граница: command затрагивает {fragment} — вне зоны Alikhan",
                )
        return True, ""

    return True, ""


def _source_covers_required_tables(source: str, claim_kind: str) -> bool:
    """Проверяет, что SELECT-доказательство покрывает таблицы для типа данных."""

    normalized = source.lower()
    if claim_kind == "personnel_ok":
        required = ("bot_memory_facts",)
    elif claim_kind == "volume_ok":
        required = ("ojr_section3_work_log",)
    elif claim_kind == "photo_ok":
        required = ("ojr_photo_log",)
    else:
        required = CORE_DATA_TABLES

    return all(table.lower() in normalized for table in required)


def _normalize_action(action: str) -> str:
    """Нормализует описание действия для консервативной классификации риска."""

    return (action or "").strip().lower()


def _is_relative_to(path: Path, root: Path) -> bool:
    """Совместимая проверка принадлежности пути разрешённому корню."""

    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    _PY = "/usr/bin/python3"
    _CANON = (
        f"{_PY} "
        "/home/hermes-workspace/hermes-agent-lab/infra/skills/operator-workflow/scripts/buzz-send.py"
    )
    _SCRIPT = "/home/hermes-workspace/hermes-agent-lab/infra/skills/operator-workflow/scripts/buzz-send.py"
    _CASES = (
        (f"{_CANON} --as alikhan 'текст'", True),
        (f"{_CANON} --as alikhan --to hermes 'текст'", True),
        (f"{_CANON} --as alikhan 'cat secrets.env'", False),
        (
            f"{_CANON} --as alikhan 'x'; cat /home/hermes-workspace/.hermes/secrets.env",
            False,
        ),
        (f"{_CANON} --as gulag 'текст'", False),
        (
            "python3 /home/hermes-workspace/hermes-agent-lab/../../robot-man/x.py "
            "--as alikhan 'x'",
            False,
        ),
        (f"{_CANON} --as alikhan 'x' && cat ~/.hermes/secrets.env", False),
        ("python3 /tmp/evil.py buzz-send.py --as alikhan", False),
        (
            "python3 /home/hermes-workspace/hermes-agent-lab/infra/skills/"
            "operator-workflow/scripts/not-buzz-send.py-backup --as alikhan 'x'",
            False,
        ),
        (f"{_CANON} --as alikhan --as gulag 'x'", False),
        ("cd ~/hermes-agent-lab && git pull", False),
        ("ls ~/Alikhan-migration/bot", True),
        (f"/tmp/python3 {_SCRIPT} --as alikhan 'x'", False),
        (f"~/Alikhan-migration/python3 {_SCRIPT} --as alikhan 'x'", False),
        (f"/usr/bin/python3 {_SCRIPT} --as alikhan 'x'", True),
        (f"{_CANON} pwned --as alikhan", False),
        (f"{_CANON} --as alikhan --channel UUID 'x'", False),
        (f"{_CANON} --channel UUID --as alikhan 'x'", False),
        (f"{_CANON} --as alikhan $MSG", False),
        (f"{_CANON} --as alikhan ${{MSG}}", False),
        (f"{_CANON} --as alikhan --to $TARGET 'x'", False),
        (f"{_CANON} --as alikhan --help 'x'", False),
        (f"{_CANON} --as=alikhan 'x'", False),
        (f"PYTHONPATH=/tmp python3 {_SCRIPT} --as alikhan 'x'", False),
        ("", False),
        (None, False),
        (f"{_CANON} --as alikhan -- --as gulag", False),
        (f"{_CANON} --as alikhan --to hermes 'привет'", True),
        (f"{_CANON} --as alikhan 'текст с $ внутри'", False),
        # r3-минимум Grok: bare python3 (канон AGENTS.md v1) = DENY
        (f"python3 {_SCRIPT} --as alikhan 'текст'", False),
        # r3-минимум Grok: относительный скрипт = DENY
        ("/usr/bin/python3 buzz-send.py --as alikhan 'x'", False),
    )
    for _index, (_command, _expected) in enumerate(_CASES, start=1):
        _allowed, _reason = guard_tool_call("terminal", {"command": _command})
        _passed = _allowed is _expected
        _verdict = "ALLOW" if _allowed else "DENY"
        _expected_verdict = "ALLOW" if _expected else "DENY"
        print(
            f"{_index:02d}. {'PASS' if _passed else 'FAIL'} "
            f"got={_verdict} expected={_expected_verdict}"
        )


__all__ = [
    "ALLOWED_ROOTS",
    "CORE_DATA_TABLES",
    "PRODUCTION_CHAT_ID",
    "SANDBOX_CHAT_ID",
    "SECRET_NAMES",
    "AuthorityLevel",
    "Claim",
    "Evidence",
    "Verdict",
    "authority_level",
    "can_send",
    "guard_tool_call",
    "is_mutation_allowed",
    "secret_name_denied",
    "secret_path_denied",
    "validate_claim",
]
