# Poll Business Logic — _get_work_items_from_template (16.07.2026)

## Design

The poll shows work items from the EJO template filtered by schedule dates from `bot_schedule_phases`. Three categories:

| Category | Condition | Show? |
|----------|-----------|-------|
| **Active** | start_date ≤ today ≤ end_date AND ostatok > 0 | ✅ Show |
| **Overdue** | end_date < today AND ostatok > 0 | ✅ Show (backlog) |
| **Future** | start_date > today | ❌ Hidden |
| No schedule | No matching phase in DB AND ostatok > 0 | ✅ Show (fallback) |
| No residual | ostatok ≤ 0 (incl. None) | ❌ Hidden |

## Implementation

```python
def _is_visible(phase_num, ostatok):
    s = schedule_map[phase_num]  # {start: date, end: date}
    if s['start'] is None:
        return ostatok > 0
    if s['start'] > today:
        return False              # Future — hide
    if s['start'] <= today and s['end'] and s['end'] >= today:
        return ostatok > 0        # Active
    if s['end'] and s['end'] < today and ostatok > 0:
        return True               # Overdue with backlog
    return False
```

## Schedule loading

```python
cu2.execute("""
    SELECT phase_num, MIN(start_date), MAX(end_date)
    FROM bot_schedule_phases
    GROUP BY phase_num
""")
```

Groups all sub-tasks under their phase number. Uses MIN start (earliest task) and MAX end (latest task) for the phase-level decision.

## Why not status-based

Previously used `WHERE status = 'active'` which was inaccurate:
- Phase 2 was marked 'active' but ended 30.06 — still appeared in poll
- Phase 4 was 'active' (future dates) but work hadn't started — appeared in poll
- Phase 7 was 'active' but template had no residuals — not in poll

Schedule dates are the source of truth. Status column is secondary.

## Residual calculation

```python
ostatok = _safe_float(ws.cell(row, 21).value)    # Col U — remaining
if ostatok <= 0:
    plan_cum = _safe_float(ws.cell(row, 18).value)  # Col R — plan cumulative
    fact_cum = _safe_float(ws.cell(row, 19).value)  # Col S — fact cumulative
    if plan_cum > 0:
        ostatok = plan_cum - fact_cum                 # Fallback calculation
```

Col 21 may be None (Excel formulas not cached by openpyxl). Fallback: plan − fact.
