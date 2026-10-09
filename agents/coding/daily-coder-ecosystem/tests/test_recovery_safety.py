from pathlib import Path
import pytest
from agent_core.contracts import ContractDenied
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.state_store import StateStore

DC = Path(__file__).resolve().parents[1]


def make(tmp_path, **kw):
    state = StateStore(tmp_path / "state.sqlite")
    o = Orchestrator(DC, state, kw.pop("provider", MockProvider()), **kw)
    run = o.create("fix a typo", tmp_path)
    return o, state, run


@pytest.mark.parametrize("change", ["pricing", "live", "approval", "budget"])
def test_execution_conditions_cannot_change_on_resume(tmp_path, change):
    o, state, run = make(tmp_path)
    if change == "pricing": o.pricing = {"changed": {"input_per_1k": 1, "output_per_1k": 1}}
    if change == "live": o.live = True
    if change == "approval": o.approvals_required = not o.approvals_required
    if change == "budget": o.budgets = {**o.budgets, "changed": True}
    with pytest.raises(ContractDenied, match="configuration"):
        o.run(run)
    assert state.get(run)["phase"] == "NEW"


def test_unfinished_reservation_blocks_replay(tmp_path):
    o, state, run = make(tmp_path)
    o.budget.reserve(run, "S", 10, estimated_usd=.1, reservation_id="accepted-call")
    result = o.run(run)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["phase"] == "NEW"
    assert state.active_budget_reservations(run)["est_usd"] == .1
    assert StateStore(state.path).active_budget_reservations(run)["calls"] == 1


def test_live_exception_retains_exposure_and_does_not_repair(tmp_path):
    class Uncertain(MockProvider):
        def invoke(self, request):
            raise TimeoutError("remote may have accepted")
    o, state, run = make(tmp_path, provider=Uncertain(), live=True)
    out = o.run(run)
    assert out["status"] == "RECONCILIATION_REQUIRED"
    assert state.active_budget_reservations(run)["calls"] >= 1
    assert state.get(run)["repair_cycles"] == 0
    before = len(state.invocations(run))
    assert o.run(run)["status"] == "RECONCILIATION_REQUIRED"
    assert len(state.invocations(run)) == before
    report = o.budget.report(run)
    assert report["usage_status"] == "unknown"
    assert report["reserved_exposure"]["calls"] >= 1


def test_provider_endpoint_cannot_change_on_resume(tmp_path):
    provider = MockProvider(); provider.base_url = "https://approved.invalid"
    o, state, run = make(tmp_path, provider=provider)
    provider.base_url = "https://different.invalid"
    with pytest.raises(ContractDenied, match="configuration"):
        o.run(run)


def test_uncertain_diagnostician_stops_repair_without_fallback(tmp_path):
    class Uncertain(MockProvider):
        def invoke(self, request): raise TimeoutError("unknown remote result")
    o, state, run = make(tmp_path, provider=Uncertain(), live=True)
    state.transition(run, "INTAKE", {}, run + ":intake")
    state.transition(run, "SIZE", {}, run + ":size")
    state.set_profile(run, "S")
    result = o._repair(run, "PLAN", "prior schema failure", {}, 0)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert state.get(run)["phase"] == "DIAGNOSE"
    assert "diagnosis" not in o.artifacts.load_all(run)
    assert len(state.invocations(run)) == 1


def test_accounting_failure_after_response_blocks_repair(tmp_path):
    from daily_coder.models import InvocationResult
    class Unpriced(MockProvider):
        def invoke(self, request):
            return InvocationResult(output={}, model="unreviewed-model", input_tokens=10, output_tokens=5)
    o, state, run = make(tmp_path, provider=Unpriced(), live=True)
    result = o.run(run)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert state.active_budget_reservations(run)["calls"] == 1
    assert state.get(run)["repair_cycles"] == 0


def test_repair_cannot_mutate_already_uncertain_run(tmp_path):
    o, state, run = make(tmp_path)
    state.set_status(run, "RECONCILIATION_REQUIRED")
    result = o._repair(run, "PLAN", "unknown", {}, 0)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert result["repair_cycles"] == 0
    assert result["phase"] == "NEW"
