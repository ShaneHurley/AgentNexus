# Worker assignment: simpleIDE gates G2, G5 and G7

Written 14 November 2026 for a Gemini 3.8 Flash worker (`gemini-3.8-flash`). Run at the highest thinking level your tool offers.

You are completing three of the seven release gates in `simpleIDE/docs/finalization-plan-2026-11-14.md`. The other four (G1, G3, G4, G6) need live host sessions, real tasks and the owner's judgment. They are not yours. Do not attempt them and do not write results for them.

| Gate | Meaning | You are done when |
|---|---|---|
| **G2** | Known false-success paths are closed | Defects R1, R2, R3 and R4 are fixed, each has unit tests that failed before and pass after, and the original reproduction script shows the corrected behavior |
| **G5** | Inside its budgets | `sx doctor --budgets` prints and enforces rule size, skill size, description lengths, an idle-token estimate and hook timings, and passes on a fresh install for every host |
| **G7** | Safe to maintain | Work is committed on branch `simpleide` and tagged, a dedicated CI job runs the simpleIDE suite and is green, and upgrade and rollback are documented |

Read this whole file before you change anything. Then follow it in order. Every step has a "Check" you must pass before moving on.

---

## 0. Ground rules

### 0.1 Where you are

- Repository: `/Users/shurley/Documents/AgentNexus`. Work from the repository root unless a step says otherwise.
- The repo is on branch `main` and has **other people's uncommitted work outside `simpleIDE/`**. You must never stage, commit, revert, stash, format or delete anything outside these paths:
  - `simpleIDE/` (everything inside it)
  - `.github/workflows/agentnexus.yml`
- Python on this Mac: use `python3.12` and `python3.10` explicitly. Plain `python3` is 3.9 here. If `python3.10` is missing, use `python3.11` and say so in your report.
- The baseline is **67 tests, all passing** (one expected skip on Python 3.10, for TOML parsing).

Read the repository's `AGENTS.md` before you start. If anything in it conflicts with this assignment, stop and report the conflict instead of choosing.

### 0.2 Allowed and forbidden

Allowed:
- Edit `simpleIDE/core/sx.py`, `simpleIDE/install.py`, files in `simpleIDE/tests/`, `simpleIDE/README.md`, files in `simpleIDE/docs/`, and `.github/workflows/agentnexus.yml`.
- Create new files only where a step tells you to.
- Run Git commands that read state, the commit and tag commands in this file, and `git push` of branch `simpleide` and its tags.

Forbidden:
- `git add -A`, `git add .` from the repo root, `git commit -a`, `git stash`, `git reset`, `git checkout -- <file>`, `git clean`, `git push --force`, pushing `main`, deleting branches or tags.
- Changing the skills (`simpleIDE/skill/`), agents (`simpleIDE/agents/`), `core/rule.md` or `core/models.json`.
- Deleting, skipping or weakening any existing test assertion. If an old test conflicts with a required fix, follow the exact instruction for that test in this file. If no instruction covers it, stop and report.
- Adding dependencies. Standard library only.
- Database schema changes. None of these fixes needs one. If you believe one is needed, stop and report.
- Fixing anything not listed here. If you find another defect, add it to `simpleIDE/docs/backlog.md` with a reproduction and keep going.
- Writing anything into `simpleIDE/docs/verified.md` or `simpleIDE/docs/comparison.md`. Those hold live evidence only.

### 0.3 Size budgets

| File | Today | Maximum after your work |
|---|---|---|
| `simpleIDE/core/sx.py` | 1,582 lines | 1,800 |
| `simpleIDE/install.py` | 537 lines | 600 |

Check with `wc -l simpleIDE/core/sx.py simpleIDE/install.py` after every phase. If a fix would exceed a budget, stop and report what you would need to remove.

### 0.4 How to work

1. **Keep a progress file.** Create `simpleIDE/docs/worker-progress.md` at the start. After every step, append one line: step number, what you did, the check result. If your session ends or context gets long, a new session restarts from this file.
2. **Test first.** For each defect: write the test, run it, see it fail, save that output, then fix, then see it pass.
3. **Small edits.** Change only the functions named in the step. Do not rename, reformat or reorder unrelated code.
4. **Run the full suite after each fix**, not only the new test:
   ```sh
   PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s simpleIDE/tests 2>&1 | tail -5
   ```
   It must end with `OK`. A line about `test: INTERRUPTED` after `OK` is expected; it comes from a deliberate negative test.
5. **Two attempts rule.** If the same check fails twice after two different fixes, stop and report the failing output, what you tried and your best diagnosis. Do not try a third approach on your own.
6. **Line numbers in this file are from 14 November** and may shift as you edit. Find code by the function name.
7. **Evidence folder.** Save every before and after output under `simpleIDE/docs/evidence/gates-2026-11/`. Create it in Phase 1.

### 0.5 Stop and report immediately if

- Any command would touch files outside the allowed paths.
- `git push` is rejected or asks for credentials.
- The suite fails on a test you did not touch and you cannot see why within two attempts.
- A budget in 0.3 would be exceeded.
- You find that a fix described here is wrong for the code as it actually is.

When you stop, write the reason in `worker-progress.md` and in your reply.

---

## 1. Phase 1: baseline and safety commit (G7, part 1)

### Step 1.1: confirm the baseline

```sh
cd /Users/shurley/Documents/AgentNexus
git status --short -- simpleIDE .github/workflows/agentnexus.yml | head -40
git branch --show-current
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s simpleIDE/tests 2>&1 | tail -5
PYTHONDONTWRITEBYTECODE=1 python3.10 -m unittest discover -s simpleIDE/tests 2>&1 | tail -5
wc -l simpleIDE/core/sx.py simpleIDE/install.py
```

**Check:** both suites report `Ran 67 tests` and `OK`. Python 3.10 shows `skipped=1`. Branch is `main`. Line counts are 1,582 and 537.

If the counts differ, someone changed the code since this file was written. Record the new numbers in the progress file and continue only if the suite is green.

### Step 1.2: create the branch and commit what exists

```sh
git switch -c simpleide            # if the branch already exists: git switch simpleide
mkdir -p simpleIDE/docs/evidence/gates-2026-11
git add simpleIDE .github/workflows/agentnexus.yml
git diff --cached --name-only | grep -v -E '^(simpleIDE/|\.github/workflows/agentnexus\.yml$)' || true
```

The last command must print nothing. If it prints any staged path outside the two allowed locations, stop: something else was staged before you started. Do not unstage it; report it.

