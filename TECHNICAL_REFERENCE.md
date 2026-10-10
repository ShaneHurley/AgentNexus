# AgentNexus technical reference

This document describes the current local architecture and the Phase 1–3 trust-boundary and lifecycle changes. It is an implementation reference, not a claim that all planned runtime consolidation is complete.

The GitHub Actions workflow at `.github/workflows/agentnexus.yml` runs the shared-contract, isolated-runner, runtime-grant, retrieval, policy, execution-boundary, adapter-status, and generated-agent checks.

## Current authorities

- IDE roster and generated projections: `agents/ide/MANIFEST.yml`, canonical agents, and the import/synchronization scripts. Edit canonical or source-of-truth files, then regenerate projections.
- Daily Coder execution: `agents/coding/daily-coder-ecosystem/config`, role metadata, `ToolBroker`, and `PolicyGateway`.
- Research Forge Wave 1: `agents/research/research-forge/config`, the Wave 1 orchestrator, policy gateway, and its persisted run artifacts.
- Shared capability metadata: `agents/shared/agent-core/registry.yaml`.
- Dashboard adapters: `gui/config/agents.json` and `gui/agent_dashboard/adapters`.

The six user-facing orchestrators remain `deep-research`, `research-messenger`, `plan-prep`, `use-master`, `daily-coder`, and `researcher`. Daily is a personal profile and capability set, not another orchestrator.

## Research evidence and retrieval

Live search returns provider-retrieved results or an empty result with `metadata.retrieval_status` set to `unavailable`, `failed`, `empty`, or `retrieved`. It does not use a language model or deterministic text to invent sources. Live reads use the same status vocabulary; configured test fixtures carry `synthetic: true` and status `fixture`. The Wave 1 verifier rejects fixture content in live runs. A retrieval status describes availability, while `verifier_status` and `claim_status` describe claim review; none substitutes for the others.

Source authenticity, content availability, and claim review are separate fields in the research record. Provider results remain `unverified` until authenticated; mock/test fixtures are labeled `synthetic_fixture`. Reads record whether content is available, empty, unavailable, or failed, and update the source content hash and access level. Lexical overlap is a review hint. It does not establish verified entailment. Live evidence acceptance requires explicit non-synthetic retrieval provenance, matching source identity and content hash, and a runtime-injected reviewed entailment checker. The default live verifier rejects claims without that checker. Similar wording, and quoted text embedded in a negation, cannot produce accepted findings. Offline exact-paragraph attribution remains a fixture check, not proof of real-world claim truth.

## Permission boundaries

Daily Coder routes `tests.run` and `shell.readonly` exclusively through `agent_core.isolation.DockerRunner`. A policy label or arbitrary registered callback cannot enable either operation. Configure `execution_policy.image` with a reviewed image digest; without it, execution is denied. Planned verification commands execute synchronously through PolicyGateway in this backend; detached host jobs remain disabled. Typed filesystem inspection and constrained Git inspection work without Docker.

The worker uses a disposable filtered workspace copy, mounted read-only, with no network, capabilities, elevated user, inherited credentials, privileged mode, or host socket mount. Hidden stores, secret/credential paths, symlinks and files matching the existing credential scanner are omitted. Pattern scanning is supplementary and is not a completeness claim. Resource limits constrain CPU, memory, processes and scratch space. Images are never pulled implicitly. Timeouts force removal; unconfirmed removal is an error. Results do not apply worker filesystem changes to the host. Engineering edits still pass through the approved write gateway. The local Docker daemon was stopped during implementation; transport/control tests ran offline, but real container behavior remains unverified on this machine.

RF code experiments use the same worker and require `isolated_image` in experiment configuration. Typed dataset computations and runtime-owned artifact recording retain their existing service, approval and ledger paths. Input and artifact paths must remain in the workspace. Background runtime workers receive a small explicit environment rather than the full host environment.

Research Forge uses `config/policies.yaml` role-to-tool allowlists in addition to registered tool manifests, operation restrictions, workspace-contained file targets (including resolved symlinks), confidentiality rules, and live-mode gates. Unknown roles and undeclared role/tool pairs fail closed. Wave 1 runtime persistence remains controlled by the orchestrator; research agents do not gain arbitrary file-write authority.

