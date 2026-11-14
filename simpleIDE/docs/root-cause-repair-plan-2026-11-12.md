# Root-cause repair plan — 12 November 2026

Status: planned, not implemented. Scope: the four reproduced defects in the [independent post-repair review](postrepair-review-2026-11-11.md), plus adjacent cases exercising the same contracts. This refines the earlier repair plan; it does not reopen every prior work item. The current baseline is 67 passing tests, with the four defects reproduced separately in [saved observations](evidence/postrepair-review-2026-11-11.json).

## Why the previous repairs were insufficient

The existing tests established that normal operations worked and several known error paths were handled. They did not establish that the software could distinguish incomplete information, conflicting ownership, or changed intent from a normal operation. Four unsafe substitutions remain:

| Defect | Incorrect assumption | Contract that must replace it |
|---|---|---|
| R4: stale submodule checks | Equal hashes imply all relevant repository content was inspected; a directory can be represented as a deleted file | Evidence is current only when a versioned, complete repository snapshot matches before, after and now |
| R1: wrong worktree branch | A registered path plus a stored branch name identifies the worker's current work | Git repository identity, worktree identity, actual branch and immutable commit must agree with the recorded ownership |
| R2: missing context | Missing configuration means an ordinary independent project | Workspace ownership must be established before opening or creating a writable ledger; missing managed context is a recovery state |
| R3: model reset on uninstall | Every installer invocation should regenerate all remaining hosts from current package defaults | Installation membership changes and model-setting changes are separate operations with explicit scope |

R1 and R2 share a workspace-identity problem and should use the same discovery/validation functions. R4 needs a structured evidence result, not another special-case string in the hash. R3 needs an operation-specific state transition, not another conditional in agent rendering.

Keep the standard library, SQLite, current CLI and existing roles. No new service, agent roster or provider integration is needed.

## Invariants to freeze before implementation

1. **No green state from incomplete evidence.** A missing, unsupported or unreadable snapshot component yields unknown/unverified, never a substitute value that can compare equal to a valid snapshot.
2. **Branch names are mutable references.** Integration results identify exact commit OIDs. Cleanup verifies the actual checkout's current commit, not merely the historical branch name or `merged` flag.
3. **Resolve ownership before mutation.** Git discovery and metadata reads happen before `connect()` can create directories, databases or migrations. Errors must not leave a new independent store behind.
4. **A disposable file cannot be the sole ownership authority.** `.simpleide/context.json` is a validated local cache. Its absence cannot erase a managed-worktree relationship.
5. **Removal preserves surviving configuration.** Removing host A cannot alter host B's model, effort, agent bytes or runtime version as a side effect.
6. **Reconciliation never converts disagreement into success.** It reports conflicts and repairs only relationships supported by matching Git identity, store identity and registry state.
7. **Positive behavior still works.** Valid clean worktrees integrate; complete unchanged snapshots stay current; independent projects can create ledgers; explicit model updates work.

## 1. Replace the digest-only freshness check with a typed repository snapshot — R4

**Files:** `core/sx.py`: `revision`, `check_cmd`, `check_summary`, `close_task`, schema migrations; focused snapshot/check tests; migration documentation.

### Representation and collection

Introduce a small `snapshot_repository(root)` helper returning structured data:

```text
algorithm: "git-source-v2"
state: "complete" | "unknown"
digest: string only when complete
reasons: bounded list of paths and reasons when unknown
```

The digest represents the documented source scope: tracked content, relevant working-tree type/mode changes, and nonignored untracked content, including supported submodules. It is not a claim that arbitrary shell commands have hermetic dependencies or that external services cannot change.

Use Git's NUL-delimited machine output and entry modes to classify paths. Parse `git ls-files --stage -z` for tracked files; enumerate untracked files separately. Do not infer a Git entry's type from `Path.is_file()` alone. Unmerged index stages, unsupported objects, failed enumeration or unreadable inputs make the result unknown.

