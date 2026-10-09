# ANX-4 execution contract and ownership

Authority: approved roadmap 2026-10-09-agentnexus-roadmap.md. Implementation starts after ANX-0 merge. No paid calls or secret mutations. TDD, disjoint worktrees, integrate serially, exact-head review and CI.

## Shared interfaces (version 1)

Preserve existing Invocation positional fields and engine compatibility. Add deadline (absolute epoch), credential_ref, catalog_id/policy_id, provider_options and maximum transport retries (0..2). TokenUsage distinguishes optional input/output/total/cached/reasoning tokens and optional cost_usd, evidence_status in unknown/estimated/reported/reconciled. Explicit known-zero usage is represented with reported or estimated evidence; missing cost is None. InvocationResult adds provider_request_id, finish_reason, usage evidence and cancellation status. Provider capabilities explicitly declare tools, JSON schema, streaming and cancellation; default unsupported.

Typed transport failures carry category, remote_acceptance (rejected/unknown), retryable, provider_request_id; sanitized messages only. One transport owner bounds retries to original deadline, retries only confirmed rejected transient responses, never blindly replays unknown acceptance. Cancellation defaults unsupported/unknown. Native adapters preserve tool IDs and cached/reasoning token categories.

SecretBroker metadata is SQLite with opaque ref, service/owner, scope, generation and revocation; raw values only in an approved OS backend. SecretUseGrant names caller, task/run, ref, purpose, expiration and effective grant. Add secret_use to six-layer capability intersection; absent field denies. Adapter-only use receives values within an authorized operation; no default raw-get API, model/worker values, ambient env fallback or plaintext fallback. Backend validation rejects fail/null/plaintext backends. Explicit developer environment override, if supported, requires a separately scoped flag and grant; supervised defaults disable it. Vault delete/rotation failure preserves metadata and reports sanitized failure.

ModelResolver(catalog,policy).explain(role, requirements, environment, override=None) returns eligible/excluded candidate IDs with reasons, selected alias, policy/catalog hashes. Requirements cover risk/privacy/features/context/output/deadline. Credential availability is reference-based, never value-based. Unknown quality is ineligible for automatic cheaper selection; qualifying held-out evidence counts distinct tasks, Wilson lower bound and baseline successful-task cost. Manual reviewed baseline remains compatible through translated policy. CatalogStore publishes immutable candidate snapshots, explicit activation and active pins; refresh never activates. Runs retain snapshots and compatible source hashes.

## Ownership

- Integrator: providers/base.py contract freeze; contracts.py/schema/registry grants; nexus_cli.py; engine_adapters.py/supervisor.py/native engine integration; shared config/dependencies/CI/docs/canonical projections; deterministic utilities.
- Worker A: secret_broker.py; providers/http.py authenticated transport only (preserve protected public reader); providers/openai_compat.py; providers/anthropic.py; providers/registry.py; provider diagnostics; corresponding new tests. Existing DC native provider compatibility translated by integrator.
- Worker B: model_resolver.py; model_catalog.py; evaluation.py; corresponding tests and proposed catalog/policy fixtures. Integrator owns production catalog.yaml/agents.yaml.

Tests: explicit zero vs missing usage, tool/stream conformance, no unknown retry, bounded deadline, missing/locked/revoked secret, failure-preserving delete/rotation, denied caller/ref/expiry, native compatibility, feature/privacy/context exclusion, override denial, pinned catalog activation, no unqualified cheap routing. Benchmark fixtures are offline harness measurements. Utilities report successful-task cost including failures/repairs and unknown costs without assuming zero. No percentage-saving promise.

## Integration gate

All offline regression/native/projection checks, independent source review and Linux/macOS CI; reviewed PR closes #5/#6/#7/#8. ANX-5 starts only after merge. Wave0 model usage receives explicit accounting; current retrieval-only Wave1 retains known zero.
