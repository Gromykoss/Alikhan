# QA Parser VOR Extraction — Full Reference

**Created:** 11.07.2026  
**File:** `bot/qa.py`  
**Function:** `_extract_vor_codes(text) → (volume_facts, remaining_text)`

## Bugs Fixed (this implementation)

### Bug 1: LLM hallucinates VOR codes

**Symptom:** Code `3.3.2.1 = 2191.3` appeared in saved QA facts even though user never sent it.  
**Root cause:** User text like `"7.2.1.1 = 1.5 м3Планы 3.3.2 = 104.3 м3"` was sent to Grok for extraction. Grok interpreted the numbers in the VOR codes and invented additional codes.  
**Fix:** Extract ALL VOR codes from original text using regex **before** anything reaches Grok. Grok only receives the remaining text (personnel, incidents, equipment).

### Bug 2: "Планы" prefix stripped by Grok

**Symptom:** User sends `"Планы 3.3.2 = 104.3"` but Grok outputs `"3.3.2 = 104.3"` without the plans marker. The fact goes to works instead of plans.  
**Root cause:** Grok didn't preserve the `Планы` prefix in its output. `fill_ejo.py`'s `volumes()` checks `'план' in txt.lower()` — without the prefix, it can't detect the plan.  
**Fix:** Regex detects `Планы`/`план` before the code and saves the fact with the original prefix preserved. Downstream `volumes()` correctly routes it to the plans dict.

## Regex Pattern Details

```python
UNIT_PATTERN = r'(?:м[23³]|м3|м2|кг|т|шт|км|пог\.?\s*м|л|мл|кв\.?\s*м|чел|чел\.|час|ч|день|дн\.)?'

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
```

### Groups

| Group | Content | Example |
|-------|---------|---------|
| 1 | Optional prefix (plan/schedule/done/etc) | `Планы`, `план`, `Прочее`, `сделано`, or empty |
| 2 | VOR code (3 or 4 part dot-separated) | `3.3.2`, `7.2.1.1` |
| 3 | Volume number | `104.3`, `104,3`, `50` |
| 4 | Measurement unit (optional) | `м3`, `м2`, `кг`, `т`, or empty |

### Key design decisions

**Explicit unit matching instead of `\S*` or `\w*`:**
- Python's `re.UNICODE` treats Cyrillic letters `П`, `л`, `а` as `\w` characters
- `\w*` would match `м3Планы` as a single 6-character unit token, consuming `Планы`
- `\w{0,4}` with Russian text still captures `м3Пл` (4 chars) — enough to eat the prefix of the next word
- Solution: match only known measurement units explicitly

**Prefix detection sets category:**
- If prefix contains `[Пп]лан` → `category='план'`
- Otherwise (including no prefix) → `category='объём'`
- `Прочее`, `сделано`, `не успели`, `объём` are recognized as prefixes but classified as `объём`

**Fact text preserves prefix:**
- `"Планы 3.3.2 = 104.3м3"` not `"3.3.2 = 104.3м3"`
- This is crucial because `fill_ejo.py`'s `volumes()` and the «Материалы и планы» sheet both search for `'план' in txt.lower()` — they need the prefix present

## Test Suite

All tests pass. Run with:
```bash
cd /home/hermes-workspace/Alikhan-migration/bot
python3 -c "
from qa import _extract_vor_codes

# 1. Combined work + plan (exact bug scenario)
f, r = _extract_vor_codes('7.2.1.1 = 1.5 м3Планы 3.3.2 = 104.3 м3')
assert len(f) == 2
assert f[0]['code'] == '7.2.1.1' and f[0]['category'] == 'объём'
assert f[1]['code'] == '3.3.2' and f[1]['category'] == 'план'

# 2. Планы prefix
f, r = _extract_vor_codes('Планы 3.3.2 = 104.3 м3')
assert f[0]['category'] == 'план'

# 3. Simple work code
f, r = _extract_vor_codes('3.3.2 = 104.3')
assert f[0]['category'] == 'объём'

# 4. Four-part code
f, r = _extract_vor_codes('7.2.1.1 = 1.5м3')
assert f[0]['code'] == '7.2.1.1'

# 5. Mixed VOR + personnel — remaining preserves personnel
f, r = _extract_vor_codes('Планы 3.3.2 = 104.3 м3. Атантай ИТР 1, рабочих 6.')
assert 'Атантай' in r
assert '3.3.2' not in r

# 6. Comma decimal
f, r = _extract_vor_codes('3.3.2 = 104,5')
assert abs(f[0]['volume'] - 104.5) < 0.01

# 7. Lowercase план
f, r = _extract_vor_codes('план 3.3.2 = 104.3')
assert f[0]['is_plan'] == True

# 8. Multiple works
f, r = _extract_vor_codes('3.3.2 = 50 4.1.1 = 30')
assert len(f) == 2

# 9. Dash and em-dash separators
f, r = _extract_vor_codes('3.3.2 — 104.3')
assert len(f) == 1

print('All tests pass')
"
```

## Downstream Routing in fill_ejo.py

```python
# volumes() — called by fill()
def volumes(date):
    f = qa(date)  # all categories
    dn, pn = {}, {}
    for x in f:
        txt = (x.get('fact','') or '').replace(',', '.')
        m = re.search(r'(\d+\.\d+\.\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)', txt)
        if m:
            cd, vl = m.group(1), float(m.group(2))
            is_plan = 'план' in txt.lower()
            if is_plan:
                if cd not in dn and cd not in pn:
                    pn[cd] = vl
            else:
                dn[cd] = vl
    return dict(pn) | dn, pn  # (all, plans-only)

# fill() — called by __main__
vols_all, plans = volumes(date)
vols = {k: v for k, v in vols_all.items() if k not in plans}  # works only
```

The key: `is_plan = 'план' in txt.lower()` works because the fact text now contains the original `"Планы"` prefix (stored by `_extract_vor_codes()`), not a stripped version from Grok.

## Edge Cases Handled

| Case | Input | Behavior |
|------|-------|----------|
| No space between unit and next word | `1.5 м3Планы 3.3.2 = 104.3` | Correctly splits: `м3` is the unit, `Планы` starts the next VOR prefix |
| No space before unit | `104.3м3` | Unit captured as `м3` |
| Comma as decimal separator | `104,5` | Volume parsed as `104.5` |
| Multiple consecutive codes | `3.3.2 = 50 4.1.1 = 30` | Both extracted via while loop |
| Remaining text punctuation artifacts | `м3. Атантай` → remaining | Leading `. ` stripped from remaining text |
| VOR-only message | `3.3.2 = 104.3` | Grok skipped entirely (no remaining text) |
