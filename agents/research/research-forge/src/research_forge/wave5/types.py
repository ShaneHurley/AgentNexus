"""Wave 5 shared types and constants."""

from __future__ import annotations

BUILDER_VERSION = "1.0.0"
DIRECTOR_ROLE_ID = "principal_research_director"
PACKET_BLOCKED = "BLOCKED"
PRE_DIRECTOR_FALLBACK = "pre_director_synthesis"
CONTESTED = "CONTESTED"

FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "raw_transcript",
        "full_source_body",
        "source_bodies",
        "search_hits",
        "reader_chunks",
    }
)

HIGH_STAKES_DOMAINS = frozenset(
    {
        "safety_critical",
        "medical",
        "legal",
        "financial",
        "security",
        "public_impact",
        "irreversible",
    }
)

HANDOFF_STRATA = (
    "easy_synthesis",
    "contradiction_heavy",
    "multi_idea_fusion",
    "high_stakes_methods",
)

DIRECTOR_ALLOWED_TOOLS: tuple[str, ...] = ("structured_synthesis",)
