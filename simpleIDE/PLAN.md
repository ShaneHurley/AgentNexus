> Status, November 11: the original design below is historical. Local repairs, migrations and verification are documented in [repair completion](docs/repair-completion-2026-11-11.md). Full native-host enforcement and the nine-task comparison remain separately qualified/pending.

# simpleIDE: full implementation plan

Implementation note (10 November 2026): the NEW/CHANGE labels below describe the original planning snapshot. The local code for phases 0, 2, 3 and 4 is now implemented and covered by the test suite. Live host verification (phase 1), the nine-task comparison (phase 5), and the evidence-based AgentNexus audit (phase 6) remain pending. See [README.md](README.md), [docs/verified.md](docs/verified.md) and [docs/comparison.md](docs/comparison.md).

Written 10 November 2026. This plan covers every rule, skill, tool, hook and subagent in simpleIDE, how they work together, and the order to build them in. Version 0.1 (the rule, one skill, four subagents, the memory CLI and the installer) already exists in this folder and passes its tests. Everything marked NEW or CHANGE below is not built yet.

Status labels used throughout:

- **BUILT**: in this folder now, covered by the 12 unit tests.
- **CHANGE**: built, but the verification research found it wrong or wasteful.
- **NEW**: not built.
- **VERIFY**: depends on tool behaviour that has only been read in documentation, not seen running.

---

## 1. The design in one page

One session is the accountable assistant. It sizes each request, does small things itself or hands them to one cheap worker, and only brings in a planner, parallel workers, a test author and a reviewer when the size of the job pays for them. Everything that can be done without a model is done by a script or a hook.

Five kinds of parts, each with one job:

| Part | Job | Cost when idle |
|---|---|---|
| **Rule** (1) | Tells the main session how to size work and when to delegate | about 600 tokens, every session |
| **Subagents** (5) | Do labour in their own context so the main context stays small | about 60 tokens each (the description) |
| **Skills** (2) | Hold the detailed playbooks, loaded only when needed | about 60 tokens each (the description) |
| **Tools** (1 script, 8 commands) | Do deterministic work: memory, test runs, scope checks, handoff packets, stats | 0 |
| **Hooks** (6) | Enforce and record without the model spending anything | 0, except two that add at most 5 lines |

Idle cost of the whole kit in a session: roughly 1,000 tokens. That is the budget, and section 2 holds it there.

---

## 2. The rules that keep it cheap

These are the design constraints. Every later section follows from them.

1. **Idle budget: 1,000 tokens.** The always-on rule stays under 2,500 bytes. No skill description over 400 characters. No hook may inject more than 5 lines.
2. **The main session's context is the expensive thing.** Every token it reads is re-read on every later turn. So: long output goes to a file and a 10-line summary comes back; exploration that would open more than about 5 files goes to a scout; test output never enters the main context in full.
3. **Delegation is not free.** Cursor's own documentation says five parallel subagents use roughly five times the tokens of one agent. A subagent pays to start, to read its brief and to re-open files. Delegate only when one of these is true:
   - the work would flood the main context (exploration, logs, large diffs);
   - the pieces are independent and can run at the same time;
   - the worker model is much cheaper than the main one (10 times or more, not 2 times).
4. **A script beats a model call.** Searching, counting, diffing, running tests, checking scope, building a handoff packet, recording what happened: all scripts.
5. **A hook beats an instruction.** Anything that must always happen (log the request, validate a brief, block a destructive command) is a hook, because instructions cost tokens and can be ignored, and hooks cost nothing and cannot.
6. **Load detail late.** The rule fits on a page. MEDIUM detail lives in the skill. LARGE, coding and research detail live in reference files the skill points to.
7. **Bounded loops.** Two repair rounds. Two attempts per brief before changing the brief or the tier. One review pass on MEDIUM.
8. **Measure, then keep or cut.** Every component must lower cost per accepted task or raise the acceptance rate in section 12's comparison. If it does neither, it is removed.

---

## 3. Inventory

