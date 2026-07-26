#!/usr/bin/env python3
"""Knowledge Graph for Alikhan — Anthropic Graph Engineering Playbook.
Extract → Resolve → Assemble → Query → Grounded Answer → Maintain.

Domain: WhatsApp bot bugs, PostgreSQL/ОЖР quirks, Hermes Bridge patterns,
document extraction, ЕЖО templates, recurring fixes.

No external NLP, no graph DB. Regex + curated seed triples + NetworkX.
"""
import os
import re
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import networkx as nx

ALIKHAN_ROOT = os.path.expanduser("~/Alikhan-migration")
# Prefer workspace path if expanduser differs
if not os.path.isdir(ALIKHAN_ROOT):
    ALIKHAN_ROOT = "/home/hermes-workspace/Alikhan-migration"

GRAPH_DIR = os.path.join(ALIKHAN_ROOT, "knowledge_graph")
GRAPH_FILE = os.path.join(GRAPH_DIR, "graph.json")
os.makedirs(GRAPH_DIR, exist_ok=True)

# ─── Source paths ───────────────────────────────────────────
CHRONOLOGY = os.path.join(ALIKHAN_ROOT, "CHRONOLOGY.md")
AGENTS_MD = os.path.join(ALIKHAN_ROOT, "AGENTS.md")
BUGS_MD = os.path.join(ALIKHAN_ROOT, "bot", "BUGS.md")
MEMORY_MD = os.path.expanduser("~/.hermes/profiles/alikhan/memories/MEMORY.md")
RUNBOOK = os.path.join(ALIKHAN_ROOT, "RUNBOOK.md")
INDEX_MD = os.path.join(ALIKHAN_ROOT, "INDEX.md")

# Bot modules of interest
BOT_COMPONENTS = {
    "main_waha": "bot/main_waha.py",
    "bridge_wrapper": "bot/bridge_wrapper.py",
    "router": "bot/router.py",
    "poll": "bot/poll.py",
    "qa": "bot/qa.py",
    "fill_ejo": "bot/fill_ejo.py",
    "document_extractor": "bot/document_extractor.py",
    "avr": "bot/avr.py",
    "vision_checklist": "bot/vision_checklist.py",
    "db": "bot/db.py",
    "db_lookup": "bot/db_lookup.py",
    "db_memory": "bot/db_memory.py",
    "messaging": "bot/messaging.py",
    "handlers": "bot/handlers.py",
    "daily_snapshot": "bot/daily_snapshot.py",
    "stt": "bot/stt.py",
    "alerter": "bot/alerter.py",
}

# ОЖР / bot tables
DB_TABLES = [
    "ojr_title_page",
    "ojr_section1_personnel",
    "ojr_section2_design_supervision",
    "ojr_section2_visits",
    "ojr_section3_work_log",
    "ojr_section4_construction_control",
    "ojr_section4_checks",
    "ojr_section5_asbuilt_docs",
    "ojr_section6_gosstroynadzor",
    "ojr_weather",
    "ojr_photo_log",
    "ojr_daily_summary",
    "ojr_materials",
    "ojr_incidents",
    "bot_memory_facts",
    "bot_memory_messages",
    "bot_schedule_phases",
    "bot_building_profiles",
    "bot_poll_state",
    "bot_calendar_events",
    "bot_poll_residuals",  # deprecated
]


def _t(subject, predicate, obj, source, confidence=0.9):
    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source": source,
        "confidence": confidence,
    }


