"""Forward explicit foreman questions to the office orchestrator webhook."""

from __future__ import annotations

import logging
import re
import threading
from typing import Callable

import requests
from secret_config import get_secret

LOGGER = logging.getLogger(__name__)

TOPIC_GENERAL = "общее"
TOPICS = ("кровля", "наружка", "материалы", "смета", TOPIC_GENERAL)
MAX_TEXT_LEN = 4000
DEFAULT_RETRIES = 1
DEFAULT_TIMEOUT = 10
DEFAULT_JOIN_TIMEOUT = 25

QUESTION_MARKERS = (
    "подскажите",
    "подскажи",
    "уточните",
    "уточни",
    "скажите",
    "скажи",
    "прошу",
    "нужен",
    "нужна",
    "нужно",
    "нужны",
    "можно ли",
    "надо ли",
    "как",
    "когда",
    "где",
    "куда",
    "сколько",
    "какой",
    "какая",
    "какие",
    "что",
    "кто",
)

COMMAND_MARKERS = (
    "ежо",
    "опрос",
    "опроса",
    "опросы",
    "авр",
    "кс-2",
    "кс2",
    "кс-6",
    "кс6",
    "снимок дня",
    "раскрой отчет",
)

LAST_HTTP_STATUS: int | None = None

QA_FACT_MARKERS = (
    "рабочие",
    "рабочих",
    "итр",
    "техника",
    "происшеств",
)

TOPIC_KEYWORDS = {
    "смета": (
        "смет", "расцен", "стоимост", "цена", "цену", "бюджет", "коэффициент",
        "акт", "кс-2", "кс2", "кс-6", "кс6", "оплат", "договор",
    ),
    "кровля": (
        "кров", "крыша", "парапет", "водосток", "мембран", "пароизоляц",
        "утепление кровли", "рулон", "воронк",
    ),
    "наружка": (
        "наруж", "фасад", "витраж", "окн", "двер", "ворот", "откос",
        "облицов", "сэндвич", "сендвич", "профлист", "ограждающ",
    ),
    "материалы": (
        "материал", "поставк", "закуп", "заказ", "склад", "привез", "достав",
        "бетон", "арматур", "металл", "цемент", "песок", "щебень", "болт",
        "крепеж", "кабель", "труба", "лист", "краск", "грунтовк",
    ),
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _contains_word(text: str, marker: str) -> bool:
    escaped = re.escape(marker).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![\w-]){escaped}(?![\w-])", text, flags=re.IGNORECASE) is not None


def _contains_topic_keyword(text: str, keyword: str) -> bool:
    escaped = re.escape(keyword).replace(r"\ ", r"\s+")
    if re.fullmatch(r"[\wа-яА-ЯёЁ]+", keyword, flags=re.IGNORECASE):
        pattern = rf"(?<![\w-]){escaped}[\wа-яА-ЯёЁ]*(?![\w-])"
    else:
        pattern = rf"(?<![\w-]){escaped}(?![\w-])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _has_question_shape(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    return "?" in t or any(_contains_word(t, marker) for marker in QUESTION_MARKERS)


