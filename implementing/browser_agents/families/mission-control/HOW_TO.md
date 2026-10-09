# How to use Mission Control

Use when a mission spans **multiple chats** (context → research → plan → implement → review → closeout).

1. Set `browser_variant` to your **current** phase (or use main to pick).
2. Run **one phase per chat**. Copy the packet + `prior_artifact_ref` into each new chat with the handoff paste named in `PHASE_HANDOFF`.
3. Phase map:

| Phase | Variant | Target family |
|-------|---------|---------------|
| Context | `phase-context` | (this conductor) |
| Extract files | `phase-assemble` | research-desk / assemble-given |
| Research | `phase-research` | research-desk tier |
| Plan | `phase-plan` | planner outline |
| Plan review | `phase-plan-review` | plan-reviewer |
| Implement | `phase-implement` | code-crafter / patch-draft + SELF_REVIEW |
| Code review | `phase-code-review` | code-reviewer ( **new chat** ) |
| Doc review | `phase-doc-review` | document-reviewer (prose) |
| Closeout | `phase-fix-review` | acceptance map |

**Not IDE /use-master:** No automatic DAG, bridge runs, or PolicyGateway from browser paste. Prefer IDE `/use-master` + ide-bridge when repo-native orchestration is required.
