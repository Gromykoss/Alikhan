"""QA module: is_qa(text) → bool, parse_qa(gid, text) → count

v2.1 (2026-07-18): RAG fixes from P1P2 report
  - Building/category validation (hallucination guard)
  - Few-shot prompt with examples
  - Retry + audit log for Grok failures
"""
import sys, os, re, time, json as _json
from datetime import datetime
from secret_config import get_evo_key

EVO = "http://127.0.0.1:8080"
KEY = get_evo_key(required=True)
SANDBOX = "120363179621030401@g.us"

sys.stdout.reconfigure(line_buffering=True)

# ─── Validation sets ─────────────────────────────────────────────────────────
ALLOWED_BUILDINGS = {'АБК', 'Общежитие', 'общая'}
ALLOWED_CATEGORIES = {
    'персонал', 'техника', 'инцидент', 'бетонирование', 'монтаж',
    'земляные работы', 'документация', 'план', 'объём'
}
ALLOWED_CONTRACTORS = ['айбикон', 'атантай', 'майкадам', 'наватек']

# Default for unknown buildings
DEFAULT_BUILDING = 'общая'

# ─── Audit log helper ────────────────────────────────────────────────────────

def _audit_log(entry_type, data):
    """Log parsing attempts to /tmp/alikhan_qa_audit.log for post-hoc analysis."""
    try:
        entry = {
            'ts': datetime.now().isoformat(),
            'type': entry_type,
            **data
        }
        with open('/tmp/alikhan_qa_audit.log', 'a') as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass  # audit log is best-effort


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
        'материалы': 'документация', 'план работ': 'план',
    }
    if v in fuzzy_map:
        return fuzzy_map[v]
    # Hallucinated category — reject
    print(f"[QA VALIDATE] Rejected hallucinated category: '{value}'", flush=True)
    _audit_log('hallucinated_category', {'rejected': value})
    return None


def validate_personnel_fact(fact_text):
    """Personnel facts MUST contain a known contractor name."""
    if not fact_text:
        return False
    return any(cnt in fact_text.lower() for cnt in ALLOWED_CONTRACTORS)


# ─── Simple pattern fallback ─────────────────────────────────────────────────

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

def _build_qa_prompt(user_text):
    """Build the Grok prompt with few-shot examples for QA fact extraction.

    Returns prompt string. The few-shot examples improve recall by showing
    Grok exactly what structured output should look like.
    """
    prompt = f"""Извлеки ВСЕ факты из ответа прораба. Если сомневаешься — извлекай. Лучше лишний факт, чем пропущенный.
Верни ТОЛЬКО JSON-массив объектов, без пояснений, без markdown.

Каждый объект:
{{"building": "АБК"|"Общежитие"|"общая", "category": "персонал"|"техника"|"инцидент"|"бетонирование"|"монтаж"|"земляные работы"|"документация", "fact": "текст факта"}}

ПРАВИЛА:
1. ИТР и рабочие — РАЗНЫЕ факты. «Атантай ИТР 1, рабочих 6» → ДВА объекта.
2. Если подрядчик не указан для персонала — НЕ извлекай этот факт (будет отклонён).
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
[{{"building":"АБК","category":"документация","fact":"акт скрытых работ"}},{{"building":"общая","category":"документация","fact":"арматура 10т"}}]

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

def parse_qa(gid, text, date_str=None):
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
                    prompt = _build_qa_prompt(chunk)
                else:
                    # Retry with clarifying prompt
                    prompt = (
                        f"ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ. Пожалуйста, верни СТРОГО JSON-массив.\n\n"
                        f"{_build_qa_prompt(chunk)}"
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
                # All retries failed — try pipe fallback
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
                            if c == 'персонал' and not validate_personnel_fact(f):
                                print(f"[QA VALIDATE] Rejected incomplete personnel: '{f}' — no contractor", flush=True)
                                continue
                            all_grok_facts.append((b, c, f))
                continue

            # Valid JSON list — validate each fact
            for obj in grok_result:
                b = validate_building(obj.get("building", DEFAULT_BUILDING))
                c_raw = obj.get("category", "")
                c = validate_category(c_raw)
                f = obj.get("fact", "")

                if not b or not c or not f:
                    continue  # skip empty facts

                # Personnel validation
                if c == 'персонал' and not validate_personnel_fact(f):
                    print(f"[QA VALIDATE] Rejected incomplete personnel: '{f}' — no contractor", flush=True)
                    _audit_log('rejected_personnel', {'fact': f})
                    continue

                all_grok_facts.append((b, c, f))

        if all_grok_facts:
            print(f"[QA Grok] Structured: {len(all_grok_facts)} validated facts from JSON", flush=True)

        # Step 5: Save everything to DB — route by category to OJR tables
        conn = get_conn()
        cur = conn.cursor()
        today = date_str or datetime.now().strftime("%Y-%m-%d")
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
        for b, c, f in all_grok_facts:
            if c == 'персонал':
                # Personnel facts are "Организация ИТР N" or "Организация N рабочих"
                # Save to OJR personnel table
                from db import save_personnel
                # Try to parse org name + ITR/workers from fact text
                fact_lower = f.lower()
                for cnt in ALLOWED_CONTRACTORS:
                    if cnt in fact_lower:
                        org_name = cnt
                        break
                else:
                    org_name = 'айбикон'  # default
                # Determine if ITR or worker
                if 'итр' in fact_lower:
                    position = 'ИТР'
                elif 'рабоч' in fact_lower:
                    position = 'Рабочий'
                else:
                    position = 'Сотрудник'
                save_personnel(gid, today, org_name, org_name, position,
                               sync_source='qa')
                count += 1
            elif c in ('инцидент', 'incident'):
                save_incident(gid, today, 'incident', f,
                              severity='minor',
                              location=b if b != 'общая' else None)
                count += 1
            elif c in ('документация', 'материалы'):
                # Save to ojr_materials
                save_material(gid, today, f, building=b if b != 'общая' else None)
                count += 1
            elif c in ('бетонирование', 'монтаж', 'земляные работы', 'техника', 'план', 'объём'):
                # These go to work_log — try to extract VOR code if present
                import re as _re2
                vor_match = _re2.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)', f)
                if vor_match:
                    vor_code = vor_match.group(1)
                    vol_match = _re2.search(r'(\d+(?:[.,]\d+)?)', f)
                    volume = float(vol_match.group(1).replace(',', '.')) if vol_match else 0
                    save_work_log(gid, today, vor_code, b, volume,
                                  category=c, created_by='qa')
                else:
                    save_work_log(gid, today, b, b, 0,
                                  work_name=f, category=c, created_by='qa')
                count += 1
            else:
                # Fallback: save as general work_log entry
                save_work_log(gid, today, b, b, 0,
                              work_name=f, category=c, created_by='qa')
                count += 1

        # Fallback: if nothing was saved, try simple "нет" patterns
        if count == 0:
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
                            from db import save_personnel
                            save_personnel(gid, today, 'айбикон', 'айбикон', 'Сотрудник', sync_source='qa')
                        else:
                            save_work_log(gid, today, b, b, 0, work_name=f, category=c, created_by='qa')
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
        _audit_log('parse_error', {'error': str(e), 'text_preview': text[:100] if text else 'N/A'})
        return 0
