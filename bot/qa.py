"""QA module: is_qa(text) → bool, parse_qa(chat_id, text) → count"""
import sys, os, re
from datetime import datetime

EVO = "http://127.0.0.1:8080"
KEY = "SuperSecretKey_Grok2026_!@#"
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)

def is_qa(text):
    # Skip if it's a question (QA is for data submissions, not questions)
    if "?" in text or any(w in text.lower() for w in ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что", "как"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    # Also detect VOR code format: "2.1.5 = 100м3"
    if re.search(r'\d\.\d\.\d+\s*=', text):
        return True
    return False

def parse_qa(gid, text):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from handlers import ask_grok
        from db import get_conn
        from main_waha import send_msg  # keep for compatibility, but thin

        prompt = f"""Извлеки ВСЕ факты из ответа прораба. Каждый факт — отдельной строкой.
Формат: building | category | fact_text
building: АБК/Общежитие/общая
category: персонал/техника/инцидент/бетонирование/монтаж/земляные работы/документация
ВАЖНО: ИТР и рабочие — это РАЗНЫЕ факты. Если сказано «5 рабочих ИТР 2», извлеки ДВЕ строки:
общая | персонал | 5 рабочих
общая | персонал | ИТР 2 человека

{text[:3000]}

Только строки фактов, без пояснений."""
        result = ask_grok(prompt, max_tokens=500)
        conn = get_conn()
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for line in result.split("\n"):
            # First check for VOR code format
            vor_match = re.match(r'(\d\.\d\.\d+)\s*=\s*(\d+(?:\.\d+)?)\s*(\S*)', line.strip())
            if vor_match:
                code, vol, unit = vor_match.groups()
                cur.execute("INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                    (gid, today, 'общая', 'объём', f'{code} = {vol}{unit}'))
                count += 1
                continue
            # Then Grok format
            parts = [p.strip() for p in line.strip().split("|", 2)]
            if len(parts) >= 3 and len(line) > 10:
                cur.execute("INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                    (gid, today, parts[0], parts[1], parts[2]))
                count += 1
        conn.commit()
        cur.close(); conn.close()
        if count > 0:
            print(f"[QA] {count} facts saved from '{text[:60]}'", flush=True)
        else:
            print(f"[QA] 0 facts from '{text[:60]}'", flush=True)
        return count
    except Exception as e:
        print(f"[QA ERR] {e}", flush=True)
        return 0
