# simpleIDE runtime evaluation — 10 November 2026

**Follow-up:** The six defects recorded below have now been fixed and verified locally. The expanded suite passes 38 tests and the original runtime probe passes all 14 expectations. See [fixes and current validation](fixes-2026-11-10.md). This document preserves the original evaluation and evidence; full live host qualification remains pending.

The local command kit runs. The four-tool orchestration workflow is not yet qualified for routine use: six reproducible defects affect installation, dispatch, and verification history. Passing the existing suite does not establish that the installed agents or hooks run in their hosts.

## What was actually run

| Check | Observed result |
|---|---|
| Existing suite, Python 3.12.0 | 22 tests passed, no skips; 4.193 seconds reported by unittest. |
| Existing suite, default `python3` (3.9.13) | 21 passed, TOML parsing test skipped. |
| Installed `.simpleide/sx.py` in a temporary Git project | Goal, criteria, config confirmation, real unittest command, artifact, local lesson, search, result, export, stats, and doctor completed as expected. |
| Additional subprocess probes | 14 targeted expectations: 3 passed, 11 failed, representing the six defects below. These are deliberately selected edge cases, not a representative success-rate benchmark. |
| Real Codex model calls | Both the ChatGPT-bundled CLI 0.163.0-alpha.10.2 and Codex.app-bundled CLI 0.167.0-alpha.3.2 read `arithmetic.txt` through a shell tool and returned 42 for `19 + 23`. |
| Codex skill discovery | Both `simpleide` and `sx-writeup` were reported in the supplied runtime skill catalog. |
| Codex custom-agent selection | Not demonstrated. Discovery calls reported a `collaboration.spawn_agent` schema without an `agent_type` argument. Enabling/disabling `multi_agent_v2` on the older CLI did not change that observation. No subagents were launched, so no worker model or role instructions were verified. |
| Codex hook execution | Not demonstrated. Installing hook entries did not produce a capture database during the initial/discovery runs. No hook-trust bypass was used. The cause remains unresolved; project/hook trust and runtime configuration need investigation. |
| Claude Code, Cursor, Antigravity live sessions | Not run. Installed desktop app presence does not prove CLI availability, agent loading, or hook behavior. |

The synthetic arithmetic and installed-command checks are smoke tests only. They are not entries in the nine-task comparison, and there was no user acceptance decision for a comparison task. No cost estimate was inferred from tokens.

Evidence: [probe output](evidence/runtime-probe-2026-11-10.json), [probe script](evidence/runtime_probe.py), [live Codex invocations and output](evidence/codex-live-2026-11-10.json), [installed-command output](evidence/installed-cli-smoke-2026-11-10.json).

## Findings

### 1. P1 — Cursor-only project installation omits both skills

At `install.py:264–267`, selecting Cursor creates its agent directory, but `.agents/skills` is added only when Codex or Antigravity is selected. A fresh `--tools cursor` install exits 0 while both `.agents/skills/simpleide/SKILL.md` and `.agents/skills/sx-writeup/SKILL.md` are absent. The default all-tools install in the existing tests masks this branch.

Include Cursor in the project shared-skill condition and add a single-tool installation test for every host.

### 2. P1 — The supplied brief template fails its own guard

`skill/simpleide/references/brief-template.md:8` and `:21` use standalone `GOAL` and `DONE WHEN` headings. `core/sx.py:654` requires a colon after each heading. Passing the first fenced brief from that file to the Cursor dispatch hook returns `permission: deny`, reporting both headings missing. The same validation serves Claude and Codex PreToolUse.

Align the template, example, and validator, then test the literal shipped template. Also decide explicitly whether an empty brief should be rejected: the current `and brief` condition bypasses validation entirely for an empty string.

### 3. P1 — Returned workers remain active in the ledger

`core/sx.py:717` updates the newest dispatch for the agent name, without matching a dispatch, child, task, or session identifier. Three `sx-worker` starts followed by three corresponding returns leave statuses `['', '', 'done']`. Two fresh dispatches then receive `allow`, `deny`, even though the original three workers have finished. The probe reproduces the stale statuses using both Cursor-shaped and Codex-shaped events.