Research Forge defaults to shared supervision; Daily Coder enables it with `supervised: true`. Their execution and cancellation acknowledgment come from durable supervisor state. Daily Task and explicitly selected legacy inbox adapters return queue/intent acknowledgment only and never imply confirmed worker termination.

The redacted response steps for the credential-like value found in historical request material are tracked in [the remediation checklist](docs/security/credential-exposure-remediation.md). The credential was not tested; owner verification and revocation remain pending.

## Validation scope and known gaps

Research Forge's supported CLI composes Wave 0 and Wave 1. Individual later-wave modules do not constitute a complete multi-wave pipeline. A mock run exercises fixtures and must not be described as live retrieval. `research-forge validate --gate wave_1_mock` validates the runtime gate, not a research packet. Supervised decision gates select the RF package explicitly. Native RF commands require the RF package as working directory; root invocation still reports missing decision configuration. Missing or invalid gates deny execution.

Durable sessions and the shared supervisor are implemented for DC and RF Wave 1. ANX-4 implements reviewed model resolution and SecretBroker; ANX-5 implements isolated knowledge stores and authorized draft retention. Automatic memory-to-engine context retrieval, validated profiles, and complete handoff/compaction integration remain ANX-6 work. See the sections below for implemented boundaries and measured limitations.


## Shared contracts and source precedence

`agent_core.contract_schema`, `contracts`, `registry_snapshot` and `runtime_authority` define the versioned authority interface. Compilation imports the IDE manifest/canonical prompts, DC tool configuration/role metadata/prompts/skills/schemas, RF policy/manifests/schemas, shared role registry/contracts, and personal skill catalog. Their content hashes form one snapshot. Contradictory DC tool declarations, duplicate IDs, invalid contracts, incompatible dependencies and unknown schema references fail closed. Existing RF roles with missing schemas are explicitly quarantined as inactive, with compilation warnings. Shared experimental services are installed but inactive; installation creates no execution grant. Prompt-only IDE specialists acquire no inferred tools.

The six orchestrators are unchanged. DC workers are leaf roles, including its bounded Master specialist. RF's runtime dispatcher can invoke its declared specialists; workers cannot delegate. Messenger has no delegation or execution grants. ANX-5 adds typed memory operations; installation leaves task memory grants empty until explicitly configured.

Effective grants intersect six named layers: user, role, profile, parent, runtime and approval, plus the immutable compiled role ceiling. Existing entry points explicitly translate legacy invocation into the existing role capabilities inside the selected workspace; this migration does not infer new authority from prompts or model output. Optional `task_grants` supplies all six layers and can only narrow them. Tool paths, skill selection and dispatch are checked before access. Existing PolicyGateway also checks the current plan hash and SQLite approval for engineering writes. Budget managers retain execution accounting; grant resource ceilings are available for deterministic narrowing, and the shared supervisor additionally enforces root/descendant reservations.

`agent-core compile-registry` publishes a content-addressed candidate without activating it. `activate-registry` requires an explicit role grant ceiling file; it is also the rollback interface. Publication and pointer replacement are atomic. Later activation intersects the persisted current ceiling and retains revocations, so rollback cannot restore revoked access or increase resource limits. Runtime discovery reads `.agentnexus/registry`, or the explicit `AGENTNEXUS_REGISTRY_STORE` override. An active snapshot must match installed source hashes and cannot broaden source capabilities. With no activated snapshot, the compiled legacy configuration is the enforced baseline.

DC stores `registry_hash` in SQLite schema version 6 and saves the complete snapshot. Migration preserves rows and creates a SQLite backup before upgrading; this runtime refuses newer schemas. RF serializes `registry_hash` with Wave 1 state and saves its snapshot. Both refuse unpinned legacy recovery or incompatible snapshot changes. Start a new run rather than replaying legacy work under changed authority. Recovery also checks engine configuration and durable receipts. Automatic migration of incompatible execution policy is unavailable.

Unauthorized capabilities are absent from compact discovery results. Loading a skill requires an effective grant and a contained active skill path. Discovery or installation is not permission to execute it. Pinned snapshots and live revocations remain separate: current restrictions apply even to previously authorized runs.


## Phase 3: durable supervision