# ─── Stage 0: CURATED SEED (domain knowledge) ───────────────
def seed_domain_triples() -> list[dict]:
    """Hard-coded high-confidence facts from MEMORY.md + AGENTS.md + architecture."""
    src = "seed:domain"
    triples = []

    # Project
    triples += [
        _t("project/alikhan", "described_as",
           "WhatsApp AI agent for ТЗРК Джеруй construction site (Python v5)", src, 0.99),
        _t("project/alikhan", "located_at", ALIKHAN_ROOT, src, 0.99),
        _t("project/alikhan", "depends_on", "service/hermes-whatsapp-bridge", src, 0.95),
        _t("project/alikhan", "depends_on", "db_table/ojr_section3_work_log", src, 0.95),
        _t("project/alikhan", "implements", "bot_component/main_waha", src, 0.95),
        _t("decision/delegation-gate", "described_as",
           "DeepSeek v4 Pro = orchestrator only; code via Codex CLI / Grok Build (25.07.2026)",
           src, 0.98),
        _t("decision/delegation-gate", "affects", "project/alikhan", src, 0.95),
        _t("decision/ojr-migration", "described_as",
           "DB restructured to 14 ОЖР tables per GOST RD-11-05-2007 (18.07.2026)", src, 0.98),
        _t("decision/ojr-migration", "occurred_on", "2026-07-18", src, 0.98),
        _t("decision/hermes-bridge-migration", "described_as",
           "Evolution API replaced by Hermes WhatsApp Bridge :3000 (15.07.2026)", src, 0.98),
        _t("decision/hermes-bridge-migration", "occurred_on", "2026-07-15", src, 0.98),
        _t("decision/hermes-bridge-migration", "implements", "bot_component/bridge_wrapper", src, 0.95),
    ]

    # Services
    triples += [
        _t("service/hermes-whatsapp-bridge", "described_as",
           "Hermes WhatsApp bridge on :3000, systemd user unit Restart=always", src, 0.95),
        _t("service/hermes-whatsapp-bridge", "located_at",
           "~/.hermes/hermes-agent/scripts/whatsapp-bridge/bridge.js", src, 0.9),
        _t("service/alikhan", "described_as",
           "alikhan.service — main bot (main_waha.py via systemd)", src, 0.95),
        _t("service/alikhan-document-extractor", "described_as",
           "document extractor HTTP on 127.0.0.1:8099", src, 0.95),
        _t("service/alikhan-document-extractor", "implements",
           "bot_component/document_extractor", src, 0.9),
    ]

    # WhatsApp groups
    triples += [
        _t("group/sandbox", "described_as",
           "Sandbox WhatsApp group 120363179621030401@g.us — full bot access", src, 0.98),
        _t("group/production", "described_as",
           "Production WhatsApp group 120363400682390076@g.us — listen + weather only; never send without approval",
           src, 0.98),
        _t("group/sandbox", "status_is", "test_target", src, 0.9),
        _t("group/production", "status_is", "protected", src, 0.95),
    ]

    # Bot components
    for name, path in BOT_COMPONENTS.items():
        triples.append(_t(f"bot_component/{name}", "located_at", path, src, 0.95))
        triples.append(_t(f"bot_component/{name}", "referenced_in", "project/alikhan", src, 0.9))

    triples += [
        _t("bot_component/main_waha", "depends_on", "bot_component/bridge_wrapper", src, 0.95),
        _t("bot_component/main_waha", "depends_on", "bot_component/router", src, 0.9),
        _t("bot_component/router", "routes_to", "bot_component/qa", src, 0.9),
        _t("bot_component/router", "routes_to", "bot_component/poll", src, 0.9),
        _t("bot_component/router", "routes_to", "bot_component/fill_ejo", src, 0.85),
        _t("bot_component/router", "routes_to", "bot_component/avr", src, 0.85),
        _t("bot_component/poll", "writes_to", "db_table/ojr_section3_work_log", src, 0.95),
        _t("bot_component/qa", "writes_to", "db_table/bot_memory_facts", src, 0.95),
        _t("bot_component/fill_ejo", "reads_from", "db_table/ojr_section3_work_log", src, 0.95),
        _t("bot_component/fill_ejo", "reads_from", "db_table/ojr_weather", src, 0.9),
        _t("bot_component/fill_ejo", "reads_from", "db_table/ojr_photo_log", src, 0.9),
        _t("bot_component/fill_ejo", "implements", "template/ejo", src, 0.95),
        _t("bot_component/avr", "implements", "template/ks2", src, 0.9),
        _t("bot_component/avr", "implements", "template/ks6", src, 0.9),
        _t("bot_component/vision_checklist", "writes_to", "db_table/ojr_photo_log", src, 0.85),
        _t("bot_component/vision_checklist", "writes_to", "db_table/ojr_section3_work_log", src, 0.8),
        _t("bot_component/document_extractor", "described_as",
           "Local document extraction service for PDF/MPP/XLSX → structured data", src, 0.9),
    ]

    # DB tables
    for table in DB_TABLES:
        triples.append(_t(f"db_table/{table}", "referenced_in", "project/alikhan", src, 0.9))
    triples += [
        _t("db_table/ojr_section3_work_log", "described_as",
           "Main ОЖР section 3 — work volumes (code, qty, building); source for ЕЖО view", src, 0.98),
        _t("db_table/bot_memory_facts", "described_as",
           "Intermediate QA facts layer before routing into ojr_* tables", src, 0.95),
        _t("db_table/bot_poll_residuals", "status_is", "deprecated", src, 0.95),
        _t("db_table/bot_poll_residuals", "replaced_by", "db_table/ojr_section3_work_log", src, 0.95),
        _t("db_table/ojr_weather", "described_as",
           "Daily weather via Open-Meteo (42.284, 72.765) → DB + Excel", src, 0.9),
        _t("db_table/ojr_photo_log", "described_as",
           "Site photos with date/work binding; building tag required for poll visibility", src, 0.9),
    ]

    # Templates
    triples += [
        _t("template/ejo", "located_at", "bot/templates/ЕЖО_шаблон.xlsx", src, 0.98),
        _t("template/ejo", "described_as",
           "Daily work journal (ЕЖО): view over ojr_section3_work_log + weather + photos; N=100%, U=O−P",
           src, 0.95),
        _t("template/vor", "located_at", "report/templates/ВОР_с_расценками.xlsx", src, 0.9),
        _t("template/vor", "described_as", "837 ВОР codes with prices (ФЕР-2020 × 0.75)", src, 0.9),
        _t("template/ks2", "described_as", "АВР КС-2 monthly act — 14/15 columns including Код ВОР", src, 0.9),
        _t("template/ks6", "described_as", "АВР КС-6 cumulative journal — 4 grouped sections, 780+ rows", src, 0.9),
    ]

    # API quirks (from MEMORY + AGENTS + audit tips)
    triples += [
        _t("api_quirk/postgres-collation-warning", "described_as",
           "PostgreSQL collation WARNING spam; fix: UPDATE pg_catalog.pg_database SET datcollversion=NULL WHERE datname='evolution_db' (autocommit). psycopg2 options/SET do not work.",
           src, 0.98),
        _t("api_quirk/postgres-collation-warning", "affects", "project/alikhan", src, 0.95),
        _t("api_quirk/postgres-collation-warning", "fixed_by",
           "fix/postgres-datcollversion-null", src, 0.95),
        _t("fix/postgres-datcollversion-null", "described_as",
           "UPDATE pg_catalog.pg_database SET datcollversion=NULL WHERE datname='evolution_db' with autocommit",
           src, 0.98),

        _t("api_quirk/bridge-photo-caption-empty", "described_as",
           "Hermes Bridge does not pass WhatsApp photo caption in media_meta; caption always empty. Real caption in msg.get('conversation','').",
           src, 0.98),
        _t("api_quirk/bridge-photo-caption-empty", "affects", "bot_component/main_waha", src, 0.95),
        _t("api_quirk/bridge-photo-caption-empty", "fixed_by", "fix/caption-fallback-chain", src, 0.95),
        _t("fix/caption-fallback-chain", "described_as",
           "main_waha.py ~632/~788: cap = media_meta.get('fileName') or media_meta.get('caption') or msg.get('conversation')",
           src, 0.98),
        _t("fix/caption-fallback-chain", "affects", "bot_component/main_waha", src, 0.9),

        _t("api_quirk/bridge-send-requires-real-jid", "described_as",
           "Bridge /send returns 500 unless real JID used (sandbox 120363179621030401@g.us)", src, 0.95),
        _t("api_quirk/bridge-send-requires-real-jid", "affects", "service/hermes-whatsapp-bridge", src, 0.9),

        _t("api_quirk/bridge-media-type-image", "described_as",
           "After Bridge migration photos arrive as _media.mediaType=='image', not Evolution imageMessage",
           src, 0.95),
        _t("api_quirk/bridge-media-type-image", "affects", "bot_component/main_waha", src, 0.9),
        _t("api_quirk/bridge-media-type-image", "fixed_by", "fix/photo-detection-media", src, 0.9),
        _t("fix/photo-detection-media", "described_as",
           "Detect images via _media.mediaType == image; Grok vision writes tags description", src, 0.9),

        _t("api_quirk/log-stale-errors-look-fresh", "described_as",
           "Old errors in /tmp/alikhan.log look fresh — always verify /send directly; use grep -cv WARNING for real log volume",
           src, 0.9),
    ]

    # Recurring bugs from MEMORY (fixed 2026-07-25)
    triples += [
        _t("bug/photo-default-building-bez-teg", "described_as",
           "Photos saved with default building='без тег' are invisible in poll", src, 0.98),
        _t("bug/photo-default-building-bez-teg", "status_is", "fixed", src, 0.95),
        _t("bug/photo-default-building-bez-teg", "occurred_on", "2026-07-25", src, 0.9),
        _t("bug/photo-default-building-bez-teg", "affects", "bot_component/poll", src, 0.95),
        _t("bug/photo-default-building-bez-teg", "affects", "bot_component/main_waha", src, 0.95),
        _t("bug/photo-default-building-bez-teg", "fixed_by", "fix/building-default-obshchiy-plan", src, 0.98),
        _t("fix/building-default-obshchiy-plan", "described_as",
           "Default building='Общий план' in main_waha.py + fallback in poll.py", src, 0.98),

        _t("bug/qa-technika-to-work-log", "described_as",
           "QA routes category='техника' to ojr_section3_work_log as volume=0", src, 0.98),
        _t("bug/qa-technika-to-work-log", "status_is", "fixed", src, 0.95),
        _t("bug/qa-technika-to-work-log", "occurred_on", "2026-07-25", src, 0.9),
        _t("bug/qa-technika-to-work-log", "affects", "bot_component/qa", src, 0.95),
        _t("bug/qa-technika-to-work-log", "affects", "db_table/ojr_section3_work_log", src, 0.9),
        _t("bug/qa-technika-to-work-log", "fixed_by", "fix/qa-technika-to-memory-facts", src, 0.98),
        _t("fix/qa-technika-to-memory-facts", "described_as",
           "Dedicated elif branch inserts category=техника into bot_memory_facts instead of work_log",
           src, 0.98),
        _t("fix/qa-technika-to-memory-facts", "writes_to", "db_table/bot_memory_facts", src, 0.9),
    ]

    # Data flow edges
    triples += [
        _t("project/alikhan", "described_as",
           "Flow: WhatsApp → Bridge:3000 → bridge_wrapper → main_waha (poll 3s) → Guard → Router → QA/DB/Weather/Grok/Schedule/Poll → Reply",
           src, 0.95),
        _t("bot_component/qa", "routes_to", "db_table/bot_memory_facts", src, 0.95),
        _t("db_table/bot_memory_facts", "routes_to", "db_table/ojr_section3_work_log", src, 0.9),
        _t("db_table/ojr_section3_work_log", "routes_to", "bot_component/fill_ejo", src, 0.9),
    ]

    return triples


