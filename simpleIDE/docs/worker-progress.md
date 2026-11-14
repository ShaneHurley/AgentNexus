# Worker progress: gates G2, G5, G7

Assignment: docs/worker-gemini-flash-gates-G2-G5-G7.md

| Step | Done | Check result |
|---|---|---|
| 1.1 | baseline | 67 OK on 3.12 and 3.10 |
| 1.2 | branch simpleide, commit, tag simpleide-v0.2-local | only allowed paths committed |
| 1.3 | progress and backlog files | files created |
| 2.1 | R4 tests written | unchanged passes, 3 fail |
| 2.2 | fix revision() | submodule-aware v2 fingerprint |
| 2.3 | check_states() and close_task() | all 4 R4 pass, full suite OK on 3.12/3.10 |
| 3.1 | R1 tests written | switched/detached fail, before saved |
| 3.2 | fix _worktree_cmd() | all 4 R1 pass, full suite OK on 3.12/3.10 |
| 4.1 | R2 tests written | first 2 fail, plain passes, before saved |
| 4.2 | fix store_root() and recovery | linked_worktree check, standalone context command |
| 4.3 | update legacy test, full suite check | all 3 R2 pass, full suite OK on 3.12/3.10 |
| 5.1 | R3 tests written | all 3 fail, before saved |
| 5.2 | fix install.py resolve_models | all 3 R3 pass, full suite OK on 3.12/3.10 |
| 5.3 | postrepair_review check | 8 OK lines; Gate G2 is met |
| 6.1 | G5 tests written | all 3 fail, before saved |
| 6.2 | doctor --budgets enforcement | all pass, 4 fresh installs exit 0 under 100ms; Gate G5 met |
| 7.1 | dedicated CI job | simpleIDE regression suite in dedicated matrix job |
| 7.2 | documentation | upgrade/rollback docs, README commands, completion doc, plan headers updated, all links resolve |
| 7.3 | final local verification | 84 OK on 3.12 and 3.10 (skipped=1); line counts within budget; no whitespace errors |
| 7.4 | push and confirm CI | pushed simpleide and 3 tags; CI run 43645835264 green (all 3 matrix jobs success); Gate G7 met |

## Final self-check

**G2**
- [x] R4: four tests, before and after files saved, all pass (R4-before.txt, R4-after.txt)
- [x] R4: `close_task` decides from state values, not display text (check_states() st != "current")
- [x] R1: four tests, before and after files saved, all pass (R1-before.txt, R1-after.txt)
- [x] R1: merge uses the captured commit; output names it (merged <piece> <commit[:12]>)
- [x] R2: three tests, before and after files saved, all pass; one existing test updated exactly as Step 4.3 says (R2-before.txt, R2-after.txt)
- [x] R3: three tests, before and after files saved, all pass (R3-before.txt, R3-after.txt)
- [x] `postrepair-after.json` check prints eight `OK` lines

**G5**
- [x] Three G5 tests pass (G5-before.txt, G5-after.txt)
- [x] `doctor --budgets` exits 0 on a fresh install of each of the four hosts, files saved (G5-doctor-claude.txt, G5-doctor-cursor.txt, G5-doctor-codex.txt, G5-doctor-antigravity.txt)
- [x] Every hook median under 100 ms at the default limit (slowest hook 88.1 ms)

**G7**
- [x] Branch `simpleide` with one commit per phase; no file outside the allowed paths committed
- [x] Tags `simpleide-v0.2-local`, `simpleide-v0.3`, `simpleide-v0.3.1` pushed
- [x] Dedicated `simpleide` CI job green on all three matrix entries (run 43645835264: ubuntu-3.11 success, ubuntu-3.12 success, macos-3.10 success)
- [x] Upgrade and rollback section, README additions, completion report, status lines in the three plans
- [x] All relative links resolve

**Budgets and scope**
- [x] `sx.py` at 1,788 lines (<= 1,800), `install.py` at 585 lines (<= 600)
- [x] No changes to skills, agents, `rule.md`, `models.json`, `verified.md`, `comparison.md`
- [x] No existing assertion removed or weakened
- [x] Backlog lists every defect you found and did not fix (none added)
