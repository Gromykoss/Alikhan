"""QA module: is_qa(text) → bool, parse_qa(gid, text) → count

v2.1 (2026-07-18): RAG fixes from P1P2 report
  - Building/category validation (hallucination guard)
  - Few-shot prompt with examples
  - Retry + audit log for Grok failures
"""
import sys, os, re, time, json as _json, traceback
from datetime import datetime, timezone, timedelta
from config import EVO, KEY, SENDER_TO_CONTRACTOR  # Bridge API (was bridge_wrapper, removed)
SANDBOX = os.environ.get("WHATSAPP_SANDBOX", "")

BISHKEK_TZ = timezone(timedelta(hours=6))

sys.stdout.reconfigure(line_buffering=True)

# ─── Validation sets ─────────────────────────────────────────────────────────
ALLOWED_BUILDINGS = {'АБК', 'Общежитие', 'общая'}
ALLOWED_CATEGORIES = {
    'персонал', 'техника', 'инцидент', 'бетонирование', 'монтаж',
    'земляные работы', 'документация', 'материалы', 'план', 'объём'
}
ALLOWED_CONTRACTORS = ['айбикон', 'атантай', 'майкадам', 'наватек']

WORKER_POSITION_RE = re.compile(
    r'(?:рабоч|работник|монтажник|монолитчик|каменщик|бетонщик|маляр|'
    r'арматурщик|сварщик|штукатур|плотник|отделочник|электрик|сантехник|'
    r'разнорабоч|подсобн)',
    re.I,
)

# Default for unknown buildings
DEFAULT_BUILDING = 'общая'

# ─── Audit log helper ────────────────────────────────────────────────────────

def _audit_log(entry_type, data):
    """Log parsing attempts to /tmp/alikhan_qa_audit.log for post-hoc analysis."""
    try:
        entry = {
            'ts': datetime.now(BISHKEK_TZ).isoformat(),
            'type': entry_type,
            **data
        }
        with open('/tmp/alikhan_qa_audit.log', 'a') as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f"[QA AUDIT] Failed to write audit log: {e}", flush=True)  # audit log is best-effort


# ─── is_qa detection ─────────────────────────────────────────────────────────

def is_qa(text):
    # Skip if it's a question (QA is for data submissions, not questions)
    if "?" in text or any(w in text.lower() for w in ["сколько", "какой", "какая", "какие", "кто", "где", "когда", "зачем", "почему", "что", "как"]):
        return False
    triggers = ["айбикон", "атантай", "майкадам", "наватек", "итр", "рабочих", "водител",
                "происшестви", "инцидент", "сделано", "не успели", "техник",
                "материал", "постав", "документац", "план на", "план работ",
                "бетонировани", "монтаж", "земляные работы"]
    if sum(1 for t in triggers if t in text.lower()) >= 1:
        return True
    # Also detect VOR code format: "2.1.5 = 100м3" or "2.2.3.2 — описание"
    if re.search(r'\d\.\d\.\d+(\s*[=—–\-]\s*|\s+)', text):
        return True
    return False


# ─── Validation helpers ──────────────────────────────────────────────────────

def validate_building(value):
    """Return validated building or DEFAULT_BUILDING. Logs hallucinated values."""
    if not value or not isinstance(value, str):
        return DEFAULT_BUILDING
    v = value.strip()
    if v in ALLOWED_BUILDINGS:
        return v
    # Fuzzy match: 'абк' → 'АБК', 'общежитие' → 'Общежитие'
    v_lower = v.lower()
    for allowed in ALLOWED_BUILDINGS:
        if allowed.lower() == v_lower:
            return allowed
    # Hallucinated building — log and replace
    print(f"[QA VALIDATE] Rejected hallucinated building: '{v}' → '{DEFAULT_BUILDING}'", flush=True)
    _audit_log('hallucinated_building', {'rejected': v, 'replaced_with': DEFAULT_BUILDING})
    return DEFAULT_BUILDING


