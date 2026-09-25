"""Live mode approval contract (RF-W1-A-02). Env alone cannot enable live."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_forge.decisions.validator import validate_decisions_for_gate
from research_forge.errors import ErrorCode, forge_error
from research_forge.settings import Settings
from research_forge.wave1.credentials import credential_refs_for_live


@dataclass(frozen=True)
class LiveRunContract:
    cli_live_flag: bool
    mode: str
    cost_ceiling_usd: float
    confidentiality: str
    approval_record_id: str | None
    provider_config_present: bool


def build_live_contract(
    *,
    cli_live: bool,
    settings: Settings,
    cost_ceiling_usd: float | None = None,
    confidentiality: str = "public",
    approval_record_id: str | None = None,
) -> LiveRunContract:
    refs = credential_refs_for_live()
    return LiveRunContract(
        cli_live_flag=cli_live,
        mode=settings.mode,
        cost_ceiling_usd=cost_ceiling_usd or 5.0,
        confidentiality=confidentiality,
        approval_record_id=approval_record_id,
        provider_config_present=bool(refs),
    )


def validate_live_contract(
    repo_root: Path,
    contract: LiveRunContract,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Return (ok, messages, forge_error_dict)."""
    failures: list[str] = []
    if not contract.cli_live_flag:
        failures.append("live requires explicit --live CLI flag")
    if contract.mode == "live" and not contract.cli_live_flag:
        failures.append("RF_MODE=live without --live is rejected")
    if contract.confidentiality == "restricted" and contract.cli_live_flag:
        failures.append("restricted confidentiality blocks public live adapters")
    if contract.cli_live_flag and not contract.approval_record_id:
        failures.append("live requires approval_record_id")
    if contract.cli_live_flag and contract.cost_ceiling_usd <= 0:
        failures.append("live requires positive cost_ceiling_usd")
    if contract.cli_live_flag and not contract.provider_config_present:
        failures.append("live requires configured credential refs (no secrets in repo)")

    ok_gate, gate_msgs = validate_decisions_for_gate(repo_root, "wave_1_live")
    if contract.cli_live_flag and not ok_gate:
        failures.extend(gate_msgs)

    if failures:
        err = forge_error(ErrorCode.POLICY_DENIED, "Live run contract invalid", failures=failures)
        return False, failures, err.to_dict()
    if contract.cli_live_flag:
        return True, [], None
    return True, [], None


def effective_mode(settings: Settings, cli_live: bool) -> str:
    if cli_live:
        return "live"
    return "mock" if settings.mode != "live" else "mock"
