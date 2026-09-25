"""KEEP-6: exactly six user-invocable orchestrators in MANIFEST."""

from __future__ import annotations

import yaml

from ai_agents_repo.paths import ide_pack_root
from ai_agents_repo.discovery import repo_root

EXPECTED = frozenset(
    {
        "deep-research",
        "plan-prep",
        "research-messenger",
        "use-master",
        "daily-coder",
        "researcher",
    }
)


def test_keep_six_user_invocable():
    manifest = ide_pack_root(root=repo_root()) / "MANIFEST.yml"
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    agents = data.get("agents") or []
    uf = {a["name"] for a in agents if a.get("user_invocable")}
    assert uf == EXPECTED
    assert len(uf) == 6
