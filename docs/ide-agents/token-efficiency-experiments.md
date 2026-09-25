# Token-efficiency experiments (feature-flagged)

All experiments ship **disabled by default**. Turning a flag on is reversible — set it back to `false` and sync or restart as noted below.

Promotion criteria (documented only; not verified in-repo): **≥15% total token reduction** on the relevant benchmark or deep-research trace, with **no decline** in Daily Coder benchmark PASS rate or deep-research adversarial PASS rate.

## 1. Conditional deep-research lanes (IDE)

| Item | Value |
|------|--------|
| Config | [`agents/ide/config/token_experiments.json`](../../agents/ide/config/token_experiments.json) |
| Flag | `conditional_deep_research_lanes` |
| Default | `false` → parent **fans out all six lanes** at Step 2 (unchanged) |

**Enable:** set `"conditional_deep_research_lanes": true`, then invoke `/deep-research`. Parent reads the flag via `#file:ide-agents/config/token_experiments.json` at entry.

**When on:** Step 2 runs lanes 1–3 only (`internal-authority-scout`, `official-standards-scout`, `academic-evidence-scout`). Lanes 4–6 run only when the brief, integrator output, or gap wave tags name a material gap that maps to `practitioner-implementation-scout`, `failure-unfavorable-scout`, or `alternatives-analogy-scout`.

Canonical behavior: [`agents/ide/canonical/deep-research.md`](../../agents/ide/canonical/deep-research.md) and [`deep-research-phase-index.md`](../../agents/ide/contracts/deep-research-phase-index.md).

## 2. Optional documentation-curator (Daily Coder, technical docs only)

| Item | Value |
|------|--------|
| Config | [`agents/coding/daily-coder-ecosystem/config/token_experiments.json`](../../agents/coding/daily-coder-ecosystem/config/token_experiments.json) |
| Flag | `documentation_curator_after_document` |
| Default | `false` → **documenter only**; no curator pass |

**Enable:** set `"documentation_curator_after_document": true` in the Daily Coder package `config/token_experiments.json` (copy ships with the ecosystem root).

**Scope:** repository technical documentation after the DOCUMENT phase only. **Must not** run for résumé, career README, or `personal-store` / `skills/personal/career-tools` outputs — use `resume-tailor` and `artifact-style-enforcer` with the résumé profile instead.

Wiring: opt-in note in [`agents/coding/daily-coder-ecosystem/agents/documenter/prompt.md`](../../agents/coding/daily-coder-ecosystem/agents/documenter/prompt.md); registry entry [`agents/shared/agent-core/registry.yaml`](../../agents/shared/agent-core/registry.yaml) (`documentation-curator`, `lifecycle: experimental`).

## 3. Research early-stop threshold (Daily Coder runtime)

| Item | Value |
|------|--------|
| Config | [`agents/coding/daily-coder-ecosystem/config/budgets.json`](../../agents/coding/daily-coder-ecosystem/config/budgets.json) per profile |
| Field | `early_stop_min_cards` |
| Default | **2** on profile **M** (matches prior hard-coded behavior); other profiles default to **2** if omitted |

**Enable / tune:** set `"early_stop_min_cards": 3` (or higher) on the target profile in `budgets.json`. Lower values increase early-stop sensitivity; `1` effectively disables the “at least two cards” gate.

Runtime: [`daily_coder/context.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/context.py) `should_stop_research`, called from [`orchestrator.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/orchestrator.py) `_research`.

## 4. Lane contract shards (IDE deep-research)

| Item | Value |
|------|--------|
| Config | [`agents/ide/config/token_experiments.json`](../../agents/ide/config/token_experiments.json) |
| Flag | `lane_contract_shards` |
| Default | `false` → load Common + assigned lane from full `subagent-contracts.md` |

**Enable:** set `"lane_contract_shards": true`. Follow [`agents/ide/contracts/deep-research-lane-shards.md`](../../agents/ide/contracts/deep-research-lane-shards.md) (stub — no split files yet).

After editing IDE canonical agents, run:

```bash
python agents/ide/scripts/sync_ide_agents.py
```
