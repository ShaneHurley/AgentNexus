# simpleIDE: finalization plan

Written 14 November 2026. This plan takes simpleIDE from its current state (built and locally tested, never used on real work) to the architecture in the design of 10 November (`claude/simpleIDE-plan.md` in the project, `simpleIDE/PLAN.md` in the repo). Section numbers such as "design §7.2" refer to that document.

Everything stated about the current state was checked against the code on 14 November: the files in `simpleIDE/`, the 67-test suite (run again today: 67 run, 1 expected skip on Python 3.10), and the review documents in `simpleIDE/docs/`.

**Assumptions I made, because they were still open.** Change them in Stage 0 if they are wrong; the stages do not change, only the order of hosts.

1. Your first host is **Codex**, because every build session so far ran there. Claude Code is second, then Cursor, then Antigravity. Codex usage resets on 16 November at 3:50 PM; Stages 0 and 1 do not need it.
2. **Mark 2 is paused as a separate build.** It enters the comparison only if it can run a task end to end on its own, and its mechanisms are judged in Stage 9.

---

## 1. What "finished" means

simpleIDE is final (version 1.0) when all seven gates are met. Each gate is something you can check, not a test count.

| # | Gate | How it is checked |
|---|---|---|
| G1 | **Runs for real in at least two hosts.** A subagent launch, the model it actually ran on, and each hook firing have been seen in a live session. | A filled row per host in `docs/verified.md`, each cell marked seen, not working, or not supported |
| G2 | **Known false-success paths are closed.** The four reproduced defects (R1 to R4) are fixed, or the affected feature is switched off with a clear error. | The four reproductions in `docs/evidence/postrepair_review.py` are normal unit tests and pass |
| G3 | **Used daily.** At least 15 real tasks closed through the ledger, at least 3 of each size. | `sx stats` |
| G4 | **Measured.** The nine-task comparison is complete and the decision rules in design §12.3 have been applied. | `docs/comparison.md` has all rows and a "what was cut" list |
| G5 | **Inside its budgets.** Idle cost at or under 1,000 tokens, rule under 2,500 bytes, `SKILL.md` under 3 KB, every hook under 100 ms. | `sx doctor` prints each number |
| G6 | **AgentNexus is sorted.** Every existing part is marked keep, port or retire, with the evidence that decided it. | `docs/agentnexus-audit.md` |
| G7 | **Safe to maintain.** Committed, tagged, CI green on the remote matrix, upgrade and rollback documented. | Git tag `simpleide-v1.0`, a green CI run |

---

## 2. Where it stands today

Status of every component in the design's inventory (design §3). "Built" means the code exists and has local tests. "Seen live" means observed in a real host session.

| # | Component | Built | Seen live | Gap to close | Stage |
|---|---|---|---|---|---|
| 1 | `core/rule.md` | Yes, 1,650 bytes | Not checked | Confirm each host loads it | 2 |
| 2 | `sx-worker` | Yes | **No launch seen** | Launch and actual model | 2 |
| 3 | `sx-planner` | Yes | No | Same, on a LARGE task | 3 |
| 4 | `sx-tester` | Yes | No | Same | 3 |
| 5 | `sx-reviewer` | Yes | No | Same; measure real-finding rate | 3, 7 |
| 6 | `sx-scout` | Yes (Codex, Antigravity only) | No | Same | 2 |
| 7 | `simpleide` skill | Yes, split, 2,534 bytes | Listed in Codex catalog only | Confirm MEDIUM loads `SKILL.md` and not `large.md` | 2 |
| 8 | `sx-writeup` skill | Yes | No | **Voice profile not created** (needs your writing samples) | 4 |
| 9 | `sx mem` | Yes | CLI ran in a Codex session | None | - |
| 10 | `sx check` | Yes | CLI ran in a Codex session | **R4: submodule edits leave a stale PASS** | 1 |
| 11 | `sx scope` | Yes | No | None known | - |
| 12 | `sx pack` | Yes | CLI ran | Uses the same check status as #10 | 1 |
| 13 | `sx worktree` | Yes | No | **R1: merge reports success on the wrong branch. R2: lost context file creates a second ledger** | 1, 5 |
| 14 | `sx doctor` | Yes | CLI ran | Does not print rule size or hook timing any more | 4 |
| 15 | `sx stats` | Yes | CLI ran | Token and cost are manual only; automatic capture not built | 4 |
| 16 | `sx hook` | Yes | Fixtures only | See 17 to 22 | 2 |
| 17 | capture-request | Yes | **No** | Left no record in the Codex trials | 2 |
| 18 | dispatch-guard | Yes | **No** | Advisory only on Codex `SubagentStart` | 2 |
| 19 | shell-guard | Yes | **No** | Denial never traced to the hook | 2 |
| 20 | return-log | Yes | **No** | | 2 |
| 21 | stop-check | Yes | **No** | | 2 |
| 22 | resume | Yes | Direct CLI call only | Session start and after compaction | 2 |
| 23 | `install.py` | Yes | Scratch installs | **R3: partial uninstall resets another host's models.** Antigravity hooks deferred | 5, 6 |

Things that drifted from the design and need a decision, not a fix:

- **Size.** `sx.py` is 1,582 lines and `install.py` 537. The design called this a small script.
- **Commands the model must remember.** The design said a task opens on its first goal and closes on its result, "no extra commands for the model to remember" (design §8.3). The repairs replaced that with explicit `task bind` and `task close --outcome --result --by --refs`. That is safer and it costs prompt text on every MEDIUM task. Stage 4 restores one-command start and finish without bringing back the unsafe guessing.
- **Order.** The design put live verification (its Phase 1) before building tools and hooks. It was skipped. Stage 2 does it now.

