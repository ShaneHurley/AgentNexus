# Codex-first contained coder (candidate policy)

## What is available

The existing bridge, supervisor, PolicyGateway, SQLite stores, and DockerRunner execute a contained coding task through the opt-in `coder-v1` policy. Codex owns ChatGPT login and refresh. The repository stores compatibility pins and credential references.

Keep the six orchestrators. Cursor and Antigravity transports, research fan-out, and dashboard work remain follow-on work. Larger and high-risk tasks retain their established workflows. This candidate accepts one to three concrete file targets; it is not a general reliability-rate claim.

## Setup

1. Preserve the current checkout and use a dedicated Git worktree on a `codex/` branch.
2. Install the workspace using `uv sync --all-packages --locked`.
3. Review the existing Codex compatibility pins with `agent-nexus codex inspect`. A new reviewed pin file is installed explicitly using `agent-nexus codex configure --pins <file> --confirm`.
4. Run `agent-nexus codex doctor --json`. It makes no model request. Missing executable, unsupported version, pin mismatch, unavailable authentication, unrecognized login status, and invalid security configuration have distinct corrective actions. Account limits and transport errors are not reported as login failures.
5. Build `tools/coder-runner/Dockerfile` with its hash-pinned requirements. Record the actual immutable image ID or registry digest in `config/policies.json` under `coder_v1_execution_policy.image` in the Daily Coder ecosystem. Never use a moving image tag. The current tested ID is local to the build host; rebuild and review the resulting ID on another host.
6. Confirm Docker is available. Task verification uses a secret-excluding source snapshot, disabled networking, bounded resources, and container cleanup. An unavailable backend leaves verification incomplete.

### Runner preparation

From the repository root:

```sh
docker build -f tools/coder-runner/Dockerfile -t agentnexus-coder-fixture tools/coder-runner
docker image inspect agentnexus-coder-fixture --format '{{.Id}}'
```

Install dependencies while preparing the image, before the task's network-disabled verification. If dependencies change, regenerate requirements from the locked workspace, rebuild, and review the new image pin. A full immutable `sha256:<64 hex>` local image ID is supported; registry images use `repository@sha256:<64 hex>`.

## Task contract

A submitted task and its explicit contract grant authority to plan, implement, test, and repair within that scope. Record:

- `schema_version`: integer 1.
- `request_sha256`: SHA256 of the exact UTF-8 request.
- `workspace`: resolved absolute workspace path.
- `acceptance_criteria`: nonempty concrete criteria.
- `allowed_paths`: one to three literal workspace-relative paths; no globs, traversal, runtime directories, or symlink escapes.
- `operations`: `create` and/or `modify`.
- `verification_commands`: exact argument-vector arrays, not shell strings.
- `limits`: tokens, calls, repair_cycles, tool_rounds, verification_timeout, deadline_seconds.
- `authorization_source`: `user-task`.
- `authorized_at`: timezone-aware ISO8601 timestamp.

Example limits: 300000 tokens, 30 model calls, 2 repair cycles, 6 tool rounds per role, 120 seconds per verification command, and 1800 seconds per active task. Parent/user limits always win. Formatting repair consumes the same budget. Concurrency is one. Existing reservations remain part of available capacity.

The plan is checked against literal paths, operations, commands, and a stable topological ordering of its change units. A derived grant binds the exact plan hash and task-contract hash. Changes use compare-and-swap base-file hashes. Changed sources must be read again and replanned, not overwritten.

Task authority excludes deployment, publishing, external messages, credential changes, destructive operations, and unrelated edits. A scope expansion records a focused question and pauses dependent work. Missing authority never becomes permission.

## Run

The bridge accepts the following explicit supervisor options:

```sh
ide-bridge daily-coder run --request "<exact task>" --repo "<task worktree>" \
  --live --provider codex_cli --repository "<AgentNexus root>" \
  --supervisor-dir "<AgentNexus root>/.agentnexus" \
  --execution-policy coder-v1 --approval-mode task --task-contract "<contract.json>" \
  --token-limit 300000 --deadline-seconds 1800
```

The public supervisor entry point is also available:

```sh
agent-nexus --repository "<AgentNexus root>" new --identity operator --project "<task worktree>"
agent-nexus --repository "<AgentNexus root>" run --session "<session id>" \
  --engine daily-coder --request "<exact task>" --workspace "<task worktree>" \
  --live --provider codex_cli --execution-policy coder-v1 --approval-mode task \
  --task-contract "<contract.json>" --token-limit 300000 --deadline-seconds 1800
agent-nexus --repository "<AgentNexus root>" status "<run id>"
agent-nexus --repository "<AgentNexus root>" resume "<run id>"
agent-nexus --repository "<AgentNexus root>" cancel "<run id>"
```

The normal contained path uses deterministic sizing and scope checks, model planning and implementation, runtime isolated verification, independent model code review, and acceptance checks. The runtime records deterministic decisions truthfully; they are not presented as model-authored or manually approved decisions. Semantic confidence depends on the acceptance tests and code review.

Legacy runs keep their prior policy and plan approval. Do not amend historical approvals.

## Handoffs and recovery

Completed role output is normalized before schema rejection discards it. The normalizer handles whitespace/BOM, one fence, a complete JSON value, and one unambiguous schema-valid object surrounded by prose. Only explicit tested aliases are allowed. Multiple candidate objects are rejected as ambiguous.

