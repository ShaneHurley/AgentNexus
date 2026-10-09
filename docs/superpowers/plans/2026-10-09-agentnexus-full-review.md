# Full review of AgentNexus Phase 1–3 changes

Review date: 2026-10-09. Baseline: `f586a2e`; reviewed the current source diff and newly added implementation/tests. The working tree also contains unrelated historical requests, teamwork material and existing runtime artifacts; those were preserved rather than attributed to this implementation or reset.

## Verdict

The implementation needed corrections. Existing green tests missed reproducible security, recovery, accounting and interface failures. The defects identified below have been repaired and covered by negative regressions. Independent reviewers rechecked the fixes and found no remaining blocking defects in the Phase 1–3 implementation delta. A separate pre-existing launcher change has the unresolved dependency-integrity finding below. This is evidence of improved behavior, not proof that software is universally bug-free.

## Findings and fixes

| Priority | Finding | Resolution |
|---|---|---|
| P1 | RF call-cache identities omitted search query/page/filter and read locator, allowing different requests to reuse evidence | Fingerprint actual normalized request arguments in addition to authorization; distinct query/page/locator regressions |
| P1 | Cached RF calls bypassed current authorization and restored earlier budget snapshots | Reauthorize cached access and restore the latest durable aggregate budget; spend stays monotonic |
| P1 | RF runtime directories, journal and execution lock could follow workspace symlinks | Refuse symlink runtime components; use a no-follow, nonreentrant execution lock; close journal connections |
| P1 | Worker snapshot could read outside the workspace if an ancestor was replaced with a symlink between inspection and open | Read through descriptor-bound traversal; an adversarial ancestor swap cannot copy outside content |
| P1 | A precreated child could execute after its parent became blocked or uncertain | Check current ancestors transactionally before reserving/dispatching |
| P1 | A crash while importing legacy execution left a runnable imported row | Atomically create partial/provenance/reconciliation state and uncertain exposure; incomplete imports cannot dispatch |
| P1 | Supervised GUI live execution did not carry explicit live authorization | Confirm before dispatch and include explicit mode; failed backend preparation cannot silently continue |
| P1 inherited | RF live reader accepted private network endpoints and followed unchecked redirects | New credential-free public retrieval transport checks every endpoint and redirect, pins numeric addresses, retains TLS hostname validation, bounds DNS workers/body/deadline and shuts down stalled sockets |
| P2 | Native DC resume did not pin per-role configs and output schemas | Include role/schema hashes in native execution identity |
| P2 | A known stale overwrite hash denial became an unresolved side effect | Check overwrite preconditions before recording dispatch; ordinary denial leaves no pending exposure |
| P2 | RF final composition could return success after its deadline | Check resource/deadline boundary before accepting final output |
| P2 | Live RF clarification pauses consumed the whole model-token grant despite no model invocation | Current HTTP-only Wave 1 adapters report known zero model tokens; future model stages must supply receipts |
| P2 | Cancellation racing native completion remained pending forever | A known terminal native result can acknowledge termination after usage settlement and descendant checks |
| P2 | Confirmed settlement could use an unknown usage category and crash accounting | Reject incompatible outcome/category combinations while retaining uncertain reservations |
| P2 | Session migration checksums were recorded but not verified | Verify current migration history; genuine v1 without a ledger still migrates with backup |
| P2 | Repeated imports could leave phantom runnable rows; native creation could orphan another run before alias persistence | Serialize/idempotently reuse imports; use the shared UUID for native DC creation and verify pinned identity before reuse |
| P2 | GUI RF ignored configured workspace; DC cached a project-bound session across different projects | Use the configured RF workspace and select an automatic session per project; explicit session restrictions remain |
| P2 | Concurrent GUI starts could read another request's session or mutable global provider | Lock session selection briefly and use a request-local session/provider for dispatch |
| P2 | A supervised live resume was classified as simulated using parser defaults | Map exits using persisted live state; supervised mock results remain SIMULATED |
| P2 | Docs described completed supervisor/session work as unimplemented and implied native RF root invocation worked | Correct authorities, commands and compatibility details; native RF still requires its package working directory |

The inherited public-reader transport fix was added to this review because permission and public-retrieval claims otherwise remained incomplete. Offline cases cover private/link-local/loopback URLs, userinfo/non-HTTP URLs, private redirects, numeric endpoint pinning, TLS original hostname, oversized bodies, DNS stalls and slow headers. No live requests were needed.

## Verification

Final results, rerun after installing the genuine compiled `rpds-py` dependency:

- Shared core, DC, all RF module tests and IDE/bridge: **566 passed, 19 subtests**, 66.47 seconds, exit 0.
- Complete dashboard suite, including localhost HTTP tests: **62 passed**, 9.01 seconds, exit 0.
- **628 distinct pytest tests plus 19 subtests; no module exclusions.**
- Separate DC unittest discovery: **121 passed**; native validation: `ok=true`, no errors.
- Canonical DC import and IDE synchronization: passed.
- Installed CLI mock smoke (sessions, RF/DC runs/resume and backup): passed.
- JavaScript syntax, workflow YAML parsing and scoped source whitespace checks: passed.

Checks include shared core, retained DC engine, RF modules, bridge and every dashboard test; no module exclusions. The formerly excluded Wave 2 collection issue was a test import-path omission, resolved by adding the RF source root to PYTHONPATH. Hatchling was installed in the project virtual environment to execute the wheel-assets test. This validates individual later-wave modules, not a composed Waves 2–6 runtime.

DC unittest discovery, native validation, canonical agent imports, generated projections, CLI mock smoke, JavaScript syntax, CI YAML and source whitespace were checked separately. Mock/synthetic results remain labeled. Regression tests exercised the unsafe behavior before the corresponding fixes.

Engineering source edits were applied through the existing PolicyGateway under bridge-approved run `5d6d4f73-0353-459b-983c-337956304043`, plan hash `834beaab3e0e29c08b0a44f8e1e58ea71a3ebf29f8de380987bf128184cf1d73`. Existing user edits/history were retained. No commit, push, paid provider call or credential operation was performed.

## Remaining finding outside the Phase 1–3 implementation

**P1 — `start_mac.sh` suppresses dependency-installation errors and can manufacture an incompatible dependency.** Lines 70–85 ignore pip failures; lines 107–124 copy packages from unrelated environments; lines 126–213 write an unofficial `rpds` implementation. Its `HashTrieMap` permits in-place assignment, whereas the supported library rejects it. The project environment was using this shim during the initial test run. Installing the genuine `rpds-py` wheel restored the supported compiled implementation; the final suites were rerun against it. The launcher itself was preserved as a pre-existing user edit and can recreate the problem on a future failed installation. Repair it before treating launcher-based installation as validated: stop on installation failure, install declared dependencies through pip, and remove copied-package/shim fallbacks. Use QUICKSTART’s explicit package installation meanwhile.

## Practical limits

- Real Docker daemon/image execution and host-crash cleanup were not exercised; controlled worker/process tests are offline.
- Real provider cancellation, billing reconciliation, streaming behavior and model quality/cost routing remain unmeasured. Unknown outcomes retain exposure and cannot automatically replay.
- Incompatible policy changes and incomplete imported runs require explicit reconciliation/new execution; the system does not promise exactly-once remote actions.
- Conventional standalone wheel execution is not a substitute for the complete repository capability sources. The local editable-checkout installation remains the supported setup.
- The native RF CLI still locates configuration by working directory; run it from its package directory or use the supervised frontend for a separate workspace.