def validate_category(value):
    """Return validated category or None. Returns None for unknown categories."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in ALLOWED_CATEGORIES:
        return v
    # Fuzzy match common misspellings
    fuzzy_map = {
        'персона': 'персонал', 'персонала': 'персонал',
        'техник': 'техника', 'инциденты': 'инцидент',
        'бетон': 'бетонирование',
        'монтажные работы': 'монтаж',
        'земляные': 'земляные работы', 'земля': 'земляные работы',
        'документы': 'документация', 'док-ты': 'документация',
        'материал': 'материалы', 'материалы': 'материалы',
        'поставка': 'материалы', 'поставки': 'материалы',
        'план работ': 'план',
    }
    # Never map materials → documentation (explicit category)
    if v in ('материалы', 'материал', 'поставка', 'поставки'):
        return 'материалы'
    if v in fuzzy_map:
        return fuzzy_map[v]
    # Hallucinated category — reject
    print(f"[QA VALIDATE] Rejected hallucinated category: '{value}'", flush=True)
    _audit_log('hallucinated_category', {'rejected': value})
    return None


def validate_personnel_fact(fact_text, sender=None):
    """Personnel facts must contain contractor or come from a mapped sender."""
    if not fact_text:
        return False
    if any(cnt in fact_text.lower() for cnt in ALLOWED_CONTRACTORS):
        return True
    return bool(sender and SENDER_TO_CONTRACTOR.get(sender))


def _contractor_from_fact_or_sender(fact_text, sender=None):
    fact_lower = (fact_text or '').lower()
    for cnt in ALLOWED_CONTRACTORS:
        if cnt in fact_lower:
            return cnt
    if sender:
        return SENDER_TO_CONTRACTOR.get(sender)
    return None


def _position_from_personnel_fact(fact_text):
    fact_lower = (fact_text or '').lower()
    if 'итр' in fact_lower:
        return 'ИТР'
    if WORKER_POSITION_RE.search(fact_lower):
        return 'Рабочие'
    return 'Сотрудник'


# ─── Simple pattern fallback ─────────────────────────────────────────────────

def _parse_no_patterns(text):
    """Simple 'no X' patterns that Grok can't parse."""
    t = text.lower()
    patterns = [
        (r'материалов?\s*нет', 'общая|материалы|Поставок материалов нет'),
        (r'поставок?\s*нет', 'общая|материалы|Поставок материалов нет'),
        (r'техник[аи]?\s*нет', 'общая|техника|Техники нет'),
        (r'происшествий?\s*нет', 'общая|инцидент|Происшествий нет'),
        (r'инцидентов?\s*нет', 'общая|инцидент|Происшествий нет'),
    ]
    lines = []
    for pat, fact in patterns:
        if re.search(pat, t):
            lines.append(fact)
    return '\n'.join(lines)


def _parse_personnel_fallback(text):
    """Regex personnel extractor for Grok/pipe failure.

    Returns list of (org_name, position, count) tuples.
    Handles: «Майкадам ИТР 1, рабочих 6», «Атантай 8 рабочих», «айбикон итр 2».
    """
    t = text.lower().replace('ё', 'е')
    results = []
    for org in ALLOWED_CONTRACTORS:
        o = re.escape(org)
        for m in re.finditer(rf'{o}\s+итр\s*(\d+)|{o}\s+(\d+)\s*итр', t, re.I):
            n = next((int(g) for g in m.groups() if g), None)
            if n:
                results.append((org, 'ИТР', n))
        for m in re.finditer(rf'{o}\s+(\d+)\s*рабоч|{o}\s*рабоч\w*\s*(\d+)', t, re.I):
            n = next((int(g) for g in m.groups() if g), None)
            if n:
                results.append((org, 'Рабочие', n))
        m = re.search(rf'{o}\s+итр\s*(\d+)[,\s]+рабоч\w*\s*(\d+)', t, re.I)
        if m:
            results.append((org, 'ИТР', int(m.group(1))))
            results.append((org, 'Рабочие', int(m.group(2))))
        m2 = re.search(rf'{o}\s+(\d+)\s*итр[,\s]+(\d+)\s*рабоч', t, re.I)
        if m2:
            results.append((org, 'ИТР', int(m2.group(1))))
            results.append((org, 'Рабочие', int(m2.group(2))))
    best = {}
    for org, pos, n in results:
        key = (org, pos)
        if key not in best or n > best[key]:
            best[key] = n
    return [(o, p, n) for (o, p), n in best.items()]