Preserve bounded sanitized raw artifacts, hashes, parse problems, evidence references, task authority, and delivery acknowledgments. Make at most one tool-free formatting repair call. If it fails, launch the workflow's pinned intended recipient with incomplete findings and missing facts, within authority and budget. Model text cannot select the recipient or add permissions. An implementer may recover context but cannot write without a valid grant. Missing verdicts never become a pass.

Native transport integrity remains strict: invalid tool calls, contradictory completion events, and unknown remote outcomes use their existing execution checks.

Recovery consults durable model/tool receipts before dispatch. Accepted effects are reused. Unknown effects retain reservations and require reconciliation. An explicitly lost pure-read receipt can be acknowledged with `agent-nexus reconcile-read`; this does not authorize writes or replay effects. Never silently reset unknown usage or source pins.

A supported unittest/pytest command must show a positive non-skipped executed-test count. Exit zero with no tests is not verified. Acceptance also requires actual snapshot/image/argv/status evidence, source hashes matching the reviewed candidate, no unresolved blocking review findings, and settled usage.

## Acceptance fixtures

`tools/coder-fixtures/run_acceptance.py` calls the public CLI and records explicit interventions without modifying grants or usage:

- `nominal`: ordinary task.
- `fenced-planner`: replaces completed planner presentation with surrounding prose and a Markdown JSON fence.
- `interrupt-after-implement`: exits 75 after durable accepted writes; resume using the ordinary public CLI.

Offline tests additionally prove that failed formatting repair dispatches the intended recipient without adding write authority. Fault injection is test evidence, not a production transport or permission bypass.

Report the requested outcome, changed files/diff, actual commands/results, review findings/disposition, model calls/tokens/unknown usage, assumptions, limitations, and resume instructions. Failed and cancelled trials remain recorded. Do not claim general reliability from a handful of successes.

## Extension path

Reuse diagnostics, task contracts, handoffs, receipts, budgets, cancellation, and evidence storage for supervised research under roadmap #31. Research adds source provenance and citation checks. Everyday connector actions require their own task grants and receipts; coding permission does not authorize messages, calendars, or publication.

## First task on this device

Use the installed runtime from the implementation worktree. For this example, create a fresh Git worktree after the candidate has been committed. Run the commands from the AgentNexus runtime root:

```sh
git worktree add --detach ../coder-example HEAD
.venv/bin/python tools/coder-fixtures/prepare_contract.py \
  --workspace ../coder-example/examples/coder-v1 \
  --request-file examples/coder-v1/request.txt \
  --allowed-path clamp.py --operation modify \
  --criterion "Values below lower return lower; other behavior is preserved" \
  --criterion "All five unchanged regression tests pass" \
  --verification-argv '["python","-m","unittest","discover","-s",".","-p","oracle_clamp.py"]' \
  --output .agentnexus/example-contract.json
.venv/bin/agent-nexus codex doctor --json
.venv/bin/agent-nexus new --identity operator --project ../coder-example/examples/coder-v1
```

Copy the returned session ID into:

```sh
.venv/bin/agent-nexus run --session "<session id>" --engine daily-coder \
  --request-file examples/coder-v1/request.txt --workspace ../coder-example/examples/coder-v1 \
  --live --provider codex_cli --execution-policy coder-v1 --approval-mode task \
  --task-contract .agentnexus/example-contract.json --token-limit 80000 --deadline-seconds 900
```

A capacity preview appears on stderr before dispatch; the terminal result remains JSON on stdout. The fixture oracle is named `oracle_clamp.py` so the intentionally broken starting example is not collected as a repository regression. Contract preparation creates a new authority record and refuses to overwrite one; use a new output name for another task. The model may modify only `clamp.py`, not the oracle.


## Explicit subscription trial budgets

`limits.codex_subscription_max_tokens_per_day` is an optional trusted runtime configuration setting. When absent, the existing daily token ceiling applies. A positive integer overrides that ceiling only for the supervised `codex_cli` provider with validated ChatGPT subscription accounting and its exact reviewed model allowlist. An explicit JSON `null` removes that route's aggregate daily token ceiling. Other providers retain their ordinary limits, and the repository default leaves this setting absent.

Task token grants, call limits, deadlines, existing reservations, usage accounting and Codex account limits still apply. The override cannot enable an API-billed or missing-model fallback. Effective limits are part of the execution configuration hash; changing them requires a new run rather than continuing an old configuration. Capacity previews show a null daily headroom when the local daily ceiling is disabled while retaining consumed usage and outstanding reservations. This is a local orchestration policy, not an increase in the signed-in account's subscription allowance.


## Optional review source projection

The trusted setting `coder_v1_review_source_projection` defaults to `"none"`.
The experimental value `"verified-additions-v1"` removes a redundant source excerpt
only when the complete candidate manifest contains that newly created file as a
single full addition whose reconstructed UTF-8 bytes match the candidate SHA-256
and the authorized source receipt hash. Modified files and uncertain evidence
retain their source entries. The complete manifest, independent review, tested
source bindings, task authority and acceptance checks remain required. Unsupported
values fail before model dispatch. The selected projection is recorded in the
execution configuration hash, so changing it requires a new run.
