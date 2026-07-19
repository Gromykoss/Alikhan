import db, json, re, requests, os, sys
import db_memory
import json
import re
from datetime import datetime

import psycopg2.extras
import requests

import db
from secret_config import get_secret
from messaging import send_msg  # unified messaging (AUDIT-011)

# WAHA API
WAHA_URL = "http://127.0.0.1:3000"
WAHA_KEY = get_secret("WAHA_KEY", "WAHA_API_KEY")
XAI_URL = "https://api.x.ai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b"  # installed model (verified 17.07.2026)


def _load_keys():
    """Load evo_key and XAI_KEY from secrets.env, fallback to n8n workflow"""
    secrets = {}
    try:
        with open('/home/hermes-workspace/.hermes/secrets.env') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    secrets[k] = v
    except:
        pass
    evo = secrets.get('EVO_KEY', '')
    xai = secrets.get('XAI_API_KEY', secrets.get('XAI_KEY', ''))
    if not xai:
        try:
            with open('/home/hermes-workspace/Alikhan-migration/n8n-workflows/Алихан_AI-whatsApp_agent.json') as f:
                workflow = json.load(f)
            for node in workflow.get("nodes", []):
                headers = node.get("parameters", {}).get("headerParameters", {}).get("parameters", [])
                for header in headers:
                    if header.get("name") == "Authorization":
                        xai = str(header.get("value", "")).replace("Bearer ", "").strip()
                        if xai:
                            break
                if xai:
                    break
        except:
            pass
    return evo, xai

evo_key, XAI_KEY = _load_keys()


def _ctx(group, sender, payload):
    if isinstance(payload, dict):
        data = dict(payload)
    else:
        data = {"userMessage": str(payload or ""), "text": str(payload or "")}
    data.setdefault("chatId", group)
    data.setdefault("number", group)
    data.setdefault("sender", sender)
    data.setdefault("quotedDocumentFileName", payload.get("quotedDocumentFileName", ""))
    data.setdefault("quotedDocumentMimeType", payload.get("quotedDocumentMimeType", ""))
    data.setdefault("quotedDocumentMessageId", payload.get("quotedDocumentMessageId", ""))
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




def ask_ollama(prompt, system=None, max_tokens=700):
    """Ask local Ollama model. Falls back to Grok on failure."""
    try:
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        r = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens}
        }, timeout=120)
        if r.status_code == 200:
            resp = r.json().get("response", "").strip()
            if resp and len(resp) > 5:
                return resp
    except Exception as e:
        print(f"[OLLAMA ERR] {e}", flush=True)
    # Fallback to Grok
    return ask_grok_raw(prompt, system=system, max_tokens=max_tokens)


def ask_grok_raw(prompt, system=None, max_tokens=700, image_base64=None, mimetype="image/jpeg"):
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


def ask_grok(prompt, system=None, max_tokens=700, image_base64=None, mimetype="image/jpeg", force_grok=False):
    # Vision always needs Grok
    if image_base64 or force_grok:
        return ask_grok_raw(prompt, system=system, max_tokens=max_tokens,
                           image_base64=image_base64, mimetype=mimetype)
    return ask_ollama(prompt, system=system, max_tokens=max_tokens)


def _download_media_base64(message_id):
    # WAHA media download
    response = requests.get(
        f"{WAHA_URL}/api/alikhan/messages/{message_id}/download",
        headers={"X-Api-Key": WAHA_KEY},
        timeout=120,
    )
    if response.status_code == 200 and response.content:
        import base64 as b64
        return b64.b64encode(response.content).decode()
    return ""