```sh
git commit -m "simpleIDE: local build with repairs, 67 tests" -- simpleIDE .github/workflows/agentnexus.yml
git tag -a simpleide-v0.2-local -m "simpleIDE before gate work"
git log --oneline -1
```

`git switch -c` carries the other uncommitted work along unchanged. That is expected and fine.

**Check:** `git show --name-only --format= HEAD | grep -v -E '^(simpleIDE/|\.github/workflows/agentnexus\.yml$)'` prints nothing (every committed file is in an allowed path). The tag exists (`git tag -l 'simpleide-*'`).

### Step 1.3: create the progress and backlog files

Create `simpleIDE/docs/worker-progress.md`:

```markdown
# Worker progress: gates G2, G5, G7

Assignment: docs/worker-gemini-flash-gates-G2-G5-G7.md

| Step | Done | Check result |
|---|---|---|
| 1.1 | baseline | 67 OK on 3.12 and 3.10 |
| 1.2 | branch simpleide, commit, tag simpleide-v0.2-local | only allowed paths committed |
```

Create `simpleIDE/docs/backlog.md` if it does not exist:

```markdown
# simpleIDE backlog

Findings deliberately not fixed yet. Each needs a reproduction.

| ID | Found | What | Reproduction | Why deferred |
|---|---|---|---|---|
```

---

## 2. Phase 2: R4, stale PASS after a submodule change (G2)

### What is wrong

`revision()` (about line 709 of `core/sx.py`) fingerprints the repository so a check can be marked "PASS current" only if nothing changed since it ran. Git lists a submodule as one entry. The code sees a directory, writes the constant `b"deleted"`, and never looks inside. Editing a file inside a submodule therefore leaves the fingerprint unchanged, `pack` still says `PASS current`, and `task close --outcome accepted` succeeds even though the check would now fail.

`close_task()` (about line 1165) also decides acceptance by searching the display text for the string `"PASS current"`. That is fragile and must be replaced by a status value.

### Step 2.1: write the failing tests

Open `simpleIDE/tests/test_repairs.py`. Add `import shlex` to the imports at the top. Add these methods to the `Repairs` class, after the last existing method. Use the existing helpers exactly as shown: `self.repository()`, `self.ok()`, `self.cli()`, `self.git()`, `self.checks()`.

```python
    def submodule_repository(self):
        library = self.base / 'library'
        library.mkdir()
        self.git('init', '-q', root=library)
        (library / 'value.txt').write_text('good\n')
        self.git('add', '.', root=library)
        self.git('commit', '-qm', 'library', root=library)
        self.repository()
        self.git('-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(library), 'dep')
        self.git('commit', '-qam', 'add dependency')
        self.ok('mem', 'add', 'goal', 'Check dependency', '--task', 't')
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote(
            'from pathlib import Path; assert Path("dep/value.txt").read_text() == "good\\n"')
        self.checks({'test': command})
        self.ok('check', '--task', 't')

    def close_accepted(self):
        result = self.ok('mem', 'add', 'result', 'Done', '--task', 't').split()[0]
        return self.cli('task', 'close', 't', '--outcome', 'accepted', '--result', result,
                        '--by', 'assistant', '--refs', 'check observation')

    def test_r4_unchanged_submodule_stays_current(self):
        self.submodule_repository()
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))

    def test_r4_submodule_file_change_invalidates_pass(self):
        self.submodule_repository()
        (self.root / 'dep/value.txt').write_text('broken\n')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        self.assertNotEqual(self.close_accepted().returncode, 0)

    def test_r4_submodule_commit_and_untracked_change_invalidate_pass(self):
        self.submodule_repository()
        (self.root / 'dep/extra.txt').write_text('untracked\n')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        (self.root / 'dep/extra.txt').unlink()
        self.assertIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))
        (self.root / 'dep/value.txt').write_text('good\n')
        self.git('commit', '--allow-empty', '-qm', 'moved', root=self.root / 'dep')
        self.assertNotIn('PASS current', self.ok('pack', '--task', 't', '--base', 'HEAD'))

    def test_r4_uninitialized_submodule_is_unknown_and_blocks_acceptance(self):
        self.submodule_repository()
        self.git('submodule', 'deinit', '-qf', 'dep')
        packet = self.ok('pack', '--task', 't', '--base', 'HEAD')
        self.assertNotIn('PASS current', packet)
        self.assertIn('unknown', packet)
        self.assertNotEqual(self.close_accepted().returncode, 0)
        decision = self.ok('mem', 'add', 'decision', 'Accept without submodule coverage', '--task', 't').split()[0]
        result = self.ok('mem', 'add', 'result', 'Done anyway', '--task', 't').split()[0]
        self.ok('task', 'close', 't', '--outcome', 'accepted', '--result', result, '--by', 'assistant',
                '--refs', 'explicit exception', '--exception', decision)
```

Run only these tests and save the output:

```sh
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s simpleIDE/tests -p test_repairs.py -k r4 -v \
  > simpleIDE/docs/evidence/gates-2026-11/R4-before.txt 2>&1; tail -15 simpleIDE/docs/evidence/gates-2026-11/R4-before.txt
```

**Check:** `test_r4_unchanged_submodule_stays_current` passes. The other three fail. If the unchanged test fails, the fixture is wrong, not the code: fix the fixture (most likely `self.repository()` writes `.gitignore` and commits; read it). If a test you expected to fail passes, stop and report.

### Step 2.2: fix `revision()`

Replace the body of `revision(root)` so it has this behavior. Keep the function name and add an optional `depth=0` parameter.

1. If `depth > 5`, return `None`.
2. `head = git(root, "rev-parse", "HEAD", check=False)`; if it fails, return `None` (unchanged behavior).
3. Start the digest with a version marker so no old fingerprint can ever match a new one:
   `digest = hashlib.sha256(b"git-source-v2\0" + head.stdout.encode())`
4. Read tracked entries with their modes: `git(root, "ls-files", "-s", "-z").stdout.split("\0")`. Each non-empty record is `"<mode> <object> <stage>\t<path>"`. Split once on `"\t"`, then split the left part on spaces.
   - If any record has a stage other than `0`, the index is mid-merge: return `None`.
   - Remember which paths have mode `160000` (submodules).
