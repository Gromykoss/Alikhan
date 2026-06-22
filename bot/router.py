import calendar
import re
from datetime import datetime, timedelta, timezone

MONTHS_RU = {
    "январь": 1,
    "января": 1,
    "февраль": 2,
    "февраля": 2,
    "март": 3,
    "марта": 3,
    "апрель": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июнь": 6,
    "июня": 6,
    "июль": 7,
    "июля": 7,
    "август": 8,
    "августа": 8,
    "сентябрь": 9,
    "сентября": 9,
    "октябрь": 10,
    "октября": 10,
    "ноябрь": 11,
    "ноября": 11,
    "декабрь": 12,
    "декабря": 12,
}


def parse_date_ru(value):
    m1 = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", value)
    if m1:
        return f"{m1.group(3)}-{m1.group(2)}-{m1.group(1)}"

    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"

    return None


def today_iso():
    return datetime.now(timezone.utc).date().isoformat()


def shift_date(days):
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def parse_month_range_ru(value):
    pattern = (
        r"(январь|января|февраль|февраля|март|марта|апрель|апреля|май|мая|"
        r"июнь|июня|июль|июля|август|августа|сентябрь|сентября|октябрь|"
        r"октября|ноябрь|ноября|декабрь|декабря)\s+(\d{4})"
    )
    match = re.search(pattern, value, re.IGNORECASE)
    if not match:
        return None

    month = MONTHS_RU.get(match.group(1).lower())
    year = int(match.group(2))
    if not month or not year:
        return None

    last_day = calendar.monthrange(year, month)[1]
    return {
        "start": f"{year}-{month:02d}-01",
        "end": f"{year}-{month:02d}-{last_day:02d}",
    }


def _get(data, path, default=None):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def extract_text(data):
    msg = data.get("message", data)
    return str(
        msg.get("conversation")
        or _get(msg, ["extendedTextMessage", "text"], "")
        or _get(msg, ["imageMessage", "caption"], "")
        or _get(msg, ["documentMessage", "caption"], "")
        or ""
    ).strip()


def quoted_document(data):
    context = data.get("contextInfo") or _get(data, ["message", "extendedTextMessage", "contextInfo"], {}) or {}
    return (
        _get(context, ["quotedMessage", "documentMessage"])
        or _get(context, ["quotedMessage", "documentWithCaptionMessage", "message", "documentMessage"])
        or _get(context, ["quotedMessage", "documentWithCaptionMessage", "documentMessage"])
    )


