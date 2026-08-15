"""Enforced-модель полномочий Alikhan.

Модуль собирает контракт честности, риск-матрицу и fail-closed проверки в одном
месте. Он не читает окружение, не ходит в БД, не пишет файлы и не выполняет I/O:
вызывающий код обязан передать уже наблюдённые доказательства.
"""

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
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
        satisfied = any(
            item.kind == DATA_EVIDENCE_KIND
            and bool(item.source)
            and _source_covers_required_tables(item.source, claim.kind)
            for item in claim.evidence
        )
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
    "is_mutation_allowed",
    "secret_name_denied",
    "secret_path_denied",
    "validate_claim",
]