5. Read untracked, non-ignored files: `git(root, "ls-files", "-z", "--others", "--exclude-standard").stdout.split("\0")`.
6. Process the union of both path sets in sorted order, skipping the same volatile `.simpleide/...` prefixes the current code skips. For each path:
   - Add a framed path to the digest: `digest.update(b"path\0" + path.encode("utf-8", "surrogateescape") + b"\0")`.
   - **Submodule** (mode `160000`): let `sub = root / path`.
     - If `(sub / ".git")` does not exist, return `None`.
     - `top = git(sub, "rev-parse", "--show-toplevel", check=False)`. If it failed, or `Path(top.stdout.strip()).resolve() != sub.resolve()`, return `None`.
     - `inner = revision(sub, depth + 1)`. If `inner is None`, return `None`.
     - `digest.update(b"submodule\0" + inner.encode() + b"\0")`.
   - **Symlink**: same as today (`b"symlink:" + os.readlink(...)`).
   - **Regular file**: same as today (mode, then contents in 64 KB blocks).
   - **Directory that is not a submodule**: return `None`.
   - **Missing**: `digest.update(b"deleted\0")` (a tracked file that was deleted is a real, comparable state).
7. Return `"v2:" + digest.hexdigest()`.

Do not change any caller of `revision()` in this step.

**Check:** run the R4 tests again. All four should now pass, except possibly the parts that depend on Step 2.3 (acceptance decided by text). Run the full suite: it must still be `OK`. Old check observations in a real store now show "stale", which is intended.

### Step 2.3: replace the text search with a status value

1. Add a function `check_states(con, root, task)` that returns a list of `(name, state)` pairs, using exactly the logic now in `check_summary()`:

   | Current text in `check_summary` | `state` value |
   |---|---|
   | `historical/unverified checks` (no config, but old test records) | `"historical"`, name `"*"` |
   | `checks unverified: configuration unconfirmed` | `"unconfirmed"`, name `"*"` |
   | `missing/unverified` | `"missing"` |
   | `interrupted/unverified` | `"interrupted"` |
   | `failed (FAIL)` | `"failed"` |
   | `freshness unknown/unverified` | `"unknown"` |
   | `stale/unverified` | `"stale"` |
   | `PASS current` | `"current"` |

   No config and no old records returns an empty list (non-code tasks), as today.

2. Rewrite `check_summary()` to call `check_states()` and map each state back to **exactly the same display text** as today. Existing tests match that text.
3. In `close_task()`, replace
   `any("PASS current" not in v for v in summaries)`
   with a test on states: acceptance needs every state to be `"current"`. Keep the error message, which lists the display summaries.
4. Search the file for any other `"PASS current"` string comparison used for a decision (not display). Convert it the same way.

**Check:** all R4 tests pass. Full suite `OK` on 3.12 and 3.10. Save:

```sh
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s simpleIDE/tests -p test_repairs.py -k r4 -v \
  > simpleIDE/docs/evidence/gates-2026-11/R4-after.txt 2>&1
```

Append to the progress file. Then commit:

```sh
git add simpleIDE
git commit -m "simpleIDE: submodule-aware check freshness (R4)" -- simpleIDE
```

---

## 3. Phase 3: R1, worktree merge and clean trust a stale branch name (G2)

### What is wrong

`_worktree_cmd()` (about lines 965 to 1090) merges and cleans using the branch name stored in SQLite (`entry["branch"]`). If the worker switched to another branch, the stored branch still points at the untouched baseline. Merge then says `merged one` without bringing in the work, and clean removes the checkout.

`worktree_inventory(root)` already returns `{resolved_path: "refs/heads/<branch>"}`, with `""` for a detached HEAD. The fix uses it.

### Step 3.1: write the failing tests

Add to `test_repairs.py`. `self.installed_repository()` already exists: it installs Codex, commits, and records goal P1 `Split work` and a criterion for task `t`. The worker branch is named `codex/sx-t-<piece>`.

```python
    def switched_worker(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        self.git('checkout', '-qb', 'worker-repair', root=worker)
        (worker / 'worker-change.txt').write_text('required implementation\n')
        self.git('add', 'worker-change.txt', root=worker)
        self.git('commit', '-qm', 'worker implementation', root=worker)
        return worker

    def test_r1_switched_branch_blocks_merge_and_clean(self):
        worker = self.switched_worker()
        self.assertNotEqual(self.cli('worktree', 'merge', 't').returncode, 0)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(worker.exists())
        self.assertFalse((self.root / 'worker-change.txt').exists())
        reconcile = self.ok('worktree', 'reconcile', 't', '--apply')
        with self.db() as c:
            self.assertNotEqual(c.execute("SELECT state FROM worktree WHERE piece='one'").fetchone()[0], 'merged')

    def test_r1_restoring_branch_allows_merge_and_clean(self):
        worker = self.switched_worker()
        self.git('checkout', '-q', 'codex/sx-t-one', root=worker)
        self.git('merge', '-q', '--ff-only', 'worker-repair', root=worker)
        out = self.ok('worktree', 'merge', 't')
        self.assertIn('merged one', out)
        self.assertTrue((self.root / 'worker-change.txt').exists())
        self.ok('worktree', 'clean', 't')
        self.assertFalse(worker.exists())

    def test_r1_detached_head_is_rejected(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        self.git('checkout', '-q', '--detach', root=worker)
        self.assertNotEqual(self.cli('worktree', 'merge', 't').returncode, 0)
        self.assertNotEqual(self.cli('worktree', 'clean', 't', '--discard').returncode, 0)
        self.assertTrue(worker.exists())

    def test_r1_commit_after_merge_blocks_clean(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        (worker / 'first.txt').write_text('first\n')
        self.git('add', 'first.txt', root=worker)
        self.git('commit', '-qm', 'first', root=worker)
        self.ok('worktree', 'merge', 't')
        (worker / 'second.txt').write_text('second\n')
        self.git('add', 'second.txt', root=worker)
        self.git('commit', '-qm', 'second', root=worker)
        self.assertNotEqual(self.cli('worktree', 'clean', 't').returncode, 0)
        self.assertTrue(worker.exists())
        self.ok('worktree', 'merge', 't')
        self.assertTrue((self.root / 'second.txt').exists())
        self.ok('worktree', 'clean', 't')
```

Save the before output with `-k r1` to `R1-before.txt`, as in Step 2.1.

**Check:** `test_r1_restoring_branch_allows_merge_and_clean` may pass already. The switched-branch, detached and commit-after-merge tests must fail. If `test_r1_commit_after_merge_blocks_clean` fails at the second `merge` call instead of at clean, note it: merge currently skips pieces whose stored branch is already integrated, and the fix in 3.2 changes that.

### Step 3.2: fix `_worktree_cmd()`