| # | Component | Type | Status | Loaded when |
|---|---|---|---|---|
| 1 | `core/rule.md` | Rule | BUILT | every session |
| 2 | `sx-worker` | Subagent | BUILT | SMALL (sometimes), MEDIUM, LARGE |
| 3 | `sx-planner` | Subagent | BUILT | LARGE |
| 4 | `sx-tester` | Subagent | BUILT | coding tasks where a wrong result is costly |
| 5 | `sx-reviewer` | Subagent | BUILT | MEDIUM (once), LARGE |
| 6 | `sx-scout` | Subagent | NEW | exploration over about 5 files, on tools with no built-in explorer |
| 7 | `simpleide` | Skill | BUILT, CHANGE (split) | MEDIUM, LARGE |
| 8 | `sx-writeup` | Skill | NEW | final write-up on MEDIUM and LARGE; building the voice profile |
| 9 | `sx mem` | Tool | BUILT (as `mem.py`) | any time |
| 10 | `sx check` | Tool | NEW | after any code change |
| 11 | `sx scope` | Tool | NEW | before review |
| 12 | `sx pack` | Tool | NEW | when briefing the reviewer |
| 13 | `sx worktree` | Tool | NEW | LARGE with parallel writers |
| 14 | `sx doctor` | Tool | NEW | after install |
| 15 | `sx stats` | Tool | NEW | weekly, and for the comparison |
| 16 | `sx hook` | Tool | NEW | called by hooks only |
| 17 | capture-request | Hook | NEW | each user prompt |
| 18 | dispatch-guard | Hook | NEW | each subagent start |
| 19 | shell-guard | Hook | NEW | each shell command |
| 20 | return-log | Hook | NEW | each subagent finish |
| 21 | stop-check | Hook | NEW | when the session tries to finish |
| 22 | resume | Hook | NEW | session start and after context compaction |
| 23 | `install.py` | Installer | BUILT, CHANGE | install time |

---

## 4. The rule (BUILT)

`core/rule.md`, placed in a marked block in `AGENTS.md`. It contains only what the main session needs on every request:

- the SMALL / MEDIUM / LARGE table and what to do for each;
- tools before models;
- the six-field brief (Goal, Context, Do, Do not touch, Done when, Return);
- cheapest model that can do it, and the two-failures rule;
- ask or assume;
- the two memory commands (search before, lesson after);
- what to do when the tool has no subagents.

Changes planned:

- **CHANGE**: add one line on scouting ("exploration that would open more than about 5 files goes to a scout or the built-in explorer; ask for locations and facts, not file contents").
- **CHANGE**: replace `mem.py` with `sx.py mem` once the tools are merged into one script (section 7).
- Keep it under 2,500 bytes. If a line is added, a line is removed.

Why it is a single static block: every one of these tools caches the start of the prompt. A rule that never changes is paid for at the cached rate. Nothing dynamic is ever written into it.

---

## 5. Subagents

All five are defined once in `agents/sx-*.md` and rendered into each tool's format by the installer. Each has a fixed return block, so the main session reads 5 to 10 lines back, not a narrative.

### 5.1 sx-worker (BUILT)

- **Job**: carry out one brief completely. Code change, document section, mechanical edit, lookup.
- **Gets**: one brief. Nothing else.
- **Rules**: reads only what the brief points to; stays in the files it was given; stops and reports if the brief is wrong or incomplete; never starts other agents.
- **Returns**: `STATUS / CHANGED / RESULT / CHECKED / NOTES`.
- **Model**: the cheap tier (section 9).

### 5.2 sx-planner (BUILT)

- **Job**: the independent reading of what you asked for. It gets your request word for word (by record id, from the capture-request hook) before it sees anyone's interpretation.
- **Returns**: goal, requirements marked stated or implied, assumptions, questions that would change the outcome, numbered acceptance criteria, interfaces to fix first, a work split with file ownership, top risks.
- **Rules**: read-only; may not invent requirements or enlarge the task; must say so when one model in one pass would do the job better than a split.
- **Model**: the strong tier. This is the one place the strong model is used as a subagent.
- **Used**: LARGE only. On MEDIUM the main session writes the criteria itself.

### 5.3 sx-tester (BUILT)

- **Job**: write tests from the acceptance criteria and agreed interfaces without reading the new implementation.
- **Rules**: each criterion gets at least one test that would fail if the behaviour were wrong; edge cases and failure paths where plausible; a regression test for bug fixes; writes test files only.
- **Returns**: `STATUS / FILES / COVERS / NOT COVERED / RUN WITH`.
- **Runs**: at the same time as the worker. Its tests are executed later, against the integrated revision, never against a half-finished tree.

### 5.4 sx-reviewer (BUILT)

- **Job**: adversarial review and the end-of-task alignment check in one pass. It gets your original request, the criteria and the actual diff (as an `sx pack` packet), not the worker's summary.
- **Order of checks**: alignment with the request, correctness, scope, weak tests, simpler alternatives.
- **Rules**: read-only; every finding needs a file and line, a breaking input, a written-out failing test or a stated rule; "nothing found" is a valid result.
- **Returns**: `VERDICT / CRITERIA / FINDINGS / NOT CHECKED`.
- **Runs**: once on MEDIUM. On LARGE, at the same time as the test run.
- **Model**: one tier above the worker, so it is not the same model grading its own kind of mistake.

### 5.5 sx-scout (NEW)

- **Job**: find things. "Where is X handled", "which files touch Y", "what does this library's API look like". It reads many files so the main session does not.
- **Returns**: at most 15 lines of `path:line` locations and established facts, each marked observed or inferred. Never file contents.
- **Rules**: read-only; no opinions about what to change.
- **Model**: the cheapest tier available.
- **Installed**: only on Codex and Antigravity. Claude Code and Cursor ship a built-in explorer that already does this on a fast model, so there the rule points at the built-in one and no file is added.

