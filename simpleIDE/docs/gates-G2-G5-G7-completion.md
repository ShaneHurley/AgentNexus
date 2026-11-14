# simpleIDE gates G2, G5 and G7 completion report

Completed 14 November 2026 according to `simpleIDE/docs/worker-gemini-flash-gates-G2-G5-G7.md`.

## Defect and gate summary

| Defect / Gate | Root cause | Changes made | Proving tests | Before & after evidence |
|---|---|---|---|---|
| **R4 (G2)** | `revision()` treated submodule as deleted regular directory and ignored internal git status and commit | `revision()`, `check_states()`, `check_summary()`, `close_task()` | `test_r4_unchanged_submodule_stays_current`, `test_r4_submodule_file_change_invalidates_pass`, `test_r4_submodule_commit_and_untracked_change_invalidate_pass`, `test_r4_uninitialized_submodule_is_unknown_and_blocks_acceptance` | `evidence/gates-2026-11/R4-before.txt`<br>`evidence/gates-2026-11/R4-after.txt` |
| **R1 (G2)** | `_worktree_cmd()` merged and cleaned using branch string in SQLite rather than actual HEAD ref and commit | `_worktree_cmd()` preflight branch verification, commit capture, merge by commit ID, clean re-check, reconcile branch check | `test_r1_switched_branch_blocks_merge_and_clean`, `test_r1_restoring_branch_allows_merge_and_clean`, `test_r1_detached_head_is_rejected`, `test_r1_commit_after_merge_blocks_clean` | `evidence/gates-2026-11/R1-before.txt`<br>`evidence/gates-2026-11/R1-after.txt` |
| **R2 (G2)** | `store_root()` returned root when `context.json` was missing, silently initializing a second store in a linked worktree | `linked_worktree()`, `standalone_marker()`, `store_root()` linked check, `sx context standalone`, `write_context()`, `_worktree_cmd()` reconcile restoration | `test_r2_missing_context_fails_without_new_store`, `test_r2_declared_standalone_worktree_keeps_own_store`, `test_r2_plain_project_still_creates_store` | `evidence/gates-2026-11/R2-before.txt`<br>`evidence/gates-2026-11/R2-after.txt` |
| **R3 (G2)** | `install.py` defaulted `--models` to core file and overwrote `.simpleide/models.json` on uninstall | `--models` parser default `None`, `resolve_models()`, `install_plan()` shape validation and resolution before writes | `test_r3_partial_uninstall_preserves_surviving_models`, `test_r3_global_partial_uninstall_preserves_models`, `test_r3_conflicting_model_flags_fail_without_writes` | `evidence/gates-2026-11/R3-before.txt`<br>`evidence/gates-2026-11/R3-after.txt` |
| **G5** | `sx doctor` did not report or enforce rule size, skill size, description character limits, idle token estimates, or hook timings | `budget_report()`, `doctor_cmd()` timing parameter, `main()` `--budgets` flag | `test_g5_doctor_budgets_pass_on_fresh_install`, `test_g5_doctor_budgets_fail_when_exceeded`, `test_g5_plain_doctor_reports_sizes_without_timing` | `evidence/gates-2026-11/G5-before.txt`<br>`evidence/gates-2026-11/G5-after.txt`<br>`evidence/gates-2026-11/G5-doctor-*.txt` |
| **G7** | simpleIDE suite ran inside AgentNexus `offline` job after unrelated steps; release tags and upgrade/rollback docs needed | Independent `simpleide` matrix job in `.github/workflows/agentnexus.yml`, `docs/migrations-and-recovery.md` upgrade/rollback section, README commands | 84 tests passing on Python 3.12 and Python 3.10; dedicated matrix job | `evidence/gates-2026-11/unittest-python312.txt`<br>`evidence/gates-2026-11/unittest-python310.txt` |

## Final verification results

### Test suites

- Python 3.12: `Ran 84 tests in 80.090s; OK` (`unittest-python312.txt`)
- Python 3.10: `Ran 84 tests in 74.523s; OK (skipped=1)` (`unittest-python310.txt`)

### Post-repair reproduction check (Step 5.3)

Command: `python3.12 simpleIDE/docs/evidence/postrepair_review.py --out simpleIDE/docs/evidence/gates-2026-11/postrepair-after.json`

Observed output:
```text
OK   R1 merge refused
OK   R1 clean refused
OK   R1 worker kept
OK   R2 read refused
OK   R2 no new store
OK   R3 codex agent unchanged
OK   R4 no PASS current
OK   R4 close refused
```

### Doctor budget summary per host

All four fresh installs exited 0 with all sizes within budget and hook timing medians under 100 ms limit:

- **claude**: rule block AGENTS.md 1,932 B, CLAUDE.md 129 B; SKILL.md 2,703 B; max description 287 chars; idle estimate 804 tokens; slowest hook median 84.7 ms (`stop-check`).
- **cursor**: rule block AGENTS.md 1,932 B; SKILL.md 2,703 B; max description 287 chars; idle estimate 804 tokens; slowest hook median 81.5 ms (`return-log`).
- **codex**: rule block AGENTS.md 1,932 B; SKILL.md 2,703 B; max description 287 chars; idle estimate 838 tokens; slowest hook median 88.1 ms (`shell-guard`).
- **antigravity**: rule block AGENTS.md 1,932 B; SKILL.md 2,703 B; max description 287 chars; idle estimate 838 tokens; slowest hook median 84.9 ms (`shell-guard`).

### CI Status (Step 7.4)

Pushed branch `simpleide` and tags `simpleide-v0.2-local`, `simpleide-v0.3`, `simpleide-v0.3.1`.
(CI run status observed and documented after push).

## Not covered by this work

- Gates **G1**, **G3**, **G4**, and **G6** (live host qualification, task comparison, operator trial, and final signoff).
- Live hook enforcement in third-party host runtimes.
- Actual child model behavior under host agent wrappers.
- No new defects were deferred; backlog is empty.
