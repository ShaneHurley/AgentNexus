# Implementation status

## Current: `0.7.0+experiments`

- Waves 0–6 mock-by-default research stack (prior work).
- **Local experiment subsystem** (this release): Creator, adversarial Pre-Reviewer, token-free Runner, Post-Reviewer.
- See [docs/EXPERIMENTS.md](EXPERIMENTS.md). Decision **RF-DEC-14** = `local_token_free_experiments_human_gated`.

## Required before live research use

1. Resolve remaining §21 decisions and approve the §22 implementation handoff.
2. Perform security review of filesystem, URI, credential, and network boundaries — use [security-review-checklist.md](./security-review-checklist.md) (includes future GitHub URL/token surfaces).
3. Add authorized live adapters behind the Policy Gateway.
4. Prefer OS/container sandbox for `python_unittest_benchmark` — optional experiment: set `RF_EXPERIMENT_SANDBOX=docker` (see [EXPERIMENTS.md](EXPERIMENTS.md) / kinds runner). Default remains in-process and is **not** a secure sandbox.

## Shipped gates (this pass)

- Wave 1 durable resume/status CLI (`runs/wave1/.../state.json`).
- Optional `PublicGitHubCodeRepositoryAdapter` (mock remains default).
- Copilot bridge experiment notes: [COPILOT_BRIDGE_EXPERIMENT.md](./COPILOT_BRIDGE_EXPERIMENT.md).

## Known limitations

- Mock sources must never be represented as real research.
- Local experiment code execution is **not** a secure sandbox.
- Experiment results are `LOCAL_OBSERVATION` only until a human/auditor promotes transfer.
- Cost uses configured abstract units rather than provider billing.
