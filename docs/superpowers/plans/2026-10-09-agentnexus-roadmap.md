# AgentNexus implementation roadmap (ANX)

Goal: deliver the approved local macOS-first architecture, optimizing cost per successful task without weakening permissions or quality. Python >=3.10; six user-facing orchestrators; engineering writes through PolicyGateway; personal writes require visible diff and confirmation.

## Delivery contract
One epic active at a time. Two implementation workers in separate worktrees with disjoint ownership; integration owner freezes shared interfaces and owns shared schema, registry, dependencies, CLI and docs. Each epic has a GitHub parent issue, child tasks and an integration PR. Independent review and green CI precede merge. Preserve local history; do not publish private runtime state or rewrite history. Current execution scope is ANX-0, ANX-4 and ANX-5; ANX-6/7 and later RF waves remain backlog. No paid calls without a separate budget approval.

## ANX-0 — Harden and publish baseline
Worker A: launcher/dependency integrity and authenticated dashboard access, Host/Origin validation and token-safe logs. Worker B: redacted publication inventory and CI/repository checks. Integration: uv workspace/lock, consistent local recovery backup, curated source branch from origin/main, roadmap and GitHub tracking. Remove environments/runtime databases from Git index while retaining local copies. Source-name policy exceptions cover explicitly approved implementation files only, never credential data.
Gate: fresh locked installation; positive/negative HTTP tests; complete offline suites; canonical import/sync; redacted source/history scan; independent review; green baseline PR CI.

## ANX-4 — Providers, secrets, routing and efficiency
4.1 Freeze shared invocation/tool/stream/capability/usage/error/cancellation interfaces and credential-use authorization. Known zero differs from unknown. Pin model catalogs/policy; record selection candidate set and exclusions. Sanitized benchmarks pin inputs/policy and count failures, repairs and escalation.
4.2 Worker A owns SecretBroker and provider adapters. Validate macOS Keychain backend, scope credential use to role/task/operation, retain references in metadata, fail closed when locked/unavailable/revoked, preserve errors on deletion/rotation, disable implicit supervised environment fallback. Consolidate OpenAI-compatible/OpenRouter/Anthropic; preserve Gemini/local/bridge compatibility explicitly.
Worker B owns ModelResolver and evaluation tools. Filter role/risk/privacy/credential/tools/schema/context/deadline eligibility before price. Reviewed catalog activation only; existing runs keep pins. Unknown quality never enables automatic cheap routing. User overrides cannot broaden eligibility.
4.3 Integrate CLI `models inspect`, `models explain`, `eval`; adapt DC/RF lifecycle and usage; remove IDE family mandates and regenerate projections. One retry owner, <=2 transport retries under original deadline/reservation; unknown acceptance blocks replay; <=1 quality repair and <=1 configured escalation. Preserve OpenRouter parameter/privacy restrictions through fallback.
Utilities: usage_report, AST repo_outline (no imports/execution), bounded context_pack with protected fields, tool_result_reduce retaining sanitized originals, evidence_extract using existing protected reader, efficiency_eval. Prefer stdlib; evaluate compatible tokenizers and Trafilatura without network bypass.
Gate: offline contract tests, credential/capability denials, unknown-cost reservation preservation, pins on resume, schema/stream/tool semantics, sanitized benchmark explanations. Paid smoke is separately authorized: $10 total, <=$1 per task, concurrency one; no production cheap-routing qualification inferred.

## ANX-5 — Memory and personal data
5.1 Freeze stable store/record IDs, provenance, verification/sensitivity, revisions, relationships, fingerprints, promotion and grants. Separate project-per-folder, Research, Daily and Shared SQLite stores; execution state separate.
5.2 Worker A owns migrations/writer serialization/FTS5/freshness/isolation and runtime-owned draft ingestion. Worker B owns non-mutating personal previews, schema validation, lineage, reviewed promotion and portability/deletion.
Automatically store authorized evidence as unverified drafts; accepted facts, personal changes and Shared promotion require confirmation. Default factual search excludes draft/stale/conflicting records; explicit inspection allowed. Max eight records/4,000-token evidence allocation, stable expansion references; protected intent/authority outside evidence allocation. FTS5 first; embeddings gated by measured misses.
Transactional migrations, backup before upgrade, local WAL/bounded busy waits, refuse unsupported newer schemas; application-validated cross-store links. Preserve authoritative personal files initially, reversible import. Deletion immediately excludes retrieval/FTS and invalidates derived contexts/caches, schedules purge, discloses backup retention. Accepted knowledge persists until deleted; caches 30 days; raw-run retention explicitly recorded at setup. Memory never stores raw secrets.
CLI `memory`: search/inspect/draft/accept/promote/export/import/backup/delete/doctor with scoped grants and confirmation for mutations.
Gate: project isolation, restart identity/history, stale facts, provenance/promotions, migration/refusal, backup/restore relationships, deletion/invalidation, non-mutating personal previews.