`agent_core.supervisor.Supervisor` links sessions and shared run UUIDs to retained DC/RF engines. `agent-nexus new`, `sessions`, `run` and `resume` call this service, with status, cancellation, run listing and SQLite backup utilities. Bridge supervised flags and dashboard adapters use the same service. DC's native PolicyGateway and approved plan remain authoritative for engineering writes; research gains no engineering write authority.

Shared execution SQLite schema version 2 stores identity/project/profile sessions, immutable configuration/registry hashes, parent links, native aliases, reservations, call outcomes, accepted checkpoints, events and artifact manifests. Migrations use consistent backups and checksums and refuse unsupported newer schemas. Explicit legacy import retains provenance and partial-completeness labels, recorded usage and uncertain exposure. Incomplete legacy execution is blocked from automatic replay. Profiles are identifiers here; validated capability profiles are Phase 6 work.

OS-owned process locks serialize each root's native execution across local processes and release on process death. Source configuration, public execution options, live authorization, registry and native provider/prompt/workflow pins are checked before resume. Child authority must match the parent's pins, workspace may narrow, deadlines and resource ceilings cannot expand. Duplicate task keys, excessive depth and child concurrency are denied. Automatic cross-workflow handoffs remain Phase 6 work.

Reservations are persisted before native execution. Root accounting includes descendants. Admission conservatively requires the native run's whole remaining lifetime grant to fit available root headroom; native engines also enforce the supplied ceilings. Confirmed cumulative usage settles only the new segment delta. Estimates remain labeled estimates; unknown remote outcomes retain exposure instead of becoming zero. Supported RF Wave 1 search/read adapters make HTTP retrieval calls and no model invocations, so their known model token usage is zero. Future model-backed stages must supply durable token receipts rather than inherit that assumption. Native settled-but-unreceipted provider results block replay. Recovery after settlement but before a shared checkpoint reconstructs authoritative terminal/human state without another engine invocation.

DC SQLite schema version 6 records tool receipts before side effects and accepted phase checkpoints. Approved file writes can reconcile against their final content hashes without replaying the write. Other uncertain tool operations remain blocked. RF Wave 1 records call IDs, reservations, cached results, budget updates and checkpoints in a workspace-local SQLite journal; journal state supersedes stale JSON. Native recovery continues accepted stages and never rewinds arbitrary work to charter. Supported integration remains Wave 1; individual later-wave modules are not a complete pipeline.

STOP persists intent independently of executor locks, blocks new dispatch and signals descendants. Cancellation acknowledgment requires native safe-boundary confirmation, settled calls and stopped descendants. The isolated Docker runner terminates its client process group and requires successful container removal before reporting confirmation. Failed cleanup raises reconciliation rather than claiming termination. Providers without cancellation confirmation remain uncertain; socket closure does not establish stopped billing. Remote exactly-once execution and automatic provider reconciliation are not promised.

Dashboard Research Forge runs execute through the supervisor. Daily Coder enables this with `supervised: true`; older HTTP configurations remain supported. Daily Task remains an explicitly labeled inbox workflow. GUI status comes from accepted checkpoints, and cancellation labels distinguish intent from acknowledgment. The supervisor is a local library/CLI service, not a newly exposed unauthenticated network API.


## Adversarial review corrections

The Phase 1–3 review added regression coverage for distinct RF search/page/locator identities, authorization on cached reads, monotonic budget recovery, native DC role/schema pins, stale-write denial, final RF deadlines, descriptor-bound worker snapshots, journal symlink refusal, blocked ancestor dispatch, terminal cancellation races, real v1 migration, invalid accounting categories and interrupted legacy import. Partial imports begin with uncertain exposure and never gain automatic replay authority. Shared-to-native DC creation uses the shared UUID so a crash before alias linkage cannot create another native execution.

Supervised GUI starts carry explicit live authorization and a per-request provider. Automatic sessions are bound to individual workspaces and selected under a lock; explicit session boundaries remain enforced. Supervised mock status remains `SIMULATED` even with legacy `--no-mark-simulated`; that flag affects the legacy wrapper only.

