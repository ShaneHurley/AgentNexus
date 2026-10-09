# Phase 3 implementation plan and review

> Execute inline using superpowers:executing-plans, with test-first changes and verification before completion.

Goal: durable sessions, recovery, cancellation and accounting while retaining DC and RF engines.
Architecture: shared supervision owns lifecycle; existing SQLite DC state and RF artifacts retain workflow decisions. Unknown external outcomes block replay and retain exposure. Single-user local macOS first; portable interfaces.
Spec: user-approved AgentNexus architecture assessment, Phase 3. No live calls, seventh orchestrator or memory work.

Review verdict: proceed with the design, with explicit reconciliation and acknowledgment gates. Time-based lease expiry alone cannot authorize a second local executor: use an OS-owned process lock and durable state. A remote call timeout is not proof of cancellation or zero cost. RF's current non-paused resume must not restart charter.

## First increment: recovery safety

- [x] Add shared `RunLock(directory, key)` and `RunBusy` / `ReconciliationRequired`. The lock is reentrant within one thread, mutually exclusive across processes, and automatically released on process death. Hash keys; reject symlink lock files. Test contention and forced worker death.
- [x] DC: hold the process lock over execution; enforce config, pricing, live mode, provider class, prompt and workflow pins. Refuse outstanding reservations before replay. Preserve live provider failure reservations, mark RECONCILIATION_REQUIRED, stop repair dispatch, and expose uncertain exposure separately from recorded spend.
- [x] RF: UUID per new run; allow resume only at acknowledged clarification pause. Deny uncheckpointed/finished resumes without altering phase or launching tools. Mock report determinism remains; run-specific packets legitimately differ.
- [x] Bridge: report successful approval as acknowledged action; map RECONCILIATION_REQUIRED and CANCEL_REQUESTED as blocked. Do not infer a completed run from approval.
- [x] Run new adversarial tests plus relevant DC/RF/core/bridge regressions. Update root operator docs and CI.

## Completed increments for full Phase 3

- [x] Shared session SQLite schema with UUIDs, engine aliases, immutable effective configuration snapshot, artifact manifests, parent accounting and migration backup/newer-schema refusal. Four `agent-nexus` frontend commands use the supervisor, never a write bypass.
- [x] Adapt DC/RF transition and external-side-effect checkpoints into the supervisor. Persist RF reservations and unique call IDs before launch; reconcile interrupted tool calls before replay. Import legacy runs with completeness/provenance; uncheckpointed RF runs require new execution.
- [x] Cancellation intent blocks new dispatch, propagates to descendants, records worker acknowledgment and confirmed process/container termination. Unsupported provider cancellation retains remote uncertainty. GUI/CLI/bridge expose the same authority.
- [x] Kill/restart injection at every external boundary, duplicate concurrent resume, crash-persistent budgets, changed config, approved-write replay, cancellation and root/descendant accounting acceptance suite.

The completed implementation retains conservative reconciliation: uncertain external operations cannot automatically replay. It does not claim exactly-once external execution or automatic provider reconciliation.


## Verification of recovery-safety increment

Test-first negative coverage exercised the previous unsafe behavior, then passed after the guards. Adversarial follow-up caught and repaired swallowed reconciliation in diagnosis and incomplete response accounting.

- DC pytest: 139 passed, 19 subtests.
- Shared core + IDE tests: 89 passed (including actual process contention/SIGKILL lock release).
- RF supported offline suite: 223 passed. Existing Wave 2 collection dependency and missing wheel-builder environment tests remain excluded; this is not an end-to-end Waves 2–6 claim.
- GUI adapter regression tests: 7 passed; HTTP socket-binding test excluded in this sandbox.
- Total: 458 distinct passing pytest tests, plus 19 subtests.
- Required DC unittest discovery: 121 passed; DC validate: no errors.
- Canonical DC import and IDE projection synchronization: passed.
- Scoped diff whitespace check: passed. Pre-existing unrelated shared-package metadata whitespace was not changed.
- No paid/live provider calls or real container execution.

Writes were scoped and applied through DC PolicyGateway under bridge-approved run `c3f6dea5-ea74-4d35-a8cc-1c70fee7600f`, plan hash `22dd8686b1215c6073d3767e9cac470aa2b29bb97d5dac5b1c83380ece9f3381`. Pre-existing working-tree edits were retained. No commit or history rewrite.

The first increment was completed before the final integration below.


## Phase 3 completion — 2026-10-09

All four increment groups are implemented. Shared execution schema v2 and DC schema v6 preserve migration backups and reject newer schemas. The CLI, optional supervised bridge path and dashboard adapters share durable authoritative state. RF Wave 1 journals persist call reservations/results/budget checkpoints and resume accepted stages. DC records pre-side-effect receipts and reconciles approved writes by their final hash. Unreceipted provider settlements and unknown calls block replay.

Final adversarial corrections: deny child delegation from blocked/uncertain parents or under changed pins; serialize native dispatch per root; require remaining root headroom to cover the native remaining grant before dispatch; recover a settled-but-uncheckpointed supervisor segment without engine replay; preserve imported legacy costs/unknown exposure; acknowledge cancellation received during final RF composition. Full native grants are conservative and can block siblings despite some residual budget. This avoids widening native pinned limits mid-run.

Fresh verification:

- Combined scoped offline suite: **531 passed, 19 subtests**, one HTTP test deselected in that invocation.
- Separate GUI/bridge invocation including the HTTP test: **33 passed** (overlapping interface tests; not added wholesale to the combined count).
- DC unittest discovery: **121 passed**; native validation: no errors.
- Canonical DC import and IDE synchronization: passed.
- Installed `agent-nexus` CLI smoke: new/sessions, completed mock RF run/resume, mock DC run and consistent backup passed.
- Scoped source diff whitespace check: passed.

The RF suite excludes the existing Wave 2 collection dependency and wheel-build-environment test. Supported integration remains Wave 1. Docker process cancellation is exercised with a controlled client and failed-cleanup tests; a real Docker daemon/image smoke remains unperformed. No live provider calls, paid evaluations, provider cancellation proof or reported-cost reconciliation measurements were performed. Those operational evaluations remain explicit rather than inferred from mocks.

Final engineering writes used PolicyGateway under bridge-approved run `5d6d4f73-0353-459b-983c-337956304043`, plan hash `834beaab3e0e29c08b0a44f8e1e58ea71a3ebf29f8de380987bf128184cf1d73`. Existing user changes and historical artifacts are retained. No commit, history rewrite or automatic credential operation.


## Full adversarial review follow-up — 2026-10-09

See [full review](2026-10-09-agentnexus-full-review.md) for reproduced defects, audited corrections and remaining operational limits. Fresh complete regression runs against the genuine `rpds-py` dependency passed **628 distinct tests plus 19 subtests**, with no RF module exclusions or dashboard HTTP exclusions. The earlier results above are historical verification of the first completion, not the current coverage limit. Individual later-wave tests do not establish a composed Waves 2–6 runtime. A separate pre-existing macOS launcher dependency/shim defect remains documented; its edits were preserved.
