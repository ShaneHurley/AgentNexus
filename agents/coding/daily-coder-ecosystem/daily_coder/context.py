"""Role context slicing.

Each role receives the smallest packet that lets it do its job, plus non-evictable
pinned fields. The full accumulating packet is never forwarded.
"""
from __future__ import annotations
import json

# Pinned slots are never compacted away: rules, permissions, acceptance criteria, anchor.
PINNED = ("ORIGINAL_REQUEST", "task_anchor", "constraints", "acceptance_criteria", "file_allowlist", "permissions", "profile", "repo", "plan_hash", "approval_hash", "budget", "pending_calls", "TASK_CONTRACT")

ROLE_INPUTS: dict[str, tuple[str, ...]] = {
    "sizer": ("request",),
    "researcher": ("request", "lane", "angle", "repo_map"),
    "brainstormer": ("request", "research_digest"),
    "master": ("request", "research_digest", "brainstorm", "diagnosis", "frontier_advice"),
    "test_designer": ("decide",),
    "planner": ("decide", "test_design", "research_digest", "skills", "SOURCE_SNAPSHOTS"),
    "plan_reviewer": ("decide", "plan", "test_design"),
    "implementer": ("plan_slice", "plan_hash", "skills", "SOURCE_SNAPSHOTS"),
    "test_author": ("test_design", "decide", "implement_summary"),
    "test_executor": ("verification_commands", "test_author"),
    "code_reviewer": ("diff", "decide", "plan", "SOURCE_SNAPSHOTS", "CANDIDATE_MANIFEST", "VERIFICATION_EVIDENCE"),
    "documenter": ("decide", "implement_summary", "diff_summary"),
    "alignment_checker": ("decide", "plan_summary", "implement_summary", "boundary"),
    "failure_diagnostician": ("failure", "phase", "evidence"),
    "frontier_advisor": ("decision_brief",),
    "skill_curator": ("run_summary",),
}

MAX_FIELD_CHARS = 6000
MAX_REQUIRED_FIELD_CHARS = 24000
REQUIRED_FIELDS = frozenset({"TASK_CONTRACT", "plan_slice", "CANDIDATE_MANIFEST", "VERIFICATION_EVIDENCE", "SOURCE_SNAPSHOTS", "REPAIR_CONTEXT"})

class ContextCapacityError(ValueError):
    reason_code = "context_capacity"
    def __init__(self, field, actual_chars, limit=MAX_REQUIRED_FIELD_CHARS):
        self.field=field; self.actual_chars=actual_chars; self.limit=limit
        super().__init__(f"context_capacity: {field} needs {actual_chars} characters; limit {limit}")
    def as_dict(self):
        return {"reason_code":self.reason_code,"field":self.field,"actual_chars":self.actual_chars,"limit":self.limit}

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
    def project(key,value):
        if key in REQUIRED_FIELDS or (key=="plan" and role in {"plan_reviewer","code_reviewer"}):
            size=len(json.dumps(value,sort_keys=True,allow_nan=False))
            if MAX_REQUIRED_FIELD_CHARS < size:
                raise ContextCapacityError(key,size)
            return value
        return _truncate(value)
    sliced = {k: project(k,packet[k]) if k in REQUIRED_FIELDS else packet[k] for k in PINNED if k in packet}
    for key in ROLE_INPUTS.get(role, ()):
        if key in packet:
            sliced[key] = project(key,packet[key])
    for k,v in (extra or {}).items():
        sliced[k] = project(k,v)
    return sliced

