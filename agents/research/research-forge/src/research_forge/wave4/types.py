"""Wave 4 shared types and constants."""

from __future__ import annotations

TACTICAL_OPPORTUNITY_TYPES: tuple[str, ...] = (
    "replace",
    "simplify",
    "decompose",
    "constrain",
    "automate",
    "standardize",
    "isolate",
    "combine",
    "remove",
    "measure",
    "change_incentives",
)

OPPORTUNITY_TO_SCHEMA: dict[str, str] = {
    "replace": "architectural",
    "simplify": "incremental",
    "decompose": "architectural",
    "constrain": "process",
    "automate": "process",
    "standardize": "process",
    "isolate": "architectural",
    "combine": "hybrid",
    "remove": "incremental",
    "measure": "research",
    "change_incentives": "process",
}

PORTFOLIO_DIMENSIONS: tuple[str, ...] = (
    "evidence",
    "root_cause_fit",
    "impact",
    "feasibility",
    "testability",
    "risk",
    "cost",
    "reversibility",
    "robustness",
    "distinctiveness",
    "compatibility",
)

IDEATOR_MAX_CANDIDATES = 2
IDEATOR_MAX_FIELD_LEN = 512
IDEATOR_MAX_TOTAL_CHARS = 4096

TEMPLATE_DEFAULT_MARKERS: tuple[str, ...] = (
    "generic rag",
    "multi-agent",
    "knowledge graph",
    "blockchain",
    "digital twin",
    "add more data",
)

NO_DEFENSIBLE_IDEA = "NO DEFENSIBLE IDEA"

IDEA_EVENT_TYPES: tuple[str, ...] = (
    "idea_added",
    "idea_superseded",
    "idea_repair",
    "idea_rejected",
    "idea_deferred",
    "idea_recommended",
)