def _parse_sender_personnel_fallback(text, sender=None):
    """Parse personnel lines without contractor when sender has a contractor mapping."""
    org_name = SENDER_TO_CONTRACTOR.get(sender) if sender else None
    if not org_name:
        return []

    results = []
    for raw_line in text.splitlines():
        line = raw_line.strip().lower().replace('ё', 'е')
        if not line:
            continue
        m = re.match(
            r'^(итр|рабоч\w*|работник\w*|монтажник\w*|монолитчик\w*|'
            r'каменщик\w*|бетонщик\w*|маляр\w*|арматурщик\w*|сварщик\w*|'
            r'штукатур\w*|плотник\w*|отделочник\w*|электрик\w*|сантехник\w*|'
            r'разнорабоч\w*|подсобн\w*)\s*[-:—–]?\s*(\d+)\b',
            line,
            re.I,
        )
        if not m:
            continue
        label = m.group(1)
        n = int(m.group(2))
        if label == 'итр':
            position = 'ИТР'
        else:
            position = 'Рабочие'
        results.append((org_name, position, n, line))

    best = {}
    seen_lines = set()
    for org, pos, n, line in results:
        line_key = (org, line)
        if line_key in seen_lines:
            continue
        seen_lines.add(line_key)
        key = (org, pos)
        if key not in best:
            best[key] = 0
        best[key] += n
    return [(o, p, n) for (o, p), n in best.items()]


