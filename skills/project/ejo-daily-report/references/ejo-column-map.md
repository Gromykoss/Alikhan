# ЕЖО Column Map — Excel Template Structure

## Sheet: «Ежедневный отчет»

Header row: 20. Data rows: 24+.

### Work volume columns (code writes these in `fill_ejo.py`)

| Col | Letter | Header (row 20) | Type | fill_ejo.py writes |
|-----|--------|-----------------|------|-------------------|
| 1 | A | Подобъект | Building name | — (template) |
| 3 | C | Код ВОР | VOR code | — (template) |
| 4 | D | Наименование работ | Description | — (template) |
| 10 | J | Ед.изм. | Unit (м3, т, шт) | — (template) |
| 11 | K | Кол-во | Plan volume | — (template) |
| 12 | L | Объем за сутки | Daily actual | `v` |
| 13 | M | — | Same as L (merged) | `v` |
| 14 | N | — | Days worked | `1` |
| 15 | O | Накопительный объем за месяц | Header (merged) | — |
| 16 | P | — | Monthly cumulative value | `prev_p + v` |
| 17 | Q | — | Monthly % | `(prev_p+v) / mp` |
| 18 | R | Накопительный объем с начала СМР | Header (merged) | — |
| 19 | S | — | SMR cumulative value | `prev_s + v` |
| 20 | T | — | SMR % | `(prev_s+v) / tp` |
| 21 | U | — | Remaining (остаток) | `k_plan − prev_s − v` |

### Where values come from

- `v` = today's volume from QA facts (`volumes()` → `bot_memory_facts`, categories: бетонирование/монтаж/земляные работы)
- `prev_p` = yesterday's monthly cumulative → `yesterday_cum()` reads col 16 from `/tmp/ЕЖО_{yesterday}_v*.xlsx`
- `prev_s` = yesterday's SMR cumulative → `yesterday_cum()` reads col 19 from same file
- `mp` = monthly plan (col 15 in template, but accessed as `ws.cell(r, 15).value` in code)
- `tp` = total plan (col 18 in template, but accessed as `ws.cell(r, 18).value` in code)
- `k_plan` = contract plan (col 11)

### Guard logic (updated 2026-07-08)

- Daily columns (L=12, M=13, N=14) are cleared for **ALL** rows with VOR codes, not just rows with work today. This prevents template contamination — old daily values from corrected templates no longer "freeze" and appear as current work.
- Cumulative columns (P=16, S=19) and remaining (U=21) are cleared only for rows with work today, then refilled.
- Monthly % (Q=17) and SMR % (T=20) are recalculated for rows with work today.
- Rows without work today: daily columns empty, cumulative columns preserved from template (carries forward via `yesterday_cum()` chain).

### Template contamination pitfall (fixed 2026-07-08)

**Problem:** `_update_template_from_correction` copies corrected ЕЖО as new template. The corrected file contains daily values (e.g., 798 in L/M for code 3.1.4). On the next day, if no work for that code, the old daily value remains visible — looks like "работы выполнены" when they weren't.

**Fix:** `fill_ejo.py` now clears L, M, N for every VOR-coded row before filling today's data. Only cumulative columns survive across days.
