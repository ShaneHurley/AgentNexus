from __future__ import annotations

import pytest

from ai_agents_repo.exceptions import RefResolutionError
from ai_agents_repo.resolve_ref import resolve_ref


def test_resolve_ide_agents_logical(use_legacy_root):
    path = resolve_ref("ide-agents/contracts/probe.md", root=use_legacy_root)
    assert path.is_file()
    assert path.name == "probe.md"


def test_resolve_v2_hub(use_v2_root):
    path = resolve_ref("ide-agents/contracts/probe.md", root=use_v2_root)
    assert path.is_file()


def test_reject_traversal(use_legacy_root):
    with pytest.raises(RefResolutionError):
        resolve_ref("ide-agents/../../outside.md", root=use_legacy_root)


def test_reject_unknown_prefix(use_legacy_root):
    with pytest.raises(RefResolutionError):
        resolve_ref("unknown/foo.md", root=use_legacy_root)


def test_must_exist(use_legacy_root):
    with pytest.raises(RefResolutionError):
        resolve_ref("ide-agents/contracts/missing.md", root=use_legacy_root, must_exist=True)
