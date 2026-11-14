# simpleIDE repair and qualification plan

> Superseded by finalization-plan-2026-11-14.md; its follow-up defects are closed in gates-G2-G5-G7-completion.md.

Written 11 November 2026. This is an implementation plan, not a claim that the repairs have shipped. Production scripts, agents and skills were unchanged in this investigation.

## Decision

Keep the standard-library CLI, SQLite stores and existing roles. Repair the state and evidence contracts before adding features or collecting cost-comparison results. First preserve evidence, then make task ownership and completion explicit, then repair worktrees, installation and recovery. Qualify one real host before extending the live matrix to the other hosts.

The existing 38 unittest cases passed again on Python 3.12.0 during this investigation. The previous [readiness review](readiness-review-2026-11-11.md) contains 13 unmet expectations across nine work areas. This follow-up adds **13 targeted unmet expectations**, grouped below; these are selected reproductions, not 13 independent root causes or an estimate of failure frequency. Source-level risks are labeled separately. No IDE/model trial was performed in this follow-up.

Evidence:

- Previous cases: [script](evidence/readiness_probe.py), [observations](evidence/readiness-probe-2026-11-11.json).
- Additional cases: [script](evidence/followup_probe.py), [observations](evidence/followup-probe-2026-11-11.json).
- Historical six-defect repair: [fix report](fixes-2026-11-10.md). Keep those regressions passing.

## Findings and disposition

P1 means repair before relying on the affected workflow or measurement. P2 means a correctness, installation or recovery repair before general release. The evidence labels N01–N13 refer to keys in the new JSON file.

| ID | Priority | Defect or gap | Evidence and consequence | Repair step |
|---|---|---|---|---|
| F01 | P1 | Session ownership is inferred from newest rows | Previous probe: A captures a request, B captures another, then A's goal binds B's request. Lifecycle/resume can likewise choose B's task. Stop uses the same selection pattern in source. | 2 |
| F02 | P1 | Results implicitly mean accepted; slug reuse retains terminal state | Previous probe records a failed/blocked result and gets accepted=1; retrying the slug keeps old completion. | 3 |
| F03 | P1 | Workers cannot retrieve parent record IDs | Previous probe: a new worktree has an empty local ledger. LARGE briefs refer to unavailable parent records. | 4 |
| F04 | P1 | Record IDs can change meaning after deletion | N01: forget P2, insert an unrelated note, then `show P2` returns the unrelated note. This can silently corrupt references in briefs, exports and decisions. Applies to the shared table schema too. | 1 |
| F05 | P1 | Check summaries do not represent all current checks | N03: test FAIL followed by lint PASS loses the failure in the stop message. N04: adding a result suppresses the failure warning entirely. N05: edit source after PASS; pack still prints PASS without indicating that the current revision was not checked. | 3 |
| F06 | P1 | Worktree cleanup destroys evidence and cannot reliably resume | N07–N08: first piece is removed before second dirty piece is rejected; retry fails on the missing first path. N09: cleanup deletes the only worker database, which is ignored by Git. Git branches are retained, but ignored evidence is not recoverable from those branches. | 4 |
| F07 | P2 | Partial uninstall removes assets still used by another host | Previous probe: removing Cursor also removes Codex's shared skills and project rule. | 5 |
| F08 | P2 | Global write-up command points at a nonexistent local script | Previous probe: exact installed skill command exits 2 in a project with only a global install. | 5 |
| F09 | P2 | Installer mutates before validating all inputs | N10: malformed Cursor hooks cause an exception after scripts and agents have already been installed. A configuration error leaves mixed installation state. | 5 |
| F10 | P2 | Hook ownership is matched by substring | N13: an unrelated user hook that echoes text containing `.simpleide/sx.py hook` is deleted during installation. This violates preservation of user hook entries. | 5 |
| F11 | P2 | Shared memory deduplication uses folder names and cannot promote local lessons | Previous probe: independent projects with the same basename miss each other's shared lesson; saving a local lesson as shared claims success without syncing it. | 6 |
| F12 | P2 | Adding FTS support does not index existing rows | N02: opening a populated store without an FTS table creates an empty index; an existing matching note disappears from search. The setup represents the supported LIKE-only storage path becoming FTS-capable. | 1, 6 |
| F13 | P2 | Recovery drops criteria and cannot identify resolved questions | Previous probe: only two of five criteria appear, with no retrieval pointer; question totals have no open/resolved state. The current total label is accurate, but incomplete for recovery. | 2, 6 |
| F14 | P2 | Empty brief sections pass validation | N11: `GOAL:` followed by `DONE WHEN:` is allowed. The existing test named “empty and missing sections” covers an empty brief and missing headings, not headings with empty contents. | 2 |
| F15 | P2 | Git's display quoting breaks scope checks | N06: with `core.quotePath=true`, `allowed/café.py` is reported outside `allowed/**` because the quoted display string is compared. Host Git settings can hide this defect, so the probe sets the option explicitly. | 3 |
| F16 | P2 | Measurement filters and attribution are inaccurate | Previous probe: `stats --task` includes other tasks. N12: opening an unrelated note marks the latest search as used. Tokens have no recording command; missing costs/usage need explicit unknown handling. | 3, 6 |
| F17 | P2 | Planner handoff and doctor coverage are incomplete | Source contract: Claude planner has Read/Grep/Glob but LARGE supplies a SQLite record ID. Doctor does not check per-host agents/skills and can accept an empty model mapping through `all([])`. These are source findings, not observed host failures. | 4, 5 |
| F18 | Release | CI and real-host qualification are incomplete | Root pytest testpaths omit simpleIDE; existing CI has no separate unittest invocation. No host has completed the live matrix. The kit is untracked in this checkout. | 0, 7 |

