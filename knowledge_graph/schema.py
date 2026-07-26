"""Pydantic schema for Alikhan Knowledge Graph — Anthropic Graph Engineering Playbook, Steps 1-3.

Domain: WhatsApp bot, PostgreSQL/ОЖР, Hermes Bridge, document extraction, ЕЖО templates.
Entity types: bugs, fixes, api_quirks, db_tables, bot_components, chronology_events, project, service, decision.
No X/Twitter entities.
"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Optional
import uuid


# Canonical entity type prefixes used in node ids: type/name
ENTITY_TYPES = (
    "bug",           # AL-XXX, BUG-AL-XXX, recurring bugs
    "fix",           # known fix / remediation
    "api_quirk",     # Bridge / Evolution / PostgreSQL / WhatsApp quirks
    "db_table",      # ojr_*, bot_* tables
    "bot_component", # main_waha, poll, qa, fill_ejo, bridge_wrapper, ...
    "event",         # chronology events
    "project",       # project/alikhan
    "service",       # systemd units / processes
    "decision",      # gates, architecture decisions
    "template",      # EJO / AVR / ВОР templates
    "group",         # WhatsApp groups
    "skill",         # project skills
    "file",          # source files referenced
)


class Entity(BaseModel):
    """A node in the knowledge graph — bug, fix, table, component, event, etc."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    type: str  # one of ENTITY_TYPES
    description: Optional[str] = None
    source_file: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Triple(BaseModel):
    """Subject-Predicate-Object triple with provenance — Step 2: strict schema."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    subject: str
    predicate: str
    # Common predicates for Alikhan domain:
    # occurred_on, described_as, mentioned_in, referenced_in,
    # fixed_by, causes, affects, routes_to, reads_from, writes_to,
    # depends_on, implements, documents, status_is, located_at
    object: str
    provenance: str
    line_hint: Optional[int] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
    extracted_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class Edge(BaseModel):
    """Graph edge — the assembled version of a Triple after resolution."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_node: str
    target_node: str
    predicate: str
    triples: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
    assembled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GraphQuery(BaseModel):
    """A query against the knowledge graph — Step 10."""
    question: str
    center_entity: Optional[str] = None
    max_hops: int = Field(default=2, ge=1, le=5)
    max_triples: int = Field(default=20, ge=1, le=100)


class GraphAnswer(BaseModel):
    """The answer from querying the graph — Step 11: every answer cites edges."""
    question: str
    answer: str
    cited_edges: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    graph_snapshot_built: Optional[str] = None