Not committed: all of `simpleIDE/` is staged in Git with no commit behind it.

---

## 3. One finding that changes the earlier advice

**Do not qualify or dogfood simpleIDE inside the AgentNexus checkout yet.** I suggested installing it there. Checking the repo's existing hooks shows why that would fail and would also spoil the measurements:

- `.codex/hooks.json` runs `enforce-agent-authority.py` on every `SubagentStart`. It tells any subagent that is not on AgentNexus's allowlist that it is read-only. An `sx-worker` launched there would be told not to write.
- `.cursor/hooks.json` runs `deny-unbridged-writes.py` after every file edit, failing closed. It denies native edits unless `IDE_BRIDGE_ACTIVE=1` or the agent is on the write allowlist, which is empty by default.
- `.claude/agents`, `.cursor/agents` and `.codex/agents` each hold 41 AgentNexus agent definitions. Their descriptions load in every session, so idle cost measured there is mostly AgentNexus, not simpleIDE.

Two ways out. The plan uses the first.

1. **Give simpleIDE its own repository** (Stage 0, decision D3). It is already self-contained: standard library only, its own tests, its own installer. Then qualify and use it in projects that do not carry AgentNexus's hooks.
2. Keep it inside AgentNexus and add `sx-worker` and `sx-tester` to AgentNexus's write allowlist. This changes AgentNexus's policy and still leaves the 41 agents in context, so the comparison stays muddied.

---

## 4. Rules for this build-out

The last four days followed one loop: a worker builds, a reviewer hunts for edge cases, a new plan is written, a worker fixes. Tests went 12, 22, 38, 67 while real use stayed at zero. These rules end that loop.

1. **Feature freeze.** Nothing is added that is not in this plan. A new idea goes into `docs/backlog.md` with the evidence that prompted it.
2. **One quality bar: would this break a real task?** A defect is fixed now only if it can produce a wrong result or lose work in the way you actually use the kit. Everything else is logged in the backlog with its reproduction.
3. **Real use outranks probes.** A failure on a real task is fixed before any finding from a review.
4. **One review per stage, time-boxed.** The reviewer gets the stage's acceptance list and reports only findings with a reproduction. No open-ended "look for anything else".
5. **Size budgets.** `sx.py` at most 1,800 lines, `install.py` at most 600, rule under 2,500 bytes, `SKILL.md` under 3 KB, skill and agent descriptions under 400 characters. A line added to the rule removes a line.
6. **Three evidence labels, never mixed.** Local test, fixture (sample input fed to a hook), live (seen in a host session). Only live evidence fills `docs/verified.md`.
7. **Every stage ends with a commit and a tag.**
8. **Bounded worker briefs.** One outcome, a done-when list, a size limit, and "stop and report" instead of "keep looking". Section 16 has the briefs ready to paste.

---

## 5. Stage 0: safeguard and decide (30 to 60 minutes, you)

**Steps**

1. Commit what exists, only the simpleIDE paths. The repo is on `main` with other work in progress, so use a branch. Five review files and this plan are not staged yet, so add the folder first:
   ```sh
   cd /Users/shurley/Documents/AgentNexus
   git switch -c simpleide
   git add simpleIDE .github/workflows/agentnexus.yml
   git commit -m "simpleIDE: local build with repairs, 67 tests" -- simpleIDE .github/workflows/agentnexus.yml
   git tag simpleide-v0.2-local
   ```
   The path list after `--` keeps your other uncommitted changes out of this commit.
2. Push the branch, and confirm the "simpleIDE regression suite" CI step is green on both matrix entries (Python 3.10 on macOS, 3.11 on Ubuntu). This has never been run remotely.
3. Create `simpleIDE/docs/backlog.md` with two entries already known: R2 and R3 (fixed in Stage 5).
4. Make the three decisions below and write them at the top of `docs/verified.md`.

**Decisions**

| # | Decision | Default in this plan |
|---|---|---|
| D1 | First host to qualify | Codex. Pick Claude Code instead if you want to start before 16 November |
| D2 | What happens to Mark 2 | Paused. Judged in Stage 9; joins the comparison only if it can run a task unaided |
| D3 | Where simpleIDE lives | Its own repository at `~/Documents/simpleIDE`, copied from the tagged commit, with its own CI file. AgentNexus keeps a one-line pointer |

If you choose D3: copy the folder, `git init`, commit, add a minimal workflow that runs `python -m unittest discover -s tests -v` on Python 3.10, 3.11 and 3.12. Leave the AgentNexus copy in place and frozen until Stage 9, so nothing there breaks.

**Done when**: the tag exists, remote CI is green or its failures are in the backlog, and D1 to D3 are written down.

---

## 6. Stage 1: fix the two defects that gate trust (about 1 day, one worker)

Only R4 and R1. Both can report success when the work is wrong, which is the one thing this kit must never do. R2 and R3 wait for Stage 5 because they cannot produce a false success in single-checkout use.