# ─── Stage 1: EXTRACT ───────────────────────────────────────
def _normalize_date(raw: str) -> str:
    """Normalize DD.MM.YYYY or YYYY-MM-DD → YYYY-MM-DD."""
    raw = raw.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return raw


def extract_entities_from_file(filepath: str) -> list[dict]:
    """Extract entities and S-P-O triples from a markdown file (Alikhan domain)."""
    triples = []
    if not os.path.exists(filepath):
        return triples

    with open(filepath, encoding="utf-8", errors="replace") as f:
        content = f.read()

    base = os.path.basename(filepath)

    # Chronology headers: ## YYYY-MM-DD — title  OR  ## DD.MM.YYYY — title  OR  ## YYYY-MM-DD (time) — title
    for match in re.finditer(
        r"^##\s+(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})(?:\s*\([^)]*\))?\s*[-—]\s*(.+)$",
        content,
        re.M,
    ):
        date = _normalize_date(match.group(1))
        title = match.group(2).strip()
        # Drop trailing time-only headers noise
        entity_id = f"event/{date}/{title[:50].strip()}"
        triples.append(_t(entity_id, "occurred_on", date, filepath, 0.95))
        triples.append(_t(entity_id, "described_as", title, filepath, 0.90))
        triples.append(_t(entity_id, "referenced_in", "project/alikhan", filepath, 0.85))

    # Bare ## YYYY-MM-DD headers (no title after dash)
    for match in re.finditer(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", content, re.M):
        date = match.group(1)
        entity_id = f"event/{date}/daily-log"
        triples.append(_t(entity_id, "occurred_on", date, filepath, 0.85))
        triples.append(_t(entity_id, "referenced_in", "project/alikhan", filepath, 0.8))

    # Bug IDs: AL-XXX, BUG-AL-XXX
    for match in re.finditer(r"\b(BUG-AL-\d+|AL-\d+)\b", content):
        bug_id = match.group(1)
        triples.append(_t(f"bug/{bug_id}", "mentioned_in", base, filepath, 0.92))
        triples.append(_t(f"bug/{bug_id}", "affects", "project/alikhan", filepath, 0.85))

    # Tasks T-XXX
    for match in re.finditer(r"\b(T-\d+)\b", content):
        triples.append(_t(f"task/{match.group(1)}", "mentioned_in", base, filepath, 0.88))

    # Bot component file references
    for name in BOT_COMPONENTS:
        if re.search(rf"\b{re.escape(name)}\.py\b|\bbot_component/{name}\b|\b{re.escape(name)}\b", content):
            # only count if looks intentional (file-ish or architectural)
            if re.search(rf"\b{re.escape(name)}\.py\b|`{re.escape(name)}|bot/{re.escape(name)}", content):
                triples.append(
                    _t(f"bot_component/{name}", "mentioned_in", base, filepath, 0.85)
                )

    # DB tables
    for table in DB_TABLES:
        if table in content:
            triples.append(_t(f"db_table/{table}", "mentioned_in", base, filepath, 0.88))

    # Services
    for svc in ("hermes-whatsapp-bridge", "alikhan.service", "alikhan-document-extractor"):
        if svc in content or svc.replace(".service", "") in content:
            sid = svc.replace(".service", "")
            triples.append(_t(f"service/{sid}", "mentioned_in", base, filepath, 0.85))

    # Project name
    if re.search(r"\bAlikhan\b|\bАлихан\b", content, re.I):
        triples.append(_t("project/alikhan", "referenced_in", base, filepath, 0.9))

    # EJO / AVR / OJR keywords
    if re.search(r"\bЕЖО\b|\bEJO\b|fill_ejo", content):
        triples.append(_t("template/ejo", "mentioned_in", base, filepath, 0.85))
    if re.search(r"\bАВР\b|\bКС-2\b|\bКС-6\b|\bavr\.py\b", content):
        triples.append(_t("template/ks2", "mentioned_in", base, filepath, 0.8))
        triples.append(_t("bot_component/avr", "mentioned_in", base, filepath, 0.8))
    if re.search(r"\bОЖР\b|\bojr_", content):
        triples.append(_t("decision/ojr-migration", "mentioned_in", base, filepath, 0.85))
    if re.search(r"Hermes Bridge|bridge_wrapper|Evolution API", content):
        triples.append(_t("decision/hermes-bridge-migration", "mentioned_in", base, filepath, 0.85))
        triples.append(_t("bot_component/bridge_wrapper", "mentioned_in", base, filepath, 0.85))

    # Status markers from BUGS.md table rows
    for match in re.finditer(
        r"\|\s*(AL-\d+|BUG-AL-\d+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s*([✅🔴][^|]*)\|",
        content,
    ):
        bug_id, symptom, cause, fix, _test, status = [g.strip() for g in match.groups()]
        bid = f"bug/{bug_id}"
        triples.append(_t(bid, "described_as", symptom[:120], filepath, 0.9))
        if cause:
            triples.append(_t(bid, "caused_by", cause[:100], filepath, 0.85))
        if fix:
            fix_id = f"fix/{bug_id.lower()}"
            triples.append(_t(bid, "fixed_by", fix_id, filepath, 0.88))
            triples.append(_t(fix_id, "described_as", fix[:120], filepath, 0.88))
        if "✅" in status:
            triples.append(_t(bid, "status_is", "fixed", filepath, 0.9))
        elif "🔴" in status:
            triples.append(_t(bid, "status_is", "active", filepath, 0.9))

    # MEMORY-style bullets with numbered recurring bugs
    for match in re.finditer(
        r"(?:recurring bugs|баг|bug)[^\n]{0,40}?(\d)\)\s*([^\n.]+)",
        content,
        re.I,
    ):
        n, text = match.group(1), match.group(2).strip()[:100]
        triples.append(_t(f"bug/memory-recurring-{n}", "described_as", text, filepath, 0.85))
        triples.append(_t(f"bug/memory-recurring-{n}", "mentioned_in", base, filepath, 0.85))

    return triples


def extract_bugs_md(filepath: str) -> list[dict]:
    """Extra structured extraction from bot/BUGS.md tables."""
    return extract_entities_from_file(filepath)


# ─── Stage 2: RESOLVE ────────────────────────────────────────
def resolve_entities(triples: list[dict]) -> list[dict]:
    """Normalize aliases and entity ids."""
    aliases = {
        "project/алихан": "project/alikhan",
        "service/alikhan.service": "service/alikhan",
        "service/hermes-whatsapp-bridge.service": "service/hermes-whatsapp-bridge",
        "template/ежо": "template/ejo",
        "template/ЕЖО": "template/ejo",
        "db_table/work_log": "db_table/ojr_section3_work_log",
        "bot_component/main": "bot_component/main_waha",
    }

    resolved = []
    for t in triples:
        t = dict(t)
        t["subject"] = aliases.get(t["subject"], t["subject"])
        t["object"] = aliases.get(t["object"], t["object"])
        # Normalize bug IDs case
        if t["subject"].startswith("bug/"):
            rest = t["subject"][4:]
            if re.match(r"(?i)(bug-)?al-\d+", rest):
                t["subject"] = "bug/" + rest.upper().replace("BUG-AL", "BUG-AL")
                # Keep BUG-AL-xxx and AL-xxx distinct prefixes as in source
                if rest.upper().startswith("BUG-AL"):
                    t["subject"] = "bug/" + rest.upper()
                elif rest.upper().startswith("AL-"):
                    t["subject"] = "bug/" + rest.upper()
        resolved.append(t)
    return resolved


# ─── Stage 3: ASSEMBLE ───────────────────────────────────────
def assemble_graph(triples: list[dict]) -> nx.DiGraph:
    """Build directed graph with typed edges and provenance."""
    G = nx.DiGraph()
    for t in triples:
        s, p, o = t["subject"], t["predicate"], t["object"]
        # Skip empty / overly long free-text objects as nodes when they're prose
        if not s or not o:
            continue
        if len(str(o)) > 200 and p in ("caused_by",):
            # keep as edge target but clip node id
            o = str(o)[:120] + "…"
        if not G.has_node(s):
            G.add_node(s, type=s.split("/")[0] if "/" in s else "unknown")
        if not G.has_node(o):
            # free-text objects (dates, descriptions) get type from predicate
            if re.match(r"\d{4}-\d{2}-\d{2}$", str(o)):
                ntype = "date"
            elif p == "described_as":
                ntype = "description"
            elif p == "status_is":
                ntype = "status"
            else:
                ntype = o.split("/")[0] if "/" in str(o) else "unknown"
            G.add_node(o, type=ntype)
        # Prefer higher confidence if edge exists
        if G.has_edge(s, o):
            old = G[s][o]
            if t["confidence"] > old.get("confidence", 0):
                G[s][o]["confidence"] = t["confidence"]
                G[s][o]["predicate"] = p
                G[s][o]["source"] = t["source"]
        else:
            G.add_edge(s, o, predicate=p, source=t["source"], confidence=t["confidence"])
    return G


def graph_stats(G: nx.DiGraph) -> dict:
    def count(prefix):
        return len([n for n in G.nodes if str(n).startswith(prefix)])

    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "projects": count("project/"),
        "events": count("event/"),
        "bugs": count("bug/"),
        "fixes": count("fix/"),
        "api_quirks": count("api_quirk/"),
        "db_tables": count("db_table/"),
        "bot_components": count("bot_component/"),
        "services": count("service/"),
        "templates": count("template/"),
        "decisions": count("decision/"),
        "tasks": count("task/"),
    }


