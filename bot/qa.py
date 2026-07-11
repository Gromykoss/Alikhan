"""QA module: is_qa(text) → bool, parse_qa(gid, text) → count"""
import sys, os, re
from datetime import datetime
from secret_config import get_evo_key

EVO = "http://127.0.0.1:8080"
KEY = get_evo_key(required=True)
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)


def is_qa(text):
    # Skip if it's a question (QA is for data submissions, not questions)
    if "?" in text or any(w in text.lower() for w in ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что", "как"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "сделано", "не успели", "техник",
                "материал", "постав", "документац", "план на", "план работ"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    # Also detect VOR code format: "2.1.5 = 100м3" or "2.2.3.2 — описание"
    if re.search(r'\d\.\d\.\d+(\s*[=—–\-]\s*|\s+)', text):
        return True
    return False


def _parse_no_patterns(text):
    """Simple 'no X' patterns that Grok can't parse."""
    t = text.lower()
    patterns = [
        (r'материалов?\s*нет', 'общая|документация|Поставок материалов нет'),
        (r'поставок?\s*нет', 'общая|документация|Поставок материалов нет'),
        (r'техник[аи]?\s*нет', 'общая|техника|Техники нет'),
        (r'происшествий?\s*нет', 'общая|инцидент|Происшествий нет'),
        (r'инцидентов?\s*нет', 'общая|инцидент|Происшествий нет'),
    ]
    lines = []
    for pat, fact in patterns:
        if re.search(pat, t):
            lines.append(fact)
    return '\n'.join(lines)


def _extract_vor_codes(text):
    """Extract VOR codes (3-part and 4-part) from the original user text.
    Returns (volume_facts, remaining_text).
    volume_facts: list of dicts with code, volume, unit, is_plan
    remaining_text: original text with VOR code segments removed.

    Handles patterns like:
      "3.3.2 = 104.3"              → work (объём)
      "Планы 3.3.2 = 104.3"        → plan (план)
      "план 3.3.2 = 104.3"         → plan
      "Прочее 3.3.2 = 104.3"       → work
      "7.2.1.1 = 1.5м3"            → work (4-part code)
      "Планы 3.3.2 = 104.3 м3"     → plan with unit
    """
    facts = []
    remaining = text

    # Match VOR code segments: optional prefix (Планы/план/Прочее/сделано etc),
    # code (3 or 4 part), = or —, volume, optional unit suffix.
    # The unit suffix is explicitly matched against known measurement units.
    # This avoids eating Russian words like "Планы" that may appear immediately
    # after the unit (e.g. "1.5 м3Планы 3.3.2 = 104.3").

    UNIT_PATTERN = r'(?:м[23³]|м3|м2|кг|т|шт|км|пог\.?\s*м|л|мл|кв\.?\s*м|чел|чел\.|час|ч|день|дн\.)?'
    # Full pattern in parts so we can reference groups by number:
    pattern = re.compile(
        r'('                          # Group 1: optional plan/prefix
        r'\w*[Пп]лан\w*'
        r'|\b[Пп]рочее\b'
        r'|\b[Сс]делано\b'
        r'|\b[Нн]е\s*успели\b'
        r'|\w*[Оо]бъём\b'
        r')?'                          # End group 1
        r'\s*'
        r'(\d+\.\d+\.\d+(?:\.\d+)?)'  # Group 2: VOR code
        r'\s*[=—–\-]\s*'
        r'(\d+(?:[.,]\d+)?)'           # Group 3: volume
        r'\s*'
        r'(' + UNIT_PATTERN + r')'     # Group 4: unit
    )

    def remove_first_match(text, m):
        """Remove the matched segment (including surrounding whitespace) from text."""
        return text[:m.start()].rstrip() + ' ' + text[m.end():].lstrip()

    while True:
        m = pattern.search(remaining)
        if not m:
            break
        prefix = (m.group(1) or '').strip()
        code = m.group(2)
        vol_str = m.group(3).replace(',', '.')
        unit = (m.group(4) or '').strip()
        vol = float(vol_str)

        # Detect plan: Планы, план, плановый etc.
        is_plan = bool(re.search(r'[Пп]лан', prefix))

        # Determine category
        if is_plan:
            category = 'план'
        else:
            category = 'объём'

        # Build fact text preserving the original prefix (crucial for downstream plan detection)
        if prefix:
            fact_text = f"{prefix} {code} = {vol_str}{unit}".strip()
        else:
            fact_text = f"{code} = {vol_str}{unit}".strip()

        facts.append({
            'code': code,
            'volume': vol,
            'unit': unit,
            'fact': fact_text,
            'category': category,
            'is_plan': is_plan,
        })

        # Remove the matched segment from remaining text
        remaining = remove_first_match(remaining, m)

    # Clean up extra whitespace and punctuation artifacts
    remaining = re.sub(r'^[.\s,;:]+', '', remaining).strip()
    remaining = re.sub(r'[.\s,;:]+$', '', remaining).strip()
    remaining = ' '.join(remaining.split()).strip()

    return facts, remaining


def parse_qa(gid, text, date_str=None):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from handlers import ask_grok
        from db import get_conn

        # Step 1: Extract VOR codes from the ORIGINAL text using regex — NO LLM involved
        vor_facts, remaining_text = _extract_vor_codes(text)

        if vor_facts:
            print(f"[QA VOR] Extracted {len(vor_facts)} VOR codes directly: {[f['code'] for f in vor_facts]}", flush=True)
            for f in vor_facts:
                print(f"  {f['fact']} → category={f['category']}", flush=True)

        # Step 2: Send ONLY the remaining text (personnel/incidents/equipment) to Grok
        # If remaining text is empty or only whitespace, skip Grok
        grok_input = remaining_text[:3000] if remaining_text.strip() else ""
        
        grok_result = ""
        if grok_input:
            print(f"[QA] Sending to Grok (VOR-free): '{grok_input[:100]}...'", flush=True)
            prompt = f"""Извлеки ВСЕ факты из ответа прораба. Каждый факт — отдельной строкой.
Формат: building | category | fact_text
building: АБК/Общежитие/общая
category: персонал/техника/инцидент/бетонирование/монтаж/земляные работы/документация
ВАЖНО: ИТР и рабочие — это РАЗНЫЕ факты. Если сказано «Атантай ИТР 1, рабочих 6», извлеки ДВЕ строки С НАЗВАНИЕМ ПОДРЯДЧИКА:
общая | персонал | Атантай ИТР 1
общая | персонал | Атантай 6 рабочих

{grok_input}

Только строки фактов, без пояснений."""
            grok_result = ask_grok(prompt, max_tokens=500)

        conn = get_conn()
        cur = conn.cursor()
        today = date_str or datetime.now().strftime("%Y-%m-%d")
        count = 0

        # Step 3: Save VOR codes directly (no LLM involved — prevents hallucination)
        for f in vor_facts:
            cur.execute(
                "INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                (gid, today, 'общая', f['category'], f['fact'])
            )
            count += 1

        # Step 4: Process Grok results for personnel/incidents/equipment
        if grok_result:
            for line in grok_result.split("\n"):
                parts = [p.strip() for p in line.strip().split("|", 2)]
                if len(parts) >= 3 and len(line) > 10:
                    cur.execute(
                        "INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                        (gid, today, parts[0], parts[1], parts[2])
                    )
                    count += 1

        # Fallback: if nothing was saved, try simple "нет" patterns
        if count == 0:
            for line in _parse_no_patterns(text).split("\n"):
                parts = [p.strip() for p in line.strip().split("|", 2)]
                if len(parts) >= 3:
                    cur.execute(
                        "INSERT INTO bot_memory_facts (chat_id,fact_date,building,category,fact,source) VALUES (%s,%s,%s,%s,%s,'qa')",
                        (gid, today, parts[0], parts[1], parts[2])
                    )
                    count += 1

        conn.commit()
        cur.close()
        conn.close()
        if count > 0:
            print(f"[QA] {count} facts saved from '{text[:60]}'", flush=True)
        else:
            print(f"[QA] 0 facts from '{text[:60]}'", flush=True)
        return count
    except Exception as e:
        print(f"[QA ERR] {e}", flush=True)
        return 0
