"""Gateway-wrapped reader calls."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from urllib.parse import urlparse

from research_forge.budget.manager import BudgetManager
from research_forge.budget.wrapper import budget_wrapped_call
from research_forge.policy.gateway import PolicyGateway


def gated_read(
    gateway: PolicyGateway,
    budget: BudgetManager,
    adapter: Any,
    *,
    role: str,
    phase: str,
    source_ref: dict[str, Any],
    live: bool,
    cost_usd: float = 0.02,
    locator: str | None = None,
) -> dict[str, Any]:
    tool_id = getattr(adapter, "adapter_id", "unknown_reader")
    normalized = dict(source_ref)
    path = normalized.get("path")
    url = normalized.get("url") or normalized.get("canonical_url")
    if path and url: raise PermissionError("ambiguous reader resource: path and URL")
    if tool_id == "local_reader_v1":
        if not path or url: raise PermissionError("local reader requires an explicit path")
        resolved = Path(str(path)).expanduser()
        if not resolved.is_absolute(): resolved = gateway.workspace_root / resolved
        resolved = resolved.resolve()
        if not resolved.is_relative_to(gateway.workspace_root): raise PermissionError("reader path escapes workspace")
        normalized = {"path":str(resolved), "confidentiality":source_ref.get("confidentiality", "public")}
        target = resolved.as_uri()
    else:
        if path or not url or urlparse(str(url)).scheme not in {"http", "https"}:
            raise PermissionError("web reader requires a single HTTP resource")
        if normalized.get("url") and normalized.get("canonical_url") and normalized["url"] != normalized["canonical_url"]:
            raise PermissionError("conflicting URL identity")
        normalized = {"url":str(url), "canonical_url":str(url), "confidentiality":source_ref.get("confidentiality","public")}
        target = str(url)

    return budget_wrapped_call(
        gateway,
        budget,
        cost_usd=cost_usd,
        auth_kwargs={
            "role": role,
            "phase": phase,
            "tool_id": tool_id,
            "operation": "read_document",
            "target": target,
            "live": live,
            "confidentiality": source_ref.get("confidentiality", "public"),
        },
        request={"source":normalized,"locator":locator},
        fn=lambda: adapter.read(normalized, locator=locator),
    )
