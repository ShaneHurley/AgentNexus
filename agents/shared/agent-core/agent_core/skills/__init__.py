"""Shared Developer & Research Skills Suite.

Provides core utility skills for agent cutout templates and orchestrators:
- AST syntax & structure validation (ast_validator)
- Unified diff generation & patch applicability testing (diff_tool)
- Repository code searching with line citations (code_search)
- Token-frugal document compaction (summarizer)
- Sensitive secret & token leak scanning (secret_scanner)
- Architecture Decision Record (ADR) generation & parsing (adr_generator)
"""

from agent_core.skills.adr_generator import format_adr, parse_adr, save_adr
from agent_core.skills.ast_validator import validate_python_code
from agent_core.skills.code_search import search_code
from agent_core.skills.diff_tool import generate_unified_diff, validate_patch
from agent_core.skills.secret_scanner import scan_for_secrets
from agent_core.skills.summarizer import compact_document, summarize_key_points

__all__ = [
    "validate_python_code",
    "generate_unified_diff",
    "validate_patch",
    "search_code",
    "compact_document",
    "summarize_key_points",
    "scan_for_secrets",
    "format_adr",
    "parse_adr",
    "save_adr",
]
