"""Allowlisted GitHub clone + read-only API helpers (REC-GH-CLONE / REC-GH-READ).

Security posture:
- HTTPS github.com (or configured hosts) only
- Clone targets must land under ``allowed_repo_roots``
- Tokens from SecretStore / env only; never logged
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEFAULT_HOSTS = frozenset({"github.com"})
REPO_PATH_RE = re.compile(r"^/([^/]+)/([^/]+?)(?:\.git)?/?$")


class GitHubRemoteError(ValueError):
    pass


def parse_github_https_url(url: str, *, allowed_hosts: frozenset[str] | set[str] = DEFAULT_HOSTS) -> tuple[str, str, str]:
    raw = (url or "").strip()
    if not raw:
        raise GitHubRemoteError("empty github url")
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise GitHubRemoteError("only https:// github URLs are allowed")
    host = (parsed.hostname or "").lower()
    if host not in {h.lower() for h in allowed_hosts}:
        raise GitHubRemoteError(f"host not allowlisted: {host}")
    if parsed.username or parsed.password:
        raise GitHubRemoteError("credentials must not appear in the URL")
    match = REPO_PATH_RE.match(parsed.path or "")
    if not match:
        raise GitHubRemoteError("URL must look like https://github.com/{owner}/{repo}")
    owner, repo = match.group(1), match.group(2)
    if ".." in owner or ".." in repo:
        raise GitHubRemoteError("invalid owner/repo")
    canonical = f"https://{host}/{owner}/{repo}"
    return owner, repo, canonical


def _under_allowed_root(target: Path, allowed_roots: list[Path]) -> bool:
    resolved = target.resolve()
    for root in allowed_roots:
        root = root.resolve()
        if resolved == root or root in resolved.parents:
            return True
    return False


def resolve_clone_destination(
    *,
    owner: str,
    repo: str,
    dest: Path | None,
    allowed_roots: list[Path],
) -> Path:
    if dest is None:
        if not allowed_roots:
            raise GitHubRemoteError("allowed_repo_roots is empty")
        dest = allowed_roots[0] / "github" / owner / repo
    else:
        dest = Path(dest)
    dest = dest.resolve()
    if not _under_allowed_root(dest, allowed_roots):
        raise GitHubRemoteError("clone destination escapes allowed_repo_roots")
    return dest


def clone_github_repo(
    url: str,
    *,
    allowed_roots: list[Path],
    dest: Path | None = None,
    token: str | None = None,
    allowed_hosts: frozenset[str] | set[str] = DEFAULT_HOSTS,
) -> dict[str, Any]:
    owner, repo, canonical = parse_github_https_url(url, allowed_hosts=allowed_hosts)
    target = resolve_clone_destination(owner=owner, repo=repo, dest=dest, allowed_roots=allowed_roots)
    target.parent.mkdir(parents=True, exist_ok=True)
    if (target / ".git").is_dir():
        # Update existing clone (fetch only; no arbitrary remotes).
        cmd = ["git", "-C", str(target), "fetch", "--depth", "1", "origin"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise GitHubRemoteError(_redact(proc.stderr or proc.stdout or "git fetch failed"))
        return {
            "ok": True,
            "action": "fetch",
            "path": str(target),
            "canonical_url": canonical,
            "owner": owner,
            "repo": repo,
        }
    clone_url = canonical + ".git"
    env = os.environ.copy()
    # Prefer header auth via GIT_ASKPASS-less embed only when token present — use x-access-token form
    # but never echo it. Pass via URL for git; redact in errors.
    if token:
        clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    cmd = ["git", "clone", "--depth", "1", clone_url, str(target)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
    if proc.returncode != 0:
        raise GitHubRemoteError(_redact(proc.stderr or proc.stdout or "git clone failed"))
    return {
        "ok": True,
        "action": "clone",
        "path": str(target),
        "canonical_url": canonical,
        "owner": owner,
        "repo": repo,
    }


def _redact(text: str) -> str:
    text = re.sub(r"x-access-token:[^@\s]+", "x-access-token:[REDACTED]", text)
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "ghp_[REDACTED]", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "github_pat_[REDACTED]", text)
    return text


def github_api_get(
    path: str,
    *,
    token: str | None = None,
    allowed_hosts: frozenset[str] | set[str] = DEFAULT_HOSTS,
) -> dict[str, Any]:
    if not path.startswith("/"):
        raise GitHubRemoteError("API path must be absolute under api.github.com")
    # api.github.com is the REST host for github.com allowlist entries
    if "github.com" not in {h.lower() for h in allowed_hosts}:
        raise GitHubRemoteError("GitHub API disabled for this host allowlist")
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "daily-coder-github-remote",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — fixed host
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            return {"ok": True, "status": resp.status, "data": data}
    except urllib.error.HTTPError as exc:
        detail = _redact(exc.read().decode("utf-8", errors="replace")[:500])
        raise GitHubRemoteError(f"GitHub API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GitHubRemoteError(f"GitHub API network error: {exc.reason}") from exc


def repo_metadata(owner: str, repo: str, *, token: str | None = None) -> dict[str, Any]:
    result = github_api_get(f"/repos/{owner}/{repo}", token=token)
    data = result.get("data") or {}
    # Return a slim, non-secret subset
    return {
        "ok": True,
        "owner": owner,
        "repo": repo,
        "full_name": data.get("full_name"),
        "default_branch": data.get("default_branch"),
        "private": data.get("private"),
        "html_url": data.get("html_url"),
        "description": data.get("description"),
        "stargazers_count": data.get("stargazers_count"),
        "forks_count": data.get("forks_count"),
        "open_issues_count": data.get("open_issues_count"),
    }


def list_pulls(
    owner: str,
    repo: str,
    *,
    state: str = "open",
    token: str | None = None,
    per_page: int = 20,
) -> dict[str, Any]:
    if state not in ("open", "closed", "all"):
        raise GitHubRemoteError("state must be open|closed|all")
    per_page = max(1, min(int(per_page), 50))
    result = github_api_get(
        f"/repos/{owner}/{repo}/pulls?state={state}&per_page={per_page}",
        token=token,
    )
    rows = result.get("data") or []
    pulls = [
        {
            "number": p.get("number"),
            "title": p.get("title"),
            "state": p.get("state"),
            "html_url": p.get("html_url"),
            "user": (p.get("user") or {}).get("login"),
            "draft": p.get("draft"),
        }
        for p in rows
        if isinstance(p, dict)
    ]
    return {"ok": True, "owner": owner, "repo": repo, "state": state, "pulls": pulls}


def resolve_github_token(secrets: Any | None) -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN", "github_token"):
        if secrets is not None:
            val = secrets.get(name)
            if val:
                return val
        env = os.environ.get(name)
        if env:
            return env
    return None