The 12 November root-cause plan proposes a larger design (typed snapshots, a registry in Git's common directory). Stage 1 takes the smallest change that closes each false-success path. Stage 5 decides whether the larger design is still needed.

### 6.1 R4: `sx check` must not show PASS when a submodule changed

Where: `core/sx.py`, `revision()` (line 709), consumed by `check_summary()` (733) and `close_task()` (1145).

Cause: Git lists a submodule as one entry. `revision()` sees a directory, falls through to the constant `deleted`, and never looks inside.

Change:

1. Read entry modes with `git ls-files -s -z`. Do not infer type from the filesystem.
2. For a submodule entry (mode 160000): confirm it is an initialized checkout whose top level is that path, then include its HEAD commit and the result of `revision()` on it, recursively, to a depth of 5.
3. If a submodule is not initialized, cannot be read, or the depth limit is hit, return unknown (`None`). The existing code already turns that into "freshness unknown/unverified", which blocks acceptance unless an explicit exception is recorded.
4. A path that is a directory and not a submodule is an error state (unknown), never `deleted`.
5. Prefix the new digest with a version (`v2:`), so no check recorded under the old method can compare equal to a new one. Old observations become "stale", which is correct. No schema change needed.
6. Replace the string test in `close_task()` (`"PASS current" not in v`) with one function that returns a status value, used by `check_summary`, `pack`, `close_task` and `stop-check`.

Done when:

- The R4 reproduction (pass, edit the submodule file, `pack`, `task close --outcome accepted`) now shows stale and rejects the close.
- Changing a submodule's commit, a tracked file in it, or an untracked non-ignored file in it changes the status. An unchanged initialized submodule stays current across repeated runs.
- An uninitialized submodule gives unknown and cannot be accepted without `--exception`.
- A repository with no submodules behaves exactly as before.

### 6.2 R1: `sx worktree merge` and `clean` must act on what is actually in the worktree

Where: `core/sx.py`, `_worktree_cmd()` (line 965), `worktree_inventory()` (858).

Cause: merge and clean test and merge the branch name stored in SQLite. If the worker switched branches, the stored branch is still the untouched baseline, so "merged" is reported and the checkout is removed with the real work never integrated.

Change:

1. Before any merge, clean or reconcile changes anything, for every piece: the branch Git reports for that worktree path must equal the recorded branch. A different branch or a detached HEAD stops the whole operation with a message naming the piece and both branches.
2. Capture each worker's HEAD commit id at that point. Merge the commit id, not the branch name. After merging, verify that commit is an ancestor of the parent's HEAD, and print it.
3. `clean` re-reads the worker's current HEAD and requires that commit to be integrated. A commit added after the merge blocks cleanup. `--discard` may skip integration; it may never skip the branch check.
4. `reconcile --apply` may not mark a piece merged when its actual branch differs from the recorded one.
5. Prefer no schema change. If a column for the merged commit id is needed, add a real version 1 to version 2 migration (backup, incremental, tested from both a fresh store and a version 1 store), because the current migration only runs on stores with no version.

Done when:

- The R1 reproduction fails at preflight for both merge and clean, and nothing in any checkout has changed.
- A detached HEAD, and a commit added after merge, are both rejected.
- Two valid pieces still merge in order, the parent contains both changes, and the output names the commits.
- All 67 existing tests still pass. New tests are in `tests/test_repairs.py`.

**Stage 1 ends with**: R4 and R1 ported from `docs/evidence/postrepair_review.py` into normal unit tests, suite green on Python 3.10 and 3.12, commit, tag `simpleide-v0.3`. One review, limited to the two done-when lists.

---

## 7. Stage 2: qualify the first host live (half a day, you at the keyboard)

This is the design's Phase 1 and the most important stage in the plan. Everything that makes simpleIDE cheap depends on three facts that have never been observed: a subagent launches, it runs on the model it was pinned to, and hooks fire.

The Codex trials so far ran `codex exec` with `--ephemeral`, and in one case with user config ignored. Hooks left no records there. Run this stage in a normal interactive session, and approve project trust and hooks through the host's own prompts. Do not bypass trust to get a pass.

### 7.1 Set up a clean project

```sh
mkdir ~/sx-qual-codex && cd ~/sx-qual-codex && git init
printf '19 + 23\n' > arithmetic.txt
printf 'def labels(values):\n    return values\n' > normalize.py
python3 ~/Documents/simpleIDE/install.py --target . --tools codex --dry-run
python3 ~/Documents/simpleIDE/install.py --target . --tools codex --hooks
git add . && git commit -m "qualification baseline"
python3 .simpleide/sx.py doctor
```

Use a project outside AgentNexus (section 3). If you kept simpleIDE inside AgentNexus (decision D3), the installer path is `~/Documents/AgentNexus/simpleIDE/install.py`. Restart the host after installing. For Codex, first check that the multi-agent and hook features are enabled (`codex features list`), since an earlier trial showed no `sx-*` roles with them off.

### 7.2 The checks

Run them in order. After each, record seen, not working, or not supported in `docs/verified.md`, with the host version and date. "The model said so" is not evidence; each check names where the evidence is.

| # | What you do | Evidence | Pass |
|---|---|---|---|
| Q1 | Fresh session. Ask: "What does the simpleIDE rule say to do for a MEDIUM task?" | The reply | It restates the MEDIUM row without opening a file |
| Q2 | Open the host's own list of agents and skills | The host's list | `sx-worker`, `sx-planner`, `sx-tester`, `sx-reviewer` (and `sx-scout` on Codex and Antigravity); `simpleide` and `sx-writeup` |
| Q3 | Send any prompt. Then in a terminal: `python3 .simpleide/sx.py mem recent --kind request` | The ledger | Your prompt, word for word, with no command run by the model |
| Q4 | "Read arithmetic.txt and tell me the sum." | The session | Answers 42 itself: no subagent, no skill loaded |
| Q5 | "Use the sx-worker subagent to add a one-line docstring to labels() in normalize.py. Write it a proper brief." | `sqlite3 .simpleide/project.db "select agent,requested_model,model,state,observed_launch,return_status from dispatch"` | A row for `sx-worker` with `observed_launch=1` and a return status |
| Q6 | Same row as Q5, then cross-check in the host's own record of that subagent run (its session log or transcript, or its usage page) | `requested_model` against `model`, and the host's record | The worker ran on the model in `.simpleide/models.json`, not the parent's model |
| Q7 | "Launch sx-worker with exactly this brief and nothing else: GOAL: tidy the file" | The session | The launch is refused with one line naming the missing DONE WHEN. On Codex this is advisory unless the spawn call passes through `PreToolUse`; record which |
| Q8 | With the tree clean: "Run `git reset --hard HEAD`." | The denial text | Blocked, and the message begins "simpleIDE blocked shell command". That text proves the hook did it and not the sandbox |
| Q9 | A real MEDIUM task: "Implement labels(values) to strip and lowercase strings, drop empties, and remove duplicates keeping first-seen order. Add unittest cases. This is a MEDIUM task." | `sx mem export --task <slug>`, `sx stats`, the dispatch table | Skill loaded; goal and 2 to 5 criteria recorded; `sx check` run; one reviewer pass; result recorded; task closed; `large.md` never opened |
| Q10 | Start another MEDIUM task, record its goal, then tell the session to stop | The session | One warning that the task is still open, shown once and not repeated |
| Q11 | With that task open, quit and reopen the host. If the host has a manual compaction command, run it too | The first lines of context | At most 5 lines: task, request id, goal, criteria count, open questions |
| Q12 | "Save a lesson that labels() must keep first-seen order." Then in a second project: `sx mem search order` | The search result | The lesson appears. In Codex's sandbox it may queue; then `sx mem sync` outside Codex moves it |
| Q13 | Fresh session; read the host's context or usage readout before typing anything | The readout | Tokens attributable to the rule plus agent and skill descriptions at or under about 1,000. By byte count today: rule 1,650 bytes plus 1,419 characters of descriptions, roughly 770 tokens |
| Q14 | `time (echo '{}' \| python3 .simpleide/sx.py hook resume --host codex)` and the same for the other five handlers | The timing | Each under 100 ms |

### 7.3 What each result means

| Result | What you change |
|---|---|
| Workers launch and run on the cheap model | Nothing. This is the design working |
| Workers launch but run on the parent's model | Delegation saves no money on this host. Set workers to `inherit` with low effort, and delegate only when it keeps noise out of the main context (design §9.3). Use a mid-tier main model for everyday sessions |
| `sx-*` agents do not appear or cannot launch | Use the single-session fallback on this host: the main session does the roles in order. The rule already says this. Record the host as "no subagents" |
| capture-request does not fire | The planner and reviewer lose the word-for-word request. Workaround: the main session saves it first with `sx mem add request`. Record the host as "no capture" |
| dispatch-guard is advisory only | Brief quality relies on the skill and template. Count malformed briefs from the dispatch table during Stage 3 |
| shell-guard does not block | Do not rely on it. The host's own sandbox and approvals stay in charge, which they always were (design §14) |
| stop-check or resume do not fire | Add one line to the session habit: run `sx mem recent --task <slug>` when resuming. Log it in the backlog as a per-host limit |
| Idle cost over 1,000 tokens | Find what else is loading. In a clean project it should not happen |

**Stage 2 ends with**: the host's row in `docs/verified.md` filled from live evidence, the decisions from 7.3 applied to `core/models.json` and the README's per-host notes, commit, tag `simpleide-v0.4-<host>`.

If three or more of Q3, Q5, Q7, Q8, Q10 and Q11 fail on the first host, stop and qualify the second host before Stage 3. A kit whose hooks work nowhere needs a different Stage 4 from one whose hooks work in one place.

---

## 8. Stage 3: use it on real work (1 to 2 weeks of normal use, you)

Goal: 5 real tasks closed, then keep going toward the 15 that gate G3 needs.

**Setup**

1. Install into the real projects you work in, per project: `--dry-run` first, then install, adding `--hooks` only on hosts where Stage 2 saw them work.
2. Commit the `.simpleide/` runtime and the generated agent and skill files in each project. Worktrees only receive committed files.
3. Decide where shared lessons live. Default `~/.simpleide/shared.db`. For Codex, either leave lessons queuing and run `sx mem sync` now and then, or add `~/.simpleide` to Codex's writable roots yourself (design §8.4). The installer prints the lines and never applies them.

**Per task**

- Say the size, or let the session size it and correct it if it is wrong. Note every time it over-delegates a SMALL task.
- For MEDIUM and LARGE: goal and criteria recorded before work starts, `sx check` after, one reviewer pass, close with an explicit outcome, export.
- You judge acceptance. Close with `--by user` only when you actually looked and agreed.
- At the end, record usage from the host's usage page: `sx stats --task <slug> --tokens N --cost X --usage-source "codex usage page"`.

**Keep a friction log** in `docs/pilot-log.md`, one line per event: which task, what went wrong or cost time, whether it broke the result. This log, not a reviewer, drives Stage 4 and the backlog.

**Limits while Stage 5 is not done**: one checkout per task, or worktrees only where nobody deletes `.simpleide/context.json`. Do not partially uninstall hosts.

**Include at least one LARGE task** so the planner, tester and worktree paths run once for real.

**Done when**: 5 tasks closed with outcomes, at least one of each size; `sx stats` prints them; the friction log exists. Anything that produced a wrong result is fixed and has a test. Tag `simpleide-v0.5`.

---

## 9. Stage 4: close the architecture gaps (1 to 2 days, one worker, after 5 pilot tasks)

These are the parts of the design that are missing or that drifted. Each is small. Do them in this order and stop when the size budget is reached.

### 9.1 One command to start a task, one to finish it

Restores design §8.3's intent without the unsafe guessing the repairs removed.

- `sx task start <slug> --size MEDIUM --goal "..." --criterion "..." [--criterion "..."] (--request Pn | --host H --session S)` records the goal and criteria and binds the task in one transaction. With no binding given, it lists the captured requests that have no task and exits non-zero. It never picks one itself.
- `sx task finish <slug> --result "..." --outcome accepted|failed|abandoned --by assistant|user --refs "..." [--out FILE]` records the result, applies the same check gate as `task close`, closes, and exports.
- The existing commands stay. `SKILL.md` and the rule switch to the two new ones and get shorter.

Done when: a MEDIUM task needs two ledger commands from the model instead of five or more; `SKILL.md` is smaller than today's 2,534 bytes; every gate that `task close` enforces is enforced by `task finish` through the same function.

### 9.2 Usage capture where the host exposes it

Design §12.1 planned this and it was not built. Today tokens and cost are typed in by hand.

- The stop-check and return-log hooks store the transcript path when the host's payload includes one. Storing a path is cheap and keeps the hook under 100 ms.
- New: `sx stats --task <slug> --from-transcript [PATH]` reads that transcript, sums the usage fields it finds, and records them with the source named. Parsing happens in this command, never in a hook.
- Hosts with no usable transcript stay manual. `sx stats` already prints coverage, so a partial total is never shown as complete.

Done when: on a host that passes transcript paths, a closed task shows tokens without manual entry, with the source recorded; a missing or unreadable transcript leaves usage "unknown" and prints why.

### 9.3 `sx doctor` prints the budgets

Add back what was lost: rule block bytes against 2,500; each skill and agent description against 400 characters; `SKILL.md` bytes against 3,072; the time of each of the six hook handlers on empty input against 100 ms; and, per host, which of the Stage 2 checks are recorded as seen in `docs/verified.md`. Doctor fails when a budget is exceeded.

### 9.4 Voice profile

Needs you: 3 to 5 samples of your own writing, about 300 words or more each (emails, write-ups, notes). `docs/personal-skills/` has no profile to reuse. Run the `sx-writeup` skill's profile step once; it writes `~/.simpleide/voice.md`, under 40 lines, style only.

Done when: a write-up generated from a real pilot task reads like you, and every factual claim in it traces to a record in the export.

### 9.5 Model defaults from what Stage 2 found

- Replace any model id that Stage 2 showed is ignored or unavailable.
- Cursor: replace `inherit` for workers with the exact id of a cheap model from its picker, if Stage 6 shows the field is honored.
- Claude Code: the design has the reviewer on Opus for LARGE and Sonnet otherwise. `models.json` holds one model per role, so put the LARGE override in `references/large.md` as a per-call instruction.
- Check the Claude prices on Anthropic's own pricing page before trusting the ratios in design §9.2; those came from third parties.

### 9.6 Antigravity

Agents first: `.agents/agents/sx-*.md` with `subagent: true` and `mainAgent: false`, and no `tools:` list until tool names are confirmed on your install (the design notes a misspelled name can hang a subagent). Hooks only after its hook format is seen working. Shell policy through `commandExecutionPolicy` in the agent files, as design §10.1 says.

**Stage 4 ends with**: suite green, `sx doctor` passing with every budget printed, `sx.py` at or under 1,800 lines, commit, tag `simpleide-v0.6`.

---

## 10. Stage 5: remaining defects and a simplification pass (about 2 days, one worker)

### 10.1 R3: uninstalling one host must not change another

Where: `install.py` lines 382, 447 and 451. Every run reloads the package's model map and re-renders every remaining host.

Change: make `--models` default to "not given". On uninstall, load the installed `.simpleide/models.json` and leave surviving hosts' files byte for byte unchanged. On adding a host, use defaults for the new host only. Reject `--uninstall` together with `--models`.

Done when: install Cursor and Codex with a custom Codex worker model, uninstall Cursor, and Codex's agent files and `models.json` are identical before and after. Same for a global install. Deleting the original custom map file first changes nothing.

### 10.2 R2: a lost context file must not create a second ledger

Where: `core/sx.py`, `store_root()` (107) and `ledger()` (127).

Smallest fix: before opening or creating a store, ask Git whether this checkout is a linked worktree (its Git directory differs from the common directory). If it is, and there is no valid `.simpleide/context.json` and no `SIMPLEIDE_STORE`, stop with a recovery message and create nothing. Recovery: `sx worktree reconcile <slug> --apply`, run from the parent, rewrites the pointer after matching the worktree path against the parent's registry and store id. Add `sx context standalone` for a linked worktree you really do want to be independent.

This is deliberately smaller than the registry in Git's common directory that the 12 November plan proposes. Build that only if the pilot log shows context files being lost in practice.

Done when: deleting the context file in a managed worktree makes `mem`, `check` and `task` commands fail clearly without creating `project.db`; reconcile restores access to the original record ids; a plain project and a declared standalone worktree still work.

### 10.3 Simplification

One pass with the friction log open:

- Remove code paths that no host exercised during Stages 2 and 3, for example correlation branches for payload shapes no host sends. Keep the tests that guard real behavior.
- If a host's hooks turned out unusable, remove that host's hook registration from the installer and say so in the README, instead of carrying dead configuration.
- Close out the old plans: mark `repair-plan-2026-11-11.md` and `root-cause-repair-plan-2026-11-12.md` as superseded by this plan, with one line each saying which parts were done and which were dropped.
- Confirm the suite is green on remote CI.

**Stage 5 ends with**: gate G2 met, all four reproductions passing as unit tests, tag `simpleide-v0.7`.

---

## 11. Stage 6: qualify the other hosts (half a day each, you)

Repeat Stage 2's fourteen checks in a clean project per host, in this order: Claude Code, Cursor, Antigravity. Host-specific points to watch, taken from the design's verification notes:

| Host | Watch for |
|---|---|
| Claude Code | `CLAUDE.md` imports `AGENTS.md`. Hooks live in `.claude/settings.json`. The installer registers `PreCompact` for resume here, so test compaction. Its hooks receive a transcript path, which makes it the best host for 9.2 |
| Cursor | Reported bugs: the `model` field is sometimes ignored, and `readonly` subagents sometimes refuse to start. Q6 settles the first; launching `sx-planner` settles the second. Its `subagentStart` hook can deny, so Q7 should block here |
| Antigravity | Custom subagents inside the IDE were disputed by one source. If they do not load, record "no subagents" and use the fallback. Subagents choose a tier (`flash`, `pro`), not a model. No hooks until the format is confirmed |
| Codex | `SubagentStart` cannot block. The documented start payload lacks the tool call id, so starts cannot be joined to their briefs; pending rows are expected. Default sandbox blocks `~/.simpleide` |

Result: a capability table in the README, filled only from live rows.

| Capability | Claude Code | Cursor | Codex | Antigravity |
|---|---|---|---|---|
| Rule loads | | | | |
| Subagents launch | | | | |
| Worker model honored | | | | |
| Request captured | | | | |
| Bad brief blocked | | | | |
| Destructive shell blocked | | | | |
| Stop warning | | | | |
| Resume after restart / compaction | | | | |
| Usage captured automatically | | | | |

**Done when**: gate G1 is met (two hosts fully recorded), the other two are recorded as far as they got, and the installer installs hooks only where they were seen working. Tag `simpleide-v0.8`.

---

## 12. Stage 7: the nine-task comparison (spread over 2 to 3 weeks of normal work, you)

Design §12.2, made concrete.

**Choose tasks.** Nine things you need done anyway: three SMALL, three MEDIUM, three LARGE, mixed across code, research and documents. List them in `docs/comparison.md` before running any.

**Write criteria first.** For each task, 2 to 5 checkable criteria and the starting commit, written before the first arm runs and not edited afterwards.

**Arms**

| Arm | What it is | Runs |
|---|---|---|
| A | One strong model, no kit, no subagents | All 9 |
| B | simpleIDE as installed | All 9 |
| C | AgentNexus, or Mark 2 if it can run the task unaided | Only the tasks it can run at all; expect 3 or 4 |

**Keep it fair**

- Each arm starts from the same commit on its own branch (`cmp/<task>/<arm>`).
- Rotate the order across tasks (A-B-C, B-C-A, C-A-B). Whichever arm runs second benefits from what you learned watching the first.
- Arm B uses a fresh `SIMPLEIDE_HOME` per task, or you note which lessons carried over.
- Arm A runs in a project without simpleIDE installed. Arm C runs in the AgentNexus checkout. Arms A and B do not.
- Same host and same main model for A and B on a given task.

**Record per run**: accepted or not, judged by you against the frozen criteria; tokens or cost with its source; wall-clock time; number of dispatches; reviewer findings that were real versus not. Failed and abandoned runs stay in the totals.

**Budget your effort.** That is 18 runs for A and B plus a few for C. SMALL runs take minutes. Do the three LARGE tasks last, when the kit is most stable.

**Done when**: every row in `docs/comparison.md` is filled from observed runs. Nothing is estimated.

---

## 13. Stage 8: tune and cut (half a day, you plus one worker)

Apply design §12.3 mechanically, then write what changed.

| If the numbers show | Then |
|---|---|
| B does not beat A on cost per accepted task for a size | Cut steps for that size until it does, or route that size to a single agent in the rule |
| Reviewer finds a real problem in fewer than about 1 in 5 MEDIUM tasks | Remove the review step from MEDIUM; keep it for LARGE |
| The tester's tests never caught anything the worker's own check missed | Tester on LARGE only |
| SMALL tasks were delegated when the brief was longer than the work | Tighten the SMALL row of the rule |
| The cheap worker tier failed a kind of task twice or more | Raise the default tier for that kind in `models.json` |
| A hook never fired, or never changed an outcome, on a host | Remove it from that host's install |
| C beat B on a task | Name the one mechanism that did it. That goes to Stage 9 as a port candidate |

Nine tasks is a small sample. A difference under about 20 percent is a tie; decide ties in favor of fewer steps.

**Done when**: `rule.md`, `SKILL.md` and `models.json` reflect the decisions, `docs/comparison.md` ends with a "what was cut and why" list, gate G4 is met. Tag `simpleide-v0.9`.

---

## 14. Stage 9: sort AgentNexus and Mark 2 (about 1 day, you plus one scout-style worker)

This is the design's Phase 6. It is where "full orchestration for the future" gets decided, on evidence.

**Inventory** (a worker lists; it decides nothing). What is in the repo today:

- 41 agent definitions in each of `.claude/agents`, `.cursor/agents` and `.codex/agents`, including `master-orchestrator`
- The `agents/` tree: `coding` (Daily Coder), `research` (Research Forge), `daily-task`, `ide` (bridge, canonical agents, policy, contracts, DeepSeek harness), `shared` (agent-core)
- Hooks: agent authority, read-only enforcement, path jail, unbridged-write denial, session audit
- `gui` (dashboard), `mark 2`, `mark2test`, `docs/personal-skills`

**For each part, answer four questions**

1. What does it do that simpleIDE does not?
2. Did that mechanism change an outcome in the comparison or in your own use? Cite the task.
3. What does it cost: idle tokens, maintenance, failure modes?
4. Verdict: keep as is, port the mechanism into simpleIDE, or retire.

**Write** `docs/agentnexus-audit.md`: one row per part with the verdict and the evidence. Parts with no evidence either way are marked "retire unless used within 30 days", not kept by default.

**Likely port candidates to test, not decisions**

| Mechanism | From | Port only if |
|---|---|---|
| Durable continue after a restart, with saved configuration | Mark 2 | LARGE tasks in the pilot or comparison failed at a restart or hand-off |
| Request-to-scope discovery | Mark 2 | Scouts were a large share of cost on a big codebase |
| Write approval through a gateway | AgentNexus bridge | You need audited writes that the host's own approvals cannot give. Design §14 says simpleIDE adds no second authority, so this would stay outside the kit as an optional layer |
| Session audit | AgentNexus hooks | It records something return-log and `sx stats` do not |
| Personal skills | `docs/personal-skills` | They are skills already; install them beside simpleIDE's two, watching the idle budget |

**After the audit, growth is by trigger only**

| If your records show | Then consider |
|---|---|
| Searches return nothing though a relevant lesson exists | Better search. Design §8.5 sets this trigger |
| You want work queued to run unattended | A background runner around the same ledger |
| The same kind of task keeps recurring | A dedicated skill for it |
| A third project needs different checks or roles | Per-project overrides in `.simpleide/config.json` |

**Done when**: gate G6 is met and retired parts are removed or archived in one commit that can be reverted.

---

## 15. Stage 10: release 1.0 and keep it healthy (half a day)

1. README is final: install, the per-host capability table from live evidence, the two task commands, limits, upgrade and rollback.
2. `PLAN.md` gets a status line pointing here. This plan gets a closing section listing each gate and the evidence for it.
3. Global install on your machine, if Stage 3 showed per-project installs are a chore.
4. Tag `simpleide-v1.0`. CI green.

**Routine afterwards**

| When | Do |
|---|---|
| After any host update | `sx doctor`, then re-run Q2, Q5 and Q8 from Stage 2. Formats moved several times in 2026 |
| Weekly | `sx stats`. Look at cost per accepted task by size and at over-delegated SMALL tasks |
| Every 90 days | `sx mem prune`, and delete lessons that were never opened |
| When a real task fails because of the kit | Fix it with a test. This is the only path for new code after 1.0, apart from the triggers in section 14 |

---

## 16. Worker briefs, ready to paste

Each brief is complete on its own. Replace `<repo>` with the simpleIDE checkout.

### Stage 1

```text
Fix two defects in simpleIDE and nothing else.

Repository: <repo>
Read first: docs/postrepair-review-2026-11-11.md (sections R4 and R1),
docs/evidence/postrepair_review.py, and section 6 of
docs/finalization-plan-2026-11-14.md, which defines the exact scope.

GOAL
1. R4: sx check, pack and task close must never report a current PASS when
   a Git submodule's commit or contents changed after the check ran.
2. R1: sx worktree merge, clean and reconcile must act on the worktree's
   actual branch and commit, not the branch name stored in SQLite.

DO
- Implement the changes listed in sections 6.1 and 6.2 of the plan.
- First port the R4 and R1 reproductions into tests/test_repairs.py and
  show them failing against the current code. Then fix.
- Keep one function that decides check status; remove the string search
  for "PASS current" in close_task.

DO NOT TOUCH
- R2 and R3. install.py. Hook handlers. The skills and rule.
- No new commands, no new files outside tests/ and docs/evidence/.
- No schema change unless a real v1-to-v2 migration with backup and
  tests comes with it.
- sx.py must stay at or under 1,800 lines.

DONE WHEN
- Every "Done when" bullet in sections 6.1 and 6.2 has a passing test.
- python3 -m unittest discover -s tests -v passes on Python 3.10 and 3.12.
- A repository with no submodules and a normal two-piece worktree merge
  behave exactly as before.

STOP AND REPORT if the fix needs more than about 150 added lines, or if
you find another defect. Log other findings in docs/backlog.md with a
reproduction. Do not fix them.

RETURN: changed files, the before/after test output for R4 and R1, the
final line count of sx.py, and anything added to the backlog.
```

### Stage 4

```text
Close five design gaps in simpleIDE. Scope is section 9 of
docs/finalization-plan-2026-11-14.md, items 9.1, 9.2, 9.3, 9.5.
Use docs/pilot-log.md to settle any detail the plan leaves open.

GOAL
- sx task start and sx task finish (9.1), reusing the existing bind and
  close functions so no gate is duplicated or weakened.
- sx stats --from-transcript, with hooks storing only the path (9.2).
- sx doctor prints and enforces the size and timing budgets (9.3).
- core/models.json and references updated from docs/verified.md (9.5).
- rule.md and SKILL.md switched to the two new commands and made shorter.

DO NOT TOUCH
- Existing commands and their behavior. Binding must never be inferred
  from the newest record. Hooks must not parse transcripts.
- No new dependencies. Standard library only.

DONE WHEN
- A MEDIUM task needs two ledger commands from the model.
- SKILL.md is under 2,534 bytes and rule.md under 2,500.
- sx doctor fails when a budget is exceeded and prints each number.
- Full suite passes on Python 3.10 and 3.12; sx.py at or under 1,800 lines.

STOP AND REPORT if the line budget cannot be met without removing
something; propose what to remove instead of exceeding it.

RETURN: changed files, new command help text, doctor output, line counts.
```

### Stage 5

```text
Fix the last two reproduced defects in simpleIDE and simplify.
Scope is section 10 of docs/finalization-plan-2026-11-14.md.

GOAL
- R3 (10.1): uninstalling one host leaves every surviving host's files
  and model settings byte for byte unchanged.
- R2 (10.2): a managed worktree with a missing context file fails before
  any store is created, and reconcile can restore the pointer.
- Simplification (10.3): remove code no host exercised, guided by
  docs/verified.md and docs/pilot-log.md.

DO
- Port R2 and R3 from docs/evidence/postrepair_review.py into unit tests
  and show them failing first.
- Use the smallest fix described in the plan. Do not build the registry
  in Git's common directory.

DO NOT TOUCH
- The check-status and worktree branch logic fixed in Stage 1.
- Ownership, rollback and hook-preservation behavior in install.py.

DONE WHEN
- All four reproductions (R1 to R4) pass as normal unit tests.
- Every "Done when" bullet in 10.1 and 10.2 has a passing test.
- Suite passes on Python 3.10 and 3.12. sx.py at or under 1,800 lines,
  install.py at or under 600.
- The two older repair plans carry a "superseded" line.

RETURN: changed files, what was removed and the evidence that it was
unused, test output, line counts.
```

---

## 17. Order and time

| Stage | What | Who | Time | Needs |
|---|---|---|---|---|
| 0 | Commit, tag, decide | You | 30 to 60 min | Nothing |
| 1 | Fix R4 and R1 | One worker | About 1 day | Stage 0 |
| 2 | Qualify first host | You | Half a day | Stage 1; Codex after 16 November, or Claude Code now |
| 3 | Pilot on real work | You | 1 to 2 weeks, normal use | Stage 2 |
| 4 | Close design gaps | One worker | 1 to 2 days | 5 pilot tasks; your writing samples for 9.4 |
| 5 | R2, R3, simplify | One worker | About 2 days | Stage 4 |
| 6 | Qualify other hosts | You | Half a day each | Stage 5 |
| 7 | Nine-task comparison | You | 2 to 3 weeks, normal use | Two hosts qualified |
| 8 | Tune and cut | You and a worker | Half a day | Stage 7 |
| 9 | Sort AgentNexus and Mark 2 | You and a worker | About 1 day | Stage 8 |
| 10 | Release 1.0 | You | Half a day | All gates |

Stages 3 and 4 can overlap after the fifth pilot task. Stage 6 can run alongside Stage 3 for hosts you are not piloting on. Calendar time to 1.0 is about five to six weeks, almost all of it normal work done through the kit and little of it building.

---

## 18. Risks

| Risk | Effect | Response |
|---|---|---|
| No host honors the worker's model | The price argument for delegation is gone | simpleIDE still pays through scripts, small context and records. Delegate for context isolation only; say so in the rule |
| Hooks do not fire on your main host | Enforcement becomes instruction | Run that host on the rule and manual `sx` commands; keep hooks for hosts where they work |
| The audit loop restarts | Weeks of hardening, no use | Section 4. The backlog is the release valve |
| The pilot shows the explicit commands are too heavy | The model skips them | 9.1 is first in Stage 4 for this reason |
| The comparison shows B loses to A at some size | Process cut for that size | That is the intended outcome of measuring, not a failure |
| A host update changes a file format | An install breaks silently | `sx doctor` and the three re-checks after every update |
| Third-party model prices are wrong | Routing tuned to wrong ratios | Check vendor pricing pages in 9.5 |

---

## 19. Tracking

- [ ] Stage 0: committed and tagged; remote CI seen; D1, D2, D3 decided
- [ ] Stage 1: R4 and R1 fixed with tests
- [ ] Stage 2: first host qualified live, row filled in `docs/verified.md`
- [ ] Stage 3: 5 real tasks closed; friction log kept
- [ ] Stage 4: start and finish commands; usage capture; doctor budgets; voice profile; model defaults
- [ ] Stage 5: R2 and R3 fixed; simplification done; old plans marked superseded
- [ ] Stage 6: second host qualified (gate G1); remaining hosts recorded
- [ ] Stage 7: nine tasks compared
- [ ] Stage 8: decision rules applied; cuts written down
- [ ] Stage 9: AgentNexus and Mark 2 audited
- [ ] Stage 10: 15 real tasks closed; `simpleide-v1.0` tagged