### Related risks to cover during the repairs

These are visible failure paths or concurrency hazards in the source; this review did not force each one at runtime. They belong in the same fixes rather than separate subsystems:

- `check_cmd` chooses a log number with an exists-then-write loop. Concurrent checks can select the same path. It also buffers all stdout in RAM and creates the artifact only after the process finishes. Allocate a unique artifact first and stream into it.
- `insert` checks for a duplicate before inserting and commits a record before updating its run. Concurrent duplicates can raise a uniqueness error, and interruption can leave the record/run pair inconsistent. Make each logical write transactional and resolve duplicate inserts atomically.
- `worktree_cmd` rewrites the whole JSON registry without locking. Concurrent adds can lose an entry; interruption after Git changes but before writing state leaves an orphaned operation. Use the existing SQLite store for the small registry and explicit reconciliation with Git.
- Dispatch admission for Claude/Codex checks active children before the lifecycle event records the launch. Simultaneous admissions can exceed three workers. Missing lifecycle events can leave counts stale. Exact enforcement depends on the host exposing correlatable, blocking events; preserve that limitation in documentation.
- `show`/`forget` accept loosely parsed IDs; config, hook and model structures are not consistently validated before attribute access. Add bounded input validation to the affected commands. Do not let a traceback masquerade as successful logging, or silently claim a denied launch when the host only permits advisory output.
- Installed local commands assume invocation at the project root. Verify hook working directories and either render a correct location or explicitly run from the discovered execution root. Global commands must also work from project subdirectories and paths with spaces.

## Design contracts to implement

These decisions keep the repair bounded and remove ambiguity for implementation.

### Identity, task and session

Use the existing task slug as the unique run ID. A completed slug is immutable: retries get a new slug and an optional `retry_of` link. Do **not** add attempt-number joins throughout every table or silently reopen completed runs. An exact duplicate goal for an active run remains idempotent; trying to add a goal to a terminal slug returns a clear error before changing anything.

Give each ledger a persistent random store ID. Keep `P123` and `S123` as convenient local display IDs, but put the store ID/location alongside them in worktree handoffs and exports. Within each store, record numbers must never be reused after deletion. Use `INTEGER PRIMARY KEY AUTOINCREMENT` with a versioned table migration that preserves existing row numbers and UIDs. This prevents future reuse; it cannot reconstruct IDs already reused or the highest deleted ID from before the migration.

