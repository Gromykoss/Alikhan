"""Router module: route(text) → action and reply"""
import re, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SIM_DATE, VOICE_TRIGGERS  # unified config (AUDIT-012)

_RU_MONTHS = {
    "январь": 1, "января": 1, "февраль": 2, "февраля": 2,
    "март": 3, "марта": 3, "апрель": 4, "апреля": 4,
    "май": 5, "мая": 5, "июнь": 6, "июня": 6,
    "июль": 7, "июля": 7, "август": 8, "августа": 8,
    "сентябрь": 9, "сентября": 9, "октябрь": 10, "октября": 10,
    "ноябрь": 11, "ноября": 11, "декабрь": 12, "декабря": 12,
}

def _parse_avr_month(normalized):
    match = re.search(r"(?:^|\s)авр(?:\s+за)?\s+([а-я]+)(?:\s+(\d{4}))?(?:\s|$)", normalized)
    if not match:
        return None
    token = match.group(1)
    matches = {_RU_MONTHS[name] for name in _RU_MONTHS if name.startswith(token) and len(token) >= 3}
    if len(matches) != 1:
        return None
    year = int(match.group(2)) if match.group(2) else datetime.now().year
    return {"month": matches.pop(), "year": year}

def route(text, chat_id, sender=""):
    """Returns (action, reply, voice_triggered)."""
    from handlers import ask_grok

    # AVR is an operational command and may be sent without addressing the bot by name.
    normalized = text.lower().replace("ё", "е")
    if re.search(r"(?:^|\s)авр\s+за\s+весь\s+период(?:\s|$)", normalized):
        return "AVR_ALL", "", False
    avr_month = _parse_avr_month(normalized)
    if avr_month:
        return "AVR_MONTH", avr_month, False
    if (re.search(r"(?:^|\s)авр(?:\s|$)", normalized)
            or "формируй авр" in normalized
            or "сформируй авр" in normalized
            or re.search(r"(?:^|\s)кс[-\s]?[26](?:\s|$)", normalized)):
        return "AVR", "", False

    # 1. QA — skip if question words present (STT output may contain data words)
    from qa import is_qa, parse_qa
    question_words = ["сколько", "какой", "какая", "какое", "какие", "что", "как",
                       "где", "когда", "почему", "зачем", "чей", "чья", "скока", "чё"]
    is_question = any(w in text.lower() for w in question_words)
    if is_qa(text) and not is_question:
        count = parse_qa(chat_id, text, date_str=SIM_DATE)
        if count > 0:
            return "QA", f"✅ Принято: {count} фактов", False

    # 2. Work-code bypass — if text contains "code = value" pattern, skip name check
    if re.search(r'\d+\.\d+\.\d+(?:\.\d+)?\s*[=—–\-:\s]+\s*\d+', text):
        return "RESIDUAL", "", False

    # 2. Name check
    if not re.search(r'[ао]л[еи][хгк]', text.lower()):
        return "IGNORE", "", False

    # 2.5 Command detection — skip Grok/verify for known commands
    cmd_words = ["запускай опрос", "начать опрос", "заполни ежо", "сформируй ежо",
                 "формируй ежо", "сделай ежо", "закрыть опрос", "завершить опрос",
                 "закончить опрос", "стоп опрос", "формируй отчет", "сформируй отчет",
                 "сделай отчет", "заполни отчет",
                 "авр", "формируй авр", "сформируй авр", "кс-2", "кс-6",
                 "статус опроса", "что собрано", "сводка опроса", "опрос статус",
                 "опрос стоп", "опрос закрыть", "опрос завершить", "опрос закончить",
                 "опрос окончен", "опрос завершен"]
    if any(w in text.lower() for w in cmd_words):
        return "CMD", "", False

    # 3. Voice trigger
    voice = any(w in text.lower() for w in VOICE_TRIGGERS)

    # 3.5 Schedule lookup
    from db_lookup import lookup_schedule
    schedule_reply = lookup_schedule(chat_id, text)
    if schedule_reply:
        return "SCHEDULE", schedule_reply, voice

    # 4. Weather / DB
    from db_lookup import lookup_facts
    db_reply, weather_reply = lookup_facts(chat_id, text)

    if weather_reply:
        reply = weather_reply
        action = "WEATHER"
    elif db_reply:
        # Summarize with Grok
        reply = ask_grok(
            f"Ты — строительный инспектор на площадке ТЗРК Джеруй (один объект). "
            f"Строятся: АБК, Общежитие, Галерея. "
            f"ПРОСУММИРУЙ все числа из фактов ниже. Дай точную итоговую цифру. "
            f"Вот факты из базы за сегодня:\n{db_reply}\n\n"
            f"Ответь на вопрос прораба коротко и по делу (1-2 предложения):\n{text[:500]}",
            max_tokens=200
        ).strip()
        action = "DB"
    else:
        # Grok fallback
        reply = ask_grok(
            f"Ты — строительный инспектор на площадке ТЗРК Джеруй (Кыргызстан, горы, ~2700м). "
            f"Строятся: АБК (2 этажа), Общежитие (3 этажа), Галерея. "
            f"Сегодня {datetime.now().strftime('%d.%m.%Y, %A')}. "
            f"Если вопрос про факты (техника, рабочие, происшествия) — скажи что нужно уточнить в БД. "
            f"Отвечай как прораб: коротко, по делу, без воды.\n\n"
            f"Вопрос: {text[:1800]}", max_tokens=200
        ).strip()
        action = "GROK"

    # Verification (Claude Code pattern: verify > write, 2-3x quality)
    # Skip for trusted sources: WEATHER (API), SCHEDULE (DB static)
    if action not in ("WEATHER", "SCHEDULE"):
        try:
            from verify import verify_reply
            reply, score, issues = verify_reply(reply, text, db_reply,
                                                db_facts_available=(db_reply is not None))
        except Exception as e:
            print(f"[VERIFY ERR] {e}", flush=True)

    return action, reply, voice
