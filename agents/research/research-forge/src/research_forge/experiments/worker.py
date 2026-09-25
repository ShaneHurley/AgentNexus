"""Background worker: execute approved experiment with zero model calls."""

from __future__ import annotations

import sys

from research_forge.experiments.config import load_experiment_config
from research_forge.experiments.ledger_events import append_event, experiment_ledger
from research_forge.experiments.runner import ExperimentRunner
from research_forge.experiments.store import ExperimentStore
from research_forge.settings import find_package_root, find_workspace_root


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m research_forge.experiments.worker EXP-ID", file=sys.stderr)
        return 2
    experiment_id = args[0]
    package_root = find_package_root()
    workspace_root = find_workspace_root()
    cfg = load_experiment_config(package_root)
    prefix = str(cfg.get("ledger_run_prefix", "exp-"))
    store = ExperimentStore(workspace_root, package_root=package_root, cfg=cfg)
    runner = ExperimentRunner(package_root, workspace_root, store)
    ledger = experiment_ledger(workspace_root)
    approvals = store.read_json(experiment_id, "approvals.json") or {}
    try:
        result = runner.run_foreground(
            experiment_id,
            approve=bool(approvals.get("approve")),
            approve_long=bool(approvals.get("approve_long")),
            approve_code=bool(approvals.get("approve_code_execution")),
            approve_external=bool(approvals.get("approve_external_data")),
        )
        append_event(
            ledger,
            experiment_id=experiment_id,
            event_type="experiment_finished",
            payload={"exit_code": result.get("exit_code"), "token_budget": 0, "background": True},
            actor="local_experiment_runner",
            prefix=prefix,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        store.set_status(experiment_id, "failed", error=str(exc))
        append_event(
            ledger,
            experiment_id=experiment_id,
            event_type="experiment_finished",
            payload={"exit_code": 1, "error": str(exc), "token_budget": 0, "background": True},
            actor="local_experiment_runner",
            prefix=prefix,
        )
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