Store request host/session identity in dedicated columns instead of overloading free-form `refs`. Add a small session binding table keyed by `(host, session_id)` with active task and primary request ID. Binding must be explicit or derived from an explicitly selected request whose host/session is known. A new session never inherits another session's task because it was most recently updated.

Keep `mem add goal` as the basic CLI. Add `--request Pn` to associate a known original request. Add `sx task bind <slug> --request Pn`, deriving the host/session from that request, with `--host` and `--session` available for deliberate manual binding when capture is unavailable. If no session/request is available, create an unbound task and give a retrieval/binding instruction; do not guess. A binding change is logged, and must not rewrite earlier dispatch ownership.

### Outcomes and observations

Writing a result records evidence; it does not close or accept a run. Add `sx task close <slug> --outcome accepted|failed|abandoned --result Pn --by user|assistant --refs <evidence>` and validate that the result belongs to that task. `blocked` remains an open condition described by records, not an automatic accepted or terminal state. No outcome is inferred from prose.

For the A/B/C comparison, only `--by user` with the actual user decision referenced counts as user acceptance. The flag records attribution; it does not itself prove consent. Ordinary assistant-completed tasks can be distinguished in stats. Existing automatically accepted runs remain preserved with `legacy-unverified` provenance and are excluded from newly verified acceptance totals. Document this reporting change.

A terminal update and its supporting record associations commit together. Repeating the same close is idempotent; changing a terminal outcome is rejected pending an explicit correction procedure, not silently overwritten. A retry uses a new slug.

### Execution directory versus evidence store

Separate `execution_root` (where Git/checks run) from `store_root` (where the task ledger and durable artifacts live). Resolve the store from an explicit `SIMPLEIDE_STORE`, then an ignored `.simpleide/context.json` created for a managed worktree, then the execution root. The context file contains the parent store path, its store ID and the worktree's task. Validate the ID and existence before use. A broken pointer must report an error rather than create an empty replacement ledger.

Keep `SIMPLEIDE_PROJECT` compatible as the execution-root override. Do not repurpose it to point workers at the parent's checkout: that would execute checks against the wrong source tree. `SIMPLEIDE_HOME` continues to control the shared lesson store.

New worktrees write their observations and logs directly into the parent store while executing commands in their own checkout. Existing independent worker stores are backed up/exported before cleanup and references are retained with their original store identity; never merge numeric P IDs by assumption.

### Minimal persistence additions

Use the existing SQLite file and installer directory. No server, dependency framework or background worker is required.

| Location | Additions |
|---|---|
| Ledger metadata | schema version and persistent store UUID; migration provenance |
| `rec` | non-reused numeric IDs; host/session for requests; explicit `resolved_by` link for questions |
| `run` | primary request ID, retry link, outcome provenance/actor and result ID; optional usage source |
| session table | host/session → task/request binding |
| existing `dispatch` | pending/started/returned/cancelled/unknown state, requested versus observed model, correlation identity; pending rows are not counted as observed launches |
| check observation table | linked test record, task, check name/command, command/config fingerprint, execution root, revision fingerprint before/after, exit status, duration, durable artifact |
| worktree table | task/piece/path/branch/base commit, operation state and last diagnostic; replaces mutable JSON registry |
| `.simpleide/install-manifest.json` | manifest version, installed hosts, owned assets/hook entries, hashes and enabled-hook state |
| `.simpleide/context.json` | ignored worktree store pointer; never copied as a portable project setting |

Prefer small helpers in `core/sx.py` for context resolution, migrations, task selection and current check summaries. Keep `core/mem.py` as the compatibility wrapper. Split modules only if implementation becomes clearer enough to justify updating installer/runtime packaging.

## Ordered implementation work

### Step 0 — Establish the regression boundary and CI gate

**Files:** `tests/test_simpleide.py`, `tests/test_sx.py`, `tests/test_regressions.py`, new focused test files under `tests/`, and `.github/workflows/agentnexus.yml` only for the test step.

