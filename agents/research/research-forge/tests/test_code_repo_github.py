from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from research_forge.wave6.adapters.code_repo_github import PublicGitHubCodeRepositoryAdapter


def test_public_github_adapter_rejects_non_github() -> None:
    adapter = PublicGitHubCodeRepositoryAdapter()
    out = adapter.read({"url": "https://example.com/org/repo"})
    assert out.get("error") == "not_github_url"


def test_public_github_adapter_metadata_mock() -> None:
    adapter = PublicGitHubCodeRepositoryAdapter()
    payload = {
        "default_branch": "main",
        "description": "demo",
        "stargazers_count": 1,
    }

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode()

    with patch("research_forge.wave6.adapters.code_repo_github.urllib.request.urlopen", return_value=Resp()):
        out = adapter.read({"url": "https://github.com/octocat/Hello-World"})
    assert out["access_level"] == "metadata"
    assert out["default_branch"] == "main"


def test_write_denied() -> None:
    adapter = PublicGitHubCodeRepositoryAdapter()
    try:
        adapter.write_file("x", "y")
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass
