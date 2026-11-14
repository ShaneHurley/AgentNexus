# Upgrades, identity and recovery

The November 11 repair uses schema version 1 for both project and shared ledgers. The first open of a pre-versioned populated database serializes migration and creates `project.db.pre-v1-<random>.bak` (or the corresponding shared-store filename) through SQLite's backup API. Surviving record numbers, UIDs, bodies and timestamps are retained. Migration and FTS initialization commit together; an error rolls back. A new FTS index is rebuilt from existing records. Future schema versions newer than the runtime are refused.

Each store has a persistent random ID. `P12` and `S12` are local display IDs, not portable identities. Exports include store ID and location. AUTOINCREMENT prevents future reuse of deleted numbers; it cannot recover historical reuse or the highest number deleted before migration. References whose contents were already lost remain unresolved. Records supporting new outcome, request, check or resolution associations cannot be deleted; record a correction instead.

Old automatically accepted outcomes retain their original value with `legacy-unverified` provenance. They are excluded from explicit acceptance totals. A result is now evidence only. Close an open task explicitly with its own result, outcome, actor and evidence references. Identical closure is idempotent; a changed terminal outcome or a new goal using that slug is rejected. Retry with a new slug and `--retry-of OLD`. The reporting field `user` means user-attributed closure with recorded references, not independent proof of consent. Only an actual user decision may support it.

## Sessions and dispatch recovery

Capture hooks store request host/session separately from free-form references. Select the original request with `mem add goal ... --request Pn` or `task bind SLUG --request Pn`. When capture is unavailable, use a deliberate `task bind SLUG --host HOST --session ID`. An unbound session receives a binding instruction. It never inherits the newest task. After terminal closure, a new captured prompt remains unassigned until selected for a new task.

`task dispatches SLUG` prints pending, started, returned, cancelled and unknown observations, requested and observed models, and correlation IDs. Admission can reserve slots only when the blocking event supplies stable session/call identity. Unknown lifecycle starts retain their observed model if supplied, but do not acquire an invented task or requested model. Pending reservations count toward the limit; they do not count as observed launches. Starts and returns with conflicting IDs cannot be joined.

A host missing the admission-to-start join can leave both a pending intent and an uncorrelated start. Check host evidence, then reconcile deliberately with `task cancel SLUG --dispatch NUMBER --refs 'observed cancellation or completed worker evidence'`. Do not cancel a live reservation merely to admit another worker. Cancellation is an operator observation, not a fabricated return. If an observed start was cancelled, it remains in observed launch totals. Use the single-parent role fallback when reliable joins or blocking hooks are unavailable.

## Worktrees

Execution root is where Git and checks run (`SIMPLEIDE_PROJECT` remains an execution override). Evidence store selection is: explicit existing `SIMPLEIDE_STORE`, validated `.simpleide/context.json`, then execution root. Managed pointers contain the parent store path/ID and task; missing or mismatched pointers fail without creating a replacement store. Do not set the execution root to the parent merely to retrieve evidence.

Commit the local installation, its manifest and host assets before creating workers, or use a verified global installation. Worktrees receive committed files only. `worktree add` reserves its piece in SQLite, creates Git state outside a write transaction, verifies runtime assets, writes an ignored context pointer, and saves a hashed readable request/criteria artifact in the parent. Give that Markdown path to Read/Grep/Glob-only planners. `pack` regenerates the version when criteria change.

Manage worktrees from the parent checkout. `merge` and `clean` preflight every affected checkout and pointer. Cleanup requires Git ancestry integration unless `--discard` is separately explicit; branches are retained. Legacy independent worker databases and ignored artifacts are backed up into parent artifacts with their own store-ID manifest; numeric IDs are never merged. Managed observations already live in the parent. Cleanup persists each removal, and retry accepts an already removed piece only when its recorded removal has durable archive evidence.

`worktree reconcile SLUG` previews Git/registry status and reserved operation owners. After an interrupted operation, `--apply` may release a reservation whose same-host process is demonstrably gone, mark a verified removal, or recognize an integrated branch. It refuses potentially live owners. Retry `add`, `merge` or `clean` afterward. Resolve and commit a Git merge conflict manually before retry; simpleIDE never resets the conflict. An unexpected missing checkout or moved parent needs explicit investigation/restoration, not a new empty ledger. Old `worktrees.json` is imported once; its source and `.imported.bak` are retained.