1. Turn the old and new probe expectations into normal unittest regressions alongside each repair. Preserve audit JSON as historical evidence; do not overwrite it with passing results.
2. Add `python -m unittest discover -s simpleIDE/tests -v` as an independent step to the existing CI job. Do not change root pytest discovery to import these modules indirectly.
3. Isolate HOME, SIMPLEIDE_HOME, project roots and Git configuration in test fixtures. Use installed commands for integration coverage. Keep live host tests separate from offline CI.
4. Capture the baseline 38-test result and expected failures from the new regression cases. Commit fixes with their passing regressions rather than leaving CI intentionally red between repair commits.

Tests that currently expect automatic latest-request binding or implicit acceptance must be updated to the explicit contracts, with replacement regressions proving that ambiguous binding and implicit acceptance are rejected. Preserve their underlying coverage; do not keep the unsafe behavior solely to satisfy an old assertion.

**Done when:** CI explicitly runs the kit's tests; new cases fail for the intended reason on the old implementation. Existing six-defect regressions still run. Python 3.12 runs TOML parsing with no skip; the existing 3.10 CI leg keeps its documented TOML skip, and 3.11 covers parsing in CI.

### Step 1 — Preserve record identity and make migrations atomic

**Depends on:** Step 0 fixtures. **Files:** `core/sx.py` schema/connect/insert/forget helpers; migration and memory tests.

1. Introduce a schema version and store ID. Before a version-changing migration, create a consistent SQLite backup through SQLite's backup API. Do not copy a live database file without its journal state.
2. Migrate `rec` to AUTOINCREMENT, preserving every surviving ID, UID and field. Recreate indexes and FTS triggers deliberately. Perform migration under one serialized transaction and verify foreign/reference integrity for new relations.
3. Add the columns/tables required above through versioned migrations. Import existing worktree JSON once, preserving the source file as a backup until reconciled. Do not automatically assign historical sessions or rewrite old accepted outcomes as verified.
4. Make insert + run association one logical transaction. Resolve concurrent dedup conflicts through SQL uniqueness handling and reselecting the canonical row. Request and test events continue to receive unique event UIDs.
5. Populate a newly created FTS index from all existing records. Add correct update/delete triggers where indexed text may change. Restrict the fallback to FTS unavailability; surface corruption or unrelated SQL failures instead of masking them.
6. Validate `P<number>`/`S<number>` inputs and report missing/deleted records clearly. Existing exported references that cannot be recovered stay unresolved rather than being relabeled.

**Acceptance:** N01 and N02 pass; record IDs and search results survive migration/restart; concurrent first opens and duplicate writes succeed without data loss; injected migration failure rolls back; old fixture databases remain readable; `PRAGMA integrity_check` is clean. Preserve the backup and supply the exact rollback procedure.

### Step 2 — Bind sessions, dispatches and recovery to explicit tasks

**Depends on:** Step 1. **Files:** `core/sx.py` task commands and all hooks; `core/rule.md`; simpleide skill, LARGE guide and brief template; hook regression tests.

1. Implement the binding contract and make request capture retain verbatim body plus host/session metadata. Use the selected primary request when packing a task; subsequent prompts remain additional evidence.
2. Centralize task resolution: explicit validated task/context, matching dispatch intent, then this host/session's binding. Conflicts produce a diagnostic. Remove every project-wide “latest open run” fallback from dispatch, resume and stop.
3. Preserve a validated PreToolUse intent by exact host/session/tool-call identity. A lifecycle event consumes that intent only when correlation is unambiguous. If the host omits the needed join fields, retain an uncorrelated observation; do not invent a task, requested model, or successful block.
4. Count pending admission reservations plus running workers where the host supports blocking admission and stable IDs. Reservations are not dispatch observations. Release on matched cancellation/return; surface unmatched or stale reservations for explicit reconciliation. Do not silently expire a live worker to admit another one. Repeated events remain idempotent.
5. Parse brief sections, accepting both the shipped colon form and supported standalone headings. Require non-whitespace content for GOAL and DONE WHEN; a following heading is not content. Do not impose a brief requirement on lifecycle payloads that never contain one.
6. Resume stays at most five lines: task/store; original request reference; goal; criterion count plus a command that retrieves **all** criteria; open-question count plus retrieval pointer. Quote generated commands correctly. For an unbound session, give a short binding instruction or no context, never another session's task.
7. Stop remains a one-time task warning, scoped to the bound task. Step 3 supplies its current check summary. Logging failures emit a concise diagnostic appropriate to the host; no false claim of enforcement.