Make these changes in `_worktree_cmd()` only.

1. **Branch identity check, in the preflight loop** that runs before any merge or clean (the loop commented "Every piece and pointer is checked before the first destructive operation"). For every entry not in state `removed` and present in `inventory`:
   ```python
   actual = inventory[entry["path"]]
   if actual != "refs/heads/" + entry["branch"]:
       raise ValueError("piece %s: worktree is on %s, expected %s; restore the expected branch first"
                        % (entry["piece"], actual or "a detached HEAD", entry["branch"]))
   ```
   This check applies to merge and clean, and `--discard` never skips it.
2. **Capture each worker's commit in the same loop**:
   `heads[entry["id"]] = git(Path(entry["path"]), "rev-parse", "HEAD").stdout.strip()`.
   Replace every `merge-base --is-ancestor entry["branch"] HEAD` test in preflight, merge and clean with the captured commit id: `git(root, "merge-base", "--is-ancestor", heads[entry["id"]], "HEAD", check=False)`.
3. **Merge the commit id, not the branch name**:
   `git(root, "merge", "--no-ff", "--no-edit", heads[entry["id"]], check=False)`.
   After a successful merge, verify the commit is now an ancestor of `HEAD`; if not, raise. Print `merged <piece> <first 12 characters of the commit>`. Keep the existing `merged <piece>` start of the line so existing tests still match.
4. **Merge must not skip a piece just because its state is `merged`.** Decide by ancestry of the captured commit only.
5. **Clean**: the existing integration test now uses the captured current HEAD, so a commit added after an earlier merge blocks cleanup. Just before each `git worktree remove`, re-read the worker's HEAD and branch. If either changed since preflight, raise without removing.
6. **Reconcile with `--apply`**: only mark a piece `merged` if the actual branch equals the recorded branch **and** its current HEAD is an ancestor of `HEAD`. Print the actual branch in the reconcile line.

Do not change `worktree add`, `archive_worker()`, the operation locks in `worktree_cmd()`, or the database schema.

**Check:** all R1 tests pass. Full suite `OK` on both Pythons. Pay attention to these existing tests, which must still pass unchanged: `test_worktree_context_executes_worker_and_preserves_evidence`, `test_cleanup_preflights_all_and_rejects_bad_store`, `test_concurrent_worktree_add_and_missing_runtime`, `test_worktree_legacy_archive_and_interrupted_clean_recovery`, `test_full_installed_workflow`. Save `R1-after.txt`, update progress, then:

```sh
git add simpleIDE
git commit -m "simpleIDE: worktree merge and clean verify actual branch and commit (R1)" -- simpleIDE
git tag -a simpleide-v0.3 -m "R4 and R1 fixed"
```

---

## 4. Phase 4: R2, a lost context file creates a second ledger (G2)

### What is wrong

`store_root(root)` (about line 107) decides which SQLite store a command uses. In a managed worktree, `.simpleide/context.json` points at the parent store. If that file is missing, `store_root()` returns the worker itself, and the next command silently creates a new, empty `project.db` there. Records then split between two ledgers.

### Step 4.1: write the failing tests

```python
    def test_r2_missing_context_fails_without_new_store(self):
        self.installed_repository()
        worker = Path(self.ok('worktree', 'add', 't', 'one').splitlines()[0])
        (worker / '.simpleide/context.json').unlink()
        for args in (('mem', 'show', 'P1'), ('mem', 'add', 'note', 'lost'), ('task', 'dispatches', 't')):
            result = self.cli(*args, root=worker, installed=True)
            self.assertNotEqual(result.returncode, 0, args)
            self.assertIn('reconcile', result.stderr + result.stdout)
        self.assertFalse((worker / '.simpleide/project.db').exists())
        self.ok('worktree', 'reconcile', 't', '--apply')
        self.assertIn('Split work', self.ok('mem', 'show', 'P1', root=worker, installed=True))

    def test_r2_declared_standalone_worktree_keeps_own_store(self):
        self.installed_repository()
        other = self.base / 'standalone-worktree'
        self.git('worktree', 'add', '-q', '-b', 'standalone', str(other))
        self.assertNotEqual(self.cli('mem', 'add', 'note', 'mine', root=other, installed=True).returncode, 0)
        self.ok('context', 'standalone', root=other, installed=True)
        self.ok('mem', 'add', 'note', 'mine', root=other, installed=True)
        self.assertTrue((other / '.simpleide/project.db').exists())

    def test_r2_plain_project_still_creates_store(self):
        self.repository()
        self.ok('mem', 'add', 'note', 'plain')
        self.assertTrue((self.root / '.simpleide/project.db').exists())
```

Save the before output with `-k r2` to `R2-before.txt`.

**Check:** the first two fail; the plain-project test passes. (`context` is not a command yet, so the second test fails on it. That is expected.)

### Step 4.2: fix `store_root()` and add recovery

1. Add a helper `linked_worktree(root)` that returns `True` only when `root` is a Git linked worktree:
   ```python
   r = subprocess.run(["git", "rev-parse", "--git-dir", "--git-common-dir"], cwd=root,
                      capture_output=True, text=True)
   ```
   If `r.returncode != 0` (not a Git repo, or Git missing), return `False`. Otherwise resolve both printed paths relative to `root` and return `True` if they differ.
2. Add a helper `standalone_marker(root)` that returns the path given by `git rev-parse --git-path simpleide-standalone`, resolved relative to `root`. This file lives inside the worktree's private Git directory, so it is never committed and needs no `.gitignore` change.
3. In `store_root()`, in the branch where there is no `SIMPLEIDE_STORE` and no pointer file, before `return root`:
   ```python
   if linked_worktree(root) and not standalone_marker(root).exists():
       raise ValueError("this is a Git linked worktree with no simpleIDE context; from the parent "
                        "checkout run: sx worktree reconcile <task> --apply, or declare it independent "
                        "with: sx context standalone")
   ```
   This runs before `connect()` can create anything. Do not change the rest of `store_root()`.
4. Add the command `sx context standalone`. In `main()`, add a parser `context` with one positional choice `standalone`. Behavior: if `.simpleide/context.json` exists, refuse ("managed worktree; use worktree reconcile"). Otherwise write the marker file with `{"declared": <timestamp>}` and print its path. It must work in a linked worktree that has no store yet, so it must not call `ledger()` or `store_root()`.
5. Extract the code in `_worktree_cmd()` that writes `context.json` during `add` (it writes `store_root`, `store_id` and `task`, then adds the file to `info/exclude`) into a helper `write_context(path, root, con, slug)`. Call it from `add` exactly as before.
6. In `_worktree_cmd()` `reconcile`, when `--apply` is given: for each entry that is present in the inventory, whose actual branch matches, and whose `context.json` is missing, call `write_context()` and print `restored context for <piece>`.

