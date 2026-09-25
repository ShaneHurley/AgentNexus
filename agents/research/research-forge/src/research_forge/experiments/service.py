"""Orchestrates create → pre-review → run → post-review with policy + ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_forge.experiments.config import load_experiment_config
from research_forge.experiments.creator import ExperimentCreator
from research_forge.experiments.ledger_events import append_event, experiment_ledger
from research_forge.experiments.post_review import ExperimentPostReviewer
from research_forge.experiments.pre_review import ExperimentPreReviewer
from research_forge.experiments.runner import ExperimentRunner, ExperimentRunnerError
from research_forge.experiments.store import ExperimentStore
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
from research_forge.settings import find_package_root, find_workspace_root


def _register_experiment_tools(gw: PolicyGateway) -> None:
    caps_read = {
        "read": True,
        "write": False,
        "network": False,
        "execute": False,
        "credential": False,
        "data_class": "local",
    }
    caps_write = {**caps_read, "write": True}
    caps_run = {**caps_write, "execute": True}
    for tool_id, caps in (
        ("experiment.create", caps_write),
        ("experiment.pre_review", caps_write),
        ("experiment.run", caps_run),
        ("experiment.read", caps_read),
    ):
        err = gw.register_tool(ToolManifest(tool_id=tool_id, capabilities=caps))
        if err:
            raise RuntimeError(err.to_dict().get("message") or str(err))


class ExperimentService:
    def __init__(
        self,
        package_root: Path | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        # Single-arg backward compat: ExperimentService(path) uses path for both roots.
        if package_root is not None and workspace_root is None:
            # Ambiguous only when caller intended workspace-only; tests pass one tree.
            # If package_root lacks assets, treat it as workspace and resolve package separately.
            if (package_root / "config" / "experiments.yaml").is_file():
                workspace_root = package_root
            else:
                workspace_root = package_root
                package_root = None

        try:
            self.package_root = (package_root or find_package_root()).resolve()
        except FileNotFoundError as exc:
            ws = (workspace_root or find_workspace_root()).resolve()
            raise FileNotFoundError(
                f"{exc} workspace_root={ws}. "
                "Config/schemas live in the research-forge package, not your project cwd."
            ) from exc
        self.workspace_root = (workspace_root or find_workspace_root()).resolve()
        # Keep alias for older call sites / tests
        self.repo_root = self.package_root

        self.cfg = load_experiment_config(self.package_root)
        self.store = ExperimentStore(
            self.workspace_root, package_root=self.package_root, cfg=self.cfg
        )
        self.ledger = experiment_ledger(self.workspace_root)
        self.prefix = str(self.cfg.get("ledger_run_prefix", "exp-"))
        policy_path = self.package_root / "config" / "policies.yaml"
        self.gateway = PolicyGateway(policy_path, mode="mock")
        _register_experiment_tools(self.gateway)
        self.creator = ExperimentCreator(
            self.package_root, self.workspace_root, self.store
        )
        self.pre_reviewer = ExperimentPreReviewer(
            self.package_root, self.workspace_root, self.store
        )
        self.runner = ExperimentRunner(
            self.package_root, self.workspace_root, self.store
        )
        self.post_reviewer = ExperimentPostReviewer(
            self.package_root, self.workspace_root, self.store
        )

    def _authorize(self, tool_id: str, operation: str, target: str) -> None:
        ok, decision = self.gateway.authorize(
            role="experiment_operator",
            phase="local_experiment",
            tool_id=tool_id,
            operation=operation,
            target=target,
            live=False,
        )
        if not ok:
            raise PermissionError(f"Policy denied: {decision.get('reason')}")

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self._authorize("experiment.create", "experiment_create", "local://experiments")
        proposal = self.creator.create(**kwargs)
        append_event(
            self.ledger,
            experiment_id=proposal["experiment_id"],
            event_type="experiment_proposed",
            payload={"kind": proposal["kind"], "title": proposal["title"]},
            actor="experiment_creator",
            prefix=self.prefix,
        )
        return proposal

    def create_from_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._authorize("experiment.create", "experiment_create", "local://experiments")
        proposal = self.creator.create_from_dict(payload)
        append_event(
            self.ledger,
            experiment_id=proposal["experiment_id"],
            event_type="experiment_proposed",
            payload={"kind": proposal["kind"], "title": proposal["title"]},
            actor="experiment_creator",
            prefix=self.prefix,
        )
        return proposal

    def pre_review(self, experiment_id: str) -> dict[str, Any]:
        self._authorize("experiment.pre_review", "experiment_pre_review", f"local://{experiment_id}")
        review = self.pre_reviewer.review(experiment_id)
        append_event(
            self.ledger,
            experiment_id=experiment_id,
            event_type="experiment_pre_reviewed",
            payload={"verdict": review["verdict"], "scores": review["scores"]},
            actor="experiment_pre_reviewer",
            prefix=self.prefix,
        )
        return review

    def pipeline(
        self,
        experiment_id: str,
        *,
        approve: bool,
        approve_long: bool = False,
        approve_code: bool = False,
        approve_external: bool = False,
        background: bool = False,
    ) -> dict[str, Any]:
        """Run pre-review → run → post-review in one process (fail-fast on pre FAIL)."""
        review = self.pre_review(experiment_id)
        if review.get("verdict") != "PASS":
            return {
                "experiment_id": experiment_id,
                "pre_review_verdict": review.get("verdict"),
                "rejection_reasons": review.get("rejection_reasons"),
                "status": "rejected",
                "ok": False,
            }
        result = self.run(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code,
            approve_external=approve_external,
            background=background,
        )
        if background:
            return {
                "experiment_id": experiment_id,
                "pre_review_verdict": "PASS",
                "status": "running",
                "background": True,
                "ok": True,
                "result": result,
            }
        post = self.post_review(experiment_id)
        exit_code = result.get("exit_code")
        status = self.store.read_json(experiment_id, "status.json") or {}
        return {
            "experiment_id": experiment_id,
            "pre_review_verdict": "PASS",
            "observed_class": post.get("observed_class"),
            "exit_code": exit_code,
            "status": post.get("status"),
            "run_status": status.get("status"),
            "evidence_usability": post.get("evidence_usability"),
            "artifact_dir": str(self.store.exp_dir(experiment_id, create=False)),
            "ok": exit_code == 0,
        }

    def run(
        self,
        experiment_id: str,
        *,
        approve: bool,
        approve_long: bool = False,
        approve_code: bool = False,
        approve_external: bool = False,
        background: bool = False,
    ) -> dict[str, Any]:
        self._authorize("experiment.run", "experiment_run", f"local://{experiment_id}")
        if not approve:
            raise ExperimentRunnerError("--approve required")
        append_event(
            self.ledger,
            experiment_id=experiment_id,
            event_type="experiment_approved",
            payload={
                "approve_long": approve_long,
                "approve_code": approve_code,
                "approve_external": approve_external,
                "background": background,
            },
            actor="human",
            prefix=self.prefix,
        )
        append_event(
            self.ledger,
            experiment_id=experiment_id,
            event_type="experiment_started",
            payload={"background": background, "token_budget": 0},
            actor="local_experiment_runner",
            prefix=self.prefix,
        )
        if background:
            return self.runner.run_background(
                experiment_id,
                approve=approve,
                approve_long=approve_long,
                approve_code=approve_code,
                approve_external=approve_external,
            )
        result = self.runner.run_foreground(
            experiment_id,
            approve=approve,
            approve_long=approve_long,
            approve_code=approve_code,
            approve_external=approve_external,
        )
        append_event(
            self.ledger,
            experiment_id=experiment_id,
            event_type="experiment_finished",
            payload={"exit_code": result.get("exit_code"), "token_budget": 0},
            actor="local_experiment_runner",
            prefix=self.prefix,
        )
        return result

    def status(self, experiment_id: str) -> dict[str, Any]:
        self._authorize("experiment.read", "experiment_read", f"local://{experiment_id}")
        status = self.store.read_json(experiment_id, "status.json")
        if not status:
            raise FileNotFoundError(experiment_id)
        result = self.store.read_json(experiment_id, "result.json")
        out = dict(status)
        if result:
            out["has_result"] = True
            out["exit_code"] = result.get("exit_code")
        return out

    def post_review(self, experiment_id: str) -> dict[str, Any]:
        self._authorize("experiment.read", "experiment_read", f"local://{experiment_id}")
        post = self.post_reviewer.review(experiment_id)
        append_event(
            self.ledger,
            experiment_id=experiment_id,
            event_type="experiment_post_reviewed",
            payload={
                "observed_class": post["observed_class"],
                "status": post["status"],
                "not_a_causal_conclusion": True,
            },
            actor="experiment_post_reviewer",
            prefix=self.prefix,
        )
        return post

    def list_experiments(self) -> list[dict[str, Any]]:
        self._authorize("experiment.read", "experiment_read", "local://experiments")
        items: list[dict[str, Any]] = []
        for eid in self.store.list_ids():
            st = self.store.read_json(eid, "status.json") or {"status": "unknown"}
            prop = self.store.read_json(eid, "proposal.json") or {}
            items.append(
                {
                    "experiment_id": eid,
                    "status": st.get("status"),
                    "kind": prop.get("kind"),
                    "title": prop.get("title"),
                }
            )
        return items