**Acceptance:** interleaved A/B captures, goal creation, starts, returns, resume and stops never cross tasks; task switching with an outstanding child retains the child's original task; duplicate and unknown callbacks do not complete another worker; three parallel admissions reject a fourth where enforceable; empty sections are denied; shipped brief examples still pass; an unbound session cannot inherit another user's task. Actual host callback envelopes remain subject to Step 7.

### Step 3 — Make completion and test evidence trustworthy

**Depends on:** Steps 1–2. **Files:** `core/sx.py` check/task/stats/pack/scope/stop; README and skill commands; command/evidence tests.

1. Implement explicit close and immutable terminal slugs as specified above. Remove `insert(result) → accepted`. Update every shipped workflow to record the result and close explicitly. Validate missing/foreign result IDs before any mutation.
2. Allocate each check artifact with an exclusive unique filename before starting the process. Stream combined stdout/stderr to that file; summarize it after exit. Retain output on interruption and record interrupted/error state rather than PASS. This removes the filename race and unbounded stdout buffering.
3. Store a structured check observation in addition to the human-readable test record. Include command/config digest, command exit code, execution root, duration, artifact path, and revision fingerprint before/after execution.
4. For Git projects, fingerprint HEAD and tested worktree contents: tracked changes, deletions, modes and nonignored untracked content. Use NUL-delimited Git paths. Exclude simpleIDE's own volatile DB/artifacts/context and self-generated output by a documented policy. Record both pre/post values; a change during the check marks the observation non-current. Do not call HEAD alone proof that dirty source was tested.
5. A current check must match the check command/config and current source fingerprint. Choose the latest observation **per check name**. Report failed, missing, interrupted and stale checks distinctly in `pack` and stop; a passing lint cannot hide a failed test. Older observations lacking revision data remain historical/unverified.
6. For non-Git projects, label revision freshness unknown unless an explicit file set can be fingerprinted. Research/document tasks may close against recorded non-code evidence; do not manufacture a test requirement where none was configured. Unknown code freshness requires an explicit recorded acceptance exception rather than a green check claim.
7. Accepted closure checks configured required checks and reports any mismatch. An intentional acceptance exception must be explicitly recorded and retained in the close evidence. Failed/abandoned closure can preserve failures without prompting an endless repair loop.
8. Apply `stats --task` before aggregation. Report verified-user, assistant and legacy acceptance separately; report coverage for known tokens/costs instead of treating partial sums as complete totals. Add optional `--tokens` and `--usage-source` inputs alongside manual cost; reject negative/nonfinite numbers and unknown tasks. Do not add provider integrations in this repair.
9. Change Git path collection to `-z` output for both tracked and untracked files, and correctly parse numstat rename records. Compare raw paths, escape them only for display. Keep pack within 25 lines, with retrieval pointers when evidence is longer.

**Acceptance:** N03–N06 pass; test FAIL/lint PASS is visibly failing; a code edit after PASS is stale; changing the configured command makes the old result non-current; check output survives interruption; concurrent checks keep distinct artifacts; task filtering excludes the other task; invalid costs/tokens are rejected; failed/abandoned results never increase accepted counts; terminal-slug reuse fails without modifying records. Unicode, tabs, newline filenames and renames are handled under either `core.quotePath` setting.

### Step 4 — Give worktrees durable context and recoverable lifecycle operations

**Depends on:** Steps 1–3. **Files:** `core/sx.py` context/worktree/pack/export; installed ignore rules in `install.py`; coding/LARGE references and brief template; worktree integration tests.

