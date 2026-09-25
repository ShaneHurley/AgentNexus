"""Local Experiment Runner — token_budget=0, typed kinds only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.experiments.config import load_experiment_config
from research_forge.experiments.kinds import (
    run_dataset_profile,
    run_group_comparison,
    run_python_unittest_benchmark,
)
from research_forge.experiments.store import ExperimentStore
from research_forge.schemas_pkg.registry import get_experiment_registry


class ExperimentRunnerError(ValueError):
    pass


class ExperimentRunner:
    role_id = "local_experiment_runner"

    def __init__(
        self,
        package_root: Path,
        workspace_root: Path | None = None,
        store: ExperimentStore | None = None,
    ) -> None:
        self.package_root = package_root
        self.workspace_root = (workspace_root or package_root).resolve()
        self.store = store or ExperimentStore(
            self.workspace_root, package_root=self.package_root
        )
        self.cfg = load_experiment_config(self.package_root)
        self.registry = get_experiment_registry(self.package_root)

    def _resolve(self, rel: str) -> Path:
        p = Path(rel)
        if not p.is_absolute():
            return (self.workspace_root / p).resolve()
        return p.resolve()

    def _check_gates(
        self,
        experiment_id: str,
        *,
        approve: bool,
        approve_long: bool,
        approve_code: bool,
        approve_external: bool,
        background: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        proposal = self.store.read_json(experiment_id, "proposal.json")
        if not proposal:
            raise ExperimentRunnerError(f"missing proposal for {experiment_id}")
        pre = self.store.read_json(experiment_id, "pre-review.json")
        if not pre:
            raise ExperimentRunnerError("pre-review.json required; run pre-review first")
        if pre.get("verdict") != "PASS":
            raise ExperimentRunnerError("pre-review verdict is not PASS")
        if not approve:
            raise ExperimentRunnerError("--approve required to run")
        if (pre.get("requires_long_approval") or background) and not approve_long:
            raise ExperimentRunnerError("--approve-long required for long/background runs")
        if pre.get("requires_code_approval") and not approve_code:
            raise ExperimentRunnerError("--approve-code-execution required for code experiments")
        if pre.get("requires_external_data_approval") and not approve_external:
            raise ExperimentRunnerError("--approve-external-data required for paths outside allowlist")
        return proposal, pre

    def _execute_kind(self, proposal: dict[str, Any]) -> dict[str, Any]:
        raw_tail = int(self.cfg.get("raw_tail_chars", 4000))
        kind = proposal["kind"]
        data_path = self._resolve(proposal["inputs"]["data_path"])
        if kind == "dataset_profile":
            return run_dataset_profile(data_path, raw_tail=raw_tail)
        if kind == "group_comparison":
            return run_group_comparison(
                data_path,
                group_column=proposal["inputs"]["group_column"],
                metric_column=proposal["inputs"]["metric_column"],
                min_group_n=int(self.cfg.get("min_group_n", 2)),
                raw_tail=raw_tail,
            )
        if kind == "python_unittest_benchmark":
            start = proposal["inputs"].get("unittest_start") or proposal["inputs"]["data_path"]
            return run_python_unittest_benchmark(
                self._resolve(start),
                repetitions=int(proposal.get("repetitions", 1)),
                raw_tail=raw_tail,
            )
        raise ExperimentRunnerError(f"unsupported kind: {kind}")

    def run_foreground(
        self,
        experiment_id: str,
        *,
        approve: bool,
        approve_long: bool = False,
        approve_code: bool = False,
        approve_external: bool = False,
    ) -> dict[str, Any]:
        proposal, _pre = self._check_gates(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code,
            approve_external=approve_external,
            background=False,
        )
        approvals = {
            "approve": approve,
            "approve_long": approve_long,
            "approve_code_execution": approve_code,
            "approve_external_data": approve_external,
            "background": False,
        }
        self.store.write_json(experiment_id, "approvals.json", approvals)
        self.store.set_status(experiment_id, "running")

        try:
            raw = self._execute_kind(proposal)
            result: dict[str, Any] = {
                "experiment_id": experiment_id,
                "kind": proposal["kind"],
                "exit_code": raw["exit_code"],
                "duration_seconds": raw["duration_seconds"],
                "metrics": raw["metrics"],
                "token_budget": 0,
                "raw_stdout_tail": raw["raw_stdout_tail"],
                "raw_stderr_tail": raw["raw_stderr_tail"],
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            if raw["exit_code"] != 0:
                result["error"] = "nonzero_exit"
            self.registry.validate("experiment_run_result", result)
            self.store.write_json(experiment_id, "result.json", result)
            status = "succeeded" if raw["exit_code"] == 0 else "failed"
            self.store.set_status(experiment_id, status)
            return result
        except Exception as exc:  # noqa: BLE001 — capture into failed result
            result = {
                "experiment_id": experiment_id,
                "kind": proposal["kind"],
                "exit_code": 1,
                "duration_seconds": 0.0,
                "metrics": {},
                "token_budget": 0,
                "raw_stdout_tail": "",
                "raw_stderr_tail": "",
                "error": str(exc),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            self.store.write_json(experiment_id, "result.json", result)
            self.store.set_status(experiment_id, "failed", error=str(exc))
            raise

    def run_background(
        self,
        experiment_id: str,
        *,
        approve: bool,
        approve_long: bool,
        approve_code: bool = False,
        approve_external: bool = False,
    ) -> dict[str, Any]:
        self._check_gates(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code,
            approve_external=approve_external,
            background=True,
        )
        approvals = {
            "approve": approve,
            "approve_long": approve_long,
            "approve_code_execution": approve_code,
            "approve_external_data": approve_external,
            "background": True,
        }
        self.store.write_json(experiment_id, "approvals.json", approvals)
        self.store.set_status(experiment_id, "running", background=True)

        exp_dir = self.store.exp_dir(experiment_id)
        log_path = exp_dir / "job.log"
        # Spawn worker: python -m research_forge.experiments.worker EXP-ID
        env = os.environ.copy()
        env["RF_WORKSPACE"] = str(self.workspace_root)
        env["RF_PACKAGE_ROOT"] = str(self.package_root)
        proc = subprocess.Popen(
            [sys.executable, "-m", "research_forge.experiments.worker", experiment_id],
            cwd=str(self.workspace_root),
            env=env,
            stdout=log_path.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )
        self.store.write_json(
            experiment_id,
            "job.json",
            {"pid": proc.pid, "started": True},
        )
        (exp_dir / "job.pid").write_text(str(proc.pid), encoding="utf-8")
        return {"experiment_id": experiment_id, "status": "running", "pid": proc.pid, "background": True}
