"""Local experiment subsystem tests — mock/local files only."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from research_forge.experiments.config import _load_experiment_config_cached, load_experiment_config
from research_forge.experiments.creator import ExperimentCreator
from research_forge.experiments.kinds import run_dataset_profile, run_group_comparison
from research_forge.experiments.post_review import ExperimentPostReviewer
from research_forge.experiments.pre_review import ExperimentPreReviewer
from research_forge.experiments.runner import ExperimentRunner, ExperimentRunnerError
from research_forge.experiments.service import ExperimentService
from research_forge.experiments.store import ExperimentStore
from research_forge.schemas_pkg.registry import get_experiment_registry, get_registry


def _clear_caches() -> None:
    get_registry.cache_clear()
    get_experiment_registry.cache_clear()
    _load_experiment_config_cached.cache_clear()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal repo tree with config + schemas copied from real package."""
    real = Path(__file__).resolve().parents[1]
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "experiments.yaml").write_text(
        (real / "config" / "experiments.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "config" / "policies.yaml").write_text(
        (real / "config" / "policies.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "config" / "defaults.yaml").write_text("mode: mock\n", encoding="utf-8")
    import shutil

    shutil.copytree(real / "schemas", tmp_path / "schemas")
    (tmp_path / ".research-forge" / "data").mkdir(parents=True)
    (tmp_path / "runs").mkdir()
    monkeypatch.chdir(tmp_path)
    _clear_caches()
    yield tmp_path
    _clear_caches()


def _write_csv(repo: Path) -> Path:
    p = repo / ".research-forge" / "data" / "example.csv"
    p.write_text("group,value\nA,10\nA,12\nB,18\nB,20\n", encoding="utf-8")
    return p


def _base_kwargs(data: str) -> dict:
    return {
        "title": "Compare group means",
        "question": "Does group B have a higher observed mean than group A?",
        "why_run": "Decide whether a stronger controlled follow-up is worth designing.",
        "hypothesis": "Group B has a higher observed value than group A in the available file.",
        "expected_support": "Group B has the largest mean with a meaningful observed gap.",
        "expected_reject": "Group B does not have the largest mean.",
        "expected_inconclusive": "Too few usable rows or only one valid group.",
        "decision_impact": "Use the result only to decide whether to design a stronger follow-up study.",
        "kind": "group_comparison",
        "data_path": data,
        "group_column": "group",
        "metric_column": "value",
    }


def test_creator_schema_and_ledger(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    get_registry(repo).validate("local_experiment_proposal", prop)
    assert prop["token_budget"] == 0
    assert (repo / ".research-forge" / "experiments" / prop["experiment_id"] / "proposal.json").is_file()
    ok, _ = svc.ledger.verify_chain(f"exp-{prop['experiment_id']}")
    assert ok


def test_pre_review_reject_weak_impact(repo: Path) -> None:
    _write_csv(repo)
    creator = ExperimentCreator(repo)
    prop = creator.create(**{**_base_kwargs(".research-forge/data/example.csv"), "decision_impact": "weak"})
    review = ExperimentPreReviewer(repo).review(prop["experiment_id"])
    assert review["verdict"] == "REJECT"
    assert "actionable_below_threshold" in review["rejection_reasons"]


def test_pre_review_reject_non_discriminating_outcomes(repo: Path) -> None:
    _write_csv(repo)
    creator = ExperimentCreator(repo)
    kwargs = _base_kwargs(".research-forge/data/example.csv")
    same = "Same outcome text for all classes."
    kwargs.update(
        {
            "expected_support": same,
            "expected_reject": same,
            "expected_inconclusive": same,
        }
    )
    prop = creator.create(**kwargs)
    review = ExperimentPreReviewer(repo).review(prop["experiment_id"])
    assert review["verdict"] == "REJECT"
    assert "expected_outcomes_not_discriminating" in review["rejection_reasons"]


def test_pre_review_reject_missing_data(repo: Path) -> None:
    creator = ExperimentCreator(repo)
    prop = creator.create(**_base_kwargs(".research-forge/data/missing.csv"))
    review = ExperimentPreReviewer(repo).review(prop["experiment_id"])
    assert review["verdict"] == "REJECT"
    assert "usable_data_below_threshold" in review["rejection_reasons"]


def test_group_comparison_happy_path(repo: Path) -> None:
    csv_path = _write_csv(repo)
    out = run_group_comparison(csv_path, group_column="group", metric_column="value")
    assert out["exit_code"] == 0
    assert out["metrics"]["largest_mean_group"] == "B"
    assert out["metrics"]["inconclusive"] is False
    assert out["raw_stdout_tail"] == ""


def test_group_comparison_inconclusive(repo: Path) -> None:
    p = repo / ".research-forge" / "data" / "tiny.csv"
    p.write_text("group,value\nA,1\n", encoding="utf-8")
    out = run_group_comparison(p, group_column="group", metric_column="value", min_group_n=2)
    assert out["metrics"]["inconclusive"] is True


def test_dataset_profile_jsonl(repo: Path) -> None:
    p = repo / ".research-forge" / "data" / "rows.jsonl"
    p.write_text('{"x": 1}\n{"x": 2, "y": 3}\n', encoding="utf-8")
    out = run_dataset_profile(p)
    assert out["metrics"]["row_count"] == 2
    assert "x" in out["metrics"]["columns"]
    assert out["raw_stdout_tail"] == ""


def test_runner_refuses_without_pre_review(repo: Path) -> None:
    _write_csv(repo)
    prop = ExperimentCreator(repo).create(**_base_kwargs(".research-forge/data/example.csv"))
    with pytest.raises(ExperimentRunnerError, match="pre-review"):
        ExperimentRunner(repo).run_foreground(prop["experiment_id"], approve=True)


def test_runner_refuses_without_approve(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    review = svc.pre_review(prop["experiment_id"])
    assert review["verdict"] == "PASS"
    with pytest.raises(ExperimentRunnerError, match="approve"):
        ExperimentRunner(repo).run_foreground(prop["experiment_id"], approve=False)


def test_code_kind_requires_code_approval(repo: Path) -> None:
    td = repo / ".research-forge" / "data" / "suite"
    td.mkdir(parents=True)
    (td / "test_noop.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )
    kwargs = _base_kwargs(".research-forge/data/suite")
    kwargs.update(
        {
            "kind": "python_unittest_benchmark",
            "title": "Local unittest smoke",
            "question": "Do local noop unit tests pass quickly?",
            "hypothesis": "Noop suite exits 0.",
            "group_column": None,
            "metric_column": None,
            "unittest_start": ".research-forge/data/suite",
        }
    )
    svc = ExperimentService(repo)
    prop = svc.create(**kwargs)
    review = svc.pre_review(prop["experiment_id"])
    assert review["requires_code_approval"] is True
    with pytest.raises(ExperimentRunnerError, match="approve-code-execution"):
        ExperimentRunner(repo).run_foreground(prop["experiment_id"], approve=True)


def test_full_flow_post_review_boundary(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    assert svc.pre_review(prop["experiment_id"])["verdict"] == "PASS"
    result = svc.run(prop["experiment_id"], approve=True)
    assert result["token_budget"] == 0
    post = svc.post_review(prop["experiment_id"])
    assert post["status"] == "LOCAL_OBSERVATION"
    assert post["not_a_causal_conclusion"] is True
    assert post["observed_class"] == "support"
    get_registry(repo).validate("experiment_post_review", post)


def test_post_review_inconclusive_without_ab_hypothesis(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    kwargs = _base_kwargs(".research-forge/data/example.csv")
    kwargs["hypothesis"] = "Treatment arm shows a higher observed value in the file."
    prop = svc.create(**kwargs)
    assert svc.pre_review(prop["experiment_id"])["verdict"] == "PASS"
    svc.run(prop["experiment_id"], approve=True)
    post = svc.post_review(prop["experiment_id"])
    assert post["observed_class"] == "inconclusive"


def test_pipeline_one_shot(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    summary = svc.pipeline(prop["experiment_id"], approve=True)
    assert summary["ok"] is True
    assert summary["pre_review_verdict"] == "PASS"
    assert summary["observed_class"] in ("support", "reject", "inconclusive")
    assert summary["exit_code"] == 0


def test_create_from_json(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    payload = {
        "title": "Compare group means",
        "question": "Does group B have a higher observed mean than group A?",
        "why_run": "Decide whether a stronger follow-up is worth designing.",
        "hypothesis": "Group B has a higher observed value than group A in the available file.",
        "expected_support": "Group B has the largest mean with a meaningful gap.",
        "expected_reject": "Group B does not have the largest mean.",
        "expected_inconclusive": "Too few usable rows or only one valid group.",
        "decision_impact": "Use only to decide whether to design a stronger follow-up.",
        "kind": "group_comparison",
        "inputs": {
            "data_path": ".research-forge/data/example.csv",
            "group_column": "group",
            "metric_column": "value",
        },
    }
    prop = svc.create_from_json(payload)
    assert prop["experiment_id"].startswith("EXP-")
    assert prop["token_budget"] == 0


def test_create_from_json_rejects_existing_id(repo: Path) -> None:
    _write_csv(repo)
    svc = ExperimentService(repo)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    payload = {
        "experiment_id": prop["experiment_id"],
        "title": "Dup",
        "question": "q?",
        "why_run": "Decide whether follow-up is worth designing now.",
        "hypothesis": "Group B has a higher observed value than group A.",
        "expected_support": "B higher",
        "expected_reject": "B not higher",
        "expected_inconclusive": "too few rows",
        "decision_impact": "Use only to decide on a stronger follow-up.",
        "kind": "group_comparison",
        "inputs": {
            "data_path": ".research-forge/data/example.csv",
            "group_column": "group",
            "metric_column": "value",
        },
    }
    with pytest.raises(ValueError, match="already exists"):
        svc.create_from_json(payload)


def test_create_from_dict_missing_title(repo: Path) -> None:
    creator = ExperimentCreator(repo)
    with pytest.raises(ValueError, match="Missing required proposal fields"):
        creator.create_from_dict(
            {
                "question": "q?",
                "why_run": "why run this local check carefully",
                "hypothesis": "h",
                "expected_support": "s",
                "expected_reject": "r",
                "expected_inconclusive": "i",
                "decision_impact": "Use only for follow-up design decision.",
                "kind": "dataset_profile",
                "inputs": {"data_path": "x.csv"},
            }
        )


def test_pipeline_failed_run_ok_false(repo: Path) -> None:
    td = repo / ".research-forge" / "data" / "bad_suite"
    td.mkdir(parents=True)
    (td / "test_fail.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_fail(self):\n        self.assertTrue(False)\n",
        encoding="utf-8",
    )
    kwargs = _base_kwargs(".research-forge/data/bad_suite")
    kwargs.update(
        {
            "kind": "python_unittest_benchmark",
            "title": "Failing suite",
            "question": "Do failing tests report nonzero exit?",
            "hypothesis": "Suite exits nonzero.",
            "expected_support": "exit 0",
            "expected_reject": "exit nonzero",
            "expected_inconclusive": "could not run",
            "group_column": None,
            "metric_column": None,
            "unittest_start": ".research-forge/data/bad_suite",
        }
    )
    svc = ExperimentService(repo)
    prop = svc.create(**kwargs)
    summary = svc.pipeline(
        prop["experiment_id"], approve=True, approve_code=True
    )
    assert summary["exit_code"] != 0
    assert summary["ok"] is False


def test_post_review_group_alpha_not_ab(repo: Path) -> None:
    p = repo / ".research-forge" / "data" / "alpha.csv"
    p.write_text("group,value\nalpha,1\nalpha,2\nbeta,9\nbeta,10\n", encoding="utf-8")
    svc = ExperimentService(repo)
    kwargs = _base_kwargs(".research-forge/data/alpha.csv")
    kwargs["hypothesis"] = "Group alpha has a higher observed value than group beta."
    prop = svc.create(**kwargs)
    assert svc.pre_review(prop["experiment_id"])["verdict"] == "PASS"
    svc.run(prop["experiment_id"], approve=True)
    post = svc.post_review(prop["experiment_id"])
    # Must not treat "group alpha" as "group a"; two-label path claims alpha higher → reject
    assert post["observed_class"] == "reject"


def test_post_review_empty_dataset_profile_inconclusive(repo: Path) -> None:
    p = repo / ".research-forge" / "data" / "empty.csv"
    p.write_text("col\n", encoding="utf-8")
    svc = ExperimentService(repo)
    kwargs = _base_kwargs(".research-forge/data/empty.csv")
    kwargs.update(
        {
            "kind": "dataset_profile",
            "title": "Empty profile",
            "question": "Does the file have usable rows?",
            "hypothesis": "File has usable rows.",
            "group_column": None,
            "metric_column": None,
        }
    )
    prop = svc.create(**kwargs)
    assert svc.pre_review(prop["experiment_id"])["verdict"] == "PASS"
    svc.run(prop["experiment_id"], approve=True)
    post = svc.post_review(prop["experiment_id"])
    assert post["observed_class"] == "inconclusive"


def test_long_requires_approve_long(repo: Path) -> None:
    _write_csv(repo)
    kwargs = _base_kwargs(".research-forge/data/example.csv")
    kwargs["estimated_runtime_seconds"] = 400
    svc = ExperimentService(repo)
    prop = svc.create(**kwargs)
    review = svc.pre_review(prop["experiment_id"])
    assert review["requires_long_approval"] is True
    with pytest.raises(ExperimentRunnerError, match="approve-long"):
        ExperimentRunner(repo).run_foreground(prop["experiment_id"], approve=True)


def test_background_status_without_model_calls(repo: Path) -> None:
    _write_csv(repo)
    kwargs = _base_kwargs(".research-forge/data/example.csv")
    kwargs["estimated_runtime_seconds"] = 400
    svc = ExperimentService(repo)
    prop = svc.create(**kwargs)
    svc.pre_review(prop["experiment_id"])
    out = svc.run(prop["experiment_id"], approve=True, approve_long=True, background=True)
    assert out["background"] is True
    st = svc.status(prop["experiment_id"])
    assert st["status"] in ("running", "succeeded", "failed")
    import time

    for _ in range(50):
        st = svc.status(prop["experiment_id"])
        if st["status"] != "running":
            break
        time.sleep(0.1)
    assert st["status"] in ("succeeded", "failed", "running")


def test_store_read_does_not_mkdir(repo: Path) -> None:
    store = ExperimentStore(repo, package_root=repo)
    missing_id = "EXP-DOESNOTEXIST"
    assert store.read_json(missing_id, "proposal.json") is None
    assert not (store.root / missing_id).exists()


def test_foreign_cwd_uses_package_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Experiments work from a project without config/; assets come from package_root."""
    package = Path(__file__).resolve().parents[1]
    foreign = tmp_path / "other_project"
    foreign.mkdir()
    (foreign / ".research-forge" / "data").mkdir(parents=True)
    csv_path = foreign / ".research-forge" / "data" / "example.csv"
    csv_path.write_text("group,value\nA,10\nA,12\nB,18\nB,20\n", encoding="utf-8")

    monkeypatch.setenv("RF_PACKAGE_ROOT", str(package))
    monkeypatch.delenv("RF_WORKSPACE", raising=False)
    monkeypatch.chdir(foreign)
    _clear_caches()

    from research_forge.settings import find_package_root, find_workspace_root

    assert find_package_root() == package.resolve()
    assert find_workspace_root() == foreign.resolve()

    svc = ExperimentService(package, foreign)
    prop = svc.create(**_base_kwargs(".research-forge/data/example.csv"))
    assert svc.pre_review(prop["experiment_id"])["verdict"] == "PASS"
    result = svc.run(prop["experiment_id"], approve=True)
    assert result["token_budget"] == 0
    post = svc.post_review(prop["experiment_id"])
    assert post["status"] == "LOCAL_OBSERVATION"
    assert (
        foreign / ".research-forge" / "experiments" / prop["experiment_id"] / "result.json"
    ).is_file()
    _clear_caches()


def test_install_layout_find_package_root_without_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulate site-packages layout: research_forge next to config/ + schemas/."""
    import research_forge as rf
    import shutil

    real = Path(__file__).resolve().parents[1]
    site = tmp_path / "site-packages"
    pkg = site / "research_forge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("# stub\n", encoding="utf-8")
    shutil.copytree(real / "config", site / "config")
    shutil.copytree(real / "schemas", site / "schemas")

    monkeypatch.delenv("RF_PACKAGE_ROOT", raising=False)
    monkeypatch.setattr(rf, "__file__", str(pkg / "__init__.py"))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir(exist_ok=True)
    monkeypatch.chdir(unrelated)
    _clear_caches()

    from research_forge.settings import find_package_root

    assert find_package_root() == site.resolve()
    load_experiment_config(find_package_root())
    get_registry(find_package_root()).validate(
        "local_experiment_proposal",
        {
            "experiment_id": "EXP-TEST000001",
            "title": "t",
            "question": "q?",
            "why_run": "why run this local check now",
            "hypothesis": "h",
            "expected_support": "s1",
            "expected_reject": "s2",
            "expected_inconclusive": "s3",
            "decision_impact": "Use only for a follow-up design decision.",
            "kind": "dataset_profile",
            "inputs": {"data_path": "x.csv"},
            "estimated_runtime_seconds": 10,
            "repetitions": 1,
            "token_budget": 0,
            "created_at": "2020-01-01T00:00:00+00:00",
        },
    )
    _clear_caches()


def test_cli_foreign_cwd_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = Path(__file__).resolve().parents[1]
    foreign = tmp_path / "cli_project"
    foreign.mkdir()
    (foreign / ".research-forge" / "data").mkdir(parents=True)
    (foreign / ".research-forge" / "data" / "example.csv").write_text(
        "group,value\nA,10\nA,12\nB,18\nB,20\n", encoding="utf-8"
    )
    proposal = {
        "title": "Compare group means",
        "question": "Does group B have a higher observed mean than group A?",
        "why_run": "Decide whether a stronger follow-up is worth designing.",
        "hypothesis": "Group B has a higher observed value than group A in the available file.",
        "expected_support": "Group B has the largest mean with a meaningful gap.",
        "expected_reject": "Group B does not have the largest mean.",
        "expected_inconclusive": "Too few usable rows or only one valid group.",
        "decision_impact": "Use only to decide whether to design a stronger follow-up.",
        "kind": "group_comparison",
        "inputs": {
            "data_path": ".research-forge/data/example.csv",
            "group_column": "group",
            "metric_column": "value",
        },
    }
    prop_path = foreign / "proposal.json"
    prop_path.write_text(json.dumps(proposal), encoding="utf-8")

    env = os.environ.copy()
    env["RF_PACKAGE_ROOT"] = str(package)
    env.pop("RF_WORKSPACE", None)
    env.pop("RF_RUN_DIR", None)
    env["PYTHONPATH"] = str(package / "src") + os.pathsep + env.get("PYTHONPATH", "")

    create = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_forge",
            "experiment",
            "create",
            "--from-json",
            str(prop_path),
            "--compact",
        ],
        cwd=str(foreign),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert create.returncode == 0, create.stderr
    created = json.loads(create.stdout.strip().splitlines()[-1])
    eid = created["experiment_id"]

    pipe = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_forge",
            "experiment",
            "pipeline",
            eid,
            "--approve",
            "--compact",
        ],
        cwd=str(foreign),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert pipe.returncode == 0, pipe.stderr
    summary = json.loads(pipe.stdout.strip().splitlines()[-1])
    assert summary["ok"] is True
    assert summary["observed_class"] == "support"
    assert (foreign / ".research-forge" / "experiments" / eid / "result.json").is_file()