# ─── VOR code extraction ─────────────────────────────────────────────────────

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

    UNIT_PATTERN = r'(?:м[23³]|м3|м2|кг|т|шт|км|пог\.?\s*м|л|мл|кв\.?\s*м|чел|чел\.|час|ч|день|дн\.)?'
    pattern = re.compile(
        r'('                          # Group 1: optional plan/prefix
        r'\w*[Пп]лан\w*'
        r'|\b[Пп]рочее\b'
        r'|\b[Сс]делано\b'
        r'|\b[Нн]е\s*успели\b'
        r'|\w*[Оо]бъём\b'
        r')?'                          # End group 1
        r'[\w\s]*?'
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
        is_plan = bool(re.search(r'[Пп]лан|завтра', prefix))
        if not is_plan:
            full_match = m.group(0)
            is_plan = bool(re.search(r'[Пп]лан|завтра', full_match))

        # Determine category
        category = 'план' if is_plan else 'объём'

        # Build fact text preserving the original prefix
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

        remaining = remove_first_match(remaining, m)

    # Clean up extra whitespace and punctuation artifacts
    remaining = re.sub(r'^[.\s,;:]+', '', remaining).strip()
    remaining = re.sub(r'[.\s,;:]+$', '', remaining).strip()
    remaining = ' '.join(remaining.split()).strip()

    return facts, remaining


# ─── Grok prompt builder ─────────────────────────────────────────────────────

def _build_qa_prompt(user_text, sender=None):
    """Build the Grok prompt with few-shot examples for QA fact extraction.

    Returns prompt string. The few-shot examples improve recall by showing
    Grok exactly what structured output should look like.
    """
    personnel_rule = "Если подрядчик не указан для персонала — извлекай факт: подрядчик будет определён по отправителю." if sender and SENDER_TO_CONTRACTOR.get(sender) else "Если подрядчик не указан для персонала — НЕ извлекай этот факт (будет отклонён)."

    prompt = f"""Извлеки ВСЕ факты из ответа прораба. Если сомневаешься — извлекай. Лучше лишний факт, чем пропущенный.
Верни ТОЛЬКО JSON-массив объектов, без пояснений, без markdown.

Каждый объект:
{{"building": "АБК"|"Общежитие"|"общая", "category": "персонал"|"техника"|"инцидент"|"бетонирование"|"монтаж"|"земляные работы"|"документация"|"материалы"|"план"|"объём", "fact": "текст факта"}}

ПРАВИЛА:
1. ИТР и рабочие — РАЗНЫЕ факты. «Атантай ИТР 1, рабочих 6» → ДВА объекта.
2. {personnel_rule}
3. building определяй по явному упоминанию: «АБК» или «Общежитие». Если не указано → «общая».
4. category выбирай из разрешённого списка. Если факт не подходит ни под одну категорию — не извлекай.
5. Не выдумывай данные. Только то, что явно указано в тексте.

ПРИМЕР 1:
Текст: «АйБиКон ИТР 2, рабочих 10. Атантай ИТР 1, рабочих 6. Происшествий нет.»
Ответ:
[{{"building":"общая","category":"персонал","fact":"АйБиКон ИТР 2"}},{{"building":"общая","category":"персонал","fact":"АйБиКон 10 рабочих"}},{{"building":"общая","category":"персонал","fact":"Атантай ИТР 1"}},{{"building":"общая","category":"персонал","fact":"Атантай 6 рабочих"}},{{"building":"общая","category":"инцидент","fact":"Происшествий нет"}}]

ПРИМЕР 2:
Текст: «Сделано бетонирование фундамента АБК. Монтаж стен Общежития. Техника: кран 1 ед., экскаватор 2 ед.»
Ответ:
[{{"building":"АБК","category":"бетонирование","fact":"бетонирование фундамента"}},{{"building":"Общежитие","category":"монтаж","fact":"монтаж стен"}},{{"building":"общая","category":"техника","fact":"кран 1 ед"}},{{"building":"общая","category":"техника","fact":"экскаватор 2 ед"}}]

ПРИМЕР 3:
Текст: «Документация: получен акт скрытых работ по АБК. Материалы: доставка арматуры 10т.»
Ответ:
[{{"building":"АБК","category":"документация","fact":"акт скрытых работ"}},{{"building":"общая","category":"материалы","fact":"арматура 10т"}}]

ТЕКСТ ПРОРАБА:
{user_text}

Только JSON-массив, без пояснений, без markdown."""

    return prompt


# ─── Chunking helper ─────────────────────────────────────────────────────────

def _smart_chunk(text, max_chars=3000):
    """Split text at sentence boundaries, not mid-word."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # Find last sentence boundary before max_chars
        chunk = remaining[:max_chars]
        # Try: newline, period, comma, space
        for sep in ['\n', '. ', '; ', ', ', ' ']:
            last = chunk.rfind(sep)
            if last > max_chars * 0.5:  # At least 50% of max
                chunk = chunk[:last + len(sep)]
                break
        chunks.append(chunk)
        remaining = remaining[len(chunk):].lstrip()
        # Safety: if no split found, force at max_chars
        if chunk == remaining[:len(chunk)]:
            remaining = remaining[max_chars:]

    return [c.strip() for c in chunks if c.strip()]


# ─── Main parse function ─────────────────────────────────────────────────────

def parse_qa(gid, text, date_str=None, sender=None):
    """Parse QA message and save facts to DB.

    Pipeline:
      1. Regex: extract VOR codes (no LLM)
      2. Grok: extract personnel/equipment/incidents from remaining text
      3. Validate: building/category against allowed sets
      4. Retry: if Grok fails, retry with clarifying prompt
      5. Fallback: pipe format + simple patterns

    Returns: number of facts saved.
    """
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

        # Step 2: Smart chunk remaining text and send to Grok
        chunks = _smart_chunk(remaining_text.strip(), max_chars=3000)

        all_grok_facts = []
        for chunk_idx, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            if len(chunks) > 1:
                print(f"[QA] Grok chunk {chunk_idx+1}/{len(chunks)}: '{chunk[:80]}...'", flush=True)
            else:
                print(f"[QA] Sending to Grok (VOR-free): '{chunk[:100]}...'", flush=True)

            # Step 3: Try Grok with retry + audit log
            grok_result = None
            grok_raw = ""
            retry_attempts = 0
            MAX_RETRIES = 3

            while retry_attempts < MAX_RETRIES and grok_result is None:
                if retry_attempts == 0:
                    prompt = _build_qa_prompt(chunk, sender=sender)
                else:
                    # Retry with clarifying prompt
                    prompt = (
                        f"ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ. Пожалуйста, верни СТРОГО JSON-массив.\n\n"
                        f"{_build_qa_prompt(chunk, sender=sender)}"
                    )

                try:
                    grok_raw = ask_grok(prompt, max_tokens=500, force_grok=True)
                    # Try to parse as JSON immediately
                    grok_text = grok_raw.strip()
                    if grok_text.startswith("```"):
                        grok_text = grok_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    facts = _json.loads(grok_text)
                    if isinstance(facts, list):
                        grok_result = facts
                        break
                    else:
                        # Got valid JSON but not a list
                        print(f"[QA Grok] Retry {retry_attempts+1}: got JSON but not a list", flush=True)
                except _json.JSONDecodeError as e:
                    print(f"[QA Grok] Retry {retry_attempts+1}: JSON parse failed ({e})", flush=True)
                    _audit_log('grok_json_fail', {
                        'attempt': retry_attempts + 1,
                        'error': str(e),
                        'raw_preview': grok_raw[:200] if 'grok_raw' in dir() else 'N/A',
                    })
                except Exception as e:
                    print(f"[QA Grok] Retry {retry_attempts+1}: API error ({e})", flush=True)
                    _audit_log('grok_api_error', {
                        'attempt': retry_attempts + 1,
                        'error': str(e),
                    })
                    time.sleep(1 * (retry_attempts + 1))  # exponential-ish backoff

                retry_attempts += 1

            # Step 4: Process Grok results with validation
            if grok_result is None:
                # All retries failed — try pipe fallback + personnel regex on original chunk
                if grok_raw and grok_raw.strip():
                    print(f"[QA Grok] All retries failed, falling back to pipe format", flush=True)
                    _audit_log('grok_all_retries_failed', {'text_preview': chunk[:100]})
                    for line in grok_raw.split("\n"):
                        parts = [p.strip() for p in line.strip().split("|", 2)]
                        if len(parts) >= 3 and len(line) > 10:
                            b = validate_building(parts[0])
                            c = validate_category(parts[1])
                            f = parts[2]
                            if not c:
                                continue  # skip hallucinated categories in pipe format
                            if c == 'персонал' and not validate_personnel_fact(f, sender=sender):
                                print(f"[QA VALIDATE] Rejected incomplete personnel: '{f}' — no contractor", flush=True)
                                continue
                            all_grok_facts.append((b, c, f))
                # Always try personnel regex on original user chunk when Grok JSON failed
                for org_name, position, n in _parse_personnel_fallback(chunk):
                    fact = f"{org_name} {position} {n}" if position != 'Рабочие' else f"{org_name} {n} рабочих"
                    if position == 'ИТР':
                        fact = f"{org_name} ИТР {n}"
                    all_grok_facts.append(('общая', 'персонал', fact))
                    print(f"[QA PIPE FALLBACK] personnel from text: {fact}", flush=True)
                for org_name, position, n in _parse_sender_personnel_fallback(chunk, sender=sender):
                    fact = f"{org_name} {position} {n}" if position != 'Рабочие' else f"{org_name} {n} рабочих"
                    if position == 'ИТР':
                        fact = f"{org_name} ИТР {n}"
                    all_grok_facts.append(('общая', 'персонал', fact))
                    print(f"[QA PIPE FALLBACK] personnel from sender: {fact}", flush=True)
                continue

            # Valid JSON list — validate each fact
            for obj in grok_result:
                b = validate_building(obj.get("building", DEFAULT_BUILDING))
                c_raw = obj.get("category", "")
                c = validate_category(c_raw)
                f = obj.get("fact", "")

                if not b or not c or not f:
                    print(f"[QA VALIDATE] Skipped empty fact: building={b!r} category={c!r} fact={f[:60]!r}", flush=True)
                    continue  # skip empty facts

                # Personnel validation
                if c == 'персонал' and not validate_personnel_fact(f, sender=sender):
                    print(f"[QA VALIDATE] Rejected incomplete personnel: '{f}' — no contractor", flush=True)
                    _audit_log('rejected_personnel', {'fact': f})
                    continue

                print(f"[QA GROK FACT] raw_cat='{c_raw}' → validated='{c}' | building='{b}' | fact='{f[:80]}'", flush=True)
                all_grok_facts.append((b, c, f))

        if all_grok_facts:
            print(f"[QA Grok] Structured: {len(all_grok_facts)} validated facts from JSON", flush=True)

        sender_personnel = _parse_sender_personnel_fallback(text, sender=sender)
        if sender_personnel:
            existing_personnel = {
                (_contractor_from_fact_or_sender(f, sender=sender), _position_from_personnel_fact(f))
                for _, c, f in all_grok_facts
                if c == 'персонал'
            }
            for org_name, position, n in sender_personnel:
                if (org_name, position) in existing_personnel:
                    continue
                fact = f"{org_name} {position} {n}" if position != 'Рабочие' else f"{org_name} {n} рабочих"
                if position == 'ИТР':
                    fact = f"{org_name} ИТР {n}"
                all_grok_facts.append(('общая', 'персонал', fact))
                print(f"[QA SENDER FALLBACK] personnel from sender: {fact}", flush=True)

        # Step 5: Save everything to DB — route by category to OJR tables
        conn = get_conn()
        cur = conn.cursor()
        today = date_str or datetime.now(BISHKEK_TZ).strftime("%Y-%m-%d")
        count = 0

        # Import OJR helpers
        from db import save_work_log, save_incident, save_material

        # Save VOR codes directly — route to ojr_section3_work_log
        for f in vor_facts:
            save_work_log(gid, today, f['code'], 'общая', f['volume'],
                          unit=f.get('unit','м³'), category=f['category'],
                          created_by='qa')
            count += 1

        # Save validated Grok facts — route by category
        print(f"[QA SAVE] Routing {len(all_grok_facts)} grok-validated facts to DB tables", flush=True)
        for b, c, f in all_grok_facts:
            print(f"[QA SAVE] fact category='{c}' building='{b}' text='{f[:80]}'", flush=True)
            if c == 'персонал':
                # Personnel facts are "Организация ИТР N" or "Организация N рабочих"
                # Save to OJR personnel table
                from db import save_personnel
                # Try to parse org name + ITR/workers from fact text
                org_name = _contractor_from_fact_or_sender(f, sender=sender)
                if not org_name:
                    print(f"[QA VALIDATE] Rejected incomplete personnel at save: '{f}' — no contractor", flush=True)
                    _audit_log('rejected_personnel_save', {'fact': f, 'sender': sender})
                    continue
                # Determine if ITR or worker
                position = _position_from_personnel_fact(f)
                # Parse headcount from fact (e.g. "8 рабочих" → 8, "ИТР 1" → 1)
                num_match = re.search(r'(\d+)', f)
                n = int(num_match.group(1)) if num_match else 1
                print(f"[QA SAVE] → save_personnel: org='{org_name}' pos='{position}' count={n}", flush=True)
                # ONE row per org+position+day with workers_count=N.
                # Multi-insert loop previously raced: save_personnel closed ALL
                # open org+position rows before EACH insert, so insert #2 set
                # end_date=today-1 on insert #1 → get_staff counted only 1 of N.
                slot_name = f"{org_name}-{position}" if position else org_name
                save_personnel(gid, today, org_name, slot_name, position,
                               sync_source='qa', workers_count=max(1, n))
                count += 1
            elif c in ('инцидент', 'incident'):
                print(f"[QA SAVE] → save_incident", flush=True)
                save_incident(gid, today, 'incident', f,
                              severity='minor',
                              location=b if b != 'общая' else None)
                count += 1
            elif c in ('документация', 'материалы'):
                # Save to ojr_materials
                print(f"[QA SAVE] → save_material: category='{c}'", flush=True)
                save_material(gid, today, f, building=b if b != 'общая' else None)
                count += 1
            elif c == 'техника':
                # Equipment goes to bot_memory_facts, NOT work_log
                print(f"[QA SAVE] → bot_memory_facts (техника)", flush=True)
                try:
                    cur.execute(
                        "INSERT INTO bot_memory_facts (chat_id, fact_date, building, category, fact, source) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (chat_id, fact_date, building, category, fact) DO NOTHING",
                        (gid, today, b if b != 'общая' else 'общая', 'техника', f, 'qa'))
                except Exception as e:
                    print(f"[QA SAVE ERR] bot_memory_facts INSERT failed: {e}", flush=True)
                    traceback.print_exc()
                    _audit_log('bot_memory_facts_insert_error', {
                        'error': str(e),
                        'fact': f,
                        'group_id': gid,
                    })
                count += 1
            elif c in ('план', 'объём'):
                # These go to work_log — extract VOR code, require volume > 0
                print(f"[QA SAVE] → план/объём → work_log", flush=True)
                import re as _re2
                vor_match = _re2.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)', f)
                if vor_match:
                    vor_code = vor_match.group(1)
                    vol_match = _re2.search(r'(\d+(?:[.,]\d+)?)', f)
                    volume = float(vol_match.group(1).replace(',', '.')) if vol_match else 0
                    if volume > 0:
                        save_work_log(gid, today, vor_code, b, volume,
                                      category=c, created_by='qa')
                    # volume=0 with VOR code — skip, not a real work
                # No VOR code — skip, don't save to work_log
                count += 1
            else:
                # Unknown category (бетонирование, монтаж, земляные работы etc.) — don't save to work_log
                print(f"[QA SAVE] ⚠ UNKNOWN category='{c}' — NOT SAVED to DB", flush=True)
                pass

        # Fallback: if nothing was saved — personnel regex + simple "нет" patterns
        # (covers Grok JSON fail / empty pipe where workers count still must be stored)
        if count == 0:
            from db import save_personnel
            fallback_personnel = _parse_personnel_fallback(text) + _parse_sender_personnel_fallback(text, sender=sender)
            for org_name, position, n in fallback_personnel:
                print(f"[QA FALLBACK] personnel org='{org_name}' pos='{position}' count={n}", flush=True)
                # Single row + workers_count (same anti-race as main path)
                slot_name = f"{org_name}-{position}" if position else org_name
                save_personnel(gid, today, org_name, slot_name, position,
                               sync_source='qa', workers_count=max(1, n))
                count += 1
            for line in _parse_no_patterns(text).split("\n"):
                parts = [p.strip() for p in line.strip().split("|", 2)]
                if len(parts) >= 3:
                    b = validate_building(parts[0])
                    c = validate_category(parts[1])
                    f = parts[2]
                    if b and c and f:
                        if c in ('инцидент', 'incident'):
                            save_incident(gid, today, 'incident', f, location=b if b != 'общая' else None)
                        elif c in ('документация', 'материалы'):
                            save_material(gid, today, f, building=b if b != 'общая' else None)
                        elif c == 'персонал':
                            # Prefer parsed counts; generic single row only if no regex hit
                            if not fallback_personnel:
                                save_personnel(gid, today, 'АйБиКон', 'АйБиКон', 'Сотрудник',
                                               sync_source='qa', workers_count=1)
                        else:
                            # Unknown category — skip, don't save to work_log
                            continue
                        count += 1

        conn.commit()
        cur.close()
        conn.close()

        if count > 0:
            print(f"[QA] {count} facts saved from '{text[:60]}'", flush=True)
            _audit_log('parse_success', {
                'facts_saved': count,
                'vor_count': len(vor_facts),
                'grok_count': len(all_grok_facts),
                'text_preview': text[:100],
            })
        else:
            print(f"[QA] 0 facts from '{text[:60]}'", flush=True)
            _audit_log('parse_empty', {'text_preview': text[:100]})

        return count

    except Exception as e:
        print(f"[QA ERR] {e}", flush=True)
        traceback.print_exc()
        _audit_log('parse_error', {'error': str(e), 'text_preview': text[:100] if text else 'N/A'})
        return 0
