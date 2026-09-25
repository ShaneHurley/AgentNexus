"""Research Forge CLI — mock-by-default, no side effects on stub commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

from research_forge.decisions.validator import validate_decisions_for_gate
from research_forge.errors import ErrorCode, ForgeError, forge_error
from research_forge.settings import (
    find_package_root,
    find_repo_root,
    find_workspace_root,
    load_settings,
)
from research_forge.wave0.doctor import run_doctor
from research_forge.wave0.dry_run import plan_dry_run
from research_forge.wave0.integration import run_wave0_fixture
from research_forge.wave0.replay import replay_bundle
from research_forge.wave1.baseline import run_baseline_mock
from research_forge.wave1.orchestrator import Wave1Orchestrator
from research_forge.wave1.persistence import load_run_state, save_run_state, status_payload

app = typer.Typer(
    no_args_is_help=True,
    help="Research Forge — evidence-first deep research (mock default).",
)
experiment_app = typer.Typer(no_args_is_help=True, help="Local token-free experiments")
app.add_typer(experiment_app, name="experiment")


def _exit_error(err: ForgeError) -> None:
    typer.echo(json.dumps(err.to_dict(), indent=2))
    raise typer.Exit(code=2)


def _repo() -> Path:
    return find_repo_root()


def _echo_json(payload: Any, *, compact: bool) -> None:
    if compact:
        typer.echo(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    else:
        typer.echo(json.dumps(payload, indent=2))


def _experiment_service(workspace: Path | None = None):
    from research_forge.experiments.service import ExperimentService

    try:
        package_root = find_package_root()
    except FileNotFoundError as exc:
        _exit_error(
            forge_error(
                ErrorCode.BLOCKED,
                str(exc),
                workspace=str(find_workspace_root(workspace)),
                hint="Set RF_PACKAGE_ROOT to your research-forge checkout or pip install -e that tree.",
            )
        )
    ws = find_workspace_root(workspace)
    return ExperimentService(package_root, ws)


@app.command()
def run(
    fixture: Path | None = typer.Option(None, help="Wave 0 mock fixture path"),
    request: Path | None = typer.Option(None, help="Wave 1 research_request JSON"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; no provider events"),
    live: bool = typer.Option(False, "--live", help="Live providers (requires gate approval)"),
    wave1: bool = typer.Option(False, "--wave1", help="Run Wave 1 sequential orchestrator"),
) -> None:
    root = _repo()
    gate = "wave_1_mock" if wave1 or request else "wave_0"
    ok, msgs = validate_decisions_for_gate(root, gate)
    if not ok:
        _exit_error(forge_error(ErrorCode.BLOCKED, f"Decision gate failed for {gate}", failures=msgs))
    if live:
        ok_live, live_msgs = validate_decisions_for_gate(root, "wave_1_live")
        if not ok_live:
            _exit_error(
                forge_error(ErrorCode.POLICY_DENIED, "Live mode blocked", failures=live_msgs)
            )
    if dry_run:
        plan = plan_dry_run(root)
        typer.echo(json.dumps(plan, indent=2))
        return
    if wave1 or request:
        if request is None:
            _exit_error(forge_error(ErrorCode.SCHEMA_INVALID, "Wave 1 run requires --request JSON"))
        req = json.loads(request.read_text(encoding="utf-8"))
        orch = Wave1Orchestrator(root, live=live)
        result = orch.run(req)
        state = result.get("state")
        if isinstance(state, dict) and state.get("run_id"):
            try:
                save_run_state(root, state, live=live)
                result = {**result, "persisted": True}
            except (OSError, ValueError) as exc:
                result = {**result, "persisted": False, "persist_error": str(exc)}
        typer.echo(json.dumps({k: v for k, v in result.items() if k != "report"}, indent=2))
        if not result.get("ok"):
            raise typer.Exit(code=2)
        return
    if fixture is None:
        _exit_error(
            forge_error(
                ErrorCode.NOT_IMPLEMENTED,
                "Provide --fixture (Wave 0), --request/--wave1 (Wave 1), or --dry-run",
            )
        )
    result = run_wave0_fixture(root, fixture)
    typer.echo(json.dumps(result, indent=2))


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Persisted Wave 1 run id"),
    answer: list[str] = typer.Option(
        [],
        "--answer",
        "-a",
        help="Clarification answer as CLQ-ID=value (repeatable)",
    ),
    live: bool = typer.Option(False, "--live", help="Live providers (requires gate approval)"),
) -> None:
    """Resume a paused Wave 1 run from durable state on disk."""
    root = _repo()
    try:
        state, meta = load_run_state(root, run_id)
    except FileNotFoundError:
        _exit_error(
            forge_error(
                ErrorCode.NOT_FOUND,
                f"No persisted state for run {run_id}",
                hint="Run wave1 first so state is saved under runs/wave1/<run_id>/state.json",
            )
        )
    except ValueError as exc:
        _exit_error(forge_error(ErrorCode.SCHEMA_INVALID, str(exc)))
    use_live = live or bool(meta.get("live"))
    if use_live:
        ok_live, live_msgs = validate_decisions_for_gate(root, "wave_1_live")
        if not ok_live:
            _exit_error(
                forge_error(ErrorCode.POLICY_DENIED, "Live mode blocked", failures=live_msgs)
            )
    answers: dict[str, str] = {}
    for item in answer:
        if "=" not in item:
            _exit_error(
                forge_error(
                    ErrorCode.SCHEMA_INVALID,
                    f"Invalid --answer {item!r}; expected CLQ-ID=value",
                )
            )
        key, _, value = item.partition("=")
        answers[key.strip()] = value.strip()
    orch = Wave1Orchestrator(root, live=use_live)
    result = orch.resume(state, answers)
    if isinstance(result.get("state"), dict) and result["state"].get("run_id"):
        try:
            save_run_state(root, result["state"], live=use_live)
            result = {**result, "persisted": True}
        except (OSError, ValueError) as exc:
            result = {**result, "persisted": False, "persist_error": str(exc)}
    typer.echo(json.dumps({k: v for k, v in result.items() if k != "report"}, indent=2))
    if not result.get("ok"):
        raise typer.Exit(code=2)


@app.command()
def status(run_id: str | None = typer.Argument(None, help="Run id; omit to list recent")) -> None:
    """Show Wave 1 run status from durable state (Wave 0: use validate/doctor)."""
    root = _repo()
    payload = status_payload(root, run_id)
    typer.echo(json.dumps(payload, indent=2))
    if run_id and not payload.get("found"):
        raise typer.Exit(code=2)


@app.command()
def validate(
    gate: str = typer.Option("wave_0", help="wave_0 | wave_1_mock | wave_1_live"),
) -> None:
    root = _repo()
    if gate not in ("wave_0", "wave_1_mock", "wave_1_live"):
        _exit_error(forge_error(ErrorCode.SCHEMA_INVALID, f"Unknown gate: {gate}"))
    ok, msgs = validate_decisions_for_gate(root, gate)  # type: ignore[arg-type]
    payload = {"gate": gate, "ok": ok, "messages": msgs}
    typer.echo(json.dumps(payload, indent=2))
    if not ok:
        raise typer.Exit(code=2)


@app.command()
def doctor() -> None:
    root = _repo()
    settings = load_settings(root)
    report = run_doctor(root, settings)
    typer.echo(json.dumps(report, indent=2))
    if not report.get("ok"):
        raise typer.Exit(code=2)


@app.command("baseline")
def baseline_cmd(mock: bool = typer.Option(True, help="Run mock baseline suite")) -> None:
    root = _repo()
    ok, msgs = validate_decisions_for_gate(root, "wave_1_mock")
    if not ok:
        _exit_error(forge_error(ErrorCode.BLOCKED, "Decision gate failed", failures=msgs))
    if mock:
        typer.echo(json.dumps(run_baseline_mock(root), indent=2))


@app.command("replay")
def replay_cmd(bundle: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    root = _repo()
    result = replay_bundle(root, bundle)
    typer.echo(json.dumps(result, indent=2))
    if not result.get("ok"):
        raise typer.Exit(code=2)


@experiment_app.command("create")
def experiment_create(
    title: str | None = typer.Option(None),
    question: str | None = typer.Option(None),
    why_run: str | None = typer.Option(None, "--why-run"),
    hypothesis: str | None = typer.Option(None),
    expected_support: str | None = typer.Option(None, "--expected-support"),
    expected_reject: str | None = typer.Option(None, "--expected-reject"),
    expected_inconclusive: str | None = typer.Option(None, "--expected-inconclusive"),
    decision_impact: str | None = typer.Option(None, "--decision-impact"),
    kind: str | None = typer.Option(None),
    data: str | None = typer.Option(None, "--data"),
    group_column: str | None = typer.Option(None, "--group-column"),
    metric_column: str | None = typer.Option(None, "--metric-column"),
    unittest_start: str | None = typer.Option(None, "--unittest-start"),
    estimated_runtime_seconds: int = typer.Option(30, "--estimated-runtime-seconds"),
    repetitions: int = typer.Option(1, "--repetitions"),
    idea_id: str | None = typer.Option(None, "--idea-id"),
    from_json: str | None = typer.Option(
        None,
        "--from-json",
        help="Proposal JSON path, or '-' for stdin (agent-friendly)",
    ),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="Project dir for .research-forge/ (default: cwd)"
    ),
    compact: bool = typer.Option(False, "--compact", help="Single-line JSON stdout"),
) -> None:
    svc = _experiment_service(workspace)
    try:
        if from_json is not None:
            raw = sys.stdin.read() if from_json == "-" else Path(from_json).read_text(encoding="utf-8")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("--from-json must be a JSON object")
            proposal = svc.create_from_json(payload)
        else:
            required = {
                "title": title,
                "question": question,
                "why_run": why_run,
                "hypothesis": hypothesis,
                "expected_support": expected_support,
                "expected_reject": expected_reject,
                "expected_inconclusive": expected_inconclusive,
                "decision_impact": decision_impact,
                "kind": kind,
                "data": data,
            }
            missing = [k for k, v in required.items() if not v]
            if missing:
                raise ValueError(
                    f"Missing required options {missing} (or pass --from-json)"
                )
            proposal = svc.create(
                title=title,  # type: ignore[arg-type]
                question=question,  # type: ignore[arg-type]
                why_run=why_run,  # type: ignore[arg-type]
                hypothesis=hypothesis,  # type: ignore[arg-type]
                expected_support=expected_support,  # type: ignore[arg-type]
                expected_reject=expected_reject,  # type: ignore[arg-type]
                expected_inconclusive=expected_inconclusive,  # type: ignore[arg-type]
                decision_impact=decision_impact,  # type: ignore[arg-type]
                kind=kind,  # type: ignore[arg-type]
                data_path=data,  # type: ignore[arg-type]
                group_column=group_column,
                metric_column=metric_column,
                unittest_start=unittest_start,
                estimated_runtime_seconds=estimated_runtime_seconds,
                repetitions=repetitions,
                idea_id=idea_id,
            )
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.SCHEMA_INVALID, str(exc)))
    if compact:
        _echo_json(
            {"experiment_id": proposal["experiment_id"], "kind": proposal["kind"], "status": "proposed"},
            compact=True,
        )
    else:
        _echo_json(proposal, compact=False)
    typer.echo(f"Created {proposal['experiment_id']}", err=True)


@experiment_app.command("pre-review")
def experiment_pre_review(
    experiment_id: str = typer.Argument(...),
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    svc = _experiment_service(workspace)
    try:
        review = svc.pre_review(experiment_id)
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.BLOCKED, str(exc)))
    if compact:
        _echo_json(
            {
                "experiment_id": experiment_id,
                "verdict": review.get("verdict"),
                "rejection_reasons": review.get("rejection_reasons"),
            },
            compact=True,
        )
    else:
        _echo_json(review, compact=False)
    if review.get("verdict") != "PASS":
        raise typer.Exit(code=2)


@experiment_app.command("run")
def experiment_run(
    experiment_id: str = typer.Argument(...),
    approve: bool = typer.Option(False, "--approve"),
    approve_long: bool = typer.Option(False, "--approve-long"),
    approve_code_execution: bool = typer.Option(False, "--approve-code-execution"),
    approve_external_data: bool = typer.Option(False, "--approve-external-data"),
    background: bool = typer.Option(False, "--background"),
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    svc = _experiment_service(workspace)
    try:
        result = svc.run(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code_execution,
            approve_external=approve_external_data,
            background=background,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.POLICY_DENIED, str(exc)))
    if compact:
        _echo_json(
            {
                "experiment_id": experiment_id,
                "exit_code": result.get("exit_code"),
                "status": result.get("status", "succeeded" if result.get("exit_code") == 0 else "failed"),
                "background": bool(result.get("background")),
            },
            compact=True,
        )
    else:
        _echo_json(result, compact=False)


@experiment_app.command("pipeline")
def experiment_pipeline(
    experiment_id: str = typer.Argument(...),
    approve: bool = typer.Option(False, "--approve"),
    approve_long: bool = typer.Option(False, "--approve-long"),
    approve_code_execution: bool = typer.Option(False, "--approve-code-execution"),
    approve_external_data: bool = typer.Option(False, "--approve-external-data"),
    background: bool = typer.Option(False, "--background"),
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(
        True, "--compact/--verbose", help="Compact summary (default) or full nested JSON"
    ),
) -> None:
    """pre-review → run → post-review in one process."""
    svc = _experiment_service(workspace)
    try:
        summary = svc.pipeline(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code_execution,
            approve_external=approve_external_data,
            background=background,
        )
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.POLICY_DENIED, str(exc)))
    _echo_json(summary, compact=compact)
    if not summary.get("ok"):
        raise typer.Exit(code=2)
    if not summary.get("background") and summary.get("exit_code") not in (0, None):
        raise typer.Exit(code=2)


@experiment_app.command("status")
def experiment_status(
    experiment_id: str = typer.Argument(...),
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    svc = _experiment_service(workspace)
    try:
        st = svc.status(experiment_id)
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.NOT_IMPLEMENTED, str(exc)))
    _echo_json(st, compact=compact)


@experiment_app.command("post-review")
def experiment_post_review(
    experiment_id: str = typer.Argument(...),
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    svc = _experiment_service(workspace)
    try:
        post = svc.post_review(experiment_id)
    except Exception as exc:  # noqa: BLE001
        _exit_error(forge_error(ErrorCode.BLOCKED, str(exc)))
    if compact:
        _echo_json(
            {
                "experiment_id": experiment_id,
                "observed_class": post.get("observed_class"),
                "status": post.get("status"),
                "evidence_usability": post.get("evidence_usability"),
            },
            compact=True,
        )
    else:
        _echo_json(post, compact=False)


@experiment_app.command("list")
def experiment_list(
    workspace: Path | None = typer.Option(None, "--workspace"),
    compact: bool = typer.Option(False, "--compact"),
) -> None:
    svc = _experiment_service(workspace)
    _echo_json(svc.list_experiments(), compact=compact)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