### Step 4.3: update one existing test that relied on the old behavior

`test_worktree_legacy_archive_and_interrupted_clean_recovery` deletes the context file of worktree `one` and then records a finding there, to simulate a legacy independent worker store. That now fails by design. Change only this: directly after `context.unlink()`, add

```python
        self.ok('context', 'standalone', root=one, installed=True)
```

Everything else in that test stays the same. It still proves that independent worker evidence survives cleanup.

**Check:** R2 tests pass. Full suite `OK` on both Pythons. Confirm with `grep -n "context.json" simpleIDE/core/sx.py` that every place that reads the pointer still behaves as before when the file exists. Save `R2-after.txt`, update progress, commit:

```sh
git add simpleIDE
git commit -m "simpleIDE: refuse to create a second ledger in a managed worktree (R2)" -- simpleIDE
```

---

## 5. Phase 5: R3, uninstalling one host resets another's models (G2)

### What is wrong

In `install.py`, `--models` defaults to the package's `core/models.json` (about line 344). Every run loads that map (about line 382), writes it to the installed `.simpleide/models.json` (about line 447), and re-renders every remaining host's agents from it. Uninstalling Cursor therefore resets a custom Codex worker model back to the default.

### Step 5.1: write the failing tests

```python
    def custom_models(self):
        custom = self.base / 'custom-models.json'
        custom.write_text(json.dumps({'codex': {'worker': {'model': 'custom-worker'}}}))
        return custom

    def test_r3_partial_uninstall_preserves_surviving_models(self):
        custom = self.custom_models()
        self.ok('--target', str(self.root), '--tools', 'cursor,codex', '--models', str(custom), install=True)
        agent = self.root / '.codex/agents/sx-worker.toml'
        installed = self.root / '.simpleide/models.json'
        agent_before, models_before = agent.read_bytes(), installed.read_bytes()
        self.assertIn(b'custom-worker', agent_before)
        custom.unlink()
        self.ok('--target', str(self.root), '--tools', 'cursor', '--uninstall', install=True)
        self.assertEqual(agent_before, agent.read_bytes())
        self.assertEqual(models_before, installed.read_bytes())
        self.ok('--target', str(self.root), '--tools', 'cursor', install=True)
        self.assertIn('custom-worker', agent.read_text())
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        self.assertIn('custom-worker', agent.read_text())

    def test_r3_global_partial_uninstall_preserves_models(self):
        custom = self.custom_models()
        self.ok('--global', '--tools', 'cursor,codex', '--models', str(custom), install=True)
        home = Path(self.env['HOME'])
        agents = list(home.rglob('sx-worker.toml'))
        self.assertEqual(len(agents), 1, agents)
        before = agents[0].read_bytes()
        self.ok('--global', '--tools', 'cursor', '--uninstall', install=True)
        self.assertEqual(before, agents[0].read_bytes())

    def test_r3_conflicting_model_flags_fail_without_writes(self):
        custom = self.custom_models()
        self.ok('--target', str(self.root), '--tools', 'cursor,codex', install=True)
        before = self.snapshot()
        result = self.cli('--target', str(self.root), '--tools', 'cursor', '--uninstall', '--models', str(custom), install=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
        result = self.cli('--target', str(self.root), '--tools', 'cursor', '--models', str(custom), install=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())
```

The last call supplies a Codex setting while selecting only Cursor. Codex is installed, so that would be a hidden change to a host the user did not select, and it must be rejected.

Save the before output with `-k r3` to `R3-before.txt`.

**Check:** all three fail on the current code (the conflicting-flags test fails because the current installer accepts both calls).

### Step 5.2: fix `install.py`

1. Change the parser: `ap.add_argument("--models", default=None, help=...)`. Update the help text: "model map to apply to the selected hosts; omitted means keep installed settings".
2. Add a pure function `resolve_models(supplied, installed, defaults, selected, previous_hosts, uninstall)`. It returns the full map to persist, or raises `ValueError`. It reads no files.
   - `supplied`: the parsed `--models` file, or `None`.
   - `installed`: the parsed installed `.simpleide/models.json`, or `None` if missing.
   - `defaults`: the parsed package `core/models.json`.
   - `selected`: the set from `--tools`.
   - `previous_hosts`: the `existing_hosts` set that `install_plan()` already computes. It includes hosts found by the legacy byte-match discovery, not only the manifest's list. Call `resolve_models()` only after `existing_hosts` has been computed.

   Rules, in this order:
   1. If `uninstall` and `supplied is not None`: raise `"--models cannot be combined with --uninstall"`.
   2. If `supplied` has an entry for a host that is in `previous_hosts` but not in `selected`: raise `"--models would change installed host <name> that is not in --tools"`.
   3. Start with a copy of `installed` if it is a dict, otherwise a copy of `defaults`. Keep every key, including `_readme`.
   4. For each host in `TOOLS`:
      - Host in `previous_hosts` **and** `installed` has a dict for it: keep the installed entry. If `supplied` has an entry for this host, update only the supplied roles on top of it (`{**installed_entry, **supplied_entry}`).
      - Otherwise (a host not installed before): if `supplied is None`, use `defaults[host]`. If `supplied` is given, use `supplied.get(host, {})` and fill each missing role with `{"model": "inherit"}`. That is today's documented partial-map behavior; keep it.
   5. Make sure every host has all four roles (`planner`, `worker`, `tester`, `reviewer`), filling missing ones with `{"model": "inherit"}`, as the current code already does after validation.
3. In `install_plan(args)`:
   - Load `supplied` only if `args.models` is set, and run the **existing** shape validation on it (the block that starts `roles = {"planner", ...}` and raises "invalid/empty model mapping"). Keep those checks; just run them on `supplied` instead of on a file that is always present.
   - **Important:** that existing block ends with a loop, `for tool in TOOLS: mapping = models.setdefault(tool, {})`, that adds every host to the map with `inherit` roles. Do **not** run that fill-in loop on `supplied`. If you do, every host appears in `supplied` and rule 2 below rejects every call. The fill-in happens only inside `resolve_models()` (its rule 5).
   - Load `installed` from `mem_dir / "models.json"` if it exists; if it is not valid JSON, raise `ValueError("installed models.json is unreadable; repair it before reinstalling")`. Do not fall back to defaults silently.
   - Call `resolve_models()` after `existing_hosts` is computed and before any rendering. Use its result everywhere the old `models` variable was used.
   - Raise these `ValueError`s before any write. The installer's existing error path already returns exit code 2 and writes nothing.