def first_match_id(value, patterns):
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def route(text_or_data, chat_id="", sender="", message_id=""):
    if isinstance(text_or_data, dict):
        data = text_or_data.get("body", {}).get("data", text_or_data)
        key = data.get("key", {})
        text = extract_text(data)
        chat_id = str(key.get("remoteJid") or data.get("chatId") or chat_id or "").strip()
        sender = str(data.get("pushName") or sender or "Unknown")
        message_id = str(key.get("id") or data.get("messageId") or message_id or "")
        from_me = key.get("fromMe") is True
        quote = quoted_document(data)
        timestamp = data.get("messageTimestamp")
    else:
        data = {}
        text = str(text_or_data or "").strip()
        from_me = False
        quote = None
        timestamp = None

    lower = text.lower()

    id_match = re.search(r"\bid\s*(\d+)\b", lower, re.IGNORECASE) or re.search(
        r"\bид\s*(\d+)\b", lower, re.IGNORECASE
    )
    lookup_id = id_match.group(1) if id_match else ""

    doc_compare_ids = re.findall(r"\b(?:id|ид)\s*(\d+)\b", text, re.IGNORECASE)

    explicit_old_id = first_match_id(
        lower,
        [
            r"стар(?:ый|ая|ое|ую|ой)?(?:\s+\S+){0,6}?\s+(?:id|ид)\s*(\d+)",
            r"(?:id|ид)\s*(\d+)(?:\s+\S+){0,6}?\s+стар(?:ый|ая|ое|ую|ой)?",
            r"пер(?:вый|вая|вое)(?:\s+\S+){0,6}?\s+(?:id|ид)\s*(\d+)",
        ],
    )
    explicit_new_id = first_match_id(
        lower,
        [
            r"нов(?:ый|ая|ое|ую|ой)?(?:\s+\S+){0,6}?\s+(?:id|ид)\s*(\d+)",
            r"(?:id|ид)\s*(\d+)(?:\s+\S+){0,6}?\s+нов(?:ый|ая|ое|ую|ой)?",
            r"втор(?:ой|ая|ое|ую)(?:\s+\S+){0,6}?\s+(?:id|ид)\s*(\d+)",
        ],
    )

    has_document_compare_intent = (
        "сравни документ" in lower
        or "сравнить документ" in lower
        or "сравни регламент" in lower
        or "сравнить регламент" in lower
        or "что изменилось между" in lower
        or "найди отличия" in lower
        or "найти отличия" in lower
        or "отличия между" in lower
        or "что появилось нового" in lower
        or "нового в новой версии" in lower
        or ("первый" in lower and "стар" in lower and "втор" in lower and "нов" in lower)
    )

    has_regulation_fact_question_intent = (
        "можно ли" in lower
        or "разрешено ли" in lower
        or "запрещено ли" in lower
        or "нельзя ли" in lower
        or "какой штраф" in lower
        or "штраф" in lower
        or "по регламенту" in lower
        or "согласно регламенту" in lower
        or "пункт" in lower
        or "раздел" in lower
        or "шашлык" in lower
        or "мангал" in lower
        or "костер" in lower
        or "костёр" in lower
        or "барашек" in lower
        or "барашка" in lower
        or "бараш" in lower
        or "баран" in lower
        or "обряд" in lower
        or "обычай" in lower
        or "зарезать" in lower
        or "кровь" in lower
        or "пролить" in lower
        or "отход" in lower
        or "мусор" in lower
        or "пожарн" in lower
        or "санитар" in lower
        or "оос" in lower
        or "окружающей среды" in lower
    )

    doc_compare_old_id = explicit_old_id or (doc_compare_ids[0] if doc_compare_ids else "")
    doc_compare_new_id = explicit_new_id or next(
        (item for item in doc_compare_ids if item != doc_compare_old_id),
        doc_compare_ids[1] if len(doc_compare_ids) > 1 else "",
    )

    command = "ai"
    summary_start_date = ""
    summary_end_date = ""
    calendar_range = "all"

    if lower == "алихан":
        command = "only_name"
    elif "статус памяти" in lower:
        command = "memory_status"
    elif lookup_id and (
        "удали событие" in lower
        or "удалить событие" in lower
        or "отмени событие" in lower
        or "отменить событие" in lower
    ):
        command = "calendar_delete"
    elif len(doc_compare_ids) >= 2 and has_document_compare_intent:
        command = "document_compare"
    elif (
        "какой сегодня день" in lower
        or "какая сегодня дата" in lower
        or "дата сегодня" in lower
        or "сегодняшняя дата" in lower
        or "какое сегодня число" in lower
        or "какой день календаря" in lower
        or "день календаря" in lower
        or "сколько времени" in lower
        or "который час" in lower
        or "время сейчас" in lower
        or "текущее время" in lower
    ):
        command = "current_datetime"
    elif has_regulation_fact_question_intent:
        command = "fact_lookup"
    elif lookup_id and (
        "id" in lower or "ид" in lower or "покажи" in lower or "найди" in lower or "подними" in lower
    ):
        command = "id_lookup"
    elif (
        "добавь событие" in lower
        or "создай событие" in lower
        or "запланируй" in lower
        or "поставь в календарь" in lower
        or "добавь в календарь" in lower
        or "состоится" in lower
        or (
            ("напомни" in lower or "напомнить" in lower)
            and (
                "совещание" in lower
                or "встреч" in lower
                or "планерк" in lower
                or "планёрк" in lower
                or "событие" in lower
                or "звонок" in lower
            )
        )
    ):
        command = "calendar_create"
    elif "что сегодня" in lower or "события на сегодня" in lower or "календарь на сегодня" in lower:
        command = "calendar_list"
        calendar_range = "today"
    elif "что завтра" in lower or "события на завтра" in lower or "календарь на завтра" in lower:
        command = "calendar_list"
        calendar_range = "tomorrow"
    elif "календарь на неделю" in lower or "события на неделю" in lower or "что на неделю" in lower:
        command = "calendar_list"
        calendar_range = "week"
    elif (
        "какие события" in lower
        or "что в календаре" in lower
        or "что запланировано" in lower
        or "события добавлены" in lower
    ):
        command = "calendar_list"
        calendar_range = "all"
    elif (
        "кто чаще всего писал" in lower
        or "активность участников" in lower
        or "кто выкладывал фото" in lower
        or "кто выкладывал документы" in lower
        or "кто отправлял фото" in lower
        or "кто отправлял документы" in lower
    ):
        command = "participant_activity"
    elif "участники" in lower or "кто в группе" in lower or "люди в группе" in lower:
        command = "group_participants"
    elif "сводка" in lower or "самари" in lower or "итоги" in lower:
        command = "period_summary"
        summary_start_date = today_iso()
        summary_end_date = today_iso()

        if "вчера" in lower:
            summary_start_date = shift_date(-1)
            summary_end_date = shift_date(-1)
        elif "сегодня" in lower:
            summary_start_date = today_iso()
            summary_end_date = today_iso()
        else:
            month_range = parse_month_range_ru(lower)
            if month_range:
                summary_start_date = month_range["start"]
                summary_end_date = month_range["end"]
            else:
                range_match = re.search(
                    r"с\s+(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})\s+по\s+(\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2})",
                    lower,
                )
                if range_match:
                    summary_start_date = parse_date_ru(range_match.group(1)) or summary_start_date
                    summary_end_date = parse_date_ru(range_match.group(2)) or summary_end_date
                else:
                    single_date = parse_date_ru(lower)
                    if single_date:
                        summary_start_date = single_date
                        summary_end_date = single_date
    elif quote and (
        "документ" in lower or "содержание" in lower or "кратко" in lower or "что в" in lower
    ):
        command = "quoted_document_summary"
    elif (
        "подними" in lower
        or "найди" in lower
        or "покажи" in lower
        or "подробнее" in lower
        or "расскажи подробнее" in lower
        or "когда это было" in lower
        or "конкретные фото" in lower
        or "переписку" in lower
    ):
        command = "fact_lookup"
    elif "кто ты" in lower or "ты кто" in lower:
        command = "who_are_you"

    cleaned_user_message = re.sub(r"^алихан\s*", "", text, flags=re.IGNORECASE).strip()

    return {
        "command": command,
        "userMessage": cleaned_user_message or text,
        "text": text,
        "number": chat_id,
        "chatId": chat_id,
        "sender": sender,
        "messageId": message_id,
        "messageTimestamp": timestamp,
        "fromMe": from_me,
        "quotedDocumentMessageId": str(_get(data, ["contextInfo", "stanzaId"], "") or ""),
        "quotedDocumentFileName": str((quote or {}).get("fileName") or (quote or {}).get("title") or ""),
        "quotedDocumentMimeType": str((quote or {}).get("mimetype") or ""),
        "summaryStartDate": summary_start_date,
        "summaryEndDate": summary_end_date,
        "calendarRange": calendar_range,
        "lookupId": lookup_id,
        "docCompareOldId": doc_compare_old_id,
        "docCompareNewId": doc_compare_new_id,
        "docCompareIds": doc_compare_ids,
        "current_datetime": datetime.now(timezone.utc).isoformat(),
    }
