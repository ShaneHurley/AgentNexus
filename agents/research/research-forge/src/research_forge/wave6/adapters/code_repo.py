"""Code repository adapter — read-only metadata (RF-W6-B-04)."""

from __future__ import annotations

import hashlib
from typing import Any

from research_forge.registries.normalize import normalize_repo_url
from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockCodeRepositoryAdapter:
    adapter_id = "mock_code_repo"
    protocol_version = PROTOCOL_VERSION

    _REPOS: dict[str, dict[str, Any]] = {
        "https://github.com/org/example": {
            "default_branch": "main",
            "files": {"README.md": "# Example\n", "src/main.py": "print('hi')\n"},
            "commits": [{"sha": "abc123", "message": "init"}],
            "issues": [{"number": 1, "title": "bug", "state": "open"}],
        }
    }

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read", "metadata"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        cursor = int(kwargs.get("cursor") or 0)
        page_size = int(kwargs.get("page_size", 10))
        keys = [k for k in self._REPOS if query.lower() in k.lower()]
        page = keys[cursor : cursor + page_size]
        results = [
            {
                "result_id": f"repo-{i}",
                "canonical_url": normalize_repo_url(url),
                "canonical_title": url.split("/")[-1],
                "source_type": "code_repository",
                "snippet": "repository metadata",
            }
            for i, url in enumerate(page, start=cursor)
        ]
        next_c = cursor + page_size if cursor + page_size < len(keys) else None
        return {"results": results, "next_cursor": next_c}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        url = normalize_repo_url(locator.get("url") or "")
        repo = self._REPOS.get(url)
        if not repo:
            return {"error": "not_found"}
        path = locator.get("path")
        if path:
            content = repo["files"].get(path)
            if content is None:
                return {"error": "file_not_found"}
            return {
                "access_level": "full",
                "access_disclosure": "public_repo_read",
                "locator": {"kind": "repo_file", "value": f"{url}/{path}"},
                "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                "text": content,
            }
        return {
            "access_level": "metadata",
            "access_disclosure": "repo_metadata_only",
            "locator": {"kind": "repo", "value": url},
            "commits": repo["commits"],
            "issues": repo["issues"],
        }

    def write_file(self, *_a: Any, **_k: Any) -> None:
        raise PermissionError("write endpoints unavailable")