4. Do not change hook handling, ownership hashing, staging or rollback.

**Check:** R3 tests pass. Full suite `OK` on both Pythons. Pay attention to `test_invalid_shapes_fail_before_mutation_without_tracebacks` and the tests in `test_simpleide.py` that pass `--models`. If an existing test passes a full four-host map while selecting fewer tools on an install where those other hosts are installed, rule 2 will reject it. In that case, stop and report the test name and the call; do not change the rule or the test on your own.

Save `R3-after.txt`, update progress, commit:

```sh
git add simpleIDE
git commit -m "simpleIDE: installer keeps surviving hosts' model settings (R3)" -- simpleIDE
```

### Step 5.3: confirm with the original reproduction script

```sh
python3.12 simpleIDE/docs/evidence/postrepair_review.py --out simpleIDE/docs/evidence/gates-2026-11/postrepair-after.json > /dev/null
python3.12 - <<'PY'
import json
d = {o['id']: o for o in json.load(open('simpleIDE/docs/evidence/gates-2026-11/postrepair-after.json'))['observations']}
r1, r2, r3, r4 = d['R1_branch_mismatch'], d['R2_missing_context'], d['R3_partial_uninstall_models'], d['R4_submodule_freshness']
checks = {
  'R1 merge refused': r1['merge']['code'] != 0,
  'R1 clean refused': r1['cleanup']['code'] != 0,
  'R1 worker kept': not r1['worker_removed'],
  'R2 read refused': r2['read']['code'] != 0,
  'R2 no new store': not r2['replacement_database_created'],
  'R3 codex agent unchanged': r3['codex_agent_unchanged'],
  'R4 no PASS current': 'PASS current' not in r4['packet']['stdout'],
  'R4 close refused': r4['close']['code'] != 0,
}
for k, v in checks.items(): print(('OK   ' if v else 'FAIL ') + k)
raise SystemExit(0 if all(checks.values()) else 1)
PY
```

Do not edit `postrepair_review.py` or the original `postrepair-review-2026-11-11.json`. They are historical evidence.

**Check:** all eight lines print `OK`. **Gate G2 is met.** Record it in the progress file.

---

## 6. Phase 6: doctor enforces the budgets (G5)

### What is needed

The design sets these budgets. `sx doctor` checks files and store health but does not print or enforce any of them.

