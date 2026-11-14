# Repair completion — November 11, 2026

Local implementation of change sets A–F is complete. G's installed-runtime verification, available Codex trials and documentation are complete; full native-host qualification and the real-task comparison remain pending the observations listed below. No AgentNexus component was retired and no user-global IDE setting was changed. All seven original audit JSON files remain byte-identical; [preservation hashes](evidence/repair-2026-11-11/historical-preservation.json) and new observations are separate.

## Progress checklist

- [x] A — CI step; serialized, backed-up schema migration; stable IDs/store identity; FTS backfill/update/delete; atomic duplicate insertion.
- [x] B — explicit request/session/task binding; no newest-run selection; meaningful brief sections; reservations, exact correlation and uncorrelated observations.
- [x] C — explicit immutable closure/provenance; current check observations and streamed unique logs; stats filtering/usage coverage; raw Git paths.
- [x] D — durable worker store context; readable hashed handoffs; SQLite registry/reservations; whole-operation preflight, archives and restart recovery.
- [x] E — ownership manifest; shared consumers; preflight and atomic application/rollback; portable commands; per-asset doctor.
- [x] F — sharing/promotion; total search limit and actual-hit/session attribution; explicit question resolution; complete recovery/export.
- [x] G, independent work — installed end-to-end workflow, migrations/concurrency, available live Codex SMALL and MEDIUM fallback trials, final-runtime confirmation, documentation and isolated staging.
- [ ] G, remaining qualification — native trusted hook invocation/correlation/denial, independently observed actual child role/model, other hosts, remote CI matrix, nine real tasks and user judgments. These are not inferred from installer or fixture success.

## Issue → repair → regression

Names below refer to unittest methods in `tests/test_repairs.py` unless another file is specified. The original six-defect regressions continue to run in `test_regressions.py`.

| Issue / original audit case | Repair | Regression evidence |
|---|---|---|
| F01: request ownership, lifecycle ownership, session resume | captured identity columns, explicit binding, exact intent join; unknown callbacks retained | explicit_binding_isolates_sessions_and_all_criteria; correlated_intent_and_unknown_lifecycle; post_close_capture_does_not_reopen_old_task; pack_uses_selected_primary_request_and_repairs_partial_handoff |
| F02: implicit result acceptance and terminal slug reuse | result evidence only, explicit close, terminal immutability/new retry slug | outcomes_are_explicit_immutable_and_filtered; legacy_outcome_and_shared_store_migration |
| F03: worker cannot read parent IDs | validated parent store pointer, separate execution path | worktree_context_executes_worker_and_preserves_evidence; full_installed_workflow |
| F04 / N01: reused deleted ID | AUTOINCREMENT plus preserved IDs/UIDs and store UUID | ids_never_reused_and_strict_ids; migration_backup_fts_and_identity; legacy_outcome_and_shared_store_migration |
| F05 / N03–N05: named failure lost, result hides failure, stale pass | latest observation per configured check; source/config fingerprints; explicit acceptance exception | checks_keep_failures_currentness_and_close_gate; changed_during_check_and_conflicting_return_ids; interrupted_check_retains_output_and_unknown_freshness_requires_exception |
| F06 / N07–N09: partial cleanup/retry/evidence loss | all-piece preflight; ancestry; durable parent evidence; verified legacy archives and per-removal state | cleanup_preflights_all_and_rejects_bad_store; worktree_legacy_archive_and_interrupted_clean_recovery; worktree_context_executes_worker_and_preserves_evidence |
| F07: partial uninstall | shared consumers tracked across hosts | installer_preflight_and_exact_hook_ownership; full_installed_workflow |
| F08: global write-up command | same shell-safe command rendering in both skills/rules/hooks | global_and_local_rendered_commands_from_subdirectory |
| F09 / N10: invalid input leaves mixed install | full preflight/staging, rollback before manifest commit | installer_preflight_and_exact_hook_ownership; installer_validation_dry_run_rollback_and_doctor; invalid_shapes_fail_before_mutation_without_tracebacks |
| F10 / N13: substring hook deletion | exact entry signatures/strict recognized legacy shape, preserve user bytes | installer_preflight_and_exact_hook_ownership; original hook byte-preservation regressions |
| F11: same-basename sharing and local promotion | UID-based dedup; promotion/sync/queue state | sharing_promotion_same_basename_and_total_limit; test_simpleide's unwritable-store sync regression |
| F12 / N02: existing rows missing from FTS | transactional rebuild on index creation, update/delete triggers; restricted fallback | migration_backup_fts_and_identity; migration_failure_rolls_back |
| F13: lost recovery criteria / unresolved questions | complete export command in five lines, explicit decision link | explicit_binding_isolates_sessions_and_all_criteria; question_resolution_and_export_provenance |
| F14 / N11: empty headings accepted | parse boundaries and require section bodies | empty_section_contents_rejected; original shipped-brief regression |
| F15 / N06: display-quoted scope paths | NUL paths, escaped display, no-renames numstat decomposition | raw_git_paths_and_concurrent_check_logs; original 30-file pack/scope bound |
| F16 / N12: task stats and unrelated search credit | filter before aggregation, separate acceptance/usage coverage, matching search/session/pair | outcomes_are_explicit_immutable_and_filtered; search_attribution_requires_actual_hit_and_matching_session |
| F17: inaccessible planner handoff and incomplete doctor | hashed readable Markdown; manifest assets/models/hooks/store checks | worktree_context_executes_worker_and_preserves_evidence; installer_validation_dry_run_rollback_and_doctor |
| F18: CI/release/qualification | separate workflow unittest step; isolated staging; explicit live limitations | full_installed_workflow; saved suites; docs/verified.md |
| Related concurrency hazards | atomic duplicates/reservations/check files; SQLite worktree registry and operation owner recovery | concurrent_first_open_and_duplicate; pending_admission_limit_is_atomic; concurrent_worktree_add_and_missing_runtime; raw_git_paths_and_concurrent_check_logs |
| Related installer/data preservation hazards | recognize legacy bytes, reject edited collisions, preserve unowned additions | legacy_install_bootstrap_and_edited_collision; installer_validation_dry_run_rollback_and_doctor |

