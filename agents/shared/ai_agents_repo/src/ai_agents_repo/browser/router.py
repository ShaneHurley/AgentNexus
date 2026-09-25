"""Resolve browser_family (+ optional variant) to AGENT_MESSAGE paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ai_agents_repo.discovery import repo_root
from ai_agents_repo.layout import layout
V3_FAMILY_IDS = frozenset(
    {
        "plans-and-places",
        "kitchen-cooking",
        "learning-coach",
        "writing-studio",
        "thinking-lab",
        "mission-control",
        "code-crafter",
        "code-reviewer",
        "document-reviewer",
        "research-desk",
    }
)

AUTHORITY_BANNER = (
    "BROWSER RCC v3 — paste harness only. Not IDE PolicyGateway, not automated /use-master execution."
)


@dataclass(frozen=True)
class RouteResult:
    family: str
    variant: str | None
    agent_message: Path
    family_root: Path
    domain: str
    authority_banner: str
    logical_slug: str


def _router_yaml_path(*, root: Path | None = None) -> Path:
    root = (root or repo_root()).resolve()
    if layout(root=root) == "v2":
        return root / "agents" / "daily-task" / "ROUTER.yaml"
    return root / "daily-task" / "ROUTER.yaml"


def load_router(*, root: Path | None = None) -> dict[str, Any]:
    path = _router_yaml_path(root=root)
    if not path.is_file():
        raise FileNotFoundError(f"ROUTER.yaml not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ROUTER.yaml must be a mapping")
    return data


def load_manifest_index(*, root: Path | None = None) -> dict[str, Any]:
    root = (root or repo_root()).resolve()
    router = load_router(root=root)
    default_index = (
        "agents/shared/browser/MANIFEST.index.json"
        if layout(root=root) == "v2"
        else "shared/browser/MANIFEST.index.json"
    )
    rel = router.get("manifest_index", default_index)
    path = (root / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"MANIFEST.index.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def family_roots(*, root: Path | None = None) -> dict[str, Path]:
    """Map each v3 family id to its preferred on-disk family root."""
    root = (root or repo_root()).resolve()
    router = load_router(root=root)
    out: dict[str, Path] = {}
    domains = router.get("domains") or {}
    for domain_id, spec in domains.items():
        if not isinstance(spec, dict):
            continue
        base = root / spec["root"]
        for fam in spec.get("families") or []:
            out[str(fam)] = base / fam
    return out


def _domain_for_family(family: str, router: dict[str, Any]) -> str:
    domains = router.get("domains") or {}
    for domain_id, spec in domains.items():
        if family in (spec.get("families") or []):
            return str(domain_id)
    return "unknown"


def resolve_paste_path(
    family: str,
    variant: str | None = None,
    *,
    root: Path | None = None,
) -> Path:
    family = family.strip()
    if family not in V3_FAMILY_IDS:
        raise KeyError(f"Unknown browser family {family!r}; expected one of {sorted(V3_FAMILY_IDS)}")
    roots = family_roots(root=root)
    if family not in roots:
        raise FileNotFoundError(f"No on-disk root for family {family!r}")
    fam_root = roots[family]
    if variant:
        candidate = fam_root / "variants" / variant / "AGENT_MESSAGE.md"
    else:
        candidate = fam_root / "AGENT_MESSAGE.md"
    if not candidate.is_file():
        raise FileNotFoundError(f"Paste file missing: {candidate}")
    return candidate


def route(
    family: str,
    variant: str | None = None,
    *,
    root: Path | None = None,
) -> RouteResult:
    root = (root or repo_root()).resolve()
    router = load_router(root=root)
    banner = (router.get("authority_banner") or AUTHORITY_BANNER).strip()
    agent_message = resolve_paste_path(family, variant, root=root)
    fam_root = family_roots(root=root)[family]
    if variant:
        logical = f"{family}/{variant}"
    else:
        logical = family
    return RouteResult(
        family=family,
        variant=variant,
        agent_message=agent_message,
        family_root=fam_root,
        domain=_domain_for_family(family, router),
        authority_banner=banner,
        logical_slug=logical,
    )