def query_graph(G: nx.DiGraph, center: str, hops: int = 2) -> str:
    """Serialize subgraph around center node as triple lines."""
    nodes = {center}
    frontier = {center}
    for _ in range(hops):
        nxt = set()
        for n in frontier:
            if n in G:
                nxt |= set(G.successors(n)) | set(G.predecessors(n))
        frontier = nxt - nodes
        nodes |= frontier

    existing = [n for n in nodes if n in G]
    if not existing:
        return f"(no nodes found for '{center}')"

    sub = G.subgraph(existing)
    lines = []
    for s, t, data in sub.edges(data=True):
        src = Path(data.get("source", "?")).name
        lines.append(
            f"({s}) --[{data.get('predicate', '?')}]--> ({t}) [src: {src}]"
        )
    return "\n".join(sorted(set(lines)))


# ─── Main ────────────────────────────────────────────────────
def build_graph():
    """Full pipeline: seed + extract → resolve → assemble → save → maintain."""
    all_triples = []

    # Curated seed first (high confidence domain facts)
    all_triples.extend(seed_domain_triples())

    # Extract from project sources
    for path in (CHRONOLOGY, AGENTS_MD, BUGS_MD, MEMORY_MD, RUNBOOK, INDEX_MD):
        if os.path.exists(path):
            all_triples.extend(extract_entities_from_file(path))
            print(f"  ✓ extracted: {path}")
        else:
            print(f"  · skip (missing): {path}")

    # Resolve
    resolved = resolve_entities(all_triples)

    # Deduplicate identical S-P-O (keep max confidence)
    best: dict[tuple, dict] = {}
    for t in resolved:
        key = (t["subject"], t["predicate"], t["object"])
        if key not in best or t["confidence"] > best[key]["confidence"]:
            best[key] = t
    resolved = list(best.values())

    # Assemble
    G = assemble_graph(resolved)

    # Save
    data = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "project": "alikhan",
        "domain": "WhatsApp bot / PostgreSQL ОЖР / Hermes Bridge / ЕЖО",
        "stats": graph_stats(G),
        "nodes": list(G.nodes(data=True)),
        "edges": [
            {
                "source": s,
                "target": t,
                "predicate": d.get("predicate"),
                "source_file": d.get("source"),
                "confidence": d.get("confidence"),
            }
            for s, t, d in G.edges(data=True)
        ],
    }
    with open(GRAPH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Stage 5: MAINTAIN
    try:
        sys.path.insert(0, GRAPH_DIR)
        import maintenance
        maintenance.run_report()
    except Exception as e:
        print(f"⚠️  Maintenance check failed (non-fatal): {e}", file=sys.stderr)

    return G


if __name__ == "__main__":
    print("🧠 Building Alikhan Knowledge Graph…")
    G = build_graph()
    stats = graph_stats(G)
    print(
        f"📊 Knowledge Graph built: {stats['nodes']} nodes, {stats['edges']} edges"
    )
    print(
        f"   🐛 {stats['bugs']} bugs, 🔧 {stats['fixes']} fixes, "
        f"⚡ {stats['api_quirks']} api_quirks, 🗄 {stats['db_tables']} db_tables"
    )
    print(
        f"   🤖 {stats['bot_components']} bot_components, 📅 {stats['events']} events, "
        f"📋 {stats['tasks']} tasks, 📐 {stats['templates']} templates"
    )
    print(f"\n🔍 Sample: project/alikhan (1 hop):")
    print(query_graph(G, "project/alikhan", hops=1)[:600])
    print(f"\n→ {GRAPH_FILE}")
