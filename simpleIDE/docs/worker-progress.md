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