## Check evidence

Confirmed configured checks are required for accepted closure. Each observation retains a unique preallocated streamed log, command/config digest, execution path, pre/post revision hashes, duration and exit code. The summary selects the newest observation per configured name. Failed, missing, interrupted, stale and unknown freshness are distinct from `PASS current`; a later lint or a result record does not hide failures.

Git fingerprints include HEAD, tracked changes/deletions/modes, and nonignored untracked content, using NUL-delimited paths. Volatile `.simpleide/project.db*`, `artifacts/`, `context.json`, `worktrees.json*` and `hook-created-*` are excluded; the installed ignore file also excludes these. Project-generated outputs outside those locations remain part of the source fingerprint unless the project deliberately ignores them. A check changing source is stale. Configuration changes also invalidate a previous pass. Non-Git freshness is unknown. An intentional exception requires a task decision plus `task close ... --exception Pn`; its reference stays in the close evidence. Tasks without configured checks can close against non-code evidence.

## Installation rollback

The versioned manifest records full host consumers, file/block hashes and exact hook entries. Incremental installation unions consumers; partial uninstall subtracts them. Edited or unknown collisions fail preflight; unowned additions survive. Existing enabled hooks stay enabled on update; first registration requires `--hooks`. Registration still requires the host's normal trust process. All replacements stage before application; an apply error restores changed files, modes and the previous manifest. Dry run uses the same validation and writes nothing.

Before a deliberate upgrade, retain the prior kit and a filesystem backup of the installation's manifest-listed files plus hook configs. To deliberately roll back runtime files, stop writers and restore those exact backed-up files/manifest, preserving unrelated user changes. An automatic failed-update rollback does not rewind database history.

To roll back a schema, stop all hooks/CLI writers first. Export any post-migration records with the repaired runtime if they must be retained. Use a consistent pre-migration backup and the compatible prior runtime. For example, with actual absolute backup/store paths substituted:

```sh
python3 - /absolute/project.db.pre-v1-ID.bak /absolute/project/.simpleide/project.db <<'PY'
import sqlite3, sys
from pathlib import Path
source = sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True)
target = sqlite3.connect(sys.argv[2])
source.backup(target)
assert target.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
target.close()
source.close()
PY
```

Repeat for the shared store if needed. Do not reopen with the new runtime until intending to migrate again. A backup cannot reconstruct previously deleted evidence, old deduplicated check events or unverifiable host/model observations.

Search attribution requires a matching host/session pair or an explicit matching search ID. A plain show with neither supplies no evidence that the opening belongs to a prior search; it remains ordinary record access and earns no usage credit. Missing identity is not treated as a shared session.

## Upgrading to the gate release (November 2026)

- Check fingerprints now use version 2 and include submodules. After upgrading, every earlier check shows "stale". Re-run `sx check --task <slug>` for open tasks. Closed tasks are not changed.
- An uninitialized or unreadable submodule makes freshness "unknown". Accepted closure then needs fresh checks or an explicit `--exception` decision.
- `worktree merge` and `clean` refuse a worktree that is on another branch or a detached HEAD. Recovery: check out the expected branch in the worker (bring the commits with `git merge --ff-only` or `cherry-pick`), then retry. Merges now use the exact commit and print it.
- A managed worktree without `.simpleide/context.json` refuses to run. Recovery: from the parent checkout, `sx worktree reconcile <slug> --apply`. For a linked worktree you want independent: `sx context standalone`.
- The installer keeps installed model settings. `--models` changes only the hosts selected with `--tools`; it cannot be combined with `--uninstall`.
- Upgrade steps: pull the branch, run `install.py --target <project> --tools <hosts>` (add `--hooks` only if hooks were enabled before; updates keep them), restart the host, run `sx doctor --budgets`.
- Rollback: `git checkout simpleide-v0.2-local -- simpleIDE` in a scratch clone, then run that version's installer over the project. No database schema changed in this release, so stores need no rollback. Check observations recorded under version 2 will look stale to the old runtime; re-run checks.