### 5.6 What is deliberately not a subagent

| Role from the original brief | Where it lives instead | Why |
|---|---|---|
| Intent / alignment agent | planner (start) and reviewer (end) | Two fresh readings of the original request already exist at the two points it matters. A third agent would repeat them. |
| Orchestrator | the main session | Subagents cannot reliably run other subagents across all four tools. The main session is the only place orchestration works everywhere. |
| Documenter | `sx mem export` plus the `sx-writeup` skill | The record is assembled by a script from stored entries. Only the final tidy-up needs a model. |
| Memory agent | `sx mem` | Search and storage are SQL. |
| Test executor | `sx check` | Running tests and summarising the output is a script. |

### 5.7 Corrections from verification (CHANGE)

| Tool | What changes | Evidence level |
|---|---|---|
| Antigravity | It does support custom subagents. Write `.agents/agents/sx-*.md` (global: `~/.gemini/config/agents/`) with `name`, `description`, `subagent: true`, `mainAgent: false`, and `model: pro` or `flash`. | Official docs. Support inside the IDE (as opposed to the app and CLI) is disputed by one third-party post: VERIFY. |
| Antigravity | Only add a `tools:` allowlist with tool names copied from its docs. The docs warn that a misspelled tool name can make the subagent hang. Until names are confirmed on your install, omit the list. | Official docs |
| Cursor | `model: fast` is no longer documented. Use `inherit`, or an exact id as shown in Cursor's model picker. | Official docs |
| Cursor | Reported bugs: the `model` field is sometimes ignored, and `readonly` subagents sometimes refuse to start. Check both on the first run. | Forum reports, acknowledged by staff |
| Codex | Remove `sandbox_mode` from agent files. Codex ignores it there; subagents inherit the parent's sandbox. Read-only for planner and reviewer becomes an instruction plus the shell-guard hook. | Official docs |
| Codex | Stop running every role on `gpt-6.1-sol`. Workers move to `gpt-6-luna` (section 9). | Official price list |
| Claude Code | No change. Keep `CLAUDE.md` importing `AGENTS.md`; this works whether or not your version reads `AGENTS.md` natively. If you ever set a role to Fable, use the full model id, since the `fable` alias has a reported fallback bug. | Official docs plus one issue report |

---

## 6. Skills

Skills cost about 60 tokens each until loaded. Two is enough.

### 6.1 simpleide (BUILT, CHANGE)

Today `SKILL.md` is 6.6 KB (about 1,650 tokens) and a MEDIUM task loads all of it, including LARGE instructions it will not use. Split it:

| File | Contents | Size target | Loaded |
|---|---|---|---|
| `SKILL.md` | Step 0 memory search, MEDIUM steps, mid-task questions, lessons, when to stop adding process | under 3 KB | every MEDIUM and LARGE |
| `references/large.md` | Planner, interface freeze, parallel dispatch, integrate, test and review together, bounded repair, acceptance | under 3 KB | LARGE only |
| `references/coding.md` | Independent tests, worktrees, `sx check`, `sx scope`, merge order | under 2 KB | coding tasks only |
| `references/research.md` | Splitting questions between scouts, source quality, checking each claim against its source, what to do with conflicts | under 2 KB | research tasks only |
| `references/brief-template.md` | The template, one worked example, four checks before sending | BUILT, 1.7 KB | when writing a brief for the first time in a session |
| `references/models.md` | The routing table from section 9 and the escalation ladder | under 1.5 KB | only when choosing a model per call |

Net effect: a MEDIUM task loads about 750 tokens of playbook, down from about 1,650.

### 6.2 sx-writeup (NEW)

Two jobs, both rare, which is why they are a separate skill and not part of the playbook:

1. **Final write-up.** Take `sx mem export --task <slug>` (assembled by script from verified records) and turn it into a short readable document: what was done, why, how it was checked, what is open. Implemented, proposed and unresolved stay in separate sections. Facts come only from the records.
2. **Voice profile.** Once, from writing samples you provide, produce `~/.simpleide/voice.md`: typical sentence length, vocabulary you use and avoid, how much technical detail, how formal, how you open and close. Under 40 lines. Every later write-up reads that file. The profile describes style only; it never licenses adding content.

Before building the profile, check whether AgentNexus already has one. The repo has `tests/writing/` and `docs/personal-skills/`, which suggests it might. Reuse it if so.

### 6.3 Where skills install (CHANGE)

One copy in `.agents/skills/simpleide/` covers Cursor, Codex and Antigravity; all three read that folder. Claude Code does not, so it gets a second copy in `.claude/skills/`. The separate `.cursor/skills/` copy the installer writes today is redundant and is dropped.

---

## 7. Tools

One script, `.simpleide/sx.py`, standard library only, with subcommands. `mem.py` stays as a two-line alias so nothing already installed breaks. Every command prints a short summary and writes anything long to `.simpleide/artifacts/`.

