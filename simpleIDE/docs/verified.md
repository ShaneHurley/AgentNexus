# Live tool verification

Partial Codex CLI observations were recorded on 10 November 2026; no tool has completed the full qualification below. For each tool, use a scratch project, install simpleIDE, restart, then record the version, whether agents and skills appear, one SMALL and one MEDIUM task, a saved lesson, actual subagent model, and observed hook behavior. Record failures plainly. The six defects from the [runtime evaluation](evaluation-2026-11-10.md) are now [fixed and verified locally](fixes-2026-11-10.md). Direct hook-process probes do not establish that hooks fired inside an IDE.

| Tool | Version | Agents visible | Skill visible | SMALL | MEDIUM | Lesson | Actual model | Hooks | Evidence/date |
|---|---|---|---|---|---|---|---|---|---|
| Claude Code | pending | pending | pending | pending | pending | pending | pending | pending | pending |
| Cursor | pending | pending | pending | pending | pending | pending | pending | pending | pending |
| Codex | CLI 0.163.0-alpha.10.2 and 0.167.0-alpha.3.2 | no selectable sx-* role demonstrated | simpleide and sx-writeup reported in runtime catalog | shell read + arithmetic passed | pending | installed CLI save/search passed; no agent-directed lesson trial | pending; no subagent launched | registered; execution/denial unverified | [evidence](evidence/codex-live-2026-11-10.json), 2026-11-10 |
| Antigravity | pending | pending | pending | pending | pending | pending | pending | pending | pending |

The dispatch brief guard can be exercised live in Cursor and Claude Code. Codex SubagentStart currently cannot block; record whether it displays the advisory context. Test shell guard with a harmless dry-run command payload before relying on it.

## November 11 repaired-runtime observations

New evidence is separate from the November 10 JSON and the original readiness audits. Local tests exercise hook processes with fixtures; they do not show host registration or enforcement. The [completion checklist](repair-completion-2026-11-11.md) records the offline gates.

| Observation | Result | Evidence |
|---|---|---|
| Codex binary | ChatGPT-bundled CLI `0.163.0-alpha.10.2` | [SMALL trace](evidence/repair-2026-11-11/live-small.json) |
| SMALL | Shell event actually read `19 + 23`; final answer 42. Skills and sx-* roles were model-reported. The model claimed a worker launch, but the JSON event stream did not expose a verifiable spawn/model observation. | SMALL trace |
| MEDIUM fallback | Actual command events implemented normalization; seven tests passed. Goal/five criteria, explicit manual binding, assistant closure, export, lesson search/show and direct resume were exercised. A separate inspection repeated the seven tests successfully. | [MEDIUM trace](evidence/repair-2026-11-11/live-medium.json), [independent records/artifacts inspection](evidence/repair-2026-11-11/live-medium-inspection.json) |
| Harmless permission attempt | Model reported `touch harmless-permission-probe.txt` failed once with Operation not permitted; an independent filesystem check found no probe file. The trace omits the command event, so neither the attempt nor its denial source is independently established. | [permission trace](evidence/repair-2026-11-11/live-native-permission.json) |
| Native hooks | No ledger was created by hooks in the SMALL trial. MEDIUM's records were created by explicit CLI commands and manual alias. No native request capture, correlated callback or hook denial was demonstrated. Trust and permission controls were left intact. | SMALL/MEDIUM traces |
| Actual role/model | Unknown. Requested/catalog model labels and model prose are insufficient. No verified child-model observation is available. | SMALL trace |
| Claude, Cursor, Antigravity | Executables unavailable on this PATH. Installed file/config tests pass locally; live workflows remain pending. Antigravity hooks remain deferred. | Completion checklist |

The MEDIUM trial began before final worktree/validation refinements; its exact installed-source hash is retained in the inspection. Current installed-CLI regressions use the final runtime. A subsequent final-runtime confirmation is retained separately as [final installed host trace](evidence/repair-2026-11-11/live-final-runtime.json); its source hashes identify exactly which code ran. These small exercises are qualification evidence, not the nine real comparison tasks or user acceptance.

### Verified payload/config contract and remaining limit

The official [Codex custom-agent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) describes standalone project `.codex/agents/*.toml` files with name, description, model and developer instructions. This supports the rendered file contract, not a claim that a particular run selected a role.

The official [hook documentation](https://learn.chatgpt.com/docs/hooks) describes project hook discovery, native trust review, and shared session/cwd/model fields. PreToolUse includes tool_use_id; the documented SubagentStart fields include agent_id/type but omit that tool-call join. SubagentStart context is advisory. Accordingly, the implementation retains unmatched observations and pending reservations instead of inventing joins. Shell and other function-tool hook coverage has documented exceptions. A configured file or direct fixture denial does not prove enforced guards.

Finish primary-host qualification through its normal trust UI: observe native request/session capture; actual role and model; correlatable start/return or an explicitly documented limitation; resume and terminal outcome; and a harmless hook-denied operation. Do not bypass trust to manufacture success. Then repeat relevant checks on the other hosts. For now use the tested single-parent fallback and explicit bindings/outcomes. The real-task comparison and keep/port/retire decision remain pending actual tasks and user judgments.