1. Implement separate execution/store resolution. Add worktree context pointers after Git creates a checkout; keep the pointer ignored. Briefs contain the execution path, installed runtime command, task, store identity and record/export paths.
2. Check whether the worker checkout actually contains the installed runtime and host assets. A worktree only receives committed files. Use a verified global installation or require the local installation to be present in the base commit; otherwise stop before dispatch with a concrete install instruction. Do not assume untracked parent assets were copied by Git.
3. Export the original request and criteria to a task Markdown artifact readable with Read/Grep/Glob. Include source record/store IDs and a content hash. Give this file path to the Claude planner and read-only reviewers; retain their tool restrictions. Regenerate when the task criteria deliberately change and identify the version in briefs.
4. Replace read/modify/write of `worktrees.json` with the small SQLite registry. Reserve a task/piece operation transactionally, release the DB transaction before invoking Git, then record the observed result. Never hold a ledger write lock across a potentially slow Git operation.
5. Reconcile interrupted operations against `git worktree list --porcelain` and branch/commit state. A retry must distinguish already-added/removed/merged from genuinely missing or conflicting state. Ambiguous operations require an explicit repair command with a preview; do not silently forget work.
6. Before merge or clean, preflight **every** affected checkout and evidence store. Before removal, ensure worker records/artifacts are in the durable parent store, or archive a legacy local store using SQLite backup plus artifact copies and a store-ID manifest. Verify the archive before deleting the checkout. Include ignored simpleIDE evidence in this check.
7. Reject cleaning a piece whose branch has not been integrated into the destination, unless a separately explicit discard option is selected. Use Git ancestry, not only the stored `merged` flag. Retain branches by default.
8. Persist each successful removal before moving to the next piece. A retry tolerates an already-removed, verified piece. A merge conflict stops without resetting or discarding changes; after manual resolution, reconciliation identifies the resulting merge before continuing.

**Acceptance:** parent P records are readable from a worker; a check executes against a worker-only file and saves evidence to the parent; two pieces merge in declared order and the final integrated revision gets fresh checks; N07–N09 pass; second-piece dirtiness causes no first-piece deletion; interrupted clean/add/merge resumes safely; concurrent adds retain both pieces; ignored artifacts survive removal; a missing/mismatched store pointer fails clearly; read-only planner receives a readable request file.

### Step 5 — Make installation ownership and updates reliable

**Depends on:** Step 1 metadata; coordinate Step 4 context ignore rules. **Files:** `install.py`, `core/sx.py` doctor, both skill templates, installer/doctor tests.

1. Build the complete install/uninstall plan in memory before mutations. Validate selected hosts (reject an empty list), model-map structure, generated agent syntax, all existing hook JSON and expected paths. The dry run uses the same plan and produces no files.
2. Write a small versioned manifest listing installed hosts and exact owned assets/hook entry signatures. Determine shared-asset consumers from the full installation, not just the current `--tools` argument. An incremental install unions hosts; partial uninstall subtracts them. Remove shared rules/skills only when no consumer remains. Always retain memory databases.
3. Bootstrap a legacy manifest conservatively from matching known generated files/entries. Unknown or edited content is preserved and reported. Do not claim that a filename prefix or arbitrary command substring establishes ownership.
4. Remove hooks by recorded exact structured entry identity, or an exact recognized legacy generated command/entry shape. Preserve user entry bytes and ordering. If a host supplies an official identifier field, use it only after verifying that host's schema; do not invent metadata in host configs.
5. Stage rendered files next to destinations and use atomic replacement. Save overwritten owned files for rollback; on a later apply error, restore already changed files and prior manifest. Write the new manifest last. Do not delete an entire skill directory before successfully staging its replacement. Preserve unowned additions or report a collision.
6. Render an `{SX}` command consistently into both skills, rules and references. For global installs use the installed absolute path with shell-safe quoting; for portable local installs define the execution-root convention and test it from subdirectories. Do not hard-code a parent-checkout path into a portable worktree skill. Correct the printed stats example as part of the same command audit.
7. Preserve enabled-hook state on update; do not unexpectedly disable it when `--hooks` is omitted. Still require explicit opt-in for first enablement. Match existing supported host config versions; reject unsupported/malformed versions before mutation.
8. Extend doctor to read the manifest and check per-host script, agent, skill, rule and hook assets at local/global paths, model roles, JSON/TOML validity and store/context health. Missing optional hooks are informational. Describe files as configured/present; runtime-loaded/enforced status belongs to Step 7. Empty model maps must not pass as complete configuration.