def _get_base64_evolution(quoted_message_id):
    """Fetch base64 using Evolution API for a message by its ID"""
    import urllib.request, json
    import os
    # Load EVO config
    secrets = {}
    try:
        with open(os.path.expanduser('~/.hermes/secrets.env')) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    secrets[k] = v
    except:
        pass
    evo_key = secrets.get('EVO_KEY', '')
    evo_base = 'http://127.0.0.1:8080'
    try:
        # First find the full message
        body = json.dumps({"where": {"key": {"id": quoted_message_id}}, "page": 1, "limit": 1}).encode()
        req = urllib.request.Request(f"{evo_base}/chat/findMessages/alikhan", data=body, method='POST')
        req.add_header('apikey', evo_key)
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=10) as r:
            records = json.loads(r.read()).get('messages', {}).get('records', [])
        if not records:
            return ""
        # Now get base64
        body2 = json.dumps({"message": records[0]}).encode()
        req2 = urllib.request.Request(f"{evo_base}/chat/getBase64FromMediaMessage/alikhan", data=body2, method='POST')
        req2.add_header('apikey', evo_key)
        req2.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req2, timeout=120) as r2:
            data = json.loads(r2.read())
            return data.get("base64", "")
    except Exception as e:
        print("Evolution base64 error:", e)
    return ""


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
    text = ctx.get("userMessage", "").lower()
    
    # Try structured facts first for building/category queries
    if any(w in text for w in ["абк", "общежит", "бетон", "монтаж", "за неделю", "за месяц"]):
        try:
            building = "АБК" if "абк" in text else ("Общежитие" if "общежит" in text else None)
            from datetime import datetime, timedelta
            start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") if "недел" in text else None
            facts = db_memory.fact_lookup(group, building=building, start_date=start)
            if facts:
                lines = [f"{f['building'] or 'Общее'} | {f['category']} | {f['fact']} | {f['fact_date']}" for f in facts[:10]]
                prompt = f"Вопрос: {ctx.get('userMessage')}\nФакты:\n" + "\n".join(lines) + "\n\nОтветь кратко на основе фактов."
                send_msg(group, ask_grok(prompt, max_tokens=800))
                return
        except:
            pass
    
    # Fallback: raw message search
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
    send_msg(group, ask_grok(prompt, max_tokens=1200, force_grok=True))


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
    doc = ctx.get("document") or {"filename": ctx.get("quotedDocumentFileName", "неизвестный документ")}
    
    if not doc or not doc.get("filename"):
        # Try most recent document in DB
        try:
            rows = db.search_messages(group, "", limit=1)
            if rows and rows[0].get('content'):
                doc = {"filename": "последний документ в чате"}
                content = rows[0].get('content','')[:5000]
                prompt = f"Вопрос пользователя: {ctx.get('text','')}\\n\\nСодержание:{content}\\n\\nОтветь кратко по содержанию."
                send_msg(group, ask_grok(prompt, max_tokens=700))
                return
        except:
            pass
        send_msg(group, "Не вижу процитированный документ.")
        return
    
    filename = doc.get("filename", "")
    # For images: re-fetch from Evolution API and use vision
    if ctx.get("quotedDocumentMimeType", "").startswith("image/"):
        msg_id = ctx.get("quotedDocumentMessageId", "")
        b64 = _get_base64_evolution(msg_id) if msg_id else ""
        if b64:
            desc = ask_grok(
                "Ты — прораб на площадке ТЗРК Джеруй (Кыргызстан, 2700м). "
                "Опиши фото: этап работ, техника, люди, материалы. "
                "Нарушения ТБ/ООС/пожарки если есть. "
                "Здание НЕ угадывай — пиши «здание не определено». "
                "Пиши как прораб — коротко, по делу.",
                image_base64=b64, mimetype=ctx.get("quotedDocumentMimeType", "image/jpeg"), max_tokens=400
            )
            send_msg(group, desc)
            return
    # Search DB: try filename first, then caption as fallback
    search_terms = [
        filename.replace('.pdf','').replace('.PDF','')[:30],
        filename[:30],
        doc.get("caption", "")[:30],
        ctx.get("quotedDocumentMessageId", "")[:20]
    ]
    rows = []
    for q in search_terms:
        if q:
            try:
                rows = db.search_messages(group, q, limit=1)
                if rows and rows[0].get('content'):
                    break
            except:
                pass
    
    if rows and rows[0].get('content'):
        content = rows[0].get('content','')[:5000]
        prompt = f"Вопрос пользователя: {ctx.get('text','')}\\n\\nСодержание документа: {content}\\n\\nОтветь кратко."
        send_msg(group, ask_grok(prompt, max_tokens=700))
        return
    
    prompt = f"Пользователь просит прочитать документ: {filename}. Содержимое не найдено в памяти."
    send_msg(group, ask_grok(prompt, max_tokens=500))


def handle_who_are_you(group, sender, payload):
    send_msg(
        group,
        "Я Алихан — AI-ассистент в WhatsApp для проектной переписки. Помогаю искать по памяти, документам и календарю, делать сводки и отвечать по найденным фактам.",
    )


def handle_ai(group, sender, payload):
    ctx = _ctx(group, sender, payload)
    send_msg(group, ask_grok(ctx.get("userMessage") or ctx.get("text") or ""))

def handle_daily_snapshot(group, sender, payload):
    """Use the in-process generate_daily_snapshot from main_waha (AUDIT-007: daily_snapshot.py removed)."""
    try:
        from main_waha import generate_daily_snapshot as _gen_snapshot
        _gen_snapshot(group)
    except Exception as e:
        send_msg(group, f"Ошибка снимка: {e}")

def handle_weather(group, sender, payload):
    import urllib.request, re
    try:
        req = urllib.request.Request("https://wttr.in/42.2,72.5?format=%C+%t+%w+%h+%P&lang=ru")
        with urllib.request.urlopen(req, timeout=10) as r:
            weather = r.read().decode().strip()
        # Convert hPa to mmHg: 1 hPa = 0.75006 mmHg
        m = re.search(r'(\d+)\s*(?:hPa|гПа)', weather)
        if m:
            hpa = int(m.group(1))
            mmhg = round(hpa * 0.75006)
            weather = re.sub(r'\d+\s*(?:hPa|гПа)', f'{mmhg} мм рт.ст.', weather)
        send_msg(group, f"🌤 ТЗРК Джеруй: {weather}")
    except Exception as e:
        send_msg(group, f"Не смог получить погоду: {e}")


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
    "daily_snapshot": handle_daily_snapshot,
    "weather": handle_weather,
    "ai": handle_ai,
    "photo": handle_photo,
    "document": handle_document,
}