RF live text retrieval now uses a public-only transport: HTTP(S), standard web ports, no URL credentials or ambient proxy/cookies, all DNS answers checked, numeric endpoint pinning, original-host TLS authentication, redirect revalidation and a 400 KB body ceiling. A bounded DNS worker pool and owned-socket shutdown watchdog enforce the call deadline, including headers and TLS. Denied or failed retrieval remains empty/failed evidence. These controls have offline adversarial coverage; real provider cancellation/accounting and real Docker execution remain unverified.

## ANX-0 locked development and publication

`pyproject.toml` defines a virtual uv workspace retaining six editable packages. `uv sync --all-packages --locked` installs the reviewed lock; supported Python remains 3.10+. The macOS launcher fails visibly on installation errors and uses supported dependencies.

The dashboard requires an explicitly supplied `AGENT_DASHBOARD_TOKEN`; browser requests use Authorization headers and the token stays in memory. Host and Origin must match the bound endpoint. Minimal health remains public. A missing private agents.json reads the adjacent example without creating files.

`python -m agent_core.release_preflight --base origin/main --fixture-manifest config/publication-fixtures.json` inventories source and scans the index, working tree, untracked files and new history with bounded reads. It emits locations, never matched secret content. Exact synthetic fixture spans require file hashes; editing a fixture invalidates approval. Pattern scanning is supplementary, not proof that all private data is absent.

Historical credential-owner revocation remains pending. Original history and backups are local recovery material, excluded from the publication branch. No paid provider calls or real isolated-runner smoke test were performed.

## ANX-4 providers and routing

Shared Invocation/InvocationResult preserve native DC positional fields and carry deadlines, request IDs, usage evidence, tool calls and cancellation capability. Missing usage is unknown; explicit zero is valid. Anthropic cache-read and cache-creation tokens are separate and included in aggregate input. Transport retries have one owner, at most two retries, and one original deadline. Only confirmed rejection permits retry; unknown remote acceptance retains exposure. Provider cancellation remains unsupported unless acknowledged.

Supervised DC uses shared OpenAI-compatible/OpenRouter/Anthropic adapters and reviewed model pins. Gemini, command and HTTP bridge remain available through legacy native commands but are explicitly unsupported in the supervised resolver path. Default catalog and role policy are offline mock only. Live routing requires a separately reviewed snapshot with exact IDs, capabilities, pricing, credentials and role permissions. Legacy tier mappings are no longer silently sufficient for supervised live dispatch.

SecretBroker requires macOS Keychain; alternate/locked/missing backends deny access. SQLite contains opaque references, caller scopes and revocation generations only. Register an existing vault service/account reference using the broker API; no vault mutation was performed for verification. Secret-use authority intersects all six layers and binds caller/run/purpose/expiry. Provider adapters acquire values inside authorized operations; ambient environment fallback is disabled. Tool credential access without a broker grant is denied. Split streaming credentials are redacted across event boundaries. Delete/rotation failures retain metadata.

Catalog/policy pairs activate through one atomic pointer, while each run embeds immutable pins. Full policy hashes pin runs; routing-policy digest excludes qualification reports to bind evaluations without circularity. Changes to routing rules invalidate qualification. Automatic cheaper selection requires at least100 held-out task clusters, repeated-run success, Wilson95% lower bound>=90%, no critical policy violations and lower successful-task cost including failures. Mock evaluation cannot qualify quality. No paid evaluations were run.

RF Wave1 is retrieval-only: known model usage zero remains zero; Brave requires broker-authorized provider/brave. Public reader remains protected and credential-free. RF Wave0 model calls require persistent token reservations; missing usage retains them. Later waves remain separately unintegrated.

Deterministic efficiency tools: AST repo_outline never imports inspected code; context_pack preserves protected intent/permissions/approvals/budget/pending calls outside an8-record/4000 estimated-token evidence budget; tool_result_reduce preserves sanitized originals, exit status and truncation; evidence_extract processes already retrieved HTML only. usage-report/eval preserve unknown cost/token fields. Token estimates are heuristic, not exact compatible tokenizer counts. Embeddings, semantic compression and cheap routing are not automatically activated.

## ANX-5 isolated knowledge memory

