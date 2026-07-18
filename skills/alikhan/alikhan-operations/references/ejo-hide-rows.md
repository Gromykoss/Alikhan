# EJO Auto-Hide Rows — Schedule-Based Visibility (v2)

**Added:** 2026-07-14, **Updated:** 2026-07-14 (schedule-aware)
**File:** `fill_ejo.py` → `_hide_rows(ws)`
**Trigger:** called automatically after every EJO generation, before saving

## Architecture

The EJO work table (rows 24-851) has a 4-level structure:
- **Level 1:** Section title — column A, no code in C (e.g. "2 ЭТАП...")
- **Level 2:** Subsection title — column A, no code in C (e.g. "2.1 Земляные работы")
- **Level 3:** Work items — column C, codes like "2.1.5", "3.1.1"
- **Level 4:** Sub-items — column C, codes like "2.1.9.1", "3.3.2.1"
- **Level-2 data rows:** Codes like "8.1", "8.2" in column C — these are WORK ITEMS, not headers

## Phase Dates (from bot_schedule_phases)

```
Phase 2: ends 2026-06-30 → DONE
Phase 3: ends 2026-07-31 → ACTIVE
Phase 4: ends 2026-10-30 → ACTIVE
Phase 7: ends 2026-10-01 → ACTIVE
Phase 8: ends 2027-07-31 → ACTIVE (future, no work yet)
```

## Rules

| Level | Visibility |
|-------|-----------|
| 1 (Этап) | Always visible |
| 2 (Раздел, col A) | Always visible |
| 2 (work codes, col C) | Visible only if subsection has children or work |
| 3-4 | Phase-dependent |

**For level 3/4 rows, per subsection:**

| Subsection state | Phase status | Action |
|-----------------|-------------|--------|
| All complete (no остаток, no daily) | Any | Hide all 3/4 |
| Has остаток | DONE (end < today) | Show only rows with остаток > 0 |
| Has work | ACTIVE (end >= today) | Show all 3/4 |
| No work | ACTIVE | Hide all 3/4 |

**For level-2 data rows (codes in col C like 8.1, 8.2):**

| Condition | Action |
|-----------|--------|
| Has level 3/4 children | Visible |
| Has остаток or daily work | Visible |
| Empty (no children, no work) | HIDDEN |

## Implementation

```python
def _hide_rows(ws):
    from datetime import date as dt_date
    from db import get_conn
    import psycopg2.extras
    
    # 1. Query phase end dates from bot_schedule_phases
    phase_ends = {}
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT phase_num, MAX(end_date) as end_date FROM bot_schedule_phases "
            "WHERE end_date IS NOT NULL GROUP BY phase_num"
        )
        for row in cur.fetchall():
            phase_ends[str(row['phase_num'])] = row['end_date']
        cur.close()
    except Exception:
        # Fallback: hardcoded from AGENTS.md
        phase_ends = {'2': date(2026,6,30), '3': date(2026,7,31),
                       '4': date(2026,10,30), '5': date(2027,7,1),
                       '6': date(2027,7,10), '7': date(2026,10,1), '8': date(2027,7,31)}
    
    today = date.today()
    
    def _code_lvl(code_str):
        """Return (section, subsection, level_depth)."""
        parts = code_str.strip().split('.')
        if len(parts) >= 2:
            return parts[0], '.'.join(parts[:2]), len(parts)
        return parts[0] if parts else '', '', len(parts)
    
    # 2. Scan rows: header_rows (col C empty, col A has text)
    header_rows = set()
    row_map = {}  # code → (row, остаток, daily)
    for r in range(24, 852):
        cd = ws.cell(r, 3).value
        if not cd:
            a_val = ws.cell(r, 1).value
            if a_val:
                header_rows.add(r)  # never hide headers
            continue
        code = str(cd).strip()
        u_val = ws.cell(r, 21).value  # остаток
        l_val = ws.cell(r, 12).value  # суточный
        row_map[code] = (r, float(u_val or 0), float(l_val or 0))
    
    # 3. Group by subsection (2nd level: "2.1", "8.3")
    subsections = {}
    for code, (r, ost, daily) in row_map.items():
        sect, sub, lvl = _code_lvl(code)
        if not sub: continue
        subsections.setdefault(sub, []).append((code, r, ost, daily, lvl))
    
    # 4. Apply rules
    visible = set()
    for sub, rows in subsections.items():
        sect = sub.split('.')[0]
        phase_end = phase_ends.get(sect)
        
        has_ostatok = any(ost > 0 for _, _, ost, _, _ in rows)
        has_daily = any(daily > 0 for _, _, _, daily, _ in rows)
        all_complete = not has_ostatok and not has_daily
        phase_done = phase_end and phase_end < today
        phase_active = phase_end and phase_end >= today
        
        # Level 1 always visible. Level 2: only if work or children.
        for code, r, ost, daily, lvl in rows:
            if lvl == 1:
                visible.add(r)
            elif lvl == 2:
                has_children = any(clvl >= 3 for _, _, _, _, clvl in rows)
                if has_children or has_ostatok or has_daily:
                    visible.add(r)
        
        # Level 3/4: phase-dependent
        for code, r, ost, daily, lvl in rows:
            if lvl <= 2: continue
            if all_complete: continue
            if phase_done and has_ostatok and ost > 0:
                visible.add(r)
            elif phase_active and (has_ostatok or has_daily):
                visible.add(r)
    
    # 5. Apply visibility (NEVER hide header_rows)
    hidden_count = 0
    for r in range(24, 852):
        if r not in visible and r not in header_rows:
            ws.row_dimensions[r].hidden = True
            hidden_count += 1
    
    print(f"[HIDE ROWS] Hidden: {hidden_count}, Visible: {len(visible)} + {len(header_rows)} headers")

## Key columns

- Col A(1) = section/subsection title (header detection)
- Col C(3) = work code
- Col L(12) = daily volume
- Col U(21) = остаток

## Example output

```
[HIDE ROWS] Hidden: 741, Visible: 39 + 48 headers
```

## Pitfalls

- **Header vs work item:** "8.1" in col C is a work item code, NOT a header. Headers are in col A only.
- **Empty sections:** Phase 8 has only level-2 items (8.1-8.8) with no children → all hidden.
- **Phase 4:** 4.1 header visible (has level 3 children 4.1.1-4.1.6), but all 3/4 hidden (no work today).
- **Hiding does not delete data** — formulas still work, user can unhide in Excel.
- **Schedule fallback:** if DB query fails, uses hardcoded dates from AGENTS.md.