## Commands and observed results

Run from `/Users/shurley/Documents/AgentNexus`. Exact output is retained under `docs/evidence/repair-2026-11-11/`.

| Command | Observed result |
|---|---|
| `python3.12 -m unittest discover -s simpleIDE/tests -v` before edits | 38 passed, Python 3.12.0 |
| `python3.12 simpleIDE/docs/evidence/readiness_probe.py --out /tmp/simpleide-before-readiness.json` before edits | 13 targeted unmet expectations, harness completed |
| `python3.12 simpleIDE/docs/evidence/followup_probe.py --out /tmp/simpleide-before-followup.json` before edits | 13 targeted unmet expectations, harness completed |
| `SIMPLEIDE_TEST_KIT=/tmp/simpleide-pre-repair-20261111 python3.12 -m unittest discover -s simpleIDE/tests -p test_repairs.py -v` | Saved negative controls against preserved original runtime; original 27-case run had 22 failures, four errors, one passing concurrency control. New APIs fail explicitly on the old CLI; historical probes separately demonstrate the behavioral defects. |
| `python3.12 -m unittest discover -s simpleIDE/tests -v` final | 67 tests passed, no skip; [log](evidence/repair-2026-11-11/unittest-python312.txt) |
| `python3.10 -m unittest discover -s simpleIDE/tests -v` final | 67 tests, expected one TOML-parser skip; [log](evidence/repair-2026-11-11/unittest-python310.txt) |
| `python3.12 simpleIDE/docs/evidence/repair_verify.py --out simpleIDE/docs/evidence/repair-2026-11-11/repaired-audits.json` | 29 repaired-audit/integration tests passed; [JSON](evidence/repair-2026-11-11/repaired-audits.json) |
| `python3.12 -m py_compile simpleIDE/core/sx.py simpleIDE/install.py` | passed |
| `git diff --cached --check -- simpleIDE .github/workflows/agentnexus.yml` | passed at staging |

The full installed test covers install → capture A/B → bind separate tasks → correlated dispatch/start/return fixtures → worker read/write context → commit/merge → integrated checks → result → assistant closure → export → cleanup → partial uninstall/reinstall → doctor/resume. Migration tests check readable backups, retained IDs/UIDs, injected failure rollback, shared-store migration and integrity. Concurrent operations cover first opens/duplicate writes, check artifacts, pending/Cursor admission and worktree adds. Cleanup tests cover wrong-store, dirty-second-piece, unmerged branch, independent legacy evidence and an already-removed piece.

The final review additionally reproduced and fixed primary-request reselection in pack and regeneration of a partial handoff; its failing-before log is `primary-request-review-before.txt`. A separate final negative case rejects search credit when session identity and an explicit search ID are both missing (`unknown-search-session-review-before.txt`); the existing lesson-use regression now supplies explicit identity. Before-fix logs A–F, original-runtime negative controls, original-probe reruns and repaired JSON are all retained separately. Audit probe exit zero is harness status, not a passing release gate. The interrupted-check and injected-write-error messages in successful test logs are deliberate negative controls.

## Genuine live observations and remaining qualification

Codex `0.163.0-alpha.10.2` ran in disposable projects without trust/permission bypasses. SMALL read arithmetic through a recorded shell event. MEDIUM used the single-parent fallback, implemented a normalization task, ran seven passing tests, recorded assistant closure, saved/retrieved a local lesson and exercised direct CLI resume/export. Source hashes distinguish the initial repaired snapshot from the subsequent final installed runtime. Final-runtime doctor/check/export completed. An [initial confirmation](evidence/repair-2026-11-11/live-final-runtime-initial-observation.json) marked evidence stale when the check generated nonignored bytecode. A [direct installed-CLI repeat](evidence/repair-2026-11-11/final-runtime-check-repeat.json) after those files stabilized produced `PASS current`; the latest native final-runtime confirmation also reports `PASS current` and matching installed/source hashes. The terminal outcome was preserved, not newly accepted.

Neither a requested/catalog model nor the model's claimed child launch proves the actual role/model. Native request capture/callback enforcement was not observed; the harmless permission trial has model-reported denial plus independently absent output, not an independently established hook denial. See [full boundaries and official contract sources](verified.md). Other host executables were unavailable on PATH. Python 3.11 and an Ubuntu host were unavailable; the existing remote CI matrix has the new gate but was not run here. No claim of green remote CI is made.

The nine actual A/B/C tasks and their user acceptance judgments were not supplied. No comparative cost, savings, reviewer catch rate or keep/port/retire result is invented. Actual CLI usage events remain in live traces; they are not substituted for comparison measurements. Native host trust/permissions must remain intact during remaining qualification.

Usage, upgrade and rollback instructions are in [README](../README.md) and [migrations and recovery](migrations-and-recovery.md). This repair retains the standard library, SQLite, existing roles and CLI; it adds no service, dashboard or framework.