For regular files, hash the path, entry type, relevant mode and file contents. Distinguish a genuinely missing tracked file from an unreadable file, unexpected directory or failed Git command. Encode records with explicit boundaries, such as length-prefixed fields or canonical serialized records; concatenating arbitrary path/content bytes without framing is not a sufficiently explicit representation.

For a gitlink/submodule:

1. Include the expected gitlink OID from the parent index.
2. Confirm the submodule is initialized as its own checkout. Verify its top-level path rather than allowing Git invoked in an empty directory to discover the parent repository.
3. Include its actual HEAD and recursively collect tracked/nonignored working-tree content, including nested submodules.
4. Track visited Git directories and impose a bounded recursion limit. A cycle, limit, missing initialization or inaccessible component returns unknown with a diagnostic; it never contributes a constant `deleted` value.

Handle symlinks explicitly. Include link text and covered in-repository targets where supported; classify unavailable/external targets as unknown unless an explicit documented check scope accounts for them. Do not silently treat the link name as proof of the target contents.

Retain the documented exclusions for simpleIDE's volatile artifacts and databases. Test the exclusions so normal recording does not invalidate every check, and unrelated source files are not accidentally excluded by an overly broad prefix. Avoid adding generic directory ignores merely to make checks green.

### Consumption and migration

Persist algorithm, state and reasons alongside the pre/post digest for each check observation. Use one helper to decide currentness; callers must consume structured status rather than searching display strings for `PASS current`.

A check is current only if all of these are true:

- The command finished successfully.
- The recorded before, recorded after and current snapshots are complete.
- Their algorithm version and digests agree.
- The configured command/check-set digest and execution identity agree.

Distinguish failed, interrupted, stale and unknown in pack/export/stop output. Accepted closure uses the same structured decision. Preserve the explicit, recorded acceptance-exception route for genuinely unsupported coverage.

Version the database migration. Existing check hashes remain historical under the old algorithm and cannot establish currentness under v2. Do not backfill a v2 digest from today's source into an old observation. Do not rewrite historical terminal outcomes; doctor/export can identify their older evidence coverage.

### Acceptance tests

- The exact R4 reproduction becomes stale, rejects accepted closure, and becomes current only after a successful rerun on the corrected source.
- Changing a submodule's checked-out commit, tracked contents, nonignored untracked contents, executable bit or nested submodule changes the snapshot.
- An unchanged, initialized submodule remains current across repeated inspections.
- Uninitialized submodules, unreadable entries, unmerged indexes and unsupported recursion yield unknown and cannot close accepted without an explicit exception.
- v1 observations cannot be mistaken for v2 evidence.
- Controlled source changes during collection/check execution prevent a current result. Document that pre/post inspection does not freeze external processes; it is not a general filesystem transaction.

## 2. Establish workspace ownership independently of context files — R2 and foundation for R1

**Files:** `core/sx.py`: root/store resolution, worktree creation, reconciliation, doctor; workspace/store tests; recovery documentation. Add ignore rules only if needed for local caches.

### Discovery interface

Introduce a read-only `discover_workspace(root)` result containing:

```text
execution root
Git common directory and worktree Git directory, if present
workspace kind: primary | managed | standalone | unresolved
workspace ID and repository ID, where registered
ledger locator and expected store ID, where registered
task/piece identity for a managed workspace
diagnostics
```

Obtain Git paths through `git rev-parse` and worktree inventory, not by assuming `.git` is a directory or deriving identity from a folder name. Resolve canonical paths and verify Git's reported top-level path. Do not open a writable ledger in this function.

### Durable ownership discovery

Add a small versioned ownership registry beneath the Git common directory, for example `<git-common-dir>/simpleide/workspaces.json`. It maps Git worktree identity to a stable workspace ID and owner ledger location/store ID. Keep task records and lifecycle state in the existing SQLite ledger. The registry is a discovery index, not a second task ledger.

This is necessary because a worker cannot consult its parent SQLite registry after losing the only path to that database. Placing discovery metadata in Git's administrative directory also keeps it outside ordinary checkout cleaning and source commits.

Writes to this registry must be serialized per common directory and use atomic replacement. Reuse a small standard-library locking/reservation mechanism; do not rely on an unlocked JSON read/modify/write. The lock must cover writers using different task stores in the same repository. Record an operation owner and diagnose abandoned reservations; do not automatically steal a possibly live reservation.