| Budget | Limit | Measured on |
|---|---|---|
| Always-on rule block | 2,500 bytes | The managed block between `<!-- simpleIDE:start` and `<!-- simpleIDE:end -->`, including the markers, in each installed rules file |
| `simpleide` skill | 3,072 bytes | Each installed `skills/simpleide/SKILL.md` |
| Each agent and skill description | 400 characters | The `description:` line of each installed `.md` agent and `SKILL.md`, and `description = "..."` in each Codex `.toml` agent |
| Idle cost per host | 1,000 tokens (estimate) | (rule block bytes + sum of that host's agent and skill description characters) / 4 |
| Each hook handler | 100 ms | Median of 3 timed runs of each of the six handlers on harmless input, after 1 warm-up run |

### Step 6.1: write the tests first

Add to `test_repairs.py`:

```python
    def test_g5_doctor_budgets_pass_on_fresh_install(self):
        for tools in ('claude', 'cursor', 'codex', 'antigravity'):
            with self.subTest(tools=tools):
                root = self.base / ('budget-' + tools)
                root.mkdir()
                self.ok('--target', str(root), '--tools', tools, install=True)
                out = self.ok('doctor', '--budgets', root=root, installed=True,
                              env={'SIMPLEIDE_HOOK_BUDGET_MS': '10000'})
                for label in ('rule block', 'SKILL.md', 'description', 'idle estimate', 'hook capture-request',
                              'hook dispatch-guard', 'hook shell-guard', 'hook return-log', 'hook stop-check', 'hook resume'):
                    self.assertIn(label, out)

    def test_g5_doctor_budgets_fail_when_exceeded(self):
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        result = self.cli('doctor', '--budgets', installed=True, env={'SIMPLEIDE_HOOK_BUDGET_MS': '0'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('OVER', result.stdout)

    def test_g5_plain_doctor_reports_sizes_without_timing(self):
        self.ok('--target', str(self.root), '--tools', 'codex', install=True)
        out = self.ok('doctor', installed=True)
        self.assertIn('rule block', out)
        self.assertNotIn('hook resume', out)
```

`SIMPLEIDE_HOOK_BUDGET_MS` overrides the 100 ms limit, so CI runners that start Python slowly do not make the suite flaky. The second test sets it to 0 so timing must fail. Save the before output with `-k g5` to `G5-before.txt`.

**Check:** all three fail (the `--budgets` flag does not exist yet).

### Step 6.2: implement

In `core/sx.py`:

1. Add `budget_report(install_dir, manifest, timing)` returning `(lines, ok)`. Find installed files through `manifest["assets"]` (keys are paths relative to `install_dir.parent`; `kind` is `"block"` for the rule):
   - For each `block` asset: extract the managed block text with the same regex `doctor_cmd()` already uses, and measure `len(block.encode())`.
   - For each asset whose path ends with `skills/simpleide/SKILL.md`: measure bytes.
   - For each asset that is an agent file (`agents/sx-*.md`, `agents/sx-*.toml`) or a `SKILL.md`: read its description. For `.md`: the value after `description:` in the front matter. For `.toml`: the string after `description =`; parse it with `json.loads()` on the quoted part, or `tomllib` when available.
   - Idle estimate per host in `manifest["hosts"]`: the largest rule block plus the descriptions of that host's agents and skills, divided by 4. Decide which files belong to a host using the `consumers` list recorded on each asset.
   - Print one line per measurement in this form, with `OVER` when the limit is exceeded and `ok` otherwise:
     `budget rule block AGENTS.md: 1,760 / 2,500 bytes ok`
     The label words in the test (`rule block`, `SKILL.md`, `description`, `idle estimate`, `hook <name>`) must appear.
   - If `timing` is true: create a `tempfile.TemporaryDirectory()`. For each handler, run `[sys.executable, str(Path(__file__).resolve()), "hook", handler, "--host", host]` with `cwd` and `SIMPLEIDE_PROJECT` set to the temp directory and `SIMPLEIDE_HOME` set to a `shared` folder inside it, so no real ledger is written. Use `host` = the first installed host that has hooks support (`claude`, `cursor` or `codex`), else `codex`. Input payloads:

     | Handler | stdin |
     |---|---|
     | capture-request | `{}` |
     | dispatch-guard | `{}` |
     | shell-guard | `{"command": "true"}` |
     | return-log | `{}` |
     | stop-check | `{}` |
     | resume | `{}` |

     Time with `time.monotonic()`. One warm-up run, then the median of 3. Limit: `float(os.environ.get("SIMPLEIDE_HOOK_BUDGET_MS", "100"))`. The exit code of the hook does not matter for timing.
2. In `doctor_cmd(root)`: add a `timing` parameter. After the existing checks, call `budget_report(install_dir, manifest, timing)`, print its lines, and combine its `ok`. Size budgets are always reported and enforced. Hook timing only runs with `--budgets`.
3. In `main()`: add `--budgets` to the `doctor` parser and pass it through.
4. Keep doctor's existing last line exactly as it is (`Files configured/present only. Live role discovery, ...`). `tests/test_sx.py` asserts that text. Print the budget lines before it.

**Check:** the G5 tests pass, and the full suite is `OK` on both Pythons. Then produce evidence on a real fresh install of every host:

```sh
cd /tmp && rm -rf sx-g5 && mkdir sx-g5 && cd sx-g5
for t in claude cursor codex antigravity; do
  mkdir $t && python3.12 /Users/shurley/Documents/AgentNexus/simpleIDE/install.py --target $t --tools $t > /dev/null
  (cd $t && python3.12 .simpleide/sx.py doctor --budgets) > /Users/shurley/Documents/AgentNexus/simpleIDE/docs/evidence/gates-2026-11/G5-doctor-$t.txt 2>&1
  echo "$t exit $?"
done
cd /Users/shurley/Documents/AgentNexus
grep -h -E 'budget|OVER' simpleIDE/docs/evidence/gates-2026-11/G5-doctor-*.txt
```

Use `/tmp`, not a folder inside the repo. These are disposable projects.

**Check:** all four exit 0, no `OVER` anywhere, and every hook median is under 100 ms with the default limit. If a hook is over 100 ms, record the numbers. Do not raise the limit and do not try to optimize hooks. Stop and report: that is a real finding for the owner.

**Gate G5 is met** when this passes. Save `G5-after.txt`, update progress, and commit:

```sh
git add simpleIDE
git commit -m "simpleIDE: doctor reports and enforces size and timing budgets (G5)" -- simpleIDE
```

---

## 7. Phase 7: CI, documentation and release tag (G7, part 2)

### Step 7.1: give simpleIDE its own CI job

In `.github/workflows/agentnexus.yml` the simpleIDE suite is a step inside the `offline` job, after AgentNexus steps. If any earlier step fails, the simpleIDE step never runs. Make it independent:

1. Remove the step named `simpleIDE regression suite` from the `offline` job. Change nothing else in that job.
2. Add a new job at the end of `jobs:`, with the same indentation as `offline:`:

```yaml
  simpleide:
    timeout-minutes: 10
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-latest
            python: "3.11"
          - os: ubuntu-latest
            python: "3.12"
          - os: macos-latest
            python: "3.10"
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - name: simpleIDE regression suite
        env:
          PYTHONDONTWRITEBYTECODE: "1"
        run: python -m unittest discover -s simpleIDE/tests -v
```

The tests need only Python and Git, both present on GitHub runners, so this job does not install AgentNexus's dependencies.

**Check:** validate the YAML and confirm the step moved:

```sh
grep -n "simpleIDE regression suite" .github/workflows/agentnexus.yml
grep -n "^  simpleide:" .github/workflows/agentnexus.yml
python3.12 -c "import yaml; yaml.safe_load(open('.github/workflows/agentnexus.yml')); print('yaml ok')" 2>&1 | tail -1
```

The suite name must appear exactly once, under the new job. If the last command says `No module named 'yaml'`, do not install anything; compare the new job's indentation by eye with the `offline:` job instead.

### Step 7.2: write the documentation

1. **`simpleIDE/docs/migrations-and-recovery.md`**: add a section `## Upgrading to the gate release (November 2026)` covering:
   - Check fingerprints now use version 2 and include submodules. After upgrading, every earlier check shows "stale". Re-run `sx check --task <slug>` for open tasks. Closed tasks are not changed.
   - An uninitialized or unreadable submodule makes freshness "unknown". Accepted closure then needs fresh checks or an explicit `--exception` decision.
   - `worktree merge` and `clean` refuse a worktree that is on another branch or a detached HEAD. Recovery: check out the expected branch in the worker (bring the commits with `git merge --ff-only` or `cherry-pick`), then retry. Merges now use the exact commit and print it.
   - A managed worktree without `.simpleide/context.json` refuses to run. Recovery: from the parent checkout, `sx worktree reconcile <slug> --apply`. For a linked worktree you want independent: `sx context standalone`.
   - The installer keeps installed model settings. `--models` changes only the hosts selected with `--tools`; it cannot be combined with `--uninstall`.
   - Upgrade steps: pull the branch, run `install.py --target <project> --tools <hosts>` (add `--hooks` only if hooks were enabled before; updates keep them), restart the host, run `sx doctor --budgets`.
   - Rollback: `git checkout simpleide-v0.2-local -- simpleIDE` in a scratch clone, then run that version's installer over the project. No database schema changed in this release, so stores need no rollback. Check observations recorded under version 2 will look stale to the old runtime; re-run checks.
2. **`simpleIDE/README.md`**: in the commands section add `sx context standalone`, `sx doctor --budgets` and one sentence on `--models` behavior. Keep the README's existing structure. Keep additions under 15 lines.
3. **`simpleIDE/docs/gates-G2-G5-G7-completion.md`**: create it with:
   - A table: defect or gate, root cause in one line, change made (functions), tests that prove it (method names), before and after evidence files.
   - The exact commands you ran for final verification and their observed results (test counts per Python version, the eight `OK` lines from Step 5.3, the doctor summary per host, CI status from Step 7.4).
   - A section **Not covered by this work**: G1, G3, G4, G6; live hook enforcement; actual child model; anything you added to the backlog.
4. **`simpleIDE/docs/finalization-plan-2026-11-14.md`**: add one line directly under the title:
   `> Status: gates G2, G5 and G7 were completed by the worker assignment in worker-gemini-flash-gates-G2-G5-G7.md; see gates-G2-G5-G7-completion.md. R2, R3 (Stage 5.1, 5.2) and doctor budgets (Stage 4.3) were done early.`
   Change nothing else in that plan.
5. Add one line directly under the title of each older plan:
   - `simpleIDE/docs/root-cause-repair-plan-2026-11-12.md`: `> Superseded: the four defects it targets were fixed with smaller changes; see gates-G2-G5-G7-completion.md.`
   - `simpleIDE/docs/repair-plan-2026-11-11.md`: `> Superseded by finalization-plan-2026-11-14.md; its follow-up defects are closed in gates-G2-G5-G7-completion.md.`

**Check:** every relative link you wrote resolves:

```sh
python3.12 - <<'PY'
import re, pathlib
bad = []
for p in pathlib.Path('simpleIDE').rglob('*.md'):
    for link in re.findall(r'\]\(([^)#]+)', p.read_text()):
        if '://' in link: continue
        if not (p.parent / link).exists(): bad.append((str(p), link))
print(bad or 'all links resolve')
PY
```

Report any broken link you did not create; fix only the ones you created.

### Step 7.3: final local verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s simpleIDE/tests -v > simpleIDE/docs/evidence/gates-2026-11/unittest-python312.txt 2>&1; tail -4 simpleIDE/docs/evidence/gates-2026-11/unittest-python312.txt
PYTHONDONTWRITEBYTECODE=1 python3.10 -m unittest discover -s simpleIDE/tests -v > simpleIDE/docs/evidence/gates-2026-11/unittest-python310.txt 2>&1; tail -4 simpleIDE/docs/evidence/gates-2026-11/unittest-python310.txt
python3.12 -m py_compile simpleIDE/core/sx.py simpleIDE/install.py
wc -l simpleIDE/core/sx.py simpleIDE/install.py
git diff --check -- simpleIDE .github/workflows/agentnexus.yml
```

**Check:** both suites `OK` with more than 67 tests (one skip on 3.10). Line counts within budget. No whitespace errors.

Commit and tag:

```sh
git add simpleIDE .github/workflows/agentnexus.yml
git commit -m "simpleIDE: dedicated CI job, upgrade and rollback docs (G7)" -- simpleIDE .github/workflows/agentnexus.yml
git tag -a simpleide-v0.3.1 -m "Gates G2, G5, G7 met locally"
git diff --name-only main...HEAD | grep -v -E '^(simpleIDE/|\.github/workflows/agentnexus\.yml$)' || echo "only allowed paths"
```

The last command must print `only allowed paths`.

### Step 7.4: push and confirm CI

```sh
git push -u origin simpleide
git push origin simpleide-v0.2-local simpleide-v0.3 simpleide-v0.3.1
```

If either push is rejected or asks for credentials, stop and report. Do not change remotes, do not use another authentication method, do not force.

The workflow runs on every push. Watch it:

```sh
gh run list --branch simpleide --limit 3
gh run watch <run-id>            # the newest "AgentNexus checks" run
gh run view <run-id> --json jobs --jq '.jobs[] | [.name, .conclusion] | @tsv'
```

If `gh` is not installed or not signed in, give the owner this link in your report and mark CI as "pushed, result not observed": `https://github.com/ShaneHurley/AgentNexus/actions?query=branch%3Asimpleide`

**Check:** all three `simpleide (...)` jobs conclude `success`. The `offline` jobs belong to AgentNexus. Report their result, but they do not decide G7, and you must not try to fix them.

If a `simpleide` job fails: read its log with `gh run view <run-id> --log-failed`. If the cause is in simpleIDE code or tests, fix it, run the local suites again, commit, push, and re-check. Two attempts at most (rule 0.4.5). Typical CI-only causes: a missing Git identity in a code path the tests did not configure, a path that resolves differently on Linux, or timing. Never mark a CI-only failing test as skipped.

Write the CI result into `gates-G2-G5-G7-completion.md`, commit it, and push once more.

**Gate G7 is met** when the `simpleide` jobs are green, the tags are pushed, and the documentation from 7.2 is committed.

---

## 8. Final self-check before you report

Go through every line. Answer each with the evidence file or command output. Write the filled list at the end of `worker-progress.md`.

**G2**
- [ ] R4: four tests, before and after files saved, all pass
- [ ] R4: `close_task` decides from state values, not display text
- [ ] R1: four tests, before and after files saved, all pass
- [ ] R1: merge uses the captured commit; output names it
- [ ] R2: three tests, before and after files saved, all pass; one existing test updated exactly as Step 4.3 says
- [ ] R3: three tests, before and after files saved, all pass
- [ ] `postrepair-after.json` check prints eight `OK` lines

**G5**
- [ ] Three G5 tests pass
- [ ] `doctor --budgets` exits 0 on a fresh install of each of the four hosts, files saved
- [ ] Every hook median under 100 ms at the default limit, or the overage reported

**G7**
- [ ] Branch `simpleide` with one commit per phase; no file outside the allowed paths committed
- [ ] Tags `simpleide-v0.2-local`, `simpleide-v0.3`, `simpleide-v0.3.1` pushed
- [ ] Dedicated `simpleide` CI job green on all three matrix entries, or "not observed" with the link
- [ ] Upgrade and rollback section, README additions, completion report, status lines in the three plans
- [ ] All relative links resolve

**Budgets and scope**
- [ ] `sx.py` at or under 1,800 lines, `install.py` at or under 600
- [ ] No changes to skills, agents, `rule.md`, `models.json`, `verified.md`, `comparison.md`
- [ ] No existing assertion removed or weakened
- [ ] Backlog lists every defect you found and did not fix

## 9. Your report

Reply with this, and nothing else:

```text
GATES: G2 met|not met, G5 met|not met, G7 met|not met
BRANCH/TAGS: <branch, tags pushed or not>
TESTS: python3.12 <n run, result>; python3.10 <n run, skips, result>
REPRODUCTION: <the eight OK/FAIL lines>
BUDGETS: <per host: rule bytes, SKILL.md bytes, largest description, idle estimate, slowest hook ms>
CI: <job name: conclusion> for each job, or "not observed" plus link
LINES: sx.py <n>, install.py <n>
CHANGED: <files>
BACKLOG: <items added, or none>
STOPPED: <reason, or "no">
NOT COVERED: G1, G3, G4, G6, live hook enforcement, actual child model
```

Do not describe the work as complete beyond these three gates. Do not offer further work.
