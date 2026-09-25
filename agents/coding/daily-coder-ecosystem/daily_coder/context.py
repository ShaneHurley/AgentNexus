"""Role context slicing.

Each role receives the smallest packet that lets it do its job, plus non-evictable
pinned fields. The full accumulating packet is never forwarded.
"""
from __future__ import annotations
import json

# Pinned slots are never compacted away: rules, permissions, acceptance criteria, anchor.
PINNED = ("ORIGINAL_REQUEST", "task_anchor", "constraints", "acceptance_criteria", "file_allowlist", "permissions", "profile", "repo")

ROLE_INPUTS: dict[str, tuple[str, ...]] = {
    "sizer": ("request",),
    "researcher": ("request", "lane", "angle", "repo_map"),
    "brainstormer": ("request", "research_digest"),
    "master": ("request", "research_digest", "brainstorm", "diagnosis", "frontier_advice"),
    "test_designer": ("decide",),
    "planner": ("decide", "test_design", "research_digest", "skills"),
    "plan_reviewer": ("decide", "plan", "test_design"),
    "implementer": ("plan_slice", "plan_hash", "skills"),
    "test_author": ("test_design", "decide", "implement_summary"),
    "test_executor": ("verification_commands", "test_author"),
    "code_reviewer": ("diff", "decide", "plan"),
    "documenter": ("decide", "implement_summary", "diff_summary"),
    "alignment_checker": ("decide", "plan_summary", "implement_summary", "boundary"),
    "failure_diagnostician": ("failure", "phase", "evidence"),
    "frontier_advisor": ("decision_brief",),
    "skill_curator": ("run_summary",),
}

MAX_FIELD_CHARS = 6000
DIGEST_CHARS = 2000
MAX_TOOL_CONTEXT_CHARS = 24000
RECENT_TOOL_RESULTS = 4

def _truncate(value, limit=MAX_FIELD_CHARS):
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    if len(text) <= limit:
        return value
    return {"_truncated": True, "_chars": len(text), "preview": text[:limit]}

def research_card_body(entry) -> dict:
    """Return the schema-valid research_card from a stored lane entry.

    Supports legacy flat cards and wrappers {"lane", "angle", "card": {...}}.
    """
    if not isinstance(entry, dict):
        return {}
    inner = entry.get("card")
    if isinstance(inner, dict) and ("observations" in inner or "unknowns" in inner or "question" in inner):
        return inner
    return entry

def research_digest(cards):
    """Compress research lanes to evidence references, not prose."""
    out = []
    for entry in cards or []:
        body = research_card_body(entry)
        obs = body.get("observations", [])[:8]
        item = {
            "question": body.get("question"),
            "scope": body.get("scope"),
            "observations": [
                {
                    "label": o.get("label"),
                    "claim": o.get("claim"),
                    "locator": o.get("locator") or o.get("source"),
                }
                for o in obs if isinstance(o, dict)
            ],
            "unknowns": list(body.get("unknowns") or [])[:5],
            "limitations": list(body.get("limitations") or [])[:3],
        }
        if isinstance(entry, dict):
            if "lane" in entry:
                item["lane"] = entry["lane"]
            if "angle" in entry:
                item["angle"] = entry["angle"]
        out.append(item)
    return out

def plan_summary(plan: dict) -> dict:
    """Bound digest of a plan artifact for downstream roles."""
    plan = plan or {}
    units = plan.get("change_units") or []
    digest = {
        "file_allowlist": list(plan.get("file_allowlist") or [])[:40],
        "change_unit_count": len(units),
        "change_unit_ids": [u.get("id") or u.get("summary") for u in units[:20]],
        "unresolved_questions": list(plan.get("unresolved_questions") or [])[:10],
        "verification_command_count": len(plan.get("verification_commands") or []),
        "rollback_present": bool(plan.get("rollback")),
    }
    return _truncate(digest, DIGEST_CHARS)

def implement_summary(implement: dict) -> dict:
    """Bound digest of implement artifact — files/flags only, no observation prose."""
    implement = implement or {}
    digest = {
        "changed_files": list(implement.get("changed_files") or [])[:40],
        "command_count": len(implement.get("commands") or []),
        "blocked": bool(implement.get("blocked")),
        "observation_count": len(implement.get("observations") or []),
    }
    return _truncate(digest, DIGEST_CHARS)

def diff_summary(diff) -> dict | None:
    """Summarize a diff artifact if present; omit when absent."""
    if not diff:
        return None
    if isinstance(diff, dict) and diff.get("unavailable"):
        return {"unavailable": True}
    files = []
    if isinstance(diff, dict):
        raw = diff.get("files") or diff.get("changed_files") or []
        if isinstance(raw, list):
            for item in raw[:40]:
                if isinstance(item, str):
                    files.append({"path": item})
                elif isinstance(item, dict):
                    files.append({
                        "path": item.get("path") or item.get("file"),
                        "additions": item.get("additions"),
                        "deletions": item.get("deletions"),
                    })
    digest = {"files": files, "file_count": len(files)}
    return _truncate(digest, DIGEST_CHARS)

def should_stop_research(cards: list, *, min_cards: int = 2) -> bool:
    """Stop further batches only when enough cards explicitly closed unknowns.

    Rules (all must hold):
    - at least `min_cards` cards (profile `early_stop_min_cards` in budgets.json; default 2)
    - every entry unwraps to a body with key "unknowns" present
    - every body.unknowns is empty
    - no observation has label == "UNKNOWN"
    """
    if len(cards) < max(1, int(min_cards)):
        return False
    for entry in cards:
        body = research_card_body(entry)
        if "unknowns" not in body:
            return False
        if body.get("unknowns"):
            return False
        for obs in body.get("observations") or []:
            if isinstance(obs, dict) and obs.get("label") == "UNKNOWN":
                return False
    return True

def build_packet(role, packet, extra=None):
    """Return the bounded slice for `role`."""
    sliced = {k: packet[k] for k in PINNED if k in packet}
    for key in ROLE_INPUTS.get(role, ()):
        if key in packet:
            sliced[key] = _truncate(packet[key])
    for k, v in (extra or {}).items():
        sliced[k] = _truncate(v)
    return sliced

def project_tool_results(results, max_chars=MAX_TOOL_CONTEXT_CHARS, recent=RECENT_TOOL_RESULTS):
    """Keep recent observations intact and reduce older results to evidence references."""
    results = list(results or [])
    if not results:
        return []
    projected = []
    older, latest = results[:-recent], results[-recent:]
    if older:
        projected.append({
            "compacted": True,
            "count": len(older),
            "evidence": [
                {
                    "call_id": item.get("call_id"),
                    "tool": item.get("tool"),
                    "arguments": item.get("arguments"),
                    "ok": item.get("ok"),
                    "result_hash": (item.get("result") or {}).get("sha256")
                        or (item.get("result") or {}).get("result_hash"),
                    "error": item.get("error"),
                }
                for item in older
            ],
        })
    projected.extend(latest)
    while len(json.dumps(projected, sort_keys=True, default=str)) > max_chars and len(projected) > 1:
        projected.pop(1 if projected[0].get("compacted") else 0)
    return projected

def estimate_tokens(prompt, packet, max_output_tokens, tool_results=None):
    """Conservative pre-call estimate matching the provider packet shape."""
    chars = len(prompt) + len(json.dumps(packet, sort_keys=True, default=str))
    chars += len(json.dumps(tool_results or [], sort_keys=True, default=str))
    return int(chars / 4) + int(max_output_tokens)
