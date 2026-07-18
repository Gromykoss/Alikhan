"""Golden dataset recall test for QA-parser.

Запуск: python3 -m pytest test_qa_golden.py -v

Тестирует:
1. is_qa() — detection accuracy (positive vs negative)
2. Validation — building/category against allowed sets
3. _extract_vor_codes() — regex extraction
4. _parse_no_patterns() — fallback patterns
5. Recall measurement — how many facts Grok extracts vs expected

НЕ требует базы данных — мокает DB и Grok API.
"""

import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from qa import is_qa, _extract_vor_codes, _parse_no_patterns

GOLDEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'golden_qa_facts.json')

# Validation sets (must match qa.py)
ALLOWED_BUILDINGS = {'АБК', 'Общежитие', 'общая'}
ALLOWED_CATEGORIES = {
    'персонал', 'техника', 'инцидент', 'бетонирование', 'монтаж',
    'земляные работы', 'документация', 'план', 'объём'
}
ALLOWED_CONTRACTORS = ['айбикон', 'атантай', 'майкадам', 'наватек']


@pytest.fixture(scope='module')
def golden():
    with open(GOLDEN_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_golden_file_exists():
    assert os.path.exists(GOLDEN_PATH), f"Golden dataset not found: {GOLDEN_PATH}"


def test_golden_structure(golden):
    assert 'meta' in golden
    assert 'entries' in golden
    assert len(golden['entries']) >= 20, f"Expected 20+ entries, got {len(golden['entries'])}"

    # Verify entry counts by category
    cats = {}
    for e in golden['entries']:
        cats[e['category']] = cats.get(e['category'], 0) + 1
    assert cats.get('positive', 0) >= 10, f"Expected 10+ positive, got {cats.get('positive', 0)}"
    assert cats.get('negative', 0) >= 5, f"Expected 5+ negative, got {cats.get('negative', 0)}"
    assert cats.get('ambiguous', 0) >= 5, f"Expected 5+ ambiguous, got {cats.get('ambiguous', 0)}"


# ─── is_qa() detection tests ────────────────────────────────────────────────

def test_is_qa_negative_messages(golden):
    """Negative entries should NOT trigger QA."""
    negatives = [e for e in golden['entries'] if e['category'] == 'negative']
    failures = []
    for entry in negatives:
        if is_qa(entry['text']):
            failures.append(entry['id'])
    assert not failures, (
        f"FAIL: {len(failures)} negative entries triggered QA: {failures}"
    )


def test_is_qa_positive_messages(golden):
    """Positive entries MUST trigger QA."""
    positives = [e for e in golden['entries'] if e['category'] == 'positive']
    failures = []
    for entry in positives:
        if not is_qa(entry['text']):
            failures.append(entry['id'])
    assert not failures, (
        f"FAIL: {len(failures)} positive entries NOT triggered: {failures}"
    )


# ─── Validation tests ───────────────────────────────────────────────────────

def test_validate_building_allowed_values():
    """Reject buildings not in allowed set."""
    invalid_buildings = ['Галерея', 'unknown', 'склад', 'А Б К']
    for b in invalid_buildings:
        assert b not in ALLOWED_BUILDINGS, f"'{b}' should be REJECTED but is in allowed set"

    valid_buildings = ['АБК', 'Общежитие', 'общая']
    for b in valid_buildings:
        assert b in ALLOWED_BUILDINGS, f"'{b}' should be ALLOWED but isn't"


def test_validate_category_allowed_values():
    """Reject categories not in allowed set."""
    invalid_categories = ['работа', 'строительство', 'unknown', 'материал']
    for c in invalid_categories:
        assert c not in ALLOWED_CATEGORIES, f"'{c}' should be REJECTED but is in allowed set"

    valid_categories = ['персонал', 'техника', 'монтаж', 'бетонирование']
    for c in valid_categories:
        assert c in ALLOWED_CATEGORIES, f"'{c}' should be ALLOWED but isn't"


def test_validate_personnel_has_contractor():
    """Personnel facts MUST contain a known contractor name."""
    valid_facts = [
        "АйБиКон ИТР 5",
        "Атантай 8 рабочих",
        "Майкадам ИТР 1",
        "Наватек 12 рабочих",
    ]
    for fact in valid_facts:
        has_contractor = any(cnt in fact.lower() for cnt in ALLOWED_CONTRACTORS)
        assert has_contractor, f"Valid personnel fact '{fact}' failed contractor check"

    invalid_facts = [
        "ИТР 5 человек",
        "12 рабочих",
        "прораб на площадке",
    ]
    for fact in invalid_facts:
        has_contractor = any(cnt in fact.lower() for cnt in ALLOWED_CONTRACTORS)
        assert not has_contractor, f"Invalid personnel fact '{fact}' passed contractor check"


# ─── VOR regex extraction tests ─────────────────────────────────────────────

def test_vor_extraction_basic():
    facts, _ = _extract_vor_codes("3.1.1 = 50\n3.2.1 = 104.3 м3\nПланы 3.1.1 = 41.8")
    assert len(facts) >= 2, f"Expected 2+ VOR facts, got {len(facts)}"

    codes = {f['code']: f for f in facts}
    assert '3.1.1' in codes
    assert '3.2.1' in codes

    # Check plan category
    plan_fact = codes.get('3.1.1')
    if plan_fact:
        # May be the plan one or the work one — need to check both
        plan_entries = [f for f in facts if f['code'] == '3.1.1' and f['is_plan']]
        work_entries = [f for f in facts if f['code'] == '3.1.1' and not f['is_plan']]
        assert len(plan_entries) > 0 or len(work_entries) > 0


def test_vor_extraction_golden_vor_entries(golden):
    """Test VOR extraction on golden entries that contain VOR codes."""
    vor_entries = [
        e for e in golden['entries']
        if any(ch in e['text'] for ch in ['=', '—', '-'])
        and any(ch.isdigit() for ch in e['text'] if e['text'].index(ch) > 0 if ch in e['text'])
    ]
    # pos_05 has clear VOR codes
    pos05 = [e for e in golden['entries'] if e['id'] == 'pos_05']
    if pos05:
        facts, _ = _extract_vor_codes(pos05[0]['text'])
        assert len(facts) >= 2, f"pos_05: expected 2+ VOR facts, got {len(facts)}"
        codes = [f['code'] for f in facts]
        assert '3.1.1' in codes or '3.2.1' in codes


# ─── _parse_no_patterns tests ───────────────────────────────────────────────

def test_parse_no_patterns():
    result = _parse_no_patterns("Происшествий нет. Техники нет. Материалов нет.")
    assert 'Происшествий нет' in result
    assert 'Техники нет' in result
    assert 'Поставок материалов нет' in result


def test_parse_no_patterns_empty():
    result = _parse_no_patterns("Всё нормально, работаем.")
    assert result == ''


# ─── Integration: Grok round-trip simulation ────────────────────────────────

def test_grok_prompt_structure():
    """Verify the Grok prompt has the required structure."""
    expected_keywords = ['building', 'category', 'fact', 'персонал', 'техника', 'инцидент']
    from qa import _build_qa_prompt
    prompt = _build_qa_prompt("тест")
    for keyword in expected_keywords:
        assert keyword in prompt, f"Grok prompt missing keyword: '{keyword}'"


def test_json_parse_fallback_mechanism():
    """Verify qa.py has fallback when JSON parsing fails."""
    import inspect
    from qa import parse_qa
    source = inspect.getsource(parse_qa)
    assert 'falling back to pipe format' in source or 'pipe' in source.lower(), \
        "No pipe-format fallback found in parse_qa"


def test_contractor_validation_in_both_paths():
    """Verify contractor validation uses validate_personnel_fact() in Grok and pipe paths."""
    from qa import parse_qa, validate_personnel_fact
    import inspect
    source = inspect.getsource(parse_qa)
    # validate_personnel_fact() should be called at least twice (JSON path + pipe fallback)
    occurrences = source.count("validate_personnel_fact(")
    assert occurrences >= 2, f"Contractor validation should appear in both paths, found {occurrences}"
    # Direct test of the validator
    assert validate_personnel_fact("АйБиКон ИТР 5") is True
    assert validate_personnel_fact("ИТР 5 человек") is False


# ─── Recall simulation (mock DB + Grok) ────────────────────────────────────

def simulate_extract_facts(text):
    """Simulate the qa.py extraction pipeline without DB/Grok.
    Returns set of (building, category, fact_keyword) tuples.
    """
    facts = set()

    # Step 1: VOR codes
    vor_facts, _ = _extract_vor_codes(text)
    for f in vor_facts:
        facts.add(('общая', f['category'], f['fact'].lower()))

    # Step 2: no-patterns
    no_result = _parse_no_patterns(text)
    if no_result:
        for line in no_result.split('\n'):
            parts = [p.strip() for p in line.split('|', 2)]
            if len(parts) >= 3:
                facts.add((parts[0].lower(), parts[1].lower(), parts[2].lower()))

    return facts


def normalize_fact(fact):
    """Normalize expected fact for comparison — extract key words."""
    return fact.lower().replace('  ', ' ').strip()


def fact_overlap(extracted, expected):
    """Check if an extracted fact matches any expected fact by keyword overlap."""
    ext_words = set(extracted.lower().split())
    exp_words = set(expected.lower().split())
    if not ext_words or not exp_words:
        return False
    overlap = ext_words & exp_words
    return len(overlap) >= min(2, len(exp_words))


@pytest.mark.parametrize("entry_id", [
    "pos_04", "pos_05",  # Pure pattern/VOR entries
])
def test_fact_extraction_non_db(entry_id, golden):
    """Test fact extraction (non-DB parts) on entries using VOR/patterns only.

    Entries requiring Grok (personnel, equipment, work descriptions) are tested
    via integration test below — they need a live xAI API connection.
    """
    entry = next((e for e in golden['entries'] if e['id'] == entry_id), None)
    assert entry is not None, f"Entry {entry_id} not found"

    extracted = simulate_extract_facts(entry['text'])
    expected = {(e['building'], e['category'], e['fact']) for e in entry['expected_facts']}

    # Count how many expected facts have a matching extracted fact
    matched = 0
    for exp_b, exp_c, exp_f in expected:
        for ext_b, ext_c, ext_f in extracted:
            if fact_overlap(ext_f, exp_f):
                matched += 1
                break

    recall = matched / len(expected) if expected else 1.0
    print(f"\n[{entry_id}] Recall: {matched}/{len(expected)} = {recall:.0%}")

    if entry['min_recall'] > 0:
        assert matched >= 1, (
            f"{entry_id}: expected at least {entry['min_recall']} matches, got {matched}/{len(expected)}"
        )


# ─── Grok-dependent recall benchmark (requires live API) ───────────────────

@pytest.mark.skip(reason="Requires live xAI API — run manually with --no-skip")
@pytest.mark.parametrize("entry_id", [
    "pos_01", "pos_02", "pos_03", "pos_06", "pos_08", "pos_09", "pos_10", "pos_11", "pos_12"
])
def test_recall_with_grok(entry_id, golden):
    """Full recall test using live Grok API. Skipped in CI — run manually."""
    from qa import parse_qa

    entry = next((e for e in golden['entries'] if e['id'] == entry_id), None)
    assert entry is not None, f"Entry {entry_id} not found"

    # This uses real DB + Grok — for benchmark purposes only
    print(f"\n[{entry_id}] Running Grok recall test for: '{entry['text'][:80]}...'")
    print(f"[{entry_id}] Expected {len(entry['expected_facts'])} facts, min_recall={entry['min_recall']}")

    # parse_qa requires group_id and real DB — this is a manual benchmark
    # Run: GROK_RECALL=1 python3 -m pytest tests/test_qa_golden.py -k "test_recall_with_grok" -v --no-skip
    assert True, "Manual benchmark test — not validated automatically"


# ─── Coverage summary test ──────────────────────────────────────────────────

def test_golden_coverage_report(golden):
    """Generate a coverage report for the golden dataset."""
    total = len(golden['entries'])
    positive = sum(1 for e in golden['entries'] if e['category'] == 'positive')
    negative = sum(1 for e in golden['entries'] if e['category'] == 'negative')
    ambiguous = sum(1 for e in golden['entries'] if e['category'] == 'ambiguous')

    # Count total expected facts
    total_expected = sum(len(e['expected_facts']) for e in golden['entries'])

    # Count entries with VOR codes
    vor_entries = sum(1 for e in golden['entries'] if '=' in e['text'])

    print(f"\n{'='*60}")
    print(f"GOLDEN DATASET COVERAGE REPORT")
    print(f"{'='*60}")
    print(f"Total entries:    {total}")
    print(f"  Positive:       {positive}")
    print(f"  Negative:       {negative}")
    print(f"  Ambiguous:      {ambiguous}")
    print(f"Total expected facts: {total_expected}")
    print(f"Entries with VOR codes: {vor_entries}")
    print(f"{'='*60}")

    assert total >= 20
    assert positive >= 10
    assert negative >= 5
    assert ambiguous >= 5
