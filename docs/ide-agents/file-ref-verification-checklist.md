# `#file:` verification checklist (editor-native)

F0 implements **in-process** resolution only (`ai_agents_repo.resolve_ref`, `audit_prompt_bytes.py`). Editor loaders are **not** exercised by unit tests.

Run these manually before F5 (IDE hub move to `shared/ide-agents/`).

## Producers (inventory)

| Producer | Location | Syntax |
|----------|----------|--------|
| Canonical orchestrators | `agents/ide/canonical/*.md` | `#file:ide-agents/...` |
| Contract shards | `agents/ide/contracts/*.md` | nested `#file:ide-agents/...` |
| Generated projections | `.cursor/agents/`, `.github/agents/`, `.claude/agents/` | copied from canonical |
| Sync script | `agents/ide/scripts/sync_ide_agents.py` | copies bodies verbatim |

## In-process resolvers (automated)

| Resolver | Proof |
|----------|-------|
| `audit_prompt_bytes.py` | `resolve_file_ref` → `ai_agents_repo.resolve_ref` |
| `ai_agents_repo.resolve_ref` | unit tests + `validate --phase F0d` sample path |

## Editor resolvers (manual — required before F5)

For each IDE, open a representative agent that references `#file:ide-agents/contracts/deep-research-phase-index.md`:

- [ ] **Cursor** — invoke `/deep-research` or open agent; confirm contract file loads (no missing `#file:` errors).
- [ ] **VS Code Copilot** — open `.github/agents/deep-research.agent.md`; confirm handoff / file refs resolve from workspace root.
- [ ] **Claude Code** — open `.claude/agents/deep-research.md` if projected; same check.

Additional cases:

- [ ] Legacy paths with spaces (removed at F6c — not in `#file:` today)
- [ ] URL-encoded segments if pasted from docs
- [ ] Windows `\` vs `/` in any user-edited ref
- [ ] Missing file shows clear error (not silent skip)
- [ ] `..` in a ref is rejected or ignored by editor (must not read outside repo)

Record results in PR evidence bundle (date, IDE version, pass/fail per row).

## After F5 (v2 hub)

Repeat the same checklist with `shared/ide-agents/` as physical hub while keeping logical `ide-agents/` in prompts.