## ANX-6 — Handoffs, context and dashboard (backlog)
Worker A owns bounded Code↔Research handoffs, acknowledgments, KEEP/STEER/STOP and descendant cancellation/accounting. Worker B owns typed compaction, evidence expansion, validated profiles, exact read-only caching and authoritative existing dashboard integration.
Research cannot acquire implementation authority. Leaf workers, <=2 active children/root, <=2 orchestration levels, duplicate/cycle prevention. Handoffs carry task/parent/objective/scope/evidence/artifacts/acceptance/deadline/reservation/grant/pins. Five compactions preserve intent/permissions/approvals/budgets/pending-call relationships; narrative never supplies authority. Cache normalized request/dependencies/principal/policy/model/prompt/schema; reauthorize hits, invalidate on revocation/deletion/change. GUI/CLI agree, including requested vs confirmed cancellation and unknown outcomes.

## ANX-7 — Measured optimizations and capability governance (backlog)
Evaluate deterministic tools/context selection/provider prompt caching/routing against held-out tasks and strong single-agent baseline. Add only justified skills/leaf specialists, with parent/tools/budget/output contracts; resident skills <=8, six orchestrators. Candidate specialist responsibilities: provider conformance, retrieval quality, migration/recovery, performance/cost. Hooks at dispatch, tool-result, checkpoint/compaction and publication are deterministic; gateways authoritative; no automatic model calls. Semantic compression/LLMLingua and hybrid retrieval remain optional evaluated flags; never compress authority fields lossily. No automatic skill/model activation.
Automatic low-cost eligibility: >=100 held-out independent tasks per role/class with repeated clustered runs, 95% Wilson lower bound >=90%, no critical violations and lower successful-task cost than baseline. High-consequence routing separately qualifies. Report tokens/cost/repairs/escalation/latency across entire task; mock harness results are not model-quality evidence.

## Later research backlog
RF Waves 2–6 are separate sequential epics only after ANX-6; module tests do not establish composition. Every wave adopts shared grants/lifecycle/accounting/artifact contracts before next wave.

## Acceptance and operations
Focused negative tests, DC unittest/validation, canonical/projection checks, clean Linux/macOS installation, schema rollback/backups, crash/duplicate/symlink/stale-pin/cancellation/unknown-cost tests and accurate docs per epic. Hypothesis tests state sequences; xdist only independent temporary stores/ports. Real Docker smoke uses pinned reviewed image; no claim of operational validation from mocks. Provider cancellation/billing/model quality stay unmeasured until separately approved live evaluation. Independently reversible activation settings/snapshots; never silently downgrade schema or resume with new policy.

## GitHub tracking

- [ANX-0: Harden and publish baseline](https://github.com/ShaneHurley/AgentNexus/issues/2)
- [ANX-4: Shared providers, secrets and measured routing](https://github.com/ShaneHurley/AgentNexus/issues/5)
- [ANX-5: Isolated memory and personal data](https://github.com/ShaneHurley/AgentNexus/issues/9)
- [ANX-6: Handoffs, context and dashboard](https://github.com/ShaneHurley/AgentNexus/issues/12)
- [ANX-7: Measured efficiency and capability governance](https://github.com/ShaneHurley/AgentNexus/issues/15)

## Implementation status (2026-10-10)
ANX-0 merged PR #18. ANX-4 merged PR #19 after independent review and updated Linux/macOS CI, including the supervised RF search adapter identity regression. ANX-5 implementation and verification use the [frozen contract](2026-10-10-anx5-memory.md). ANX-6/7 remain backlog; no paid calls or automatic model/skill activation.
