"""Public GitHub code repository adapter (REC-RF-GH-ADAPTER).

Read-only metadata/file fetch for allowlisted ``github.com`` HTTPS URLs.
Default Research Forge path remains ``MockCodeRepositoryAdapter``.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from research_forge.registries.normalize import normalize_repo_url
from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class PublicGitHubCodeRepositoryAdapter:
    adapter_id = "public_github_code_repo"
    protocol_version = PROTOCOL_VERSION

    def __init__(self, *, token: str | None = None) -> None:
        self.token = token

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read", "metadata"})

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "research-forge-public-github",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def _parse_repo(self, url: str) -> tuple[str, str] | None:
        canon = normalize_repo_url(url)
        if "github.com/" not in canon:
            return None
        parts = canon.rstrip("/").split("github.com/")[-1].split("/")
        if len(parts) < 2:
            return None
        return parts[0], parts[1]

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        # Public-only search via GitHub code/repos search — query is treated as owner/repo hint
        q = quote(f"{query} in:name")
        try:
            data = self._get(f"https://api.github.com/search/repositories?q={q}&per_page=5")
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            return {"results": [], "next_cursor": None, "error": str(exc)}
        results = []
        for i, item in enumerate(data.get("items") or []):
            results.append(
                {
                    "result_id": f"gh-{i}",
                    "canonical_url": normalize_repo_url(item.get("html_url") or ""),
                    "canonical_title": item.get("full_name") or item.get("name"),
                    "source_type": "code_repository",
                    "snippet": (item.get("description") or "")[:200],
                }
            )
        return {"results": results, "next_cursor": None}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        url = normalize_repo_url(locator.get("url") or "")
        parsed = self._parse_repo(url)
        if not parsed:
            return {"error": "not_github_url"}
        owner, repo = parsed
        path = locator.get("path")
        try:
            if path:
                api = f"https://api.github.com/repos/{owner}/{repo}/contents/{quote(str(path))}"
                data = self._get(api)
                if isinstance(data, dict) and data.get("encoding") == "base64" and data.get("content"):
                    import base64

                    text = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                    return {
                        "access_level": "full",
                        "access_disclosure": "public_github_contents_api",
                        "locator": {"kind": "repo_file", "value": f"{url}/{path}"},
                        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                        "text": text,
                    }
                return {"error": "unsupported_content", "raw_type": type(data).__name__}
            meta = self._get(f"https://api.github.com/repos/{owner}/{repo}")
            return {
                "access_level": "metadata",
                "access_disclosure": "public_github_repo_api",
                "locator": {"kind": "repo", "value": url},
                "default_branch": meta.get("default_branch"),
                "description": meta.get("description"),
                "stargazers_count": meta.get("stargazers_count"),
            }
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as exc:
            return {"error": "fetch_failed", "detail": str(exc)}

    def write_file(self, *_a: Any, **_k: Any) -> None:
        raise PermissionError("write endpoints unavailable")
