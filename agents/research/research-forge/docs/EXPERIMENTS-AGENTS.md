# Local experiments — agent guide

Token-free local experiments. Pre/post review are **deterministic Python gates**, not LLM roles. Do **not** duplicate them with chat skeptics. Wave 4 Experiment Architect is design-only and separate.

## Roots

| Root | Env / flag | Holds |
|------|------------|-------|
| package | auto from install, or `RF_PACKAGE_ROOT` | `config/`, `schemas/` |
| workspace | `--workspace`, else `RF_WORKSPACE`, else cwd | `.research-forge/`, ledger |

Prefer `RF_WORKSPACE` over legacy `RF_RUN_DIR`.

## Preferred agent workflow

1. Write a proposal JSON under the project (not a long CLI flag line).
2. `create --from-json` then `pipeline --approve --compact`.
3. Use stdout only — do **not** re-read artifact JSON unless debugging.

```powershell
cd YOUR_PROJECT
# ensure .research-forge/data/... exists

py -3.10 -m research_forge experiment create --from-json proposal.json --compact
# stdout: {"experiment_id":"EXP-...","kind":"...","status":"proposed"}

py -3.10 -m research_forge experiment pipeline EXP-XXXXXXXXXXXX --approve --compact
# stdout: compact summary with observed_class, exit_code, artifact_dir
```

### Minimal proposal.json

```json
{
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
    "metric_column": "value"
  }
}
```

## Rules

- Always `--approve` to run; `--approve-long` always required with `--background`.
- Pre-review is a structural checklist (impact length, required fields, distinct expected outcomes, data path/allowlist) — not semantic adversarial LLM review.
- Output is `LOCAL_OBSERVATION` only.
- Granular commands (`pre-review` / `run` / `post-review`) remain supported for debugging.

Human examples: [EXPERIMENTS.md](EXPERIMENTS.md).
