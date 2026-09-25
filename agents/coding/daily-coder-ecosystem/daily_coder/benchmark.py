"""Local orchestration benchmark.

Runs representative routes with the mock provider so harness changes can be compared
without spending credits. Results pin configuration and report distributions rather than
one flattering average.
"""
from __future__ import annotations
import json, shutil, statistics, tempfile, time
from pathlib import Path
from .orchestrator import Orchestrator
from .providers.mock import MockProvider
from .state_store import StateStore
from .util import canonical_json, load_json, sha256_text

SCENARIOS = [
    {"id":"trivial","request":"Fix typo","expected":"S"},
    {"id":"contained","request":"Refactor input parsing in 2 files","expected":"M"},
    {"id":"cross_cutting","request":"Add database validation across 2 files","expected":"L"},
    {"id":"high_risk","request":"Design a breaking production database migration architecture with security and concurrency concerns across 8 files","expected":"XL"},
]

def _percentile(values, fraction):
    values=sorted(values)
    if not values: return 0
    return values[min(len(values)-1,max(0,round((len(values)-1)*fraction)))]

def run_benchmark(root, output=None, baseline=None, repeats=1):
    root=Path(root)
    records=[]
    with tempfile.TemporaryDirectory() as temp:
        state=StateStore(Path(temp)/"benchmark.sqlite")
        orchestrator=Orchestrator(root,state,MockProvider(),live=False)
        for scenario in SCENARIOS:
            for repeat in range(max(1,repeats)):
                started=time.perf_counter()
                run=orchestrator.start(scenario["request"],root)
                elapsed=time.perf_counter()-started
                usage=state.total_usage(run["run_id"])
                invocations=state.invocations(run["run_id"],1000)
                records.append({
                    "scenario":scenario["id"],"repeat":repeat,"run_id":run["run_id"],
                    "expected_profile":scenario["expected"],"profile":run["profile"],
                    "status":run["status"],"calls":usage["calls"],"tokens":usage["tokens"],
                    "latency_ms":round(elapsed*1000,3),
                    "input_tokens":sum(i["input_tokens"] for i in invocations),
                    "output_tokens":sum(i["output_tokens"] for i in invocations),
                    "repairs":run.get("repair_cycles",0),
                })
                shutil.rmtree(root/".daily-coder"/"artifacts"/run["run_id"],ignore_errors=True)
    result={
        "version":1,
        "created_at":time.time(),
        "config_hash":sha256_text(canonical_json({
            "default":load_json(root/"config/default.json"),
            "budgets":load_json(root/"config/budgets.json"),
            "models":load_json(root/"config/models.json"),
        })),
        "records":records,
        "summary":{
            "runs":len(records),
            "verified_routes":sum(1 for r in records if r["profile"]==r["expected_profile"]),
            "successful":sum(1 for r in records if r["status"]=="SIMULATED"),
            "median_calls":statistics.median(r["calls"] for r in records),
            "p90_calls":_percentile([r["calls"] for r in records],0.9),
            "median_tokens":statistics.median(r["tokens"] for r in records),
            "p90_tokens":_percentile([r["tokens"] for r in records],0.9),
            "median_latency_ms":round(statistics.median(r["latency_ms"] for r in records),3),
            "p90_latency_ms":_percentile([r["latency_ms"] for r in records],0.9),
        },
    }
    if baseline:
        previous=json.loads(Path(baseline).read_text(encoding="utf-8"))["summary"]
        result["comparison"]={key:_delta(previous.get(key),result["summary"].get(key))
                              for key in ("median_calls","p90_calls","median_tokens","p90_tokens","median_latency_ms","p90_latency_ms")}
        result["comparison"]["success_regression"]=result["summary"]["successful"]<previous.get("successful",0)
    if output:
        path=Path(output); path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result

def _delta(before,after):
    if before in (None,0) or after is None: return None
    return {"before":before,"after":after,"percent":round((after-before)/before*100,2)}

GATE_ROUTE_KEYS=("verified_routes","successful")
GATE_PERCENT_KEYS=("median_calls","p90_calls","median_tokens","p90_tokens")
DEFAULT_GATE_MAX_INCREASE_PERCENT=10.0

def baseline_gate_failures(result, *, max_increase_percent=DEFAULT_GATE_MAX_INCREASE_PERCENT,
                           min_routes=4, min_successful=4):
    """Return human-readable failure reasons; empty list means pass."""
    failures=[]
    summary=result.get("summary") or {}
    for key, minimum, label in (
        ("verified_routes", min_routes, "verified routes"),
        ("successful", min_successful, "successful runs"),
    ):
        value=summary.get(key)
        if value is None or value < minimum:
            failures.append(f"{label} {value!r} below minimum {minimum}")
    comparison=result.get("comparison") or {}
    if comparison.get("success_regression"):
        failures.append("success_regression: fewer successful runs than baseline")
    for key in GATE_PERCENT_KEYS:
        delta=comparison.get(key)
        if not delta or delta.get("percent") is None:
            continue
        pct=delta["percent"]
        if pct > max_increase_percent:
            failures.append(
                f"{key} increased {pct}% (limit {max_increase_percent}% without baseline bump)"
            )
    return failures

def exit_code_for_gate(result, **gate_kwargs):
    return 1 if baseline_gate_failures(result, **gate_kwargs) else 0