def project_tool_results(results, max_chars=MAX_TOOL_CONTEXT_CHARS, recent=RECENT_TOOL_RESULTS):
    """Bound the serialized packet, retaining status and durable receipt references.

    Full results remain in the gateway's tool-operation receipts. If even their
    essential references will not fit, stop instead of silently dropping evidence.
    """
    import hashlib
    if type(max_chars) is not int or max_chars < 256 or type(recent) is not int or recent < 1:
        raise ValueError("invalid tool-context bounds")
    results = list(results or [])
    if not results:
        return []

    def encoded(value):
        return json.dumps(value, sort_keys=True, default=str)

    def compact_write(item):
        if item.get("ok") is not True or item.get("tool") not in {"filesystem.write","patch.apply"}:
            return item
        args=item.get("arguments") or {}; result=item.get("result") or {}
        if not isinstance(args,dict) or not isinstance(result,dict): return item
        projected={key:item[key] for key in ("call_id","tool","operation_ref","ok","error","turn") if key in item}
        projected.update(compacted_write=True,arguments_hash=hashlib.sha256(encoded(args).encode()).hexdigest(),
                         result_hash=hashlib.sha256(encoded(result).encode()).hexdigest())
        projected["result"]={key:result[key] for key in ("path","bytes","applied","sha256","status") if key in result}
        if "expected_sha256" in args: projected["expected_sha256"]=args["expected_sha256"]
        return projected

    results=[compact_write(item) for item in results]
    def reference(item,keep_source=False):
        if item.get("compacted_write"): return dict(item)
        result=item.get("result") or {}
        status = {key: result[key] for key in
                  ("returncode", "timeout", "cancelled", "cancellation_confirmed")
                  if isinstance(result,dict) and key in result}
        ref = {
            "call_id": item.get("call_id"), "tool": item.get("tool"),
            "operation_ref": item.get("operation_ref"), "ok": item.get("ok"),
            "error": item.get("error"), "result": status,
            "result_hash": item.get("result_hash") or hashlib.sha256(encoded(result).encode()).hexdigest(),
            "arguments_hash": item.get("arguments_hash") or hashlib.sha256(encoded(item.get("arguments")).encode()).hexdigest(),
            "truncated": True, "original_chars": item.get("original_chars",len(encoded(item))),
        }
        if item.get("tool")=="filesystem.read" and isinstance(result,dict):
            ref["result"].update({key:result[key] for key in ("path","sha256","start","end","total_lines","truncated") if key in result})
            if keep_source and "content" in result:
                ref["result"]["content"]=result["content"]
            else:
                ref["result"].update(content_omitted=True,complete=False)
        if "arguments" in item and len(encoded(item["arguments"])) <= 1000:
            ref["arguments"] = item["arguments"]
        return ref

    older, latest = results[:-recent], results[-recent:]
    projected = ([{"compacted": True, "count": len(older),
                   "evidence": [reference(item,keep_source=True) for item in older]}] if older else [])
    projected.extend(latest)
    if len(encoded(projected)) <= max_chars:
        return projected
    # Drop older source bodies first, preserving receipt identity and hashes.
    if older:
        for index,item in enumerate(projected[0]["evidence"]):
            projected[0]["evidence"][index]=reference(item)
            if len(encoded(projected)) <= max_chars: return projected
    # Reduce observations, never their receipt identity or execution outcome.
    offset = 1 if older else 0
    for index in range(offset, len(projected)):
        projected[index] = reference(projected[index])
        if len(encoded(projected)) <= max_chars:
            return projected
    # Arguments are convenient context, not essential receipt metadata.
    for item in projected:
        for ref in item.get("evidence", []) if item.get("compacted") else [item]:
            ref.pop("arguments", None)
    if len(encoded(projected)) > max_chars:
        # Receipt identities, outcomes and content hashes remain mandatory.
        # Duplicate argument hashes and size diagnostics are optional here.
        for item in projected:
            for ref in item.get("evidence", []) if item.get("compacted") else [item]:
                ref.pop("arguments_hash", None)
                ref.pop("original_chars", None)
    if len(encoded(projected)) > max_chars:
        raise ValueError("tool receipt context cannot fit; stop or split task")
    return projected

def estimate_tokens(prompt, packet, max_output_tokens, tool_results=None, *, tools=None, output_schema=None):
    """Conservative pre-call estimate matching the provider packet shape."""
    chars = len(prompt) + len(json.dumps(packet, sort_keys=True, default=str))
    chars += len(json.dumps(tool_results or [], sort_keys=True, default=str))
    if tools is not None:chars+=len(json.dumps(tools,sort_keys=True,default=str))
    if output_schema is not None:chars+=len(json.dumps(output_schema,sort_keys=True,default=str))
    return (chars+3)//4 + int(max_output_tokens)