Store a stable host dispatch/child identifier and correlate the return to that row. Include task/session identity and make duplicate return events idempotent. Cursor documents subagent identifiers, and Codex SubagentStart/SubagentStop includes `agent_id`. See [Cursor hooks](https://cursor.com/docs/hooks) and [Codex hooks](https://learn.chatgpt.com/docs/hooks).

### 4. P1 — Repeated check outcomes lose chronology and conceal the latest failure

`core/sx.py:476` sends each check to the generic deduplicating `insert()`. Its identity at `:133` excludes the timestamp and artifact reference. Running the same failing command, then a passing command, then the original failing command saves only `FAIL`, `PASS` records. The third artifact exists and the command exits 1, but `stop-check` at `:724` reads PASS as the latest observation. `pack` and the exported history also omit the final failure.

Check executions must be separate immutable observations even when command and outcome repeat. Test FAIL/PASS/FAIL and PASS/FAIL/PASS sequences and verify that their artifact references remain distinct.

### 5. P2 — Fresh Cursor hook configuration omits the required schema version

`install.py:180–227` initializes a nonexistent hook file from `{}` and adds only `hooks`. A fresh Cursor install with `--hooks` therefore produces no `version` field. Cursor's current [hook configuration reference](https://cursor.com/docs/hooks) requires a positive integer version and specifies `1`. The existing merge test supplies an already-versioned configuration, so it misses this case.

Set `version: 1` when creating a fresh Cursor configuration while preserving existing user configuration. Whether this Cursor build rejects or tolerates the missing field still requires a live host check; the reproduced finding is the schema violation.

### 6. P2 — Common destructive-command spellings bypass the shell guard

Only hook payloads were submitted; no destructive commands were executed. `git reset --hard HEAD` was denied, but `git push -f origin main`, `git clean -fdx`, and `rm --recursive /tmp/simpleide-outside-probe` were all allowed. `core/sx.py:687–688` matches only some flag spellings.

Cover equivalent flags and command structure with explicit tests. Document the remaining limits. The current regex guard does not establish general command safety or a read-only enforcement boundary. Codex itself documents exceptions in tool-hook coverage and that malformed/failed callbacks need not block execution; native permissions remain authoritative. See [Codex hooks](https://learn.chatgpt.com/docs/hooks).

## Assessment and next steps

The standard-library implementation is compact, the local memory/check/export path works, and opt-in hook installation is useful. Preserving the pending comparison and audit as pending was correct.

Fix the six defects before drawing conclusions about orchestration reliability. Extend the normal tests with these reproductions. Then verify one host at a time: visible skills and selectable custom roles, a real role launch with the observed model, a harmless hook denial through the host, and a completed MEDIUM task whose ledger reflects the actual dispatch/check sequence. Recheck those observations after fixes.

The Codex SubagentStart limitation is accurately described: it supplies context but cannot prevent startup. PreToolUse is the documented blocking path for supported local tools, including spawn_agent; the local payload probe confirms that simpleIDE emits a deny decision for a fourth active worker. This is not evidence that the installed hook intercepted a real launch. See [official Codex hook behavior](https://learn.chatgpt.com/docs/hooks).

The nine-task A/B/C comparison, actual per-role model selection, write-up grounding, and AgentNexus keep/port/retire audit remain unverified. Do not retire components or claim cost savings from these smoke tests.

## Reproduce the local evaluation

From the repository root:

```sh
python3.12 -m unittest discover -s simpleIDE/tests -v
python3.12 simpleIDE/docs/evidence/runtime_probe.py
```

The second command deliberately reports unmet expectations in JSON and exits normally unless the harness itself fails. It uses disposable projects and an isolated shared-memory directory. The implementation and original test suite were not modified during this evaluation. Only evaluation documentation and evidence were added, and the live-verification tracker was updated with partial observations.
