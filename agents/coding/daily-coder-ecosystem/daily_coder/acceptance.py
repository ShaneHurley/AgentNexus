"""Deterministic acceptance gate.

Completion is never asserted from model prose. Every requirement below is checked
against recorded artifacts, approvals, and command evidence.
"""
from __future__ import annotations

REQUIRED_ARTIFACTS = ("decide", "plan", "plan_review")

def evaluate(*, run, packet, artifacts, approvals_ok, live, config):
    """Return a verdict dict. `pass` only when every required condition holds."""
    acc = config.get("acceptance", {})
    failures: list[str] = []
    checks: dict[str, bool] = {}

    def record(name, ok, reason):
        checks[name] = bool(ok)
        if not ok:
            failures.append(reason)

    kinds = {a["kind"] for a in artifacts}
    for kind in REQUIRED_ARTIFACTS:
        record(f"artifact:{kind}", kind in kinds, f"missing {kind} artifact")

    decide = packet.get("decide") or {}
    plan = packet.get("plan") or {}
    plan_review = packet.get("plan_review") or {}
    implement = packet.get("implement") or {}
    test_exec = packet.get("test_execute") or {}
    code_review = packet.get("code_review") or {}
    alignment = packet.get("alignment") or {}
    test_design = packet.get("test_design") or {}

    record("decision_has_criteria", bool(decide.get("acceptance_criteria")), "decision has no acceptance criteria")
    record("plan_resolved", not plan.get("unresolved_questions"), "plan still contains unresolved questions")
    record("plan_review_pass", plan_review.get("verdict") == "pass", "plan review did not pass")
    record("plan_approved", approvals_ok, "plan approval was not granted")

    allowlist = plan.get("file_allowlist") or []
    changed = implement.get("changed_files") or []
    if acc.get("require_clean_scope", True):
        import fnmatch
        out_of_scope = [f for f in changed if not any(fnmatch.fnmatch(f, g) for g in allowlist)]
        record("scope_clean", not out_of_scope, f"changed files outside allowlist: {out_of_scope[:5]}")

    tests_required = bool(test_design.get("test_required", True)) and bool(changed)
    if acc.get("require_test_evidence_for_nontrivial", True) and tests_required:
        record("tests_pass", test_exec.get("verdict") == "pass", "test evidence is missing or not passing")
        record("tests_have_commands", bool(test_exec.get("commands")), "test evidence has no executed commands")
    else:
        checks["tests_pass"] = True

    if changed:
        record("code_review_pass", code_review.get("verdict") == "pass", "code review did not pass")
    else:
        checks["code_review_pass"] = True

    if acc.get("require_alignment_pass", True):
        record("alignment_pass", alignment.get("verdict") == "pass", "alignment check did not pass")

    record("revision_pinned", bool(run.get("revision") or not live), "repository revision was not pinned")

    if not live:
        return {"verdict": "simulated", "basis": "mock provider run; contracts exercised, repository correctness not certified",
                "checks": checks, "failures": failures}
    if failures:
        return {"verdict": "fail", "basis": "acceptance gate blocked completion", "checks": checks, "failures": failures}
    return {"verdict": "pass", "basis": "all acceptance conditions verified against recorded evidence",
            "checks": checks, "failures": []}
