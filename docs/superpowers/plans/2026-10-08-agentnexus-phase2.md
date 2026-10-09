# AgentNexus Phase 2 implementation record

Authority: user-approved six-phase architecture roadmap and instruction to complete Phase 2 as appropriate. Preserve pre-existing working-tree changes; no paid calls, credential tests, Git-history changes, or later-phase implementation.

1. Shared contract schemas, six-layer grants, owned source adapters, immutable snapshot compilation, progressive discovery and atomic constrained activation/rollback.
2. Pin snapshots and enforce grants in DC dispatch/skills/tools and RF dispatch/tools. Reject unsupported memory/delegation, mismatched recovery, unknown roles/callers and workspace escapes.
3. Real Docker execution backend; callbacks cannot impersonate isolation. Restrict environment, mounts, images, network, resources and cleanup. Route RF Python experiments and DC synchronous verification through it.
4. Repair prerequisite review findings: ambiguous reader target, missing live provenance, substring negation acceptance, and false Daily resume acknowledgment.
5. Run negative and existing offline tests, update reference/quickstart/CI, preserve unrelated files.

Implementation writes were staged and executed through DC PolicyGateway with bridge-recorded approvals and expected file hashes. Audit runs: `635caf4d-e6e2-42d3-91ad-26c8ff678531` and `1a2ec38e-10bd-465a-9764-e84d628342be`.

Decisions: incomplete later-wave RF manifests are inactive with explicit warnings; no inferred permissions. Live evidence without a reviewed entailment checker is rejected. Test execution uses synchronous isolated workers; detached host jobs remain unavailable. The Docker daemon is stopped, so live container validation is an outstanding environmental check. No automatic snapshot activation or provider calls occurred.

Validation is recorded in the final implementation report; tests exercise real runtime gateways and mocked Docker transport, not a live multi-wave research pipeline.


Final offline checks: shared core 70 passed; DC 129 passed plus 19 subtests; RF 217 passed (pre-existing Wave 2 collection and wheel-build dependency blockers excluded); GUI resume adapters/status 7 passed (HTTP server binding class excluded). DC unittest discovery: 121 passed. Canonical DC import, IDE projection synchronization, DC validation, workflow YAML parsing and scoped diff whitespace checks passed. Actual `ide-bridge daily-coder run --provider mock` smoke returned SIMULATED with a registry pin and expected exit 1. No paid provider calls occurred.

The local audit SQLite file briefly acquired version 5 metadata before its added column during staged implementation. A consistent backup was taken, the known additive column was reconciled and the existing row count was preserved; the bridge smoke then passed. Normal schema 4-to-5 migration and rejection of newer schemas are covered by regression tests.

Actual Docker execution is unverified because the daemon is stopped and no reviewed image was provisioned. RF live semantic acceptance remains denied without an explicitly injected reviewed checker. Source metadata with unresolved later-wave RF schemas remains inactive. The existing root RF CLI decision gate blocker is unchanged; Wave 1 execution is validated through its runtime API tests.