### 7.1 sx mem (BUILT)

`search`, `add`, `lesson`, `show`, `recent`, `export`, `forget`, `sync`, `stats`. Details in section 8.

### 7.2 sx check (NEW)

Runs the project's own verification commands and keeps the output out of the model's context.

- **Config**: `.simpleide/config.json`, for example `{"checks": {"test": "pytest -q", "lint": "ruff check ."}}`. On first run it proposes commands from what it finds (`pyproject.toml`, `package.json` scripts, `Cargo.toml`, `go.mod`) and writes the file for you to confirm. It never guesses silently on later runs.
- **Run**: `sx check [name] --task <slug>`.
- **Output to the model**, at most 15 lines: pass or fail, counts, duration, the first three failures with up to 10 lines each, and the path of the full output.
- **Side effects**: full output saved to `.simpleide/artifacts/<slug>/<name>-<n>.txt`; a `test` record written automatically with the command, outcome and artifact path.
- **Why**: test logs are the largest avoidable thing agents paste into their own context. This is the biggest single token saving in the kit after not delegating small tasks.

### 7.3 sx scope (NEW)

`sx scope --base <ref> --allow "src/api/**" --allow "tests/**"` lists changed files that fall outside the allowed patterns. Empty output means in scope. Replaces a model reading the diff to answer "did it touch anything it should not have".

### 7.4 sx pack (NEW)

Builds the reviewer's handoff packet from the database and git, at most 25 lines:

```
REQUEST   P41 (original, verbatim: sx mem show P41)
CRITERIA  P42 P43 P44
BASE      a1b2c3d
CHANGED   src/api/export.py +48 -12 | tests/api/test_export.py +61 -0
CHECKS    test: PASS 214/214 (artifact .simpleide/artifacts/export/test-2.txt)
SCOPE     ok
READ      git diff a1b2c3d -- <paths>
```

The reviewer opens what it needs. Nothing is pasted.

### 7.5 sx worktree (NEW)

`add <slug> <piece>`, `merge <slug>`, `clean <slug>`. Thin wrappers around `git worktree` that name branches consistently, merge in the order pieces were declared, stop on the first conflict, and refuse to clean a worktree with uncommitted work. Used only when two writers could touch the same files.

### 7.6 sx doctor (NEW)

Checks the install without a model: files present per tool, Python version, FTS5 available, shared database writable, hooks registered, rule block under size, model ids in `models.json` non-empty. Then prints the three things only you can check in each tool (agents visible, skill visible, which model a worker actually ran on).

### 7.7 sx stats (NEW)

Reads the task ledger (section 8.3) and prints, per size: tasks, accepted, average dispatches, repair rounds, check failures, and tokens or cost where captured. This is the "learn from measured results" part: it is how you find out whether delegation is paying.

### 7.8 sx hook (NEW)

`sx hook <event>` is the single entry point every hook calls. It reads the tool's JSON on stdin, normalises the differences between tools, and does the work in section 10. One script means one place to fix.

---

## 8. Memory

### 8.1 What exists (BUILT)

- `<project>/.simpleide/project.db`: one table of records with kind, task, title, body, tags, refs, timestamp. Kinds: goal, criteria, assumption, question, decision, finding, test, result, lesson, note.
- `~/.simpleide/shared.db`: lessons from every project, with the project they came from.
- Search: SQLite FTS5 with BM25 ranking, title weighted highest. Falls back to `LIKE` when FTS5 is missing. Queries are tokenised and quoted, so odd characters cannot break them.
- Output: one line per hit, at most 160 characters of body, 5 hits by default. A search costs the model about 200 tokens at most.
- Duplicates are detected by content hash and not stored twice.
- If the shared file cannot be written (a sandbox), the lesson is queued in the project file and `sync` pushes it later.

### 8.2 Additions (NEW)

| Addition | What | Why |
|---|---|---|
| Kind `request` | Your prompt, verbatim, stored by the capture-request hook | Planner and reviewer read the original by id, not the main session's paraphrase. Protects your exact wording from summarisation. |
| Pinned records | `request`, `goal`, `criteria` for the open task are re-supplied by the resume hook after context compaction | These are the things that must not be lost or reworded. |
| `uses` counter | Each time a lesson is returned by search and then opened with `show`, count it | `sx mem prune` lists lessons never used after 90 days, for you to keep or delete. Stops the shared file filling with noise. |
| Search log | Query, hit count, whether a hit was opened | The only honest way to tell whether keyword search is missing things. |
| `SIMPLEIDE_HOME` | Already supported; document pointing it at a synced folder | Shares lessons across machines without a server. |

### 8.3 Task ledger (NEW)

Two small tables in `project.db`, filled by hooks and tools, never by the model:

- `run`: task slug, size, tool, start, end, outcome (accepted, failed, abandoned), repair rounds, tokens and cost where known.
- `dispatch`: task, agent, model requested, brief length, time, return status.