def _looks_like_command(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    if t.startswith("/"):
        return True
    addressed_to_bot = _contains_word(t, "алихан")
    return any(_contains_word(t, marker) for marker in COMMAND_MARKERS) and (
        addressed_to_bot or "?" in t
    )


def _looks_like_poll_reply(text: str) -> bool:
    t = _normalize(text)
    if re.search(r"(?:^|\s)\d+(?:\.\d+){1,3}\s*(?:=|—|–|-|:)?\s*\d+(?:[,.]\d+)?", t):
        return True
    return False


def _looks_like_qa_fact(text: str) -> bool:
    t = _normalize(text)
    if not t:
        return False
    if "?" in t:
        return False
    if "=" in t or _looks_like_poll_reply(t):
        return True
    if "происшеств" in t and re.search(r"\b(нет|не было|0)\b", t):
        return True
    has_fact_marker = any(marker in t for marker in QA_FACT_MARKERS)
    has_number = re.search(r"\d", t) is not None
    return has_fact_marker and has_number and "?" not in t


def classify_topic(text: str) -> str:
    """Classify question topic with deterministic keywords."""
    t = _normalize(text)
    for topic in ("смета", "кровля", "наружка", "материалы"):
        if any(_contains_topic_keyword(t, keyword) for keyword in TOPIC_KEYWORDS[topic]):
            return topic
    return TOPIC_GENERAL


def classify_office_question(text: str) -> str | None:
    """Return topic for explicit office questions, otherwise None."""
    if not _has_question_shape(text):
        return None
    if _looks_like_command(text) or _looks_like_poll_reply(text) or _looks_like_qa_fact(text):
        return None
    return classify_topic(text)


def should_forward_text(text: str) -> bool:
    return classify_office_question(text) is not None


def _office_webhook_secrets() -> tuple[str, str]:
    url = get_secret("office_webhook_url", "OFFICE_WEBHOOK_URL")
    key = get_secret("office_webhook_key", "OFFICE_WEBHOOK_KEY")
    return url, key


def _truncate_text(text: str) -> str:
    value = str(text or "")
    if len(value) <= MAX_TEXT_LEN:
        return value
    return value[:MAX_TEXT_LEN]


def _safe_log(log_func: Callable[[str], None] | None, message: str) -> None:
    if log_func:
        try:
            log_func(message)
            return
        except Exception:
            pass
    LOGGER.warning(message)


def _post_to_office(
    chat_id: str,
    message_id: str,
    sender: str,
    text: str,
    topic: str,
    post: Callable[..., requests.Response] = requests.post,
    log_func: Callable[[str], None] | None = None,
    retries: int = DEFAULT_RETRIES,
) -> bool:
    global LAST_HTTP_STATUS
    url, key = _office_webhook_secrets()
    if not url or not key:
        LAST_HTTP_STATUS = None
        _safe_log(log_func, "OFFICE_FORWARD skipped: webhook config missing")
        return False

    payload = {
        "source": "hermes",
        "platform": "whatsapp",
        "chat_id": chat_id,
        "message_id": message_id,
        "from": sender,
        "text": _truncate_text(text),
        "topic": topic,
        "reply_to": None,
    }
    attempts = max(1, int(retries) + 1)
    for attempt in range(1, attempts + 1):
        try:
            resp = post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
                timeout=DEFAULT_TIMEOUT,
            )
            LAST_HTTP_STATUS = resp.status_code
            if 200 <= resp.status_code < 300:
                LOGGER.info("OFFICE_FORWARD sent topic=%s status=%s", topic, resp.status_code)
                return True
            _safe_log(
                log_func,
                f"OFFICE_FORWARD failed message_id={message_id} status={resp.status_code} attempt={attempt}/{attempts}",
            )
        except requests.RequestException as exc:
            LAST_HTTP_STATUS = None
            _safe_log(
                log_func,
                f"OFFICE_FORWARD error message_id={message_id} type={type(exc).__name__} attempt={attempt}/{attempts}",
            )
        except Exception as exc:
            LAST_HTTP_STATUS = None
            _safe_log(
                log_func,
                f"OFFICE_FORWARD error message_id={message_id} type={type(exc).__name__} attempt={attempt}/{attempts}",
            )
    return False


def forward_to_office(
    chat_id: str,
    message_id: str,
    sender: str,
    text: str,
    topic: str,
    *,
    async_send: bool = True,
    post: Callable[..., requests.Response] = requests.post,
    log_func: Callable[[str], None] | None = None,
    retries: int = DEFAULT_RETRIES,
    join_timeout: float = DEFAULT_JOIN_TIMEOUT,
) -> bool:
    """Send a webhook notification. Async mode joins through the retry budget."""
    topic = topic if topic in TOPICS else TOPIC_GENERAL
    if not async_send:
        return _post_to_office(
            chat_id, message_id, sender, text, topic, post=post, log_func=log_func, retries=retries
        )

    result: dict[str, bool] = {"ok": False}

    def runner() -> None:
        result["ok"] = _post_to_office(
            chat_id, message_id, sender, text, topic, post=post, log_func=log_func, retries=retries
        )

    try:
        thread = threading.Thread(target=runner, name="office-forward", daemon=False)
        thread.start()
        thread.join(timeout=join_timeout)
        if thread.is_alive():
            _safe_log(log_func, f"OFFICE_FORWARD timeout message_id={message_id}")
            return False
        return result["ok"]
    except Exception as exc:
        _safe_log(log_func, f"OFFICE_FORWARD thread error type={type(exc).__name__}")
        return False


def get_last_http_status() -> int | None:
    return LAST_HTTP_STATUS