Register ownership through explicit pending → active creation states around Git worktree creation. Commit the SQLite record and registry agreement before dispatching a worker. An interruption leaves a discoverable pending operation for reconciliation, not an apparently standalone checkout. Reconcile validates the Git worktree, store UUID and matching SQLite workspace ID before completing registration.

`.simpleide/context.json` becomes a derived cache containing those IDs and locator. A conflicting cache is an error. A missing cache for a registered managed worktree is a recoverable error before any database creation; `worktree reconcile ... --apply` can restore it only after the registry and store agree.

### Resolution rules

| Situation | Behavior |
|---|---|
| Ordinary primary checkout/non-Git project with no managed ownership | Existing independent-store behavior remains available |
| Registered managed worker, valid cache and matching store | Use the parent store; execute commands in the worker |
| Registered managed worker, missing/corrupt cache | Stop before writable DB open; offer verified reconciliation |
| Registered worker, missing store or wrong store UUID | Stop; preserve files and report the ownership conflict |
| Unregistered linked worktree with a valid legacy context | Validate the parent registry and migrate the ownership link explicitly |
| Unregistered linked worktree without enough evidence to distinguish unmanaged from damaged managed | Do not guess; require explicit standalone registration or verified parent binding |

Provide a narrow explicit standalone-registration command for legitimate independent linked worktrees, for example `sx context standalone`. It records that choice after checking for conflicting ownership. This is a local reversible configuration operation, not an automatic permission prompt.

An explicit `SIMPLEIDE_STORE` may select a store for standalone contexts. In an already managed workspace it must match the registered store ID; a different value must not silently bypass ownership. Changing ownership requires a separate explicit repair, not an environment-variable accident.

No scheme can infer missing history if every ownership record and context pointer was destroyed. The unresolved state is deliberate; do not claim perfect automatic recovery from absent evidence.

### Acceptance tests

- Delete only a managed context file: read/write/check fail without creating `project.db`, and reconciliation restores access to the original IDs.
- Test missing registry, corrupted cache, wrong store ID, moved store, `.git` files, spaces in paths and parent checkouts that are themselves linked worktrees.
- A plain project and deliberately standalone linked worktree still work.
- A conflicting explicit store override is rejected before mutation.
- Concurrent worktree creation retains both ownership entries; interruption between Git, SQLite and registry writes leaves recoverable pending state.
- Worker commands continue to execute in the worker directory even though evidence lives in the parent store.

## 3. Integrate and remove exact verified worker commits — R1

**Depends on:** workspace discovery/identity from step 2. **Files:** `core/sx.py`: add/merge/clean/reconcile/archive helpers; worktree schema fields; focused Git integration tests.

### One shared validation function

Create `inspect_managed_piece(...)` and use it in add retry, merge, cleanup and reconciliation. It returns an observed worktree snapshot only when all identities agree:

- Repository/common-directory identity and registered workspace ID.
- Actual worktree path/Git directory and owner store UUID.
- Actual branch equals the registered branch.
- HEAD is attached and resolves to the inspected branch's commit.
- Required clean-state checks pass for tracked/untracked files and submodules; do not let `ignoreSubmodules` configuration hide changes.

A branch mismatch or detached HEAD is a conflict, even if the old registered branch is already an ancestor of the destination. `--discard` may waive integration of the correctly identified piece; it must not waive identity validation.

For this repair, do not add automatic branch adoption. Diagnose the mismatch and let the operator restore the expected branch while preserving commits, or deliberately establish a new piece. `reconcile --apply` must never relabel a mismatched piece as merged.

### Immutable integration evidence

Capture an operation snapshot for every affected piece before mutating the first one: actual branch, worker commit OID, workspace/store IDs and destination branch/HEAD. Serialize mutating operations by repository and destination checkout, not only task slug, so two tasks cannot concurrently merge into the same destination through simpleIDE.

