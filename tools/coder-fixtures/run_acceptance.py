"""Explicit acceptance fault injection around the public agent-nexus CLI.

Every model response remains accounted. Variants never change tool grants.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from agent_core.nexus_cli import main as nexus_main
from agent_core.routing_runtime import SupervisedProvider
from daily_coder.coder_v1 import CoderV1
from daily_coder.artifacts import ArtifactStore
from daily_coder.state_store import StateStore


def format_completed_result(request, result):
    if request.role != "planner" or result.output is None or result.tool_calls:
        return False
    if not request.allow_incomplete_output:
        raise ValueError("format fixture requires opt-in coder-v1")
    original = result.output
    body = json.dumps(original, sort_keys=True)
    result.output = "Findings from the completed planning response:\n\x60\x60\x60json\n" + body + "\n\x60\x60\x60"
    result.raw_text = result.output
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--variant", choices=("nominal", "fenced-planner", "interrupt-after-implement"), default="nominal")
    parser.add_argument("cli_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    repository = args.repository.resolve()
    coding = repository / "agents/coding/daily-coder-ecosystem"
    state = StateStore(coding / ".daily-coder/state.sqlite")
    artifacts = ArtifactStore(coding / ".daily-coder/artifacts", state)
    invoke = SupervisedProvider.invoke
    run_phase = CoderV1._run_phase
    injected = False

    def response(provider, request):
        nonlocal injected
        result = invoke(provider, request)
        if args.variant == "fenced-planner" and not injected:
            original = json.dumps(result.output, sort_keys=True, default=str)
            if format_completed_result(request, result):
                artifacts.put(request.run_id, "fixture_intervention", "fixture", {
                    "variant": args.variant, "role": request.role,
                    "original_payload_sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "tools_changed": False, "usage_changed": False,
                })
                injected = True
        return result

    def phase(engine, run_id, name, profile, packet, gateway, broker):
        result = run_phase(engine, run_id, name, profile, packet, gateway, broker)
        if args.variant == "interrupt-after-implement" and name == "IMPLEMENT" and result == "ok":
            writes = [call["id"] for call in engine.state.tool_calls(run_id, limit=1000)
                      if call["phase"] == "IMPLEMENT" and call["tool"] in {"filesystem.write", "patch.apply"}
                      and call["decision"] == "allow"]
            if not writes or engine.state.get(run_id)["phase"] != "IMPLEMENT":
                raise RuntimeError("fixture requires a durable accepted implementation")
            artifacts.put(run_id, "fixture_intervention", "fixture", {
                "variant": args.variant, "accepted_write_receipts": writes,
                "durable_phase": "IMPLEMENT", "effects_replayed": False,
            })
            print(json.dumps({"run_id": run_id, "status": "FIXTURE_INTERRUPT", "write_receipts": writes}), flush=True)
            raise SystemExit(75)
        return result

    cli_args = args.cli_args[1:] if args.cli_args[:1] == ["--"] else args.cli_args
    with patch.object(SupervisedProvider, "invoke", response), patch.object(CoderV1, "_run_phase", phase):
        return nexus_main(["--repository", str(repository), *cli_args])


if __name__ == "__main__":
    raise SystemExit(main())
