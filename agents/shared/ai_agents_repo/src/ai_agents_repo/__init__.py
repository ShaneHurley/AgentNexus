"""Repository layout discovery and logical path resolution."""

from __future__ import annotations

from ai_agents_repo.discovery import find_repo_root, repo_root
from ai_agents_repo.layout import LayoutName, layout
from ai_agents_repo.paths import (
    agent_core_root,
    browser_coder_root,
    browser_daily_task_root,
    browser_deep_research_root,
    browser_legacy_root,
    browser_shared_root,
    dc_root,
    gui_root,
    hooks_dir,
    ide_pack_root,
    policy_dir,
    rf_root,
    schemas_personal_root,
    skills_root,
)
from ai_agents_repo.resolve_ref import resolve_ref

__all__ = [
    "LayoutName",
    "agent_core_root",
    "browser_coder_root",
    "browser_daily_task_root",
    "browser_deep_research_root",
    "browser_legacy_root",
    "browser_shared_root",
    "dc_root",
    "find_repo_root",
    "gui_root",
    "hooks_dir",
    "ide_pack_root",
    "layout",
    "policy_dir",
    "repo_root",
    "resolve_ref",
    "rf_root",
    "schemas_personal_root",
    "skills_root",
]
