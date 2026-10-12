# AgentNexus quickstart

## Reproducible installation (Python 3.10+)

Install a reviewed uv version and sync all editable workspace packages from the committed lockfile:

```sh
python3 -m pip install uv==0.12.24
uv sync --all-packages --locked
uv run --locked agent-nexus --help
uv run --locked python -m pytest -q -p no:cacheprovider
```

Use a fresh environment when validating an installation. Do not copy dependencies from other applications or create compatibility shims. `start_mac.sh` performs locked installation and stops on dependency errors. Existing local environments and private runtime state are preserved. Run `uv lock` only when intentionally reviewing a dependency update; ordinary installation does not update the lock.

The dashboard requires an explicitly supplied API token (`AGENT_DASHBOARD_TOKEN` or its supported programmatic token parameter). Enter it through the dashboard settings; keep it in memory, never a URL. Do not paste credentials into issues or logs. For mock CLI operation no provider credentials are needed.

The accepted delivery sequence and GitHub epic links are in [the ANX roadmap](docs/superpowers/plans/2026-10-09-agentnexus-roadmap.md). Historical phase numbering in other documents is preserved as rationale.

## Existing command reference



These commands use the repository's existing local interfaces. Run them from `/Users/shurley/Documents/AgentNexus`. Start with mock mode; it uses fixtures and does not establish live evidence.

## Check local tools

```bash
ide-bridge doctor
ide-bridge --help
python agents/daily-task/driver.py --list
```

The bridge requires the relevant packages to be installed or available in the environment. The dashboard can be started with:

```bash
PYTHONPATH=gui .venv/bin/python -m agent_dashboard --config gui/config/agents.json
```

It listens on localhost using the configured dashboard port. Research Forge uses the shared supervisor. Daily Coder uses it when `supervised: true` is configured (as in the example configuration). Daily Task remains an inbox workflow and does not imply execution acknowledgment.

## Mock coding run

```bash
ide-bridge daily-coder run --request "Inspect the project structure" --repo /absolute/path/to/project --provider mock
```

Mock results are simulated. Do not interpret exit status alone as accepted implementation. Review the emitted plan and artifacts, then use the documented approval and resume flow when the run requests it. Host shell and test execution require a reviewed, digest-pinned Docker image and a running local daemon. Detached host test jobs remain disabled.

## Mock Research Forge run

Create a schema-valid request JSON file, then run:

```bash
ide-bridge research-forge run --request /absolute/path/to/request.json --wave1 --cwd /absolute/path/to/AgentNexus/agents/research/research-forge --workspace /absolute/path/to/AgentNexus/agents/research/research-forge
```

The native RF CLI resolves configuration from its working directory. With the virtual environment activated, validate from the RF package directory:

```bash
cd agents/research/research-forge
research-forge validate --gate wave_1_mock
research-forge status RUN_ID
cd ../../..
```

The supervised frontend selects the RF source package explicitly and supports a separate workspace. The legacy native CLI requires the RF package as its working directory; invocation from the repository root fails its decision gate. Missing or invalid decisions block execution before dispatch.

When live search credentials are absent or retrieval fails, the search result is explicitly empty or failed. A configured fixture is labeled synthetic and cannot be accepted as live evidence. Live execution requires the repository's live gate and approved credentials; do not use a mock result as a quality evaluation.

## Generated IDE agent projections

```bash
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
```

Import and synchronization commands without `--check` regenerate outputs from their canonical sources. See [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md) for current boundaries and known incomplete components.


## Install the local packages

