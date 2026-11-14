# Lightweight readiness review — 11 November 2026

There is more work before routine use across chats and worktrees. The next work should improve the existing installer, SQLite ledger, and `sx.py`. The present set of roles and standard-library implementation is sufficient for that work.

Follow-up: the [detailed repair plan](repair-plan-2026-11-11.md) expands these findings, adds 13 further targeted observations, and defines implementation order, migrations and acceptance checks. These follow-up repairs are planned, not implemented.

The six previously reported defects have local fixes. This review exercised additional combinations that the previous unit suite and probes did not cover. It produced 13 unmet expectations across the work areas below. These were deliberately selected edge cases, not a representative failure-rate measurement. Implementation files were unchanged during this investigation.

Evidence: [reproduction script](evidence/readiness_probe.py) and [observed results](evidence/readiness-probe-2026-11-11.json). Every CLI check used disposable projects, isolated shared memory, and an isolated home for the global-install check. No model or live IDE trial was used in these probes.

## Fix before relying on multiple chats or LARGE work

### P1 — Bind requests and lifecycle events to the correct task and session

With requests captured from session A and then session B, creating task A attaches **B's request** to A. `core/sx.py:151` selects the latest unassigned request without considering the session. The request's session is already stored in `refs`, but this association does not use it.

Separately, a Codex-shaped PreToolUse event with `TASK: task-a` followed by a SubagentStart for the same session is logged against **task-b** when B is the newer open run. The start event has no brief, and `core/sx.py:847` falls back to the newest open run across the project. `resume` at `:913` likewise restores B into A's session. The stop hook uses the same project-wide selection pattern, although this probe did not separately test its output.

Minimal correction: bind each parent session to an explicit task/request ID. Carry that binding from validated dispatch through lifecycle events and use it for resume/stop. Do not infer ownership from which row happened to be created last. Add a two-session integration regression.

### P1 for worktree workflows — Make task records available to worker worktrees

After installing and committing the kit, recording a goal, and creating a worktree with `sx worktree add`, the installed command in the worker checkout prints `nothing recorded yet` for that task. Each checkout resolves its own `.simpleide/project.db`; the parent database is ignored by Git and is not copied into the worktree. A brief containing parent `P...` record IDs therefore cannot retrieve those records through the default worker command.

Minimal correction: give workers a deliberate pointer to the parent task store, or a pinned export with explicit paths. Keep memory lookup separate from the worker's execution directory so tests still run against the worker checkout. Add one end-to-end split/merge test that reads the original criteria inside the worktree.

## Fix before trusting completion statistics or comparing systems

### P1 for measurement — Separate recording a result from accepting a task

Recording `Blocked: acceptance criteria not met; task failed` as a `result` changes the run to `outcome='accepted'` and makes stats report `accepted=1`. `core/sx.py:153` does this for every result regardless of outcome. This is also inconsistent with the plan's accepted/failed/abandoned outcomes and the comparison protocol's user acceptance decision.

Adding a new goal under the same completed slug leaves the run accepted and preserves its old completion state because the run insertion uses `INSERT OR IGNORE` at `:150`.

Minimal correction: make outcome explicit and keep it independent of result prose. Require either a new attempt/slug or an explicit reopen operation for completed tasks. Do not infer failure or acceptance by parsing the text.

### P2 — Apply the task filter in stats

With two tasks in the ledger, `sx stats --task small-selected` still reports `tasks=2`. The `task` argument is used for cost updates but not to filter the summary query at `core/sx.py:614`.

Minimal correction: filter before aggregation and add a two-task regression. Token usage also remains uncaptured in the current implementation: the field exists, but there is no command or hook that writes it. Record actual cost manually where available and treat missing measurements as unknown during the comparison.

## Fix installation lifecycle and portability

### P2 — Preserve shared assets when uninstalling only one host

Install Cursor and Codex together, then uninstall only Cursor. Codex's agent TOML remains, but its shared `simpleide` skill and project rule disappear. `install.py:305` removes shared skills and `:318` removes the rule without checking whether other installed hosts still use them.

Minimal correction: track installed host ownership in a small install manifest, or otherwise reliably determine remaining consumers. Remove a shared asset only when the last consumer is removed. Test partial uninstall and reinstallation.

