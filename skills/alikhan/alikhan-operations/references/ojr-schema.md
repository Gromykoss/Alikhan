# ОЖР DB Schema Reference

> ГОСТ РД-11-05-2007 / Приказ Минстроя РФ №1026/пр
> Applied: 2026-07-18 | 2924 rows migrated from bot_memory_facts + bot_poll_residuals

## Quick connection

```bash
docker exec evolution-postgres psql -U evolution -d evolution_db
```

## Schema files

| File | Path |
|------|------|
| CREATE TABLE | `/home/hermes-workspace/Alikhan-migration/db/ojr_schema.sql` |
| Migration | `/home/hermes-workspace/Alikhan-migration/db/ojr_migration.sql` |
| ER Diagram | `/home/hermes-workspace/Alikhan-migration/db/ojr_er_diagram.md` |
| Fill Guide | `/home/hermes-workspace/Alikhan-migration/db/ojr_fill_guide.md` |

## Tables (14 total)

| Table | ГОСТ | Rows | Purpose |
|-------|------|------|---------|
| `ojr_title_page` | Title | 1 | Customer/contractor/designer/object/contract |
| `ojr_section1_personnel` | §1 | 71 | ITR personnel (org, name, position, dates) |
| `ojr_section2_design_supervision` | §2 | 0 | Design supervision (responsible, cert, deputies) |
| `ojr_section2_visits` | §2 | 0 | Supervision visit log |
| `ojr_section3_work_log` | §3 | 69 | Work execution (date, VOR code, volume, building, contractor) |
| `ojr_section4_construction_control` | §4 | 0 | Construction control (organization, responsible, cert) |
| `ojr_section4_checks` | §4 | 0 | Control check acts |
| `ojr_section5_asbuilt_docs` | §5 | 0 | As-built docs (acts, protocols, certificates) |
| `ojr_section6_gosstroynadzor` | §6 | 0 | State supervision (inspections, orders) |
| `ojr_weather` | — | 0 | Daily weather (temp, precip, wind, phenomenon) |
| `ojr_photo_log` | — | 2765 | Photo log (building, date, Grok Vision description, EJO grid) |
| `ojr_daily_summary` | — | 18 | Daily aggregates (volumes, personnel, completion %) |
| `ojr_materials` | — | 0 | Materials log (name, quantity, supplier, cert) |
| `ojr_incidents` | — | 0 | Incidents (type, severity, downtime) |

## ENUM types

- `ojr_supervision_status` — planned | conducted | violations_found | compliant
- `ojr_inspection_result` — no_violations | violations_found | order_issued | resolved
- `ojr_weather_phenomenon` — clear | cloudy | overcast | rain | snow | hail | fog | mixed

## Views (5)

- `ojr_v_daily_works` — works by date/building/code
- `ojr_v_active_personnel` — active ITR staff
- `ojr_v_open_gsn_orders` — unresolved GSN orders with days_left
- `ojr_v_open_cchecks` — unresolved construction control checks
- `ojr_v_recent_weather` — last 30 days weather

## Foreign keys to existing tables

| ojr_* column | → existing table | on delete |
|-------------|------------------|-----------|
| `schedule_phase_id` | `bot_schedule_phases` | SET NULL |
| `source_fact_id` | `bot_memory_facts` | SET NULL |
| `source_poll_id` | `bot_poll_state` | SET NULL |
| `file_message_id` | `bot_memory_messages` | SET NULL |

## Key UNIQUE constraints

| Table | Constraint |
|-------|-----------|
| `ojr_title_page` | only one `is_active = TRUE` |
| `ojr_section3_work_log` | `(work_date, vor_code, building, category)` — plan and fact are separate rows |
| `ojr_weather` | `weather_date` |
| `ojr_daily_summary` | `summary_date` |

## Migration pitfalls

1. **Russian decimal separator**: facts contain `113,56` — must REPLACE(..., ',', '.') before NUMERIC cast
2. **Non-numeric volume strings**: use BEGIN/EXCEPTION block to skip unparseable values
3. **v_fact.id**: must SELECT `id` column explicitly in cursor loop if referencing it
4. **Photos without building tag**: fallback to `'Общие планы'` when `tags->>'building'` is null/empty