Merge the captured worker commit OID. After success, verify that exact commit is an ancestor of destination HEAD. Record the worker commit and resulting destination commit. Report which commit was integrated; a Boolean `merged` flag is only a summary of that observation.

Before each mutation, revalidate the worktree identity and captured commit. If a later piece changed after whole-operation preflight, stop with a truthful partial-operation record; do not pretend earlier Git merges can be atomically rolled back. On retry, inspect actual ancestry and resume from recorded successful commits.

Before cleanup, inspect the worker again and require its **current actual HEAD** to be integrated. A new commit after an earlier merge invalidates cleanup eligibility. Preserve/archive evidence first, then recheck identity/HEAD and use normal `git worktree remove` without force. Record removal only after verifying the result.

simpleIDE locks serialize simpleIDE operations. They do not prevent arbitrary shells or editors from changing Git state. Require workers to finish before integration/cleanup; revalidate around each mutation and report detected races. Do not claim that `git worktree lock` freezes commits or that a series of Git commands is a transaction.

### Acceptance tests

- R1 fails before both merge and cleanup; no piece changes when a mismatch exists at initial preflight.
- Cover detached HEAD, renamed branch, replacement checkout at the same path, wrong store and wrong repository.
- A commit added after a prior successful merge blocks cleanup until integrated.
- Reconciliation cannot mark a switched branch merged based on the old branch's ancestry.
- Two valid pieces integrate in order, with recorded commit OIDs and verifiable content in the parent.
- Conflicts and injected interruption retain accurate partial progress and are recoverable without resetting unrelated work.
- Concurrent operations for separate tasks sharing one destination cannot mutate it simultaneously through simpleIDE.

## 4. Separate installer membership changes from model updates — R3

**Files:** `install.py`: argument parsing, model resolution, install planning and application; installer tests; README update semantics. Preserve the existing ownership/rollback protections.

### Operation-aware desired state

Change the `--models` parser default to `None`, so the code can distinguish omission from an explicit map. Introduce a pure model-resolution function taking:

```text
operation, selected hosts, installed hosts,
installed effective map, package defaults, explicit supplied map
```

Resolve and validate that state before rendering any assets. Rendering consumes the resolved map; it does not decide user intent or reload defaults independently.

| Operation | Model behavior |
|---|---|
| Fresh install, no `--models` | Package defaults for selected new hosts |
| Fresh install, explicit map | Preserve the documented partial-map/inherit behavior for selected hosts |
| Reinstall, no `--models` | Preserve installed effective model/effort choices while updating authorized runtime/templates |
| Add host, no `--models` | Defaults for the new host; preserve all existing host choices |
| Explicit model update during install/reinstall | Apply only supplied roles/fields for selected hosts; preserve unrelated hosts and unspecified installed fields |
| Partial uninstall | Remove selected membership/assets; preserve surviving model map and agent bytes |
| Last-host uninstall | Remove owned host assets, retain data and the existing runtime/configuration as documented; do not upgrade them incidentally |

Reject `--uninstall --models ...` as conflicting intent. If an explicit map contains changes for hosts outside `--tools`, reject with a scope diagnostic rather than applying a hidden cross-host update. Provide an explicit scoped defaults reset, such as `--reset-models`, only if required to retain a way to opt into newer defaults; never infer reset from omission. Define reset as replacing selected hosts' role mappings with package defaults and reject its combination with `--models` or uninstall.

### Preservation and recovery

Treat the installed `models.json` as effective user configuration, validated against the manifest and installed assets. Store per-host effective model/effort data or a verified configuration reference in the next manifest version. Do not depend on the original external `--models` file still existing.

If installed configuration is missing, malformed or conflicts with recorded ownership, preserve it and stop with a repair diagnostic. Do not rebuild unknown values from current defaults. A legacy uninstall may remove confidently owned selected assets while preserving unrelated assets, but must not regenerate surviving hosts from guesses.

Uninstall should calculate removal and remaining consumer changes directly from ownership. It must not run the general runtime/agent regeneration path. Shared assets remain while consumers remain; unchanged survivors remain byte-for-byte unchanged. An uninstall using a newer source kit must not implicitly install that newer runtime into the surviving installation.

