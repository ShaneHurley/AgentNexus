from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.adapters.reader.local import LocalTextReader
from research_forge.adapters.reader.web import WebDocumentReader
from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.adapters.search.public import PublicSearchAdapter
from research_forge.adapters.search.gateway import gated_search
from research_forge.budget.manager import BudgetManager
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
from research_forge.wave1.orchestrator import build_gateway
from research_forge.settings import load_settings


def _cap(tool_id: str) -> ToolManifest:
    return ToolManifest(
        tool_id=tool_id,
        capabilities={
            "read": True,
            "write": False,
            "network": False,
            "execute": False,
            "credential": False,
            "data_class": "public",
        },
    )


def test_mock_search_paging() -> None:
    adapter = MockSearchAdapterV1()
    p1 = adapter.search("q", page_size=1, cursor=0)
    assert len(p1["results"]) == 1
    p2 = adapter.search("q", page_size=1, cursor=p1["next_cursor"])
    assert p1["results"][0]["canonical_url"] != p2["results"][0]["canonical_url"]


def test_gateway_wraps_search(repo_root: Path) -> None:
    settings = load_settings(repo_root)
    gw = build_gateway(settings, live=False)
    budget = BudgetManager(repo_root / settings.budget_config)
    budget.start("S")
    out = gated_search(
        gw,
        budget,
        MockSearchAdapterV1(),
        role="test",
        phase="search",
        query="topic",
        live=False,
    )
    assert out["results"]
    assert gw.audit_log[-1]["allowed"]


def test_forbidden_domain_public_search() -> None:
    adapter = PublicSearchAdapter(forbidden_domains=frozenset({"evil.test"}))
    out = adapter.search("q", filters={"domain": "evil.test"})
    assert out["error"] == "forbidden_domain"


def test_local_reader_utf8(tmp_path: Path) -> None:
    p = tmp_path / "doc.md"
    p.write_text("# Title\n\nParagraph one.", encoding="utf-8")
    reader = LocalTextReader()
    out = reader.read({"path": str(p)})
    assert out["access_level"] == "full"
    assert out["chunks"]


def test_abstract_cannot_full_claim() -> None:
    reader = WebDocumentReader({"https://x/y": b"Abstract only snippet"})
    out = reader.read({"url": "https://x/y", "abstract_only": True})
    assert out["access_level"] == "abstract"