From the repository root, create a virtual environment if needed and install all local distributions together:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e agents/shared/ai_agents_repo -e agents/shared/agent-core -e agents/ide/bridge -e agents/coding/daily-coder-ecosystem -e agents/research/research-forge -e gui
```

Use the virtual environment's executables, or activate it before running the commands above. DC and RF require the shared `agent-core` package and this repository's source metadata.

## Inspect Phase 2 capability snapshots

```bash
.venv/bin/agent-core compile-registry --repo "$PWD" --output /tmp/agentnexus-registry
```

This prints the snapshot ID and translation warnings, and does not activate the candidate. To activate a reviewed snapshot, supply a JSON mapping of role IDs to their explicit current grant ceilings:

```bash
.venv/bin/agent-core activate-registry SNAPSHOT_ID --store /absolute/registry-store --ceiling /absolute/reviewed-ceilings.json
```

Set `AGENTNEXUS_REGISTRY_STORE` to that directory for runtime selection. Do not activate automatically after compilation. Existing runs retain their snapshot pins; recovery rejects changed or missing pins.

## Configure isolated tests

Review and install a Docker image locally, then set `execution_policy.image` in DC policies to its exact `repository@sha256:<64 hex characters>` identifier. RF code experiments use `isolated_image` in their experiment configuration. No default image or implicit pull is provided. Workers have read-only sanitized inputs and writable disposable `/tmp` and `/outputs` directories, with no network. Tests needing private files or writable source trees must be adapted; workers cannot apply host edits.

Docker is installed and its daemon responded during the October 11 local check. No reviewed worker image is configured yet; actual isolated-runner smoke validation remains necessary before claiming code/test execution is operational. No paid provider evaluation was performed. If execution is unavailable, use typed inspection; the runtime does not fall back to host subprocesses.


## Durable sessions and recovery

The shared frontend retains the existing workflow engines and their gateways:

```bash
.venv/bin/agent-nexus new --identity local --project /absolute/project
.venv/bin/agent-nexus sessions
.venv/bin/agent-nexus run --session SESSION_UUID --engine daily-coder --request "Inspect the project structure" --workspace /absolute/project
.venv/bin/agent-nexus status RUN_UUID
.venv/bin/agent-nexus resume RUN_UUID
.venv/bin/agent-nexus cancel RUN_UUID
```

For research, select `--engine research-forge --request-file /absolute/request.json`; resume clarification with `--answer CLQ-ID=value`. State defaults to `.agentnexus/sessions.sqlite`. Set the global `--state-dir /absolute/state-directory` before the command to use another store. `backup /absolute/new-backup.sqlite` creates a consistent execution-state backup. Session UUIDs, shared run UUIDs and native engine aliases remain distinct.

A completed mock run reports `SIMULATED` and exit 1; live completion reports exit 0, failed execution 2, and a blocked/waiting/reconciliation state 3. Approval success acknowledges the action and does not imply run completion. For DC approvals, use the native alias with `ide-bridge daily-coder approve NATIVE_ID --kind plan`, then resume the shared UUID. The supervised dashboard maps approvals to the same native state authority.

Bridge run/resume commands accept `--supervisor-dir /absolute/state-directory`; run also accepts `--session-id SESSION_UUID`. Legacy commands remain available. Use the same supervisor directory across interfaces to see the same authoritative state.

When `RECONCILIATION_REQUIRED` appears, preserve state and artifacts and stop retrying. Unknown calls retain reservations; a timeout does not prove no work or no charge occurred. Changed source/configuration, provider, live mode or registry pins require a new run. RF resumes durable accepted checkpoints without restarting charter. Incomplete historical runs cannot acquire replay authority through import.

Cancellation intent blocks new dispatch immediately. `CANCEL_REQUESTED` means termination is pending; only `CANCELLED` acknowledges it. A provider without confirmed cancellation retains unknown remote exposure. The supervisor serializes native execution within each root and requires remaining parent headroom to cover the native run's remaining resource grant before dispatch.

Supervised GUI live starts require explicit confirmation and carry the selected provider in the individual request. `--no-mark-simulated` remains a legacy wrapper option; supervised mock runs always retain `SIMULATED` status. RF live text retrieval permits public HTTP(S) endpoints on standard web ports and rejects private DNS addresses, URL credentials, unsafe redirects and oversized bodies. Retrieval failures remain explicit; no synthetic fallback is enabled.

## ANX-4 offline model inspection

```sh
uv run --locked agent-nexus models inspect
uv run --locked agent-nexus models explain --role dc:researcher --requirements '{"risk":"low","privacy":"local"}'
uv run --locked agent-nexus models publish --catalog candidate-catalog.yaml
uv run --locked agent-nexus models activate --catalog-hash HASH --policy reviewed-policy.yaml --policy-hash FULL_POLICY_HASH --confirm
uv run --locked agent-nexus usage-report --records sanitized-usage.json
uv run --locked agent-nexus eval --help
```

Publication creates a candidate only. Activation requires the matching catalog and policy hash plus confirmation; existing runs keep their pins. Default supervised execution remains mock-only. For live execution, first configure reviewed routing and an existing macOS Keychain reference through SecretBroker. Missing/locked/unapproved credentials fail before dispatch. Never put credential values in model catalog, grant files, URLs or CLI arguments. API/provider cancellation and real Keychain access were not operationally tested; offline contracts were tested.

## ANX-5 scoped memory setup

Memory commands require an existing workspace and an explicit version-1 grant JSON containing identity, run_id, qualified role and all six layers (user/role/profile/parent/runtime/approval). Each layer declares exact store:UUID:default/meta memory_read/memory_write capabilities, data_classes, workspace_roots and needed typed tools. Role maxima in agent-core/config/memory-capabilities.yaml remain authoritative. Do not copy grants between projects or synthesize all-powerful layers.

```sh
uv run --locked agent-nexus memory --help
uv run --locked agent-nexus memory init --store /absolute/project/knowledge.sqlite --workspace /absolute/project --grant-file /absolute/reviewed-memory-grant.json --store-id STORE_UUID --kind project --raw-run-retention none --confirm
uv run --locked agent-nexus memory draft --store /absolute/project/knowledge.sqlite --workspace /absolute/project --grant-file /absolute/reviewed-memory-grant.json --input /absolute/project/authorized-note.json
uv run --locked agent-nexus memory search --store /absolute/project/knowledge.sqlite --workspace /absolute/project --grant-file /absolute/reviewed-memory-grant.json --query "topic" --include-drafts
uv run --locked agent-nexus memory accept --store /absolute/project/knowledge.sqlite --workspace /absolute/project --grant-file /absolute/reviewed-memory-grant.json --record RECORD_UUID --expected-hash CONTENT_HASH --confirm
uv run --locked agent-nexus memory doctor --store /absolute/project/knowledge.sqlite --workspace /absolute/project --grant-file /absolute/reviewed-memory-grant.json
```

The draft input declares title, body and sources (locator, retrieved_at, content_hash, retrieval_status, synthetic); supplied human notes use provided status. Drafts are excluded from factual search unless explicitly requested. Synthetic evidence cannot be accepted. Use inspect for stable reference expansion, refresh with current dependency fingerprints, and revise with confirmation/hash to create a superseding draft. Mutating acceptance/promotion/import/export/backup/deletion commands require their documented confirmation and scopes. Inspect each subcommand's --help before use. Export/import/backup require typed memory.export/import/backup tool grants and contained non-symlink paths; existing outputs are never overwritten.

Optional automatic retention: create a version-1 memory-binding JSON with session_id, store and grant; grant identity matches the session and grant.run_id equals session_id. Role is ide:deep-research for Research or ide:daily-coder/ide:use-master for coding. Add --memory-binding /absolute/binding.json to agent-nexus run. The store must already exist and grants explicitly authorize draft writes. Research binds Research; coding binds Project or Daily; no automatic Shared writes. Changes to binding or store identity block resume. This records drafts only and defaults off without a binding.

Create Daily and Shared stores separately; do not reuse a Project UUID. Record raw-run retention explicitly at initialization (days or none). This choice does not silently purge separate execution history. Consistent backups may retain deleted content. Actual personal files and Keychain are untouched by the offline test suite. Personal show and --dry-run operations are non-mutating; confirmed career changes retain visible diff review. ANX-6 dashboard memory, caching and handoffs remain backlog.

Review corrections: search refuses overrides above eight records/4,000 token units; opaque source IDs round-trip; recognized modern provider tokens and encoded credential fields are rejected; imports retain stale/conflicted restrictions; Shared promotion requires matching current dependency fingerprints via --fingerprints when dependencies exist. Confirmed personal mutations serialize across processes, while previews create no lock or store files.


## General-purpose roadmap

See the [approved execution plan](docs/superpowers/plans/2026-10-10-general-purpose-orchestration.md) and [recorded mock baseline](docs/ide-agents/orchestration-baseline.json). Mock execution verifies harness transitions and accounting only. Codex-only execution, project profiles and hosted Daily task execution must pass their own release gates before use is advertised.


## Agent audit and Codex prerequisite

```sh
uv run --locked agent-nexus --repository . agents audit --check
uv run --locked agent-nexus --repository . agents audit --select ide:researcher --select browser:code-crafter
```

The audit reads the existing manifests and contracts without creating sessions or granting capabilities. It checks all 41 IDE agents, 96 browser pastes and ten families, projections, source pins, local guide links and literal generator commands. Selected prompt sizes are estimates and exclude runtime history/tools/provider overhead. The default 32,000-byte per-prompt ceiling reports oversized instructions; it never truncates them.

The Codex CLI transport is explicitly selectable in supervised Daily Coder runs after reviewed local configuration. It uses ChatGPT login, never extracted credentials. The built-in API catalog remains mock-only; selecting Codex supplies its own pinned baseline policy without activating cheaper routing.

```bash
agent-nexus --repository /absolute/AgentNexus codex configure --pins /absolute/reviewed-codex-pins.json --confirm
agent-nexus --repository /absolute/AgentNexus codex inspect
agent-nexus --repository /absolute/AgentNexus new --project /absolute/project --profile Code
agent-nexus --repository /absolute/AgentNexus run --session SESSION_ID --engine daily-coder --workspace /absolute/project --request "Describe the bounded task" --provider codex_cli --live --budget-usd 0 --token-limit 80000 --deadline-seconds 600
agent-nexus --repository /absolute/AgentNexus resume RUN_ID
```

The reviewed pins file has exactly `version`, `model`, `reasoning_effort`, absolute `executable` and `catalog_path`, and SHA-256 `executable_sha256`, `catalog_sha256`, `security_config_sha256`. The catalog must have one matching model with native tools disabled; use a reviewed catalog, not the ordinary host catalog. Configuration contains no login secrets. Supported CLI versions are explicitly reviewed; an app update requires new review and confirmation. Existing runs retain old pins and block on incompatible changes.

Codex runs have one active invocation per OS account across processes. Structured output requests tools through the gateway; writes still require plan approval. Reported subscription tokens are accounted separately from zero API cash exposure and unknown total dollar value. Missing usage or uncertain completion retains reservations; cancellation does not imply remote cancellation. Local character-based input estimates include role/tool schemas and a measured overhead allowance, but the CLI cannot enforce a hard remote output-token ceiling. Model-output quality failures permit at most the existing one configured schema correction after a known usage receipt.

See [transport evidence](docs/ide-agents/codex-adapter-smoke.json). Full paired Research/Code evaluations, validated project profiles/instances and the real isolated-runner gate remain pending. `--profile Code` currently stores a session label; it does not activate a separate validated execution profile. Do not infer completion from a queued or blocked run.

## Python reliability and bounded-context evaluation

The existing Codex adapter now accepts ordinary commentary (including inline Markdown paths) before its final structured envelope. Ambiguous structured messages and native-tool events remain denied. Planning roles receive a runtime-owned explanation of review, approval and gateway writes; that explanation does not grant permissions.

Run contract replay without authentication, network access, model calls or tool execution:

```bash
agent-nexus eval --mode replay --input agents/shared/agent-core/tests/fixtures/codex-replay-v1.json --output /absolute/replay-report.json
agent-nexus tools context-preview --input /absolute/context-packet.json
```

Preview input contains `protected`, `evidence`, and optionally `prompt`, `tools`, `output_schema`, `provider_overhead_tokens`, and `max_output_tokens`. Protected fields are intent, constraints (including acceptance criteria), permissions, approval_hash, plan_hash, budget and pending_calls. Counts are estimates; provider-reported usage remains authoritative.

`agent-nexus eval --mode supervised --suite /absolute/suite.json --variant baseline --repetitions 1 --output /absolute/report.json` launches the public supervised CLI with Codex subscription access and zero API cash budget. Suite version 1 declares an ID and cases with ID, profile, workspace, request_file, request_sha256, token_limit and expected_status. Supported expected states are COMPLETE and WAITING_HUMAN. Read/write approval is never automatic. At WAITING_HUMAN the command persists run/session/approval references and stops further repetitions; the approval has no timeout. Use the bridge to approve the exact reviewed plan and the saved supervisor state directory to resume. Waiting for approval is not task completion.

The `bounded-context-v1` variant is evaluation-only, disabled for normal runs. `--context-evaluation` allows explicit candidate measurement without production activation. Each run pins the context policy. Optional research evidence is bounded to eight records/4,000 estimated tokens; projected tool context is bounded to 12,000 characters rather than the baseline 24,000. Complete request estimates include role instructions, tool/output schemas and provider overhead. Current-role tools are selected from effective grants. No lossy compression of authority fields is used.

`filesystem.read` accepts `view=outline` for Python AST inspection without importing source. It also accepts `operation_ref`, `offset` and `limit` to expand its current run/role's completed read receipts. Each expansion reauthorizes the original capability and workspace; receipts are historical observations, not current facts. Truncated source reads explicitly require smaller line ranges.

Supervised reports preserve unknown cost/usage, cached-token counts when reported, native receipt counts, repairs, denied tools, configuration/code hashes and artifacts. RF Wave 1 currently has no supervised Codex investigation adapter; Research comparison cases are explicitly BLOCKED rather than relabeled Code runs. Replay proves transport contracts, not model quality. No token-efficiency qualification or production activation is claimed without completed paired measurements. Dashboard start responses expose session/create/execute/total timings; the previously timed-out RF smoke test passed in isolation without increasing its timeout.

October 11 operational check: the first user-selected game baseline did not complete. Its initial research role exhausted tool rounds, followed by a diagnostic provider configuration/schema failure. The adapter now declares required:[] for the empty no-tool object, and roles receive explicit remaining rounds with no tools on their final permitted round. A second attempt completed four research lanes, then stopped at the persistent daily token ceiling before planning or writes. No plan approval exists, and no efficiency setting was activated. The next live test requires a separately approved bounded allowance; failed runs and unknown reservations remain preserved. Latest full pytest verification: 1,049 tests and 45 subtests passed. See docs/ide-agents/python-reliability-verification.json.


## October 12 operational test status

Supplied Markdown plans can be explicitly pinned with repeated `--reference-document` options for a supervised `bounded-context-v1` evaluation. This candidate reads through PolicyGateway, reauthorizes role and target access, rejects changed sources, and keeps supplied excerpts plus research evidence within eight records and 4,000 estimated tokens. Roles without file-read authority do not receive supplied-document context. One reconnaissance lane and a deterministic empty brainstorm are used only for an explicit supplied-plan evaluation without a request to compare alternatives; normal production routing is unchanged.

Receipt reduction retains call IDs, operation references, result hashes and execution outcomes. Optional argument hashes and size diagnostics are removed only when needed to fit the bound; essential overflow still fails explicitly. Codex response deadlines are bounded at 180 seconds and may be shortened by the invocation or parent deadline. Unknown remote completion retains its reservation and is not blindly retried.

The Ceci game operational candidate is **not complete**. Run `3081b96c-be03-4e11-b6a9-235d13787497` was cancelled after receipt-context overflow (147,570 reported tokens; cancellation acknowledged). After repair, run `19e4c4b0-a3f1-4e43-aab9-de369aeda7af` completed reconnaissance and reached design but hit the previous 60-second provider deadline: 122,366 known reported tokens plus one unknown invocation/reservation. No game implementation or efficiency qualification is claimed. Original game plans and the original dirty AgentNexus checkout are preserved.

The pinned Node isolated-runner smoke test passed through PolicyGateway: workspace writes and outbound network were denied. Image: `node@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392`. This verifies the runner boundary, not a game build or iPhone-device acceptance. The image still requires an explicit execution-policy binding for future supervised game verification.

Verification: affected pytest suites passed 706 tests plus 45 subtests before the final small repairs; the final provider/context regressions passed 113 tests. Required DC unittest discovery passed 130 tests; DC validation, projection check, Ruff correctness checks and `git diff --check` passed. Linux/macOS CI and a complete real write/test/review game run remain release gates. No API spending occurred. The owner's October 12 authorization permits tests and necessary fixes without waiting; concrete plans and gateway approvals remain recorded.