**Acceptance:** old partial-uninstall/global-command cases and N10/N13 pass; invalid input changes zero destination bytes; injected write failure restores the prior installation; repeated install is idempotent; unrelated hooks survive even if their command mentions sx; uninstall one host keeps remaining hosts working; reinstall restores removed assets; dry run is empty of mutations; paths with spaces and project subdirectories work; doctor fails for a deliberately removed agent/skill and succeeds after reinstall.

### Step 6 — Correct memory sharing, search attribution and recovery details

**Depends on:** Steps 1–3; Step 5 for rendered retrieval commands. **Files:** `core/sx.py` memory/search/export/resume; skill docs; memory tests.

1. Deduplicate shared hits by actual local record UID/content identity, not `root.name`. Keep the basename for display only. Apply the limit after deduplication so hidden duplicates do not crowd out useful results; state whether the limit is total or per store (use a total displayed limit).
2. Explicitly sharing an existing local lesson atomically promotes `shared=0` to pending. Attempt sync; print synced, already shared, or queued based on actual state. Duplicate writes stay idempotent and concurrent syncs do not duplicate records.
3. Add `mem resolve Pquestion --decision Pdecision`. Validate both records, kinds and task ownership; set the explicit resolution link. A generic `--refs Pquestion` alone does not prove the question is answered. Update export/resume to distinguish open and resolved questions; retain the decision and reference as evidence.
4. Attribute opening a search result only to a search that actually contained that ID. Add an optional search ID/context for precise attribution; without it, mark only an unambiguous matching search, not the newest unrelated search. Count a lesson once per search/open pair, and avoid cross-session credit. Ordinary direct record access remains possible without changing search-use metrics.
5. Ensure resume's retrieval pointer includes all criteria, including their full bodies, and export identifies the primary request, outcome provenance and current/historical checks. Keep FTS initialization/update behavior covered by Step 1 tests.

**Acceptance:** same-basename projects share correctly; local-to-shared promotion works and queued sync recovers; N12 passes; two sessions searching/opening different records do not credit one another; resolved question count becomes zero; unrelated decisions do not resolve questions; five or more criteria are fully retrievable from the five-line resume message.

### Step 7 — Qualify, document and measure the repaired kit

**Depends on:** all affected offline repairs. **Files:** `README.md`, `PLAN.md` status note, `docs/verified.md`, `docs/comparison.md`, evidence files; generated scratch installations only for trials.

1. Run the full unittest suite on Python 3.12 and the existing CI platform/Python matrix. Run installed-CLI workflows and all old/new audit cases with repaired expectations, saving a new results file. Do not require the historical probe CLI to keep working unchanged if a documented safety contract now requires explicit task binding/outcomes; port those cases into the regression suite and record the mapping.
2. Use one end-to-end scratch workflow: install → capture two sessions → bind tasks → dispatch/return fixtures → worker context → merge → integrated checks → result → explicit close → export → partial uninstall/reinstall. This remains CLI/fixture evidence until repeated through a real host.
3. Qualify the primary host first. Codex is the practical initial candidate because its CLI was available in the earlier trial. Record exact binary/version, visible roles/skills, **actual** launched role/model, hook invocation and denial/advisory behavior, one SMALL and one MEDIUM task, lesson reuse, resume and terminal outcome. Observe a harmless deliberately denied operation; do not execute a destructive command as a test. Keep native trust/permissions intact.
4. At implementation time verify the installed host's payload/config contract against its code or official documentation, then retain representative observed payloads with private content removed. The current fixture shapes cannot establish real registration. Codex's earlier skill discovery does not establish a selectable custom role; its SubagentStart path is advisory. If a feature is unavailable, publish the tested fallback and label the limitation.
5. Repeat only the relevant qualification on Claude Code, Cursor and Antigravity. Antigravity hooks remain deferred until their actual contract is verified. A host can have qualified core commands with unsupported hooks; never label that as enforced guards.
6. Update install/upgrade/rollback instructions and explain terminal slugs, legacy outcomes, store pointers and diagnostics. Link this plan from the README without rewriting the historical original plan as if it described shipped behavior.
7. Review and stage the kit as an isolated change when implementation is ready; this repository has unrelated work and the kit is currently untracked. Do not include unrelated changes or retire AgentNexus components.
8. Run the nine real tasks only after the state/measurement fixes. Freeze each task's criteria and starting revision for A/B/C, isolate task stores and shared-memory carryover between arms, vary arm order, and record user acceptance, observed elapsed time, actual usage/cost coverage, dispatches and real reviewer findings. Preserve failed attempts in denominators. Nine tasks are a pilot; three per size cannot reliably establish a roughly one-in-five reviewer catch rate. Report uncertainty and close results as ties; expand only if the decision depends on them.