A task opens when its first `goal` is recorded and closes when a `result` is recorded. No extra commands for the model to remember.

### 8.4 Codex and the shared file

Codex's default sandbox allows writes to the workspace and temp folders only, so `~/.simpleide/` is blocked. Two choices:

1. Leave it. Lessons queue in the project and you run `sx mem sync` outside Codex now and then. No permission change.
2. Add the folder to Codex's writable roots in `~/.codex/config.toml`:
   ```toml
   [sandbox_workspace_write]
   writable_roots = ["/Users/shurley/.simpleide"]
   ```
   Whitelist the folder, not the file, because SQLite writes journal files beside it.

The installer will print option 2 and not apply it. Widening a sandbox is your call.

### 8.5 What memory will not do, and the trigger to revisit

- **No embeddings or vector store.** The verification research found no official or peer-reviewed comparison showing they beat keyword search for agent memory or code, and all four tools use plain search for code themselves. Revisit only if the search log shows a real pattern of zero-hit queries where a relevant record existed under different wording.
- **No code index.** Each tool already has grep and line-range reads. A symbol index would need invalidation on every edit. Revisit only if scouts are measurably the main cost on a large codebase.
- **No conversation storage.** Records are facts someone decided to keep, not transcripts.

---

## 9. Models

### 9.1 Routing table (CHANGE)

| Role | Claude Code | Codex | Cursor | Antigravity |
|---|---|---|---|---|
| Main session, everyday | `sonnet` | `gpt-6.1-terra`, medium | your choice in the picker | your choice in the picker |
| Main session, LARGE | `opus` (or Fable) | `gpt-6.1-sol`, high (or Astra) | strongest you have | strongest you have |
| planner | `opus` | `gpt-6.1-sol`, high | `inherit` | `pro` |
| worker | `sonnet`; `haiku` for mechanical work | `gpt-6-luna`, high | exact id of a cheap model from the picker, else `inherit` | `flash` |
| tester | `sonnet` | `gpt-6.1-terra`, medium | same as worker | `flash` |
| reviewer | `sonnet`; `opus` on LARGE | `gpt-6.1-sol`, high | `inherit` | `pro` |
| scout | built-in explorer | `gpt-6-luna`, low | built-in explorer | `flash` |

Notes:

- `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6.1-sol` and `gpt-6-astra` are confirmed ids. `gpt-6.1-luna` was not found in any official source; do not use it. Terra needs Codex CLI 0.159.0 or later.
- Antigravity lets a subagent choose a tier (`flash`, `pro`, `inherit`), not a specific model.
- A Codex issue from the GPT-5.6 period reports a Sol parent forcing Sol children. Confirm on your install that a worker pinned to Luna actually runs on Luna (section 11, phase 1).

### 9.2 Prices behind the table

Per million tokens, input / output:

| Model | Price | Source |
|---|---|---|
| `gpt-6-luna` | $0.10 / $0.50 | OpenAI price list |
| `gpt-6.1-terra` | about $1 / $5 | derived from an OpenAI statement, not a listed price |
| `gpt-6.1-sol` | $2 / $10 | OpenAI price list |
| `gpt-6-astra` | $10 / $50 | third-party |
| Claude Haiku 5.5 | $0.10 / $0.50 | third-party, reports conflict |
| Claude Sonnet 5 / 5.5 | $2 / $10 | third-party, one source says $3 / $15 |
| Claude Opus 5.5 | $4 / $20 | third-party |
| Claude Fable | $8 to $10 / $40 to $50 | third-party |

Anthropic's own pricing page was not reached during verification. Check it before relying on the Claude numbers.

### 9.3 What the prices mean for the design

- **The main session is where the money goes.** It re-reads its whole context every turn. Running everyday sessions on Astra or Fable costs about five times Sol or Sonnet for the same work. They stay available as the entry point, as you asked, but the recommendation is to pick them for LARGE sessions and use a mid-tier model for the rest.
- **Luna is 20 times cheaper than Sol.** Handing well-specified work from Sol to Luna pays for the brief many times over.
- **Sonnet is only 2 times cheaper than Opus** (if the third-party prices hold). Handing a small edit from Opus to Sonnet barely covers the cost of the handoff. On Claude, delegate small work only when it also keeps noise out of the main context, or send it to `haiku`.

### 9.4 Escalation ladder

1. Worker tier, first attempt.
2. Worker tier, second attempt with a corrected brief (most failures are brief failures).
3. One tier up, for that piece only.
4. Main session does it, or the question goes to you.

No third attempt at the same tier. Each escalation is logged in `dispatch`, so `sx stats` shows which kinds of task the cheap tier cannot handle, and the default for those can be raised.

### 9.5 Prompt caching

All four vendors discount repeated prompt prefixes. The kit is laid out to benefit without any configuration: the rule and agent definitions never change between sessions, hooks add text at the end of the context and never the start, and briefs put stable material (paths, decisions) before the variable part. Nothing else is needed.

---