KnowledgeStore uses distinct explicit paths/UUIDs for each Project, Research, Daily and Shared store. Sessions/approvals/accounting remain in execution state. Schema v1 includes record/source/relationship/dependency/revision/promotion/import lineage/tombstone tables and FTS5. Read-only connections use query_only; writers serialize short IMMEDIATE transactions, WAL and bounded busy handling. Schema migration checksums and table structure are checked; unsupported versions are refused. Use the SQLite backup API for snapshots, never copy the main file during writes.

memory_authority translates owned kind:namespace role maxima into one selected store's UUID-qualified capabilities and intersects all six explicit task layers. The separate data_classes action controls public/private/restricted reads and writes. A role cannot acquire a new namespace or data class from a summary, installed skill or supplied contract. Typed export/import/backup capabilities authorize runtime-owned portability operations only; engineering writes still require PolicyGateway. Current registry ceilings and revocations apply.

Facts remain drafts until confirmation with their current hash. Synthetic and unavailable evidence cannot be accepted as factual knowledge. Accepted facts with stale/conflicting/deleted/expired states or missing/changed dependency fingerprints are excluded from default retrieval. Explicit draft inspection remains labeled. The bounded FTS result includes provenance and relationship references; at most eight records and 4,000 conservative token units are returned. FTS and metadata filtering run locally, without embeddings or provider calls.

Import validates hashed manifests and references before a single transaction; imported facts become drafts and preserve lineage. Shared promotion requires an accepted current source, source/destination grants, explicit transformed title/body and confirmation; private body/locators are not implicitly copied. Backup requires full store authorization. Deletion immediately clears FTS, payloads and related data, increments generation and schedules physical tombstone purge. Backups can retain older content; no forensic erasure claim. Generation is the invalidation signal for future ANX-6 caches; no persistent result cache or compact-context cache is introduced here.

The raw-run retention choice is recorded at store setup; execution-state logs remain separate and are not silently purged by memory operations. Cache knowledge expires after 30 days; accepted knowledge persists until deletion. Personal-career files remain authoritative. Personal previews/show/dry-runs do not initialize absent stores; confirmed changes validate the supplied career/accomplishment schemas. Derived artifacts record source hashes and stale lineage. Personal import creates scoped drafts from explicitly selected files and retains originals. Secrets remain in SecretBroker; memory permits opaque references, rejects known credential patterns/structured fields, and does not promise universal secret detection.

Optional session-scoped --memory-binding pins configuration and store identity, automatically retaining authorized Research read text and bounded coding checkpoint outcomes as drafts. It never ingests arbitrary coding files or promotes/accepts records. Resume checks binding pins; current authorization is rechecked. Failed configured ingestion is reported as BLOCKED while known execution usage remains settled. See [ANX-5 contract](docs/superpowers/plans/2026-10-10-anx5-memory.md).

Review corrections: search refuses overrides above eight records/4,000 token units; opaque source IDs round-trip; recognized modern provider tokens and encoded credential fields are rejected; imports retain stale/conflicted restrictions; Shared promotion requires matching current dependency fingerprints via --fingerprints when dependencies exist. Confirmed personal mutations serialize across processes, while previews create no lock or store files.

Post-release ANX-5 review corrections: personal import parses and schema-validates one descriptor-bound byte snapshot, hashes those exact bytes and retains matching source metadata; an in-place change during the read is refused. Runtime checkpoint recovery recognizes authorized deletion tombstones and skips reingestion without resurrecting content or blocking otherwise reconciled execution. RF/DC recovery regressions verify that this does not redispatch native work or retain settled reservations.


## General-purpose orchestration execution

The approved [execution plan](docs/superpowers/plans/2026-10-10-general-purpose-orchestration.md) targets this Mac with Codex-only access first, then portable Linux deployment. Daily, Research and Code are profiles over the existing six orchestrators; project instances will isolate settings, grants, memory and state while sharing versioned runtime code. These profile/instance interfaces are pending implementation.

Daily Coder tool-result projection now bounds the complete serialized packet, including Unicode escaping, and retains status plus gateway tool-operation receipt references. Small arguments remain when they fit; oversized observations and optional arguments are reduced first. Essential references that cannot fit stop the invocation rather than silently discarding evidence. Full tool receipts remain in authoritative execution state; role-originated inspection/expansion must pass its normal gateway and workspace checks. Optional GitHub adapter registration performs no credential lookup; credential use remains checked when the handler is invoked.
