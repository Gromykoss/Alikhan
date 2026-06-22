import base64
import json
import re
from datetime import datetime

import psycopg2.extras
import requests

import db

EVO_URL = "http://127.0.0.1:8080"
XAI_URL = "https://api.x.ai/v1/chat/completions"


def _load_evo_key():
    with open("/tmp/evo_key.txt") as f:
        return f.read().strip()


def _load_xai_key():
    try:
        with open("/home/hermes-workspace/Alikhan-migration/n8n-workflows/Алихан_AI-whatsApp_agent.json") as f:
            workflow = json.load(f)
    except FileNotFoundError:
        return ""

    for node in workflow.get("nodes", []):
        headers = node.get("parameters", {}).get("headerParameters", {}).get("parameters", [])
        for header in headers:
            if header.get("name") == "Authorization":
                return str(header.get("value", "")).replace("Bearer ", "").strip()
    return ""


EVO_KEY = _load_evo_key()
XAI_KEY = _load_xai_key()


def _ctx(group, sender, payload):
    if isinstance(payload, dict):
        data = dict(payload)
    else:
        data = {"userMessage": str(payload or ""), "text": str(payload or "")}
    data.setdefault("chatId", group)
    data.setdefault("number", group)
    data.setdefault("sender", sender)
    data.setdefault("userMessage", data.get("text", ""))
    return data


def _fmt_dt(value):
    if not value:
        return "не указано"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _clean_json(raw):
    return re.sub(r"^```(?:json)?|```$", "", str(raw or "").strip(), flags=re.IGNORECASE).strip()


def _extract_json(raw):
    cleaned = _clean_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def send_msg(group, text):
    requests.post(
        f"{EVO_URL}/message/sendText/alikhan",
        headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
        json={"number": group, "text": str(text or "")[:4000]},
    )


