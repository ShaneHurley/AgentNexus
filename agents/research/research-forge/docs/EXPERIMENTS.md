# Local experiment subsystem

Research Forge adds three bounded, **token-free** roles for rare local experiments when real usable data or trusted local code is available:

1. **Experiment Creator** — records question, rationale, hypothesis, three outcome classes, decision impact, inputs, runtime estimate, and `token_budget: 0`.
2. **Experiment Reviewer** — required **deterministic gate** pre-review (structural checklist: decision impact, required fields, distinct expected outcomes, data existence/allowlist) and separate **post-run** interpretation. Rejects weak or incomplete proposals.
3. **Local Experiment Runner** — executes approved **typed** kinds only (no shell). Long jobs may run in the background with zero model calls.

Wave 4 Experiment Architect plans remain design-only and are **not** auto-executed.

For Cursor/agent invocation (compact JSON create + one-shot pipeline), see [EXPERIMENTS-AGENTS.md](EXPERIMENTS-AGENTS.md).

## Package root vs workspace root

You can run experiment commands from **any project directory** (for example a Carla research repo).

| Root | How it is found | Contents |
|------|-----------------|----------|
| **package_root** | Installed `research_forge` tree (wheel ships `config/` + `schemas/`), or `RF_PACKAGE_ROOT` | `config/`, `schemas/` |
| **workspace_root** | `--workspace`, else **`RF_WORKSPACE`** (preferred), else legacy `RF_RUN_DIR`, else **cwd** | `.research-forge/data`, `.research-forge/experiments`, ledger |

Prefer `RF_WORKSPACE` for experiments. `RF_RUN_DIR` also redirects experiment artifacts (shared with Wave run dirs) — avoid setting it unless you intend that.

Do **not** paste prompt text (`PS C:\...>`) into PowerShell — only type the command itself. Use the full `EXP-…` id printed by `create`, not the placeholder `EXP-...`.

Editable install (`pip install -e .` from the research-forge checkout) finds assets by walking up from the package. A normal wheel install includes `config/` and `schemas/` beside the package. If discovery still fails, set:

```powershell
$env:RF_PACKAGE_ROOT = "C:\Users\WZ69B7\Downloads\ai_agents\research-forge"
```

## Supported kinds

| Kind | Purpose |
|------|---------|
| `dataset_profile` | CSV/JSONL row/column/missing/numeric summaries |
| `group_comparison` | Unadjusted descriptive group means for one numeric metric |
| `python_unittest_benchmark` | Repeated local `unittest` discovery (not a secure sandbox) |

## PowerShell workflow (Windows)

```powershell
# cd into YOUR project (data lives here), not necessarily the research-forge checkout
cd W:\carlaStuff\carla\RNDCR_191158_Research-Driving-Simulator

New-Item -ItemType Directory -Force -Path .research-forge\data | Out-Null
@"
group,value
A,10
A,12
B,18
B,20
"@ | Set-Content -Encoding utf8 .research-forge\data\example.csv

# Optional if config is not found automatically:
# $env:RF_PACKAGE_ROOT = "C:\Users\WZ69B7\Downloads\ai_agents\research-forge"

py -3.10 -m research_forge experiment create `
  --title "Compare group means" `
  --question "Does group B have a higher observed mean than group A?" `
  --why-run "Decide whether a stronger follow-up is worth designing." `
  --hypothesis "Group B has a higher observed value in the available file." `
  --expected-support "Group B has the largest mean with a meaningful gap." `
  --expected-reject "Group B does not have the largest mean." `
  --expected-inconclusive "Too few usable rows or only one valid group." `
  --decision-impact "Use only to decide whether to design a stronger follow-up." `
  --kind group_comparison `
  --data .research-forge/data/example.csv `
  --group-column group `
  --metric-column value

# Copy the printed experiment_id (e.g. EXP-A1B2C3D4E5F6), then:
py -3.10 -m research_forge experiment pre-review EXP-A1B2C3D4E5F6
py -3.10 -m research_forge experiment run EXP-A1B2C3D4E5F6 --approve
py -3.10 -m research_forge experiment post-review EXP-A1B2C3D4E5F6

# Or one process after create:
# py -3.10 -m research_forge experiment pipeline EXP-A1B2C3D4E5F6 --approve --compact
```

## Required workflow (bash)

```bash
mkdir -p .research-forge/data
# create a real local data file, then:

research-forge experiment create \
  --title "Compare group means" \
  --question "Does group B have a higher observed mean than group A?" \
  --why-run "Decide whether a stronger controlled follow-up is worth designing." \
  --hypothesis "Group B has a higher observed value in the available file." \
  --expected-support "Group B has the largest mean with a meaningful observed gap." \
  --expected-reject "Group B does not have the largest mean." \
  --expected-inconclusive "Too few usable rows or only one valid group." \
  --decision-impact "Use only to decide whether to design a stronger follow-up." \
  --kind group_comparison \
  --data .research-forge/data/example.csv \
  --group-column group \
  --metric-column value

research-forge experiment pre-review EXP-XXXXXXXXXXXX
research-forge experiment run EXP-XXXXXXXXXXXX --approve
research-forge experiment post-review EXP-XXXXXXXXXXXX
research-forge experiment status EXP-XXXXXXXXXXXX
research-forge experiment list
```

## Approvals

| Flag | When required |
|------|----------------|
| `--approve` | Always required to run |
| `--approve-long` | Estimate &gt; 300s, repetitions &gt; 5, **or always when using `--background`** |
| `--approve-code-execution` | `python_unittest_benchmark` |
| `--approve-external-data` | Input path outside workspace data allowlist |

Pre-review must produce `pre-review.json` with verdict `PASS` before run. Never bypass it.

## Long / background jobs

```bash
research-forge experiment run EXP-ID --approve --approve-long --background
research-forge experiment status EXP-ID
research-forge experiment post-review EXP-ID
```

Background always requires `--approve-long` even if the runtime estimate is short. Background workers perform **no model calls**; they write `status.json` / `result.json` only. They inherit `RF_WORKSPACE` and `RF_PACKAGE_ROOT`.

## Code execution warning

`python_unittest_benchmark` may execute arbitrary project test code. This is **not a secure sandbox** and does not block network access by the tested code. Prefer an OS/container sandbox on trusted repos only.

## Interpretation boundary

Local output is **`LOCAL_OBSERVATION`**, not a research conclusion. Post-review reports descriptive outcomes and limitations. A human or Research Auditor decides transfer to the broader question.

Local dataset kinds load the full CSV/JSONL into memory. Prefer modest files for exploratory checks; large production dumps belong in a designed follow-up study.

## Decision

Authorized by **RF-DEC-14** = `local_token_free_experiments_human_gated`.
