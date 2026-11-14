# Independent post-repair review — 11 November 2026

The implementation is substantially improved, but it is not yet fully correct. The current 67-test suite passes on Python 3.12.0. Four additional scenarios reproduce defects outside that coverage. These were run against disposable repositories and isolated home/shared stores; no user installation or live IDE was changed.

Evidence: [reproduction script](evidence/postrepair_review.py), [observed results](evidence/postrepair-review-2026-11-11.json), [fresh unittest log](evidence/postrepair-unittest-2026-11-11.txt). All findings below are reproduced behavior, not speculative source concerns. Production implementation and the existing Git index were left unchanged during this review.

## R4 — P1: Submodule edits leave stale checks marked current and permit acceptance

Location: `core/sx.py:713–729`, `revision()`; the result feeds `check_summary()` and `close_task()`.

Git lists a submodule as one tracked gitlink path. The fingerprint code sees a directory, falls through to the `deleted` marker, and never incorporates its checked-out commit or files. Changes inside the submodule therefore leave the fingerprint unchanged.

Reproduction:

1. Add a local Git submodule with `dep/value.txt` containing `good`.
2. Configure and run a check asserting that file contains `good`; it passes.
3. Change the submodule file to `broken`.
4. `sx pack` reports `test: PASS current`, while Git reports a dirty submodule.
5. `task close ... --outcome accepted` succeeds without an exception.
6. Running the exact check command again fails with AssertionError.

Repair: recognize gitlink entries explicitly. Include the checked-out submodule commit and relevant working-tree content, recursively for nested submodules, or classify freshness as unknown when that coverage cannot be established. Do not treat a directory as a deleted regular file. Unknown coverage must use the existing explicit-exception path rather than PASS current.

Regression acceptance: dirty submodule content, a changed submodule checkout, and a dirty nested submodule invalidate prior checks. Accepted closure is rejected until fresh checks or an explicit exception. A clean, unchanged supported submodule remains current.

## R1 — P1: Worktree merge/cleanup trusts the recorded branch without checking the actual branch

Location: `core/sx.py:1053–1088`, `_worktree_cmd()`; reconcile at `:1043–1048` has the same assumption.

The inventory contains each checkout's actual branch, but merge/clean only check whether its path exists. They test ancestry and merge the branch stored in SQLite. If the worker switched branches, the stored branch can still be the unchanged baseline.

Reproduction:

1. Create a managed worktree for task `t`, piece `one`.
2. In that checkout, create another branch and commit `worker-change.txt`.
3. Run `worktree merge t`: exit 0, output `merged one`; the parent does not receive the file.
4. Run `worktree clean t`: exit 0 and the checkout is removed even though the implementation was never integrated.

The alternate branch is retained, so the committed change remains recoverable through Git. The defect is false integration reporting and cleanup approval, not demonstrated destruction of the commit.

Repair: preflight actual branch and HEAD against the recorded piece for every worktree before any merge/clean/reconcile mutation. Reject a mismatched branch or detached HEAD with a recovery instruction. If deliberate branch adoption is supported, make it explicit and validate its commit before changing the registry. Check the actual worker commit's ancestry before removal.

Regression acceptance: a switched branch or detached HEAD cannot be marked merged or removed merely because the old branch is an ancestor. The rejection happens before mutating any piece. Restoring/adopting the correct branch permits normal integration and cleanup.

## R2 — P2: Missing managed-worktree context silently creates an independent ledger

Location: `core/sx.py:107–128`, `store_root()` and `ledger()`.

The absence of `.simpleide/context.json` is treated as an ordinary independent checkout. The runtime does not distinguish a genuinely standalone project from a managed worktree whose pointer was lost.

Reproduction: create a task and managed worker, remove only its ignored context file, then run `mem show P1` from the worker. The command exits 0 with `P1: not found` and creates a new local `project.db`. Subsequent writes would enter that separate store instead of the parent.

Repair: establish durable managed-worktree recognition independent of the pointer, using Git's common-directory/worktree identity and the parent registry. For a recognized managed worker, missing context must fail before opening a new writable store. Preserve legitimate independent Git worktrees and the documented explicit store override. Recovery should validate parent store identity before reconstructing a pointer; do not guess by directory name alone.

Regression acceptance: deleting a managed pointer makes read/write/check commands fail clearly without creating a local database. Restoring a verified pointer recovers the original IDs. Ordinary standalone projects remain functional.

## R3 — P2: Partial uninstall resets the remaining host's custom models

Location: `install.py:382`, `:447`, `:451` and the remaining-host agent rendering loop.

Every invocation loads the supplied/default source model map, overwrites installed `models.json`, and regenerates every remaining host. A partial uninstall therefore also changes settings for hosts the user did not uninstall.

Reproduction: install Cursor and Codex with a custom map selecting `custom-worker` for Codex. Then run `--tools cursor --uninstall` without repeating `--models`. Codex remains installed, but its worker model changes from `custom-worker` to `gpt-6-luna`.

Repair: distinguish removal from model updates. Load and preserve the installed effective map for surviving hosts during uninstall. For incremental installation, preserve existing hosts unless the user explicitly supplies an applicable update. Keep shared-asset consumer reconciliation independent of model selection. A partial uninstall should not require the original external model-map file to remain available.

Regression acceptance: partial uninstall preserves remaining agent model/effort fields and installed map; incremental host addition preserves unrelated custom settings; explicit intended model updates still work. Verify behavior for both local and global installs.

## Verification status

- Fresh full suite: 67 passed on Python 3.12.0, no skips. Deliberate interrupted-check output at the end of the log comes from the existing negative test and is not a suite failure.
- Staged whitespace check passed: `git diff --cached --check -- simpleIDE .github/workflows/agentnexus.yml`.
- The CI workflow contains an explicit simpleIDE unittest step. Remote CI was not run by this review.
- The new four-case reproduction completed. Its saved JSON shows observed outputs; exit zero means the reproduction harness ran, not that these four expectations passed.
- Existing qualification documentation still correctly lists native hook enforcement and actual child role/model as unverified. Other hosts and the nine-task comparison remain pending. This review did not run additional paid/model-backed trials.

Fix R4 and R1 before trusting acceptance or automated worktree integration/cleanup. Add all four reproductions to normal regression coverage and repeat the installed workflow. Keep the current historical completion report and this follow-up distinct so the newly found gaps remain traceable.

Reproduce from the repository root:

```sh
python3.12 -m unittest discover -s simpleIDE/tests -v
python3.12 simpleIDE/docs/evidence/postrepair_review.py --out /tmp/simpleide-postrepair-review.json
```