def ask_grok(prompt, system=None, max_tokens=700, image_base64=None, mimetype="image/jpeg"):
    user_content = prompt
    if image_base64:
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mimetype};base64,{image_base64}"}},
        ]

    response = requests.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {XAI_KEY}", "Content-Type": "application/json"},
        json={
            "model": "grok-4-latest",
            "messages": [
                {
                    "role": "system",
                    "content": system
                    or "Ты Алихан — AI-ассистент в WhatsApp. Отвечай кратко, дружелюбно, на русском. Помогаешь с задачами, календарём, документами и памятью проекта.",
                },
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens,
        },
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    return "Извини, сейчас не могу получить ответ от AI."


def _download_media_base64(message_id):
    response = requests.post(
        f"{EVO_URL}/chat/getBase64FromMediaMessage/alikhan",
        headers={"apikey": EVO_KEY, "Content-Type": "application/json"},
        json={"message": {"key": {"id": message_id}}},
    )
    if response.status_code != 200:
        return ""
    data = response.json()
    return (
        data.get("base64")
        or data.get("data", {}).get("base64")
        or data.get("media")
        or data.get("result", {}).get("base64")
        or ""
    )


def _fact_rows(chat_id, query, lookup_id=""):
    conn = db.get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if lookup_id:
        cur.execute(
            """
            SELECT id, sender, role, message_type, file_name, COALESCE(message_time, created_at) AS item_time, content
            FROM bot_memory_messages
            WHERE id = %s
            LIMIT 1
            """,
            (lookup_id,),
        )
    else:
        terms = [t for t in re.split(r"[^a-zA-Zа-яА-ЯёЁ0-9]+", query.lower()) if len(t) > 2]
        terms = [t for t in terms if t not in {"алихан", "покажи", "найди", "подними", "расскажи", "подробнее"}]
        if not terms:
            terms = [query.strip()]
        cur.execute(
            """
            SELECT id, sender, role, message_type, file_name, COALESCE(message_time, created_at) AS item_time, content
            FROM bot_memory_messages
            WHERE (chat_id = %s OR chat_id = 'project:main')
              AND (
                EXISTS (
                  SELECT 1 FROM unnest(%s::text[]) AS term
                  WHERE lower(COALESCE(content, '')) LIKE '%%' || term || '%%'
                     OR lower(COALESCE(file_name, '')) LIKE '%%' || term || '%%'
                )
                OR message_type = 'document'
              )
            ORDER BY
              CASE WHEN message_type = 'document' THEN 1 ELSE 2 END,
              COALESCE(message_time, created_at) DESC
            LIMIT 12
            """,
            (chat_id, terms),
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def handle_only_name(group, sender, payload):
    send_msg(
        group,
        "Я на связи.",
    )


def handle_memory_status(group, sender, payload):
    conn = db.get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE chat_id = 'project:main' AND message_type = 'text') AS project_text_messages,
            COUNT(*) FILTER (WHERE chat_id = 'project:main' AND message_type = 'image') AS project_image_messages,
            COUNT(*) FILTER (WHERE chat_id = 'project:main' AND message_type = 'document') AS project_document_messages,
            COUNT(*) FILTER (WHERE chat_id = %s) AS current_chat_messages,
            COUNT(*) AS total_messages
        FROM bot_memory_messages
        """,
        (group,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    send_msg(
        group,
        "\n".join(
            [
                "Статус памяти:",
                f"Всего записей: {row['total_messages']}",
                f"Текущий чат: {row['current_chat_messages']}",
                f"Проектный архив: текст={row['project_text_messages']}, фото={row['project_image_messages']}, документы={row['project_document_messages']}",
            ]
        ),
    )


def handle_calendar_delete(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    event_id = ctx.get("lookupId")
    if not event_id:
        send_msg(group, "Укажи ID события, которое нужно удалить.")
        return
    row = db.delete_calendar_event(group, event_id)
    if not row:
        send_msg(group, f"Активное событие с ID {event_id} не найдено.")
        return
    send_msg(
        group,
        f"Событие удалено.\n\nID: {row['id']}\nНазвание: {row['title']}\nКогда: {_fmt_dt(row['event_start'])}\nГде: {row.get('location') or 'не указано'}",
    )


def handle_document_compare(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    old_id = ctx.get("docCompareOldId")
    new_id = ctx.get("docCompareNewId")
    if not old_id or not new_id:
        send_msg(group, "Для сравнения нужны два ID документов.")
        return

    old_doc = db.get_message_by_id(old_id)
    new_doc = db.get_message_by_id(new_id)
    if not old_doc or not new_doc:
        missing = []
        if not old_doc:
            missing.append(f"старый документ ID {old_id}")
        if not new_doc:
            missing.append(f"новый документ ID {new_id}")
        send_msg(group, "Не найден: " + ", ".join(missing) + ".")
        return

    prompt = "\n".join(
        [
            f"Старый документ: ID {old_id}, файл {old_doc.get('file_name') or 'без имени файла'}",
            f"Новый документ: ID {new_id}, файл {new_doc.get('file_name') or 'без имени файла'}",
            "",
            "Сравни строго старый документ с новым. Не фантазируй.",
            "Выведи: 1) краткий вывод; 2) что появилось; 3) что изменилось; 4) что удалено; 5) что сделать проектной команде.",
            "",
            "СТАРЫЙ ДОКУМЕНТ:",
            str(old_doc.get("content") or "")[:70000],
            "",
            "НОВЫЙ ДОКУМЕНТ:",
            str(new_doc.get("content") or "")[:70000],
        ]
    )
    answer = ask_grok(prompt, max_tokens=1600)
    send_msg(
        group,
        f"Сравнение документов:\nСтарый документ: ID {old_id}\nНовый документ: ID {new_id}\n\n{answer}",
    )


def handle_current_datetime(group, sender, payload):
    from datetime import timezone, timedelta
    msk = timezone(timedelta(hours=3))
    now = datetime.now(msk)
    send_msg(group, f"Сейчас: {now.strftime('%Y-%m-%d %H:%M:%S')} (МСК).")


def handle_fact_lookup(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    rows = _fact_rows(group, ctx.get("userMessage", ""), ctx.get("lookupId", ""))
    if not rows:
        send_msg(group, "В памяти не нашёл подходящих фактов.")
        return
    facts = "\n\n---\n\n".join(
        [
            f"SOURCE_ID: {r['id']}\nDOCUMENT: {r.get('file_name') or 'без файла'}\nTYPE: {r.get('message_type')}\nTIME: {_fmt_dt(r.get('item_time'))}\nCONTENT: {str(r.get('content') or '')[:12000]}"
            for r in rows
        ]
    )
    prompt = "\n".join(
        [
            "Ответь на вопрос пользователя строго по найденным документам и памяти проекта Алихан.",
            f"Вопрос: {ctx.get('userMessage', '')}",
            "Обязательно указывай ID источников. Если данных недостаточно, скажи прямо.",
            "",
            "НАЙДЕННЫЕ ДОКУМЕНТЫ И ФАКТЫ:",
            facts,
        ]
    )
    send_msg(group, ask_grok(prompt, max_tokens=1200))


def handle_id_lookup(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    msg_id = ctx.get("lookupId")
    row = db.get_message_by_id(msg_id)
    if not row:
        send_msg(group, f"ID {msg_id} не найден.")
        return
    content = str(row.get("content") or "")
    send_msg(
        group,
        "\n".join(
            [
                f"ID {row['id']}",
                f"Время: {_fmt_dt(row.get('item_time'))}",
                f"Отправитель: {row.get('sender') or 'unknown'}",
                f"Тип: {row.get('message_type') or 'text'}",
                f"Файл: {row.get('file_name') or 'нет'}",
                "",
                content[:3000] or "[пустое содержимое]",
            ]
        ),
    )


def handle_calendar_create(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    prompt = "\n".join(
        [
            "Извлеки событие календаря из текста пользователя.",
            "Верни только JSON без markdown.",
            "Поля: title, description, location, date, time, timezone, event_end_date, event_end_time, remind_minutes_before.",
            "date в YYYY-MM-DD, time в HH:MM. Если часовой пояс не указан, Asia/Bishkek.",
            f"Текущая дата и время: {datetime.now().isoformat()}",
            f"Текст: {ctx.get('userMessage', '')}",
        ]
    )
    raw = ask_grok(prompt, max_tokens=500)
    try:
        event = _extract_json(raw)
    except Exception:
        send_msg(group, "Не смог разобрать событие. Напиши дату и время явно.")
        return

    if not event.get("date") or not event.get("time"):
        send_msg(group, "Не хватает даты или времени события.")
        return

    row = db.insert_calendar_event(
        {
            "chat_id": group,
            "created_by": sender,
            "source_message_id": ctx.get("messageId", ""),
            "title": event.get("title") or "Событие",
            "description": event.get("description") or event.get("title") or "Событие",
            "location": event.get("location") or "",
            "date": event.get("date") or "",
            "time": event.get("time") or "",
            "timezone": event.get("timezone") or "Asia/Bishkek",
            "event_end_date": event.get("event_end_date") or "",
            "event_end_time": event.get("event_end_time") or "",
            "remind_minutes_before": event.get("remind_minutes_before"),
        }
    )
    send_msg(
        group,
        f"Событие добавлено.\n\nID: {row['id']}\nНазвание: {row['title']}\nКогда: {_fmt_dt(row['event_start'])} ({row['timezone']})\nГде: {row.get('location') or 'не указано'}",
    )


def handle_calendar_list(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    calendar_range = ctx.get("calendarRange", "all")
    rows = db.get_calendar_events(group, calendar_range)
    labels = {"today": "сегодня", "tomorrow": "завтра", "week": "неделю", "all": "все будущие"}
    if not rows:
        send_msg(group, f"Активных событий на {labels.get(calendar_range, 'выбранный период')} нет.")
        return
    lines = [f"События на {labels.get(calendar_range, 'выбранный период')}:"]
    for row in rows[:20]:
        lines.extend(
            [
                "",
                f"ID {row['id']}",
                f"Время: {_fmt_dt(row['event_start'])} ({row.get('timezone') or 'timezone не указан'})",
                f"Название: {row['title']}",
                f"Где: {row.get('location') or 'не указано'}",
            ]
        )
    send_msg(group, "\n".join(lines))


def handle_participant_activity(group, sender, payload):
    rows = db.get_participant_activity(group)
    if not rows:
        send_msg(group, "Данных по активности участников пока нет.")
        return
    lines = ["Активность участников:"]
    for row in rows[:30]:
        lines.append(
            f"{row['sender']} — всего: {row['total_messages']}, текст: {row['text_messages']}, фото: {row['image_messages']}, документы: {row['document_messages']}"
        )
    send_msg(group, "\n".join(lines))


def handle_group_participants(group, sender, payload):
    rows = db.get_participants(group)
    if not rows:
        send_msg(group, "Участники пока не накоплены.")
        return
    lines = ["Участники:"]
    for row in rows[:50]:
        lines.append(
            f"{row['source_label']}: {row['push_name']} — сообщений: {row['message_count']}, последний раз: {_fmt_dt(row['last_seen'])}"
        )
    send_msg(group, "\n".join(lines))


def handle_period_summary(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    start = ctx.get("summaryStartDate") or datetime.now().date().isoformat()
    end = ctx.get("summaryEndDate") or start
    rows = db.get_messages_by_date_range(group, start, end)
    if not rows:
        send_msg(group, f"За период {start} - {end} сообщений не найдено.")
        return
    data = "\n".join(
        [
            f"ID {r['id']} | {_fmt_dt(r['item_time'])} | {r.get('sender') or 'unknown'} | {r.get('message_type') or 'text'} | {str(r.get('content') or '')[:900]}"
            for r in rows[:300]
        ]
    )
    prompt = "\n".join(
        [
            f"Сделай краткую сводку переписки за период {start} - {end}.",
            "Выведи: 1) главные события; 2) работы/материалы/техника; 3) риски с ID источников; 4) документы и фото; 5) активные участники; 6) что требует внимания.",
            "",
            data[:70000],
        ]
    )
    send_msg(group, ask_grok(prompt, max_tokens=1400))


def handle_quoted_document_summary(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    msg_id = ctx.get("quotedDocumentMessageId") or ctx.get("lookupId")
    if not msg_id:
        send_msg(group, "Не вижу процитированный документ.")
        return
    row = db.get_message_by_id(msg_id) if str(msg_id).isdigit() else None
    if not row:
        send_msg(group, "Не нашёл процитированный документ в памяти. Можно прислать его ID.")
        return
    prompt = f"Кратко перескажи документ, выдели назначение, ключевые требования и риски.\n\n{str(row.get('content') or '')[:70000]}"
    send_msg(group, ask_grok(prompt, max_tokens=1000))


def handle_who_are_you(group, sender, payload):
    send_msg(
        group,
        "Я Алихан — AI-ассистент в WhatsApp для проектной переписки. Помогаю искать по памяти, документам и календарю, делать сводки и отвечать по найденным фактам.",
    )


def handle_ai(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    send_msg(group, ask_grok(ctx.get("userMessage") or ctx.get("text") or ""))


def handle_photo(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    message_id = ctx.get("messageId", "")
    media = _download_media_base64(message_id) if message_id else ""
    if not media:
        send_msg(group, "Фото получил, но не смог скачать изображение для анализа.")
        return
    answer = ask_grok(
        "Опиши фото по делу: что видно, какие работы/риски/документы можно распознать. Отвечай кратко.",
        image_base64=media,
        mimetype=ctx.get("mimetype", "image/jpeg"),
        max_tokens=900,
    )
    try:
        db.save_message(group, sender, "user", answer, "image")
    except Exception:
        pass
    send_msg(group, answer)


def handle_document(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    file_name = ctx.get("fileName") or "document"
    caption = ctx.get("caption") or ""
    media = _download_media_base64(ctx.get("messageId", "")) if ctx.get("messageId") else ""
    text = caption
    if media:
        try:
            decoded = base64.b64decode(media, validate=False)
            text = decoded[:120000].decode("utf-8", errors="ignore") or caption
        except Exception:
            text = caption
    content = f"Файл: {file_name}\n\n{text}".strip()
    try:
        db.save_message(group, sender, "user", content, "document")
    except Exception:
        pass
    summary = ask_grok(f"Кратко опиши документ и что в нём важно:\n\n{content[:70000]}", max_tokens=900)
    send_msg(group, summary)


HANDLERS = {
    "only_name": handle_only_name,
    "memory_status": handle_memory_status,
    "calendar_delete": handle_calendar_delete,
    "document_compare": handle_document_compare,
    "current_datetime": handle_current_datetime,
    "fact_lookup": handle_fact_lookup,
    "id_lookup": handle_id_lookup,
    "calendar_create": handle_calendar_create,
    "calendar_list": handle_calendar_list,
    "participant_activity": handle_participant_activity,
    "group_participants": handle_group_participants,
    "period_summary": handle_period_summary,
    "quoted_document_summary": handle_quoted_document_summary,
    "who_are_you": handle_who_are_you,
    "ai": handle_ai,
    "photo": handle_photo,
    "document": handle_document,
}
