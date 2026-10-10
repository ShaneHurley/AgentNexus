"""Offline measurements. Mock evidence can describe costs but never qualify routing."""
from __future__ import annotations
from collections import defaultdict
import math
from agent_core.model_catalog import fields, number, digest, routing_policy_digest


def _metrics(rows):
    clusters = defaultdict(list)
    for row in rows: clusters[row["task_id"]].append(row)
    # A held-out task succeeds only if every repeat succeeds without a violation.
    successes = sum(all(r["success"] and not r["critical_policy_violation"] for r in group) for group in clusters.values())
    n = len(clusters)
    z = 1.959963984540054
    lower = 0.0
    if n:
        p = successes/n
        lower = (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
    unknown = sum(r["cost_usd"] is None for r in rows)
    known = sum(r["cost_usd"] or 0 for r in rows)
    return {"distinct_tasks": n, "runs": len(rows), "successful_tasks": successes,
            "repeated_tasks": sum(len(group)>=2 for group in clusters.values()),
            "wilson_lower_95": lower, "critical_policy_violations": sum(r["critical_policy_violation"] for r in rows),
            "known_cost_usd": known, "unknown_cost_records": unknown,
            "successful_task_cost_usd": known/successes if successes and not unknown else None,
            **{key: sum(r[key] for r in rows) for key in ("input_tokens", "output_tokens", "tool_calls", "repairs", "escalations", "latency_ms")}}


def evaluate(records, *, role, evaluation_class, catalog_hash, policy_hash, corpus_hash,
             candidate, baseline, evidence_kind="mock"):
    """Aggregate full-task records, including failed/repair/escalation attempts in cost.

    policy_hash must be routing_policy_digest(policy): the canonical policy hash
    with all role qualifications fields removed. Full policy snapshots retain their
    separate hashes as run pins. ModelResolver verifies this stable evidence pin
    against the routing policy before accepting a reviewed report.

    Each record is one complete repeated task run, not one provider call. The caller
    pins a held-out corpus and supplies all attempts in that run's measurements.
    """
    for value in (role, evaluation_class, catalog_hash, policy_hash, corpus_hash, candidate, baseline):
        if not isinstance(value, str) or not value: raise ValueError("missing evaluation pin")
    for pin in (catalog_hash, policy_hash, corpus_hash):
        if len(pin) != 64 or any(c not in "0123456789abcdef" for c in pin): raise ValueError("invalid evaluation hash")
    if candidate == baseline or evidence_kind not in {"mock", "measured"}: raise ValueError("invalid evaluation")
    required = {"task_id", "run_id", "model", "success", "critical_policy_violation", "input_tokens", "output_tokens", "tool_calls", "repairs", "escalations", "latency_ms", "cost_usd"}
    validated = []; seen = set()
    for row in records:
        fields(row, required, required)
        for key in ("task_id", "run_id", "model"):
            if not isinstance(row[key], str) or not row[key]: raise ValueError("invalid record identity")
        if row["model"] not in {candidate, baseline}: raise ValueError("unexpected model")
        identity = (row["model"], row["task_id"], row["run_id"])
        if identity in seen: raise ValueError("duplicate evaluation run")
        seen.add(identity)
        for key in ("success", "critical_policy_violation"):
            if type(row[key]) is not bool: raise ValueError("invalid outcome")
        for key in ("input_tokens", "output_tokens", "tool_calls", "repairs", "escalations"):
            number(row[key], key, True)
        if row["repairs"] > 1 or row["escalations"] > 1: raise ValueError("task attempt limit exceeded")
        number(row["latency_ms"], "latency_ms")
        if row["cost_usd"] is not None: number(row["cost_usd"], "cost_usd")
        validated.append(dict(row))
    candidate_rows = [r for r in validated if r["model"] == candidate]
    baseline_rows = [r for r in validated if r["model"] == baseline]
    cm, bm = _metrics(candidate_rows), _metrics(baseline_rows)
    matched = {(r["task_id"],r["run_id"]) for r in candidate_rows} == {(r["task_id"],r["run_id"]) for r in baseline_rows}
    reasons = []
    if evidence_kind != "measured": reasons.append("mock_evidence")
    if cm["distinct_tasks"] < 100: reasons.append("insufficient_distinct_tasks")
    if cm["repeated_tasks"] != cm["distinct_tasks"]: reasons.append("missing_repeats")
    if not matched: reasons.append("unmatched_baseline")
    if cm["wilson_lower_95"] < .9: reasons.append("quality_lower_bound")
    if cm["critical_policy_violations"] or bm["critical_policy_violations"]: reasons.append("critical_policy_violation")
    if cm["successful_task_cost_usd"] is None or bm["successful_task_cost_usd"] is None: reasons.append("unknown_cost")
    elif cm["successful_task_cost_usd"] >= bm["successful_task_cost_usd"]: reasons.append("not_cheaper")
    report = dict(schema_version=1, role=role, evaluation_class=evaluation_class,
                  catalog_hash=catalog_hash, policy_hash=policy_hash, corpus_hash=corpus_hash,
                  candidate=candidate, baseline=baseline, evidence_kind=evidence_kind,
                  records_hash=digest(sorted(validated,key=lambda r:(r["model"],r["task_id"],r["run_id"]))),
                  candidate_metrics=cm, baseline_metrics=bm, matched_baseline=matched,
                  qualified=not reasons, exclusion_reasons=reasons)
    report["report_hash"] = digest(report)
    return report
