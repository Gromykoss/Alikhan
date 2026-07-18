# QA Parser Test Patterns — 15.07.2026

Test suite: `test_qa_parser.py` (6 cases, 6/6 pass after fixes).

## Test cases

### 1. Plan «на завтра» detection
```python
text = 'Планы на завтра 3.1.5 = 142,66'
facts, _ = _extract_vor_codes(text)
# facts[0]: code='3.1.5', vol=142.66, category='план', is_plan=True
```

### 2. Mixed work + plan on same code
```python
text = 'Работы 3.1.1 - 50 м2 Планы на завтра 3.1.1 - 41,8'
facts, _ = _extract_vor_codes(text)
# facts[0]: code='3.1.1', vol=50.0, is_plan=False (work)
# facts[1]: code='3.1.1', vol=41.8, is_plan=True (plan)
```
**PITFALL:** This test failed before fix — `full_match` fallback was needed because «Работы» text between prefix and code swallowed «Планы». The gap `[\w\s]*?` ate both «Работы» AND «Планы», leaving prefix group empty. Fallback checks `m.group(0)` (full match) for plan keywords.

### 3. Plan prefix variants
```python
cases = [
    ('план 3.2.1 = 100', True),
    ('Планы на завтра 4.1.1 = 200', True),
    ('план работ 5.1.1 = 300', True),
]
```

### 4. Comma decimal separator
```python
facts, _ = _extract_vor_codes('3.1.1 = 41,8')
# facts[0]: vol=41.8 (not 418)
```

### 5. No prefix = work
```python
facts, _ = _extract_vor_codes('3.1.1 = 50м2')
# facts[0]: category='объём', is_plan=False
```

### 6. Grok hallucination filter
```python
# volumes() skips facts with category NOT in ('объём', 'план')
# Grok hallucinates: [монтаж] 3.1.3 = 105.0 → SKIPPED
```

## Running

```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -m pytest test_qa_parser.py -v
```

## When tests fail

1. Check `_extract_vor_codes()` regex — prefix gap must be `[\w\s]*?` (not `\s*`)
2. Check `is_plan` detection — must check BOTH `prefix` and `m.group(0)` (full match)
3. Check `remove_first_match()` — must preserve text between matches
4. Check `['м2']` unit — regex must match Russian measurement units