Use the existing staging/rollback transaction for the explicit change set, with the manifest written last. The diff should expose only the operation's authorized scope.

### Acceptance tests

- R3 preserves Codex's model, effort, agent bytes and effective map after removing Cursor, locally and globally.
- Delete the original external custom-model file before uninstall; behavior remains correct.
- Add a host and reinstall without `--models`; existing choices survive even if package defaults changed.
- Uninstall using a newer kit preserves surviving runtime and agent bytes.
- Scoped explicit updates and scoped defaults reset work; out-of-scope updates/conflicting flags fail without writes.
- Missing/corrupt installed maps fail without replacing anything with defaults.
- Existing idempotence, shared-consumer, custom-map, edited-file preservation and rollback regressions remain meaningful.

## Delivery order and migration boundaries

1. **Regression commit preparation:** port R1–R4 into normal unittest cases, with both expected rejection and valid-operation controls. The separate audit probe's exit code is not a CI gate. Capture failures against the current runtime.
2. **Evidence correctness:** implement step 1 and its versioned check-observation migration. This removes the demonstrated false-acceptance path first.
3. **Workspace identity and commit integration:** implement steps 2–3 together around shared discovery/inspection helpers. Validate migrations of existing managed worktrees before enabling destructive operations.
4. **Installer intent:** implement step 4 with an operation/model matrix. This can be developed independently but should land with its full preservation tests.
5. **Combined verification:** run all existing and new tests, migration fixtures, installed workflows and the four-case audit. Save new evidence; do not overwrite historical failures.

Keep schema migration logic incremental. The current migration creates tables only from an unversioned database; adding version 2 must not rerun the initial `CREATE TABLE` block against existing v1 tables. Back up consistently, preserve IDs/store UUIDs and test both fresh initialization and v1 → v2 upgrade, rollback and repeated opens.

New worktree fields should minimally identify repository/workspace and the captured/integrated commits. Leave old rows explicitly unverified until reconciled from current Git/store evidence. Do not fabricate historical integration OIDs. Upgrade the manifest with an explicit version conversion; preserve old effective settings, hashes and ownership.

## Release gate: prove the contracts, not a larger test count

Use ordinary `unittest` parameterization and subprocess fixtures; no new testing framework is required. Tests should vary one invariant at a time and assert side effects as well as exit codes:

- Rejected acceptance leaves outcome unchanged.
- Rejected workspace resolution creates no replacement database.
- Rejected merge/cleanup changes no checkout at initial preflight.
- Successful integration contains the exact worker commit and implementation.
- Partial uninstall leaves survivor hashes unchanged.
- Repeated valid operations are idempotent; interrupted operations remain diagnosable.

Add deterministic mutation points around inspection/application to exercise detected races and rollback. Negative controls should temporarily reintroduce each old assumption and make the corresponding contract test fail. Do not use a test that only checks the name or internals of a new helper.

Final installed workflow: install custom models → create and bind task → create managed workers → exercise missing-context recovery and branch-mismatch rejection → integrate verified commits → run checks including a submodule → change submodule and observe rejected acceptance → repair/rerun/close → export → cleanup → partially uninstall while preserving the remaining installation.

Run the full suite on the existing supported Python/platform matrix and the installed-runtime workflow. Report local versus remote CI results separately. Review the final combined diff specifically for every call site that opens a ledger, declares checks current, marks a piece merged, removes a checkout, or renders models.

This plan does not establish native hook enforcement, actual child-model selection, other-host qualification or comparative savings. Those remain separate observed-runtime tasks already tracked in [live verification](verified.md). Fixing these four deterministic defects needs no additional paid model trials.

## Completion criteria

The work is complete when all four saved reproductions have corresponding passing regression tests, the neighboring invariant cases pass, migrations retain existing evidence and settings, the installed end-to-end workflow succeeds, and no caller can bypass the shared ownership/currentness/intent checks through an older code path. Deliver an issue-to-change-to-test checklist and new observed results. The word “complete” must describe these verified contracts, not imply that every live-host capability is qualified.