## 10. Hooks

Six hooks, one script (`sx hook <event>`). Rules for all of them: standard library only; under 100 ms; never call a model; never print more than 5 lines to the model; fail open (if the hook breaks, work continues) except shell-guard, which fails closed.

| Hook | Does | Model sees |
|---|---|---|
| **capture-request** | Stores your prompt verbatim as a `request` record with the session id | nothing |
| **dispatch-guard** | On a subagent start: logs agent, model and brief length to `dispatch`. For `sx-*` agents, rejects a brief with no `GOAL` or no `DONE WHEN` section, and rejects a fourth concurrent worker or a third repair round on the same task | on reject, one line saying what is missing |
| **shell-guard** | Blocks a short list of destructive commands unless you approve: recursive delete outside the workspace, `git push --force`, `git reset --hard`, `git clean -fd`, dropping databases, publishing packages | one line naming the blocked command |
| **return-log** | On a subagent finish: records status and marks a missing return block | nothing |
| **stop-check** | When the session tries to finish with a MEDIUM or LARGE task open: if there is no `result` record or the last `sx check` failed, it says so once. It fires at most once per task, so it cannot loop | at most 2 lines |
| **resume** | On session start with an open task, or after context compaction: re-supplies the task's goal and criteria and the count of open questions | at most 5 lines; nothing when no task is open |

### 10.1 Event names per tool

| Hook | Claude Code (`.claude/settings.json`) | Cursor (`.cursor/hooks.json`) | Codex (`.codex/hooks.json`) | Antigravity |
|---|---|---|---|---|
| capture-request | `UserPromptSubmit` | `beforeSubmitPrompt` VERIFY | `UserPromptSubmit` VERIFY | VERIFY |
| dispatch-guard | `PreToolUse` on the agent tool | `subagentStart` | `SubagentStart` | VERIFY |
| shell-guard | `PreToolUse` on the shell tool | `beforeShellExecution` | `PreToolUse` VERIFY | `commandExecutionPolicy` in agent files |
| return-log | `SubagentStop` | `subagentStop` VERIFY | VERIFY | VERIFY |
| stop-check | `Stop` | `stop` | `Stop` | VERIFY |
| resume | `SessionStart` | `sessionStart` VERIFY | `SessionStart` VERIFY | VERIFY |

The Cursor names `subagentStart`, `preToolUse`, `beforeShellExecution`, `afterFileEdit` and `stop`, and the Codex names `SubagentStart` and `Stop`, are taken from the working hook files already in the AgentNexus repo. The rest must be confirmed against each tool's hook documentation when phase 3 is built. Antigravity documents hooks but the format was not verified; it gets the rule, skills and subagents first and hooks last.

### 10.2 Installing hooks safely

Hook config files usually already exist (AgentNexus has both `.cursor/hooks.json` and `.codex/hooks.json`). The installer must merge: add entries whose command contains `.simpleide/sx.py hook`, leave every other entry alone, and remove only its own entries on uninstall. Hooks are opt-in at install (`--hooks`), because they change what the tool is allowed to do.

### 10.3 Hooks considered and left out

- **Format on edit.** Useful, but project-specific and it can fight the editor's own formatter. Put the formatter in `sx check` instead.
- **Automatic sizing of the request.** Sizing needs judgement; a keyword script would be wrong often enough to cost more than it saves.
- **Token counting on every tool call.** Too slow for the value. Usage is read once at the end of a task where the tool exposes it.

---

## 11. Workflow

### 11.1 SMALL

```
you ask
  capture-request stores the prompt                      (hook, 0 tokens)
main session sizes it SMALL
  either: answers or edits directly
  or:     writes one brief -> sx-worker -> 5-line return
main session checks the result does what was asked
done
```

- No plan, no review, no records unless something worth keeping was learned.
- Delegate only when the brief is shorter than the work, or the work would pull a lot into context.
- Verification matches the task: a calculation is re-read, a one-line fix is run once.

### 11.2 MEDIUM

```
1. sx mem search "<keywords>"                            (script)
2. main session records goal + 2-5 criteria + assumptions
3. main session decides the split: one worker by default, up to 3 if independent
4. in ONE turn, in parallel:
      sx-worker (per piece)
      sx-tester (only for code where a wrong result is costly)
5. sx check                                              (script; 15-line summary)
6. sx scope                                              (script)
7. sx pack -> sx-reviewer, one pass
8. fix findings that have evidence -> sx check again
9. record result + decisions; lesson if something was learned
10. sx-writeup only if you want a document
```

- Steps 5 and 7 can run at the same time when the tool supports parallel calls.
- One repair round is normal; a second is the limit.

### 11.3 LARGE

