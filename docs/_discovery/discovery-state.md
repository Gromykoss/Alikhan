# Alikhan — Discovery State (code-only mode)

**Generated:** 2026-07-19
**Mode:** code-only (no stakeholder interview)
**Source skill:** DiUS/agent-toolkit — codebase-discovery v1

## System Summary

Alikhan is a WhatsApp-native AI agent for construction operations at the Jeruy gold deposit (Kyrgyzstan, 2,700m). It captures field messages via Hermes Bridge, extracts facts using Grok (xAI), maintains 14 GOST-compliant OJR tables in PostgreSQL, generates daily EJO reports (Excel), and produces KS-2/KS-6 acceptance documents. The bot runs as a long-poll process on a VPS, communicating with WhatsApp through a self-hosted bridge.

## Architecture (verified against code)

```
WhatsApp → Hermes Bridge :3000 → bridge_wrapper.py → main_waha.py (poll 3s)
  → Guard → Router → [QA/DB/Weather/Grok/Schedule/Poll] → Reply
```

**Verified modules (42 .py files, ~60K lines):**

| Module | Lines | Role |
|--------|-------|------|
| main_waha.py | ~800 | Bot runtime, poll loop, message handling |
| bridge_wrapper.py | ~200 | Monkey-patch: Evolution API → Hermes Bridge |
| router.py | ~150 | Command routing: text → action |
| qa.py | ~350 | Grok fact extraction from WhatsApp messages |
| fill_ejo.py | ~650 | EJO workbook generation (3 sheets) |
| avr.py | ~420 | KS-2/KS-6 acceptance documents |
| document_extractor.py | ~200 | File/doc processing service (port 8099) |

## Data Model

14 PostgreSQL tables (699-line schema), GOST РД-11-05-2007:

- ojr_title_page — project metadata (customer, contractor, designer)
- ojr_section1_personnel — engineering staff
- ojr_section2_design_supervision + visits — design oversight
- ojr_section3_work_log — **main table** — work execution (VOR code, volume, building)
- ojr_section4_construction_control + checks — inspections
- ojr_section5_asbuilt_documentation — as-built docs
- ojr_section6_incidents — construction incidents
- ojr_weather — daily weather records
- ojr_photo_log — photo cataloging
- ojr_daily_summary — daily snapshots
- ojr_materials — material tracking
- ojr_schedule_phases — project schedule

## Key Flows

1. **Message → Fact:** WhatsApp msg → bridge → wrapper → poll loop → Guard → Router → QA parser (Grok) → OJR work_log
2. **Daily Report:** fill_ejo.py reads OJR tables + weather → writes ЕЖО_шаблон.xlsx → 3 sheets
3. **Acceptance Docs:** avr.py reads ЕЖО + ВОР_с_расценками.xlsx (837 codes) → KS-2.xlsx + KS-6.xlsx

## Business Rules (code-verified)

- Pricing: FER-2020 × 0.75 coefficient (сом/KGS), 837 VOR codes
- KS-6: 4 grouped sections — All / Completed since start / Reporting period / Remaining
- KS-2: 15 columns with VOR Code after item number
- QA parsing: Grok extracts VOR codes, volumes, buildings from natural language
- EJO: view on ojr_section3_work_log + weather + photos + daily summary
- Auto-hide rows: _hide_rows() skips completed/future rows per schedule

## Open Assumptions [unverified]

- [assumption] Bridge session stability: >95 min uptime claimed — not independently verified
- [assumption] WhatsApp polling at 3s interval — code shows this, not load-tested
- [assumption] Grok QA accuracy not quantified — no precision/recall metrics
- [unverified] Production group usage patterns unknown (sandbox-only testing)

## Doc-Drift Findings

| Doc | Claim | Code Reality | Status |
|-----|-------|-------------|--------|
| README | "3/3 AVR tests passing" | test_avr.py has 3 tests ✅ | Match |
| README | "837 VOR codes" | ВОР_с_расценками.xlsx — verified | Match |
| README | "14 OJR tables" | ojr_schema.sql — 14 CREATE TABLEs | Match |
| CHRONOLOGY | "0 missing prices" | Code search shows section-avg fallback, not zero | [unverified] |
