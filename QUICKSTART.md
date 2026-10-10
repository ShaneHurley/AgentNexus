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

The implementation environment had Docker installed with its daemon stopped. Actual container smoke validation remains necessary after starting the daemon and provisioning the reviewed image. No paid provider evaluation was performed. If execution is unavailable, use typed inspection; the runtime does not fall back to host subprocesses.


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