```
1. sx mem search
2. sx-planner reads the original request by id            (strong model, read-only)
      -> if it returns questions, ask you and stop
3. main session records goal, criteria, assumptions, and freezes interfaces as decisions
4. in ONE turn, in parallel:
      sx-worker per independent piece (own worktree if files could overlap)
      sx-tester from criteria + interfaces
5. sx worktree merge -> one integrated revision
6. in ONE turn, in parallel:
      sx check on the integrated revision
      sx-reviewer on sx pack
7. repair: one focused brief per real failure -> sx check on affected tests
      at most 2 rounds, enforced by dispatch-guard
8. main session accepts against each criterion, one by one
9. record tests, result, decisions, lessons
10. sx mem export -> sx-writeup -> docs/simpleide/<slug>.md
```

What may overlap, and what may not:

| Safe together | Never together |
|---|---|
| Workers on different files | Two writers on the same files in one checkout |
| Worker and tester | Tests running against a half-merged tree |
| Test run and review | Review of a revision that is still changing |
| Several scouts | Planner and workers (the plan comes first) |

### 11.4 Questions that come up mid-task

Every one is recorded: `sx mem add question "<question>" --task <slug> --body "<options, and what was done meanwhile>"`.

- If the answer changes the objective, permissions, compatibility or something that cannot be undone: stop and ask you.
- Otherwise: take the safe reversible option, record it as an assumption, continue, and list it in the final summary.
- When answered, the answer is recorded as a decision that refers back to the question.

The resume hook reports the number of open questions at the start of the next session, so none are lost between sessions.

### 11.5 When things go wrong

| Situation | Response |
|---|---|
| Worker returns `blocked` | Read why. Usually the brief is missing something. Fix the brief; do not re-send it unchanged. |
| Worker fails the same brief twice | Move that piece one tier up (section 9.4). |
| Tests still fail after 2 repair rounds | Stop. Record what fails and the best diagnosis. Bring it to you. |
| Reviewer finding has no evidence | Ignore it. |
| Reviewer says `cannot tell` | Treat the criterion as not yet met and verify it another way. |
| Provider error or timeout mid-task | The records and git state are the checkpoint. On restart the resume hook supplies goal and criteria; `sx mem recent --task <slug>` shows where it stopped. Nothing is re-done that has a `result`. |
| Session context gets compacted | The resume hook re-supplies request id, goal and criteria. Everything else is retrieved by search when needed. |
| A task turns out bigger than sized | Step up one size from where you are. Records made so far carry over. |

---

## 12. Measurement

The kit earns its place by numbers, or parts of it get cut.

### 12.1 What is recorded automatically

Per task, from the ledger: size, outcome, dispatches by agent and model, repair rounds, check failures, duration. Tokens and cost where the tool exposes them (Claude Code's hooks are given the transcript path, which contains usage; for the others, read the tool's usage page and enter it with `sx stats --cost <slug> <usd>`). Token capture is best effort and will be incomplete on some tools.

### 12.2 The comparison

Nine tasks you actually need doing, three of each size, mixed between code, research and documents. Each run three ways:

| Arm | What it is |
|---|---|
| A. Single strong agent | One strong model, no kit, no subagents |
| B. simpleIDE | As installed |
| C. AgentNexus | The existing system, where it can run the task at all |

Score each run on: accepted or not (you judge against criteria written before the run), cost or tokens, wall-clock time, number of dispatches, number of reviewer findings that were real versus not.

### 12.3 Decision rules

- If B does not beat A on cost per accepted task for a size, B's process for that size is too heavy. Cut steps until it does, or route that size to a single agent.
- If the reviewer's real-finding rate is under about 1 in 5 on MEDIUM, drop review from MEDIUM and keep it for LARGE.
- If the independent tester's tests never catch anything the worker's own check missed, make it LARGE-only.
- If a lesson is never opened in 90 days, it is offered for deletion.
- Where C beats B, find out which specific mechanism did it and port that mechanism only.

Nine tasks is a small sample. It will show large differences and miss small ones; treat close results as ties.

---

## 13. Build order

Each phase is independently useful, has its own acceptance check, and can be rolled back with `install.py --uninstall` or a git revert of this folder.

### Phase 0: corrections (about half a day)

Apply section 5.7 and 6.3.

1. Antigravity agent files (no `tools:` list yet).
2. One skill copy in `.agents/skills/`, plus `.claude/skills/`. Drop `.cursor/skills/`.
3. Cursor defaults `inherit`; remove `fast`.
4. Codex: remove `sandbox_mode`; new model defaults; installer prints the optional `config.toml` lines and writes nothing there.
5. Update `core/models.json`, README and tests.

**Done when**: unit tests pass; a dry-run install shows the new paths; generated Antigravity files have the four required frontmatter keys; no generated Codex file contains `sandbox_mode`.

### Phase 1: prove it runs in each tool (about half a day, needs you at the keyboard)

In a scratch project, for each of the four tools:

1. Install. Restart the tool.
2. Confirm the agents and the skill are listed.
3. Give it one SMALL prompt, one MEDIUM prompt, and "save a lesson that X".
4. Note which model each subagent actually ran on.