### P2 — Render global command paths in the write-up skill

A global Codex install puts `sx.py` under the isolated home, but the installed `sx-writeup/SKILL.md` still prescribes `python3 .simpleide/sx.py ...` from the project. Running that command in the scratch project exits 2 because the local script does not exist. The main rule substitutes a global path, while the skill is copied verbatim (`install.py:333` and `skill/sx-writeup/SKILL.md:7`).

Minimal correction: render the installed command location consistently into both skills and rules, and test the exact global skill command in a project with no local install.

## Repair memory and recovery behavior

### P2 — Deduplicate shared lessons by actual records, not folder name

Two separate directories with the same basename cannot find each other's shared lessons using the default search. Explicit `--scope shared` finds the lesson. `core/sx.py:298` filters shared hits by `project != root.name`, which cannot distinguish these directories and suppresses a lesson even when no local copy exists.

Minimal correction: suppress a shared hit only when the current project actually holds the same record/content identity. A basename is useful display text, not a project identifier.

### P2 — Allow a local lesson to be promoted to shared

Save a lesson with `--local`, then save the identical lesson without `--local`. The command says `already recorded + shared`, but another project cannot find it. Deduplication at `core/sx.py:141` returns the old row before its `shared` state is updated; `sync()` consequently has nothing queued.

Minimal correction: an explicit share request should update the existing local record to pending sync, then report whether it synced or queued. Keep ordinary duplicate writes idempotent.

### P2 — Restore access to all acceptance criteria

For a goal with five criteria, the resume hook emits the goal plus only criteria 1 and 2. It supplies no record IDs or retrieval command for criteria 3–5. `core/sx.py:917` truncates the first three records to stay within its five-line output bound. The output bound can be preserved by listing criterion IDs or a task retrieval command.

The plan also calls for open-question counts, but there is no question-resolution state: after recording a decision that references a question, resume still reports one question recorded. That label accurately counts all recorded questions; it does not distinguish answered from open questions. Treat this as a missing recovery feature rather than a claim that the displayed total is arithmetically wrong.

## Remaining qualification and release work

Two source-level contract checks also need attention. The LARGE playbook gives `sx-planner` an original-request record ID, but its Claude definition permits only Read, Grep, and Glob (`agents/sx-planner.md:5`). Those tools do not run `sx mem show` against SQLite. Supply an exported request file in that brief, or deliberately provide a way to query the ledger; verify the chosen route live. This is a static mismatch, not an observed Claude session failure.

`sx doctor` checks script, rule, and model-map presence, but does not inspect the installed agent or skill files. Extend that existing command to catch missing files per installed host. Runtime discovery still needs the separate live check; a passing filesystem check must not be treated as proof of registration.

1. Qualify the IDE used most often in a clean scratch project. Confirm an actual role launch, actual model, skill loading, hook invocation/denial, and one completed MEDIUM task. The prior Codex trial demonstrated skill discovery and a simple shell task; it did not demonstrate a selectable custom role or hook enforcement. The existing [live matrix](verified.md) accurately remains incomplete.
2. Add the simpleIDE unittest command to existing CI. The root pytest `testpaths` in `pyproject.toml:27` exclude `simpleIDE/tests`, and the current workflow has no separate simpleIDE step. Its tests currently depend on manual execution.
3. Review and commit the lightweight kit as an isolated change before distributing it. At this review, Git reports the whole `simpleIDE/` directory as untracked. Keep unrelated AgentNexus work separate.
4. After outcome/session fixes, run the [nine real-task comparison](comparison.md), recording user acceptance and observed time/cost. Use those results to decide which optional reviewer/tester steps earn their cost. Keep the AgentNexus keep/port/retire audit pending until those observations exist.

The next implementation can stay within this small footprint: session/task binding, explicit outcomes, reliable worktree context, install ownership/path rendering, and memory/recovery corrections. There is no evidence here that additional agent roles, a new orchestration service, or a dashboard would improve readiness.

## Reproduce

From the repository root:

```sh
python3.12 simpleIDE/docs/evidence/readiness_probe.py
```

The script prints expectations and observations as JSON and exits normally when observations disagree with expectations. An exception indicates a harness/command failure. The evidence file preserves this review's observed state; future fixes should write a separate result file for comparison.
