"""Router module: route(text) → action and reply"""
import re, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VOICE_TRIGGERS = ["голосом", "озвучь", "голос"]
SANDBOX = "120363179621030401@g.us"

def route(text, chat_id, sender=""):
    """Returns (action, reply, voice_triggered)."""
    from handlers import ask_grok

    # 1. QA
    from qa import is_qa, parse_qa
    if is_qa(text):
        count = parse_qa(chat_id, text)
        if count > 0:
            return "QA", f"✅ Принято: {count} фактов", False

    # 2. Name check
    if not re.search(r'[ао]л[еи][хгк]', text.lower()):
        return "IGNORE", "", False

    # 3. Voice trigger
    voice = any(w in text.lower() for w in VOICE_TRIGGERS)

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
    try:
        from verify import verify_reply
        reply, score, issues = verify_reply(reply, text, db_reply)
    except Exception as e:
        print(f"[VERIFY ERR] {e}", flush=True)

    return action, reply, voice
