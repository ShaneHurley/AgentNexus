# Wave 1 mock happy path (Research Forge)

Short onboarding path for the **mock-by-default** Wave 1 vertical slice — no live providers, no network research.

## Prerequisites

- Python 3.10+
- From `agents/research/research-forge/`: `pip install -e ".[dev]"`

## Steps

1. **Doctor** — config and fixtures load cleanly:

   ```bash
   python -m research_forge doctor
   ```

2. **Wave 0 gate** (optional sanity):

   ```bash
   python -m research_forge validate --gate wave_0
   ```

3. **Wave 1 mock run** — uses bundled fixture request:

   ```bash
   python -m research_forge run --wave1 --request fixtures/wave1_e2e_request.json
   ```

   Expect JSON with `"ok": true`. If the clarifier pauses, state is persisted under `runs/wave1/<run_id>/state.json`.

4. **Status / resume** (when paused):

   ```bash
   python -m research_forge status <run_id>
   python -m research_forge resume <run_id> -a CLQ-001=... -a CLQ-002=... -a CLQ-003=...
   ```

5. **Baseline comparison** (optional):

   ```bash
   python -m research_forge baseline
   ```

## What is *not* in this path

- Live providers (`--live`) until the decision gate and [security-review-checklist.md](../../agents/research/research-forge/docs/security-review-checklist.md) are signed off.
- Treating mock sources as real literature.
- Remote GitHub SaaS as the only work surface (Daily Coder still prefers a local `--repo`; optional `daily-coder github clone` is gated).
- Live scholarly/patent/code adapters — blocked until [security-review-checklist.md](../../agents/research/research-forge/docs/security-review-checklist.md) sign-off.

## See also

- [research-forge/docs/wave1-release.md](../../agents/research/research-forge/docs/wave1-release.md)
- [Documentation hub](../README.md)