**Acceptance:** CI is green; offline tests demonstrate every repaired contract; the primary host completes the live workflow with linked observations; other hosts remain explicitly pending/limited until observed; comparison claims are based on actual runs. The keep/port/retire decision follows the comparison, not installer success.

## Delivery sequence and review gates

| Change set | Scope | Gate before proceeding |
|---|---|---|
| A | Test harness/CI, schema migration, stable IDs, FTS backfill | Existing data retained; failed migration rolls back; old tests plus new identity cases pass |
| B | Session/request binding, dispatch correlation, meaningful brief validation | Interleaved sessions and duplicate events remain isolated |
| C | Explicit outcomes, check evidence/currentness, stats and path parsing | Failures/stale checks cannot appear as verified acceptance |
| D | Worktree store context, readable request export, lifecycle recovery | Evidence survives cleanup and retries; integrated check runs on merged source |
| E | Manifest-based installer, path rendering, rollback and doctor | Partial uninstall and failed update preserve the working installation |
| F | Memory sharing, question resolution and search attribution | Cross-project/recovery scenarios pass with correct IDs and counts |
| G | Primary-host qualification, then remaining hosts and comparison | Claims match recorded host observations and measured outcomes |

Implement sequentially where these sets touch `core/sx.py`; splitting them among simultaneous writers would create avoidable conflicts. Installer tests can be prepared independently after the context/manifest interfaces are fixed, but no parallel agent work is necessary for this plan.

Each change set should contain its behavior change, meaningful regression tests and relevant documentation. Do not write tests that only assert a helper's implementation details. Use negative controls: wrong session, wrong store, stale revision, dirty second worktree, missing asset, and failed check. They must fail for the intended reason before their fix.

## Migration and rollback limits

- Back up local and shared stores before changing their schema; keep IDs intact. Do not reconstruct missing original requests, lost worker databases, past ID reuse, deduplicated old tests or unverifiable host/model observations.
- Old `outcome='accepted'` rows are historical observations of the old implementation, not proof of user acceptance. Preserve them and their legacy provenance.
- Install rollback restores files/manifest, not database history. To revert schema, stop writers and restore the pre-migration SQLite backup with the compatible prior runtime; new post-migration records must be exported first if they are to be retained.
- A moved parent ledger, interrupted Git operation or ambiguous callback must be diagnosable. Prefer an explicit unresolved state to silently binding to a different store/task.
- Keep shell enforcement claims bounded. The current guard is a convenience check for known command forms; expanding it into a shell sandbox is outside these fixes. Host-native permissions remain the execution boundary.

## Commands to reproduce this investigation

From the AgentNexus repository root:

```sh
python3.12 -m unittest discover -s simpleIDE/tests -v
python3.12 simpleIDE/docs/evidence/readiness_probe.py
python3.12 simpleIDE/docs/evidence/followup_probe.py
```

The two audit scripts print expectations and observations and normally exit zero even when expectations are unmet. Their exit codes are harness status, not release gates. Use the unittest regressions as CI gates. Each probe uses temporary projects/stores; neither invokes an IDE or sends work to a model.
