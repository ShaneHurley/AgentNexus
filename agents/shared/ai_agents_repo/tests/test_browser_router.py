"""Browser RCC router (F2b) — routes all ten families when content is present."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_agents_repo.browser.router import V3_FAMILY_IDS, family_roots, load_router, route
from ai_agents_repo.discovery import repo_root as live_repo_root


def _write_agent(root: Path, family: str, variant: str | None = None) -> None:
    if variant:
        base = (
            root
            / "agents"
            / "daily-task"
            / "browser"
            / "families"
            / family
            / "variants"
            / variant
        )
    else:
        if family in {"code-crafter", "code-reviewer", "document-reviewer"}:
            base = root / "agents" / "coding" / "browser" / family
        elif family == "research-desk":
            base = root / "agents" / "research" / "browser" / family
        else:
            base = root / "agents" / "daily-task" / "browser" / "families" / family
    base.mkdir(parents=True, exist_ok=True)
    (base / "AGENT_MESSAGE.md").write_text(
        "=== EMBEDDED BEHAVIORAL CONTRACT ===\nSTATUS COMPLETE VALIDATION.PERFORMED UNTRUSTED\n",
        encoding="utf-8",
    )


@pytest.fixture
def v2_with_router(v2_tree: Path) -> Path:
    root = v2_tree
    checkout = live_repo_root()
    (root / "agents" / "daily-task" / "ROUTER.yaml").write_text(
        (checkout / "agents" / "daily-task" / "ROUTER.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (root / "agents" / "shared" / "browser").mkdir(parents=True, exist_ok=True)
    idx_src = checkout / "agents" / "shared" / "browser" / "MANIFEST.index.json"
    (root / "agents" / "shared" / "browser" / "MANIFEST.index.json").write_text(
        idx_src.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    for fam in V3_FAMILY_IDS:
        _write_agent(root, fam)
    return root


def test_load_router(v2_with_router: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_AGENTS_REPO_ROOT", str(v2_with_router))
    from ai_agents_repo.discovery import repo_root as rr

    rr.cache_clear()
    data = load_router(root=v2_with_router)
    assert data["schema_version"] == 1
    assert "authority_banner" in data


def test_route_all_ten(v2_with_router: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_AGENTS_REPO_ROOT", str(v2_with_router))
    from ai_agents_repo.discovery import repo_root as rr

    rr.cache_clear()
    for fam in V3_FAMILY_IDS:
        result = route(fam, root=v2_with_router)
        assert result.agent_message.is_file()
        assert result.authority_banner


def test_family_roots_count(v2_with_router: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_AGENTS_REPO_ROOT", str(v2_with_router))
    from ai_agents_repo.discovery import repo_root as rr

    rr.cache_clear()
    roots = family_roots(root=v2_with_router)
    assert set(roots.keys()) == V3_FAMILY_IDS
