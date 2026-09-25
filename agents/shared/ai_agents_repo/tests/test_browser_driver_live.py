"""Smoke-route all ten v3 families against the live checkout (when content present)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agents_repo.browser.router import V3_FAMILY_IDS, route
from ai_agents_repo.discovery import repo_root


@pytest.mark.parametrize("family", sorted(V3_FAMILY_IDS))
def test_live_family_main_paste_resolves(family: str):
    root = repo_root()
    router = root / "agents" / "daily-task" / "ROUTER.yaml"
    if not router.is_file() and not (root / "daily-task" / "ROUTER.yaml").is_file():
        pytest.skip("F2 router not present in this checkout")
    result = route(family, root=root)
    assert result.agent_message.is_file()
    assert result.domain in {"daily-task", "coder", "deep-research", "unknown"}