**Done when**: for each tool there is a line in `docs/verified.md` saying what was seen, with the tool version. Anything that did not work is listed as not working, not assumed.

This phase comes before building more, because everything after it depends on subagents and skills actually loading.

### Phase 2: tools (1 to 2 days)

`sx.py` with `check`, `scope`, `pack`, `worktree`, `doctor`, `stats`, and `mem` moved in. Ledger tables. `request` kind.

**Done when**: each command has unit tests including failure cases (no git repo, failing tests, missing config); `sx check` on a failing test suite prints 15 lines or fewer and saves the full output; `sx pack` output is 25 lines or fewer on a 30-file change.

### Phase 3: hooks (1 to 2 days)

`sx hook` with the six handlers; installer merge and unmerge for Claude Code, Cursor and Codex. Antigravity only after its hook format is confirmed.

**Done when**: unit tests feed recorded hook payloads from each tool and get the right decision; installing into a project that already has hooks leaves the existing entries byte-for-byte intact; each hook runs in under 100 ms; with hooks installed, a brief without `DONE WHEN` is rejected in a live session on each supported tool.

### Phase 4: skill split and write-up (1 day)

Split `simpleide` into the files in section 6.1. Add `sx-scout`. Add `sx-writeup` and build the voice profile from your samples.

**Done when**: `SKILL.md` is under 3 KB; a MEDIUM run in a live session loads `SKILL.md` and not `large.md`; a write-up generated from a real task contains no claim that is not in a record.

### Phase 5: comparison and tuning (spread over 1 to 2 weeks of normal use)

Run section 12. Apply the decision rules. Adjust `rule.md` and `models.json`.

**Done when**: `docs/comparison.md` has the table for all nine tasks and a short list of what was cut or changed because of it.

### Phase 6: decide what happens to AgentNexus

With measured results in hand, go through the existing system (41 agents in each of three tool folders, six orchestrators, the bridge, the runtime) and sort each part into keep, port into simpleIDE, or retire. This is the audit the original brief asks for, and it should be done against numbers from phase 5, not opinion.

---

## 14. Reliability and permissions

- **No second authority.** simpleIDE adds no permission system of its own. Each tool's approvals and sandbox stay in charge. The shell-guard hook only ever blocks; it never grants.
- **Read-only roles** are enforced by the tool where it can (Claude Code tool lists, Cursor `readonly`, Antigravity tool lists once names are confirmed) and by instruction plus shell-guard on Codex.
- **Project isolation.** Project records never leave `project.db`. Only records explicitly saved as lessons go to the shared file, and `--local` keeps even those in the project.
- **Recovery.** State lives in two places that survive a crash: git, and `project.db`. There is no in-memory state to lose.
- **Nothing paid is switched on silently.** Models are chosen in `models.json`, which you edit. The installer never changes a tool's default model, sandbox or approval settings.
- **Uninstall is clean.** Only `sx-*` files, the `simpleide` skill folders, the marked rule block and its own hook entries are removed. Databases are kept.

---

## 15. Risks and open items

| Risk | Effect | What to do |
|---|---|---|
| Model ignores the sizing rule and over-delegates | Higher cost on small tasks | dispatch-guard counts it; `sx stats` shows it; tighten the rule wording |
| Cursor ignores a subagent's `model` | Workers run on the expensive main model | Check in phase 1; if it happens, set Cursor workers to `inherit` and pick a cheaper main model for everyday work |
| Codex forces child models to match the parent | Same | Check in phase 1; fall back to low reasoning effort on the same model |
| Antigravity custom agents not available in the IDE | No subagents there | The rule already covers "no subagents: do the roles yourself in order" |
| Hook event names differ from this plan | A hook does not fire | Phase 3 confirms each one against the tool's docs before writing config |
| Third-party prices are wrong | Routing table is tuned to the wrong ratios | Check vendor pricing pages; the structure of the table does not change, only which tier is "cheap enough" |
| Shared lessons accumulate noise | Search returns junk | `uses` counter and `prune` |
| Tool formats change again | Install breaks quietly | `sx doctor` after every tool update; formats moved several times during 2026 |

Not yet verified by a live run: everything in phase 1. Not verified in documentation: the items marked VERIFY in sections 5.7 and 10.1.

---

## 16. Sources

Tool formats, model ids and prices come from the verification report of 10 November 2026, which drew on:

- Cursor: cursor.com/docs/subagents, cursor.com/docs/skills
- Claude Code: code.claude.com/docs/en/sub-agents, code.claude.com/docs/en/memory
- Codex: developers.openai.com/codex/subagents, learn.chatgpt.com/docs/config-file/config-reference, developers.openai.com/api/docs/pricing
- Antigravity: antigravity.google/docs/subagents, antigravity.google/docs/rules, antigravity.google/docs/customization-discovery

Hook event names for Cursor and Codex marked as confirmed come from `.cursor/hooks.json` and `.codex/hooks.json` in the AgentNexus repo.
