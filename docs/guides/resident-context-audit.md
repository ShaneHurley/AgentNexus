# Resident context audit (`~/.cursor`)

Always-on IDE context often costs more tokens than a single agent projection. Use this checklist periodically (and before adding plugins) to keep resident load bounded.

## Scope

Audit everything the IDE loads **without** an explicit `@` mention:

| Area | Typical paths (Windows) | What to inspect |
|------|-------------------------|-----------------|
| User rules | `%USERPROFILE%\.cursor\rules\`, project `.cursor/rules/` | `alwaysApply: true` rule bodies and globs |
| User skills | `%USERPROFILE%\.cursor\skills\`, `%USERPROFILE%\.cursor\skills-cursor\` | Skill `description` lines (shown in skill pickers) and full `SKILL.md` when auto-attached |
| Plugins | `%USERPROFILE%\.cursor\plugins\` | Bundled rules, skills, MCP server descriptors |
| MCP | Cursor MCP settings / plugin manifests | Tool count, long `instructions` blocks, duplicate servers |
| Agents | `%USERPROFILE%\.cursor\agents\`, project `.cursor/agents/` | Subagent definitions you did not intend to keep resident |

This repo’s **six UF orchestrators** and delegate roster live under [`agents/ide/`](../../agents/ide/); personal career work stays **on-demand skills** in [`agents/shared/skills/personal/`](../../agents/shared/skills/personal/) (see [ADR KEEP-6](../decisions/ADR-TOKEN-TOPOLOGY-2026-09.md)).

## Checklist

1. **Inventory always-on rules** — List every rule with `alwaysApply: true`. For each: still needed? Can it become `alwaysApply: false` with a narrow glob?
2. **Deduplicate** — Same policy in user rules, plugin rules, and project rules counts triple. Keep one authoritative copy.
3. **Skill descriptions** — Descriptions are resident metadata. Shorten to one line; move procedure into the body loaded only when the skill runs.
4. **Plugin sprawl** — Disable plugins whose MCP tools you never use; each may inject rules and tool schemas every session.
5. **MCP tool surface** — Fewer servers beats “convenience” servers with 40+ tools. Prefer task-specific servers enabled only for relevant worktrees.
6. **Cross-check engineering boundaries** — Resident prompts must not route résumé/career work through Daily Coder `documenter`; use [`resume-tailor`](../../agents/shared/skills/personal/career-tools/resume-tailor.md) instead.
7. **Measure** — After changes, start a fresh chat and note system/resident size if your IDE exposes it; compare before/after on the same task.

## Red flags

- Multiple “always follow” essays (>2k words total) before the first user message
- Duplicate Glean / Notion / Figma instruction blocks from plugins **and** user rules
- Personal career facts referenced in always-on rules (privacy leak + token waste)
- Seventh “orchestrator” or mega-agent rule contradicting [`AGENTS.md`](../../AGENTS.md) KEEP-6

## Related docs

- [IDE hooks and skills](../ide-agents/hooks-and-skills.md)
- [Personal skills operator guide](../personal-skills/README.md)
- [Token topology ADR](../decisions/ADR-TOKEN-TOPOLOGY-2026-09.md)
- Daily Coder benchmark gate: [`agents/coding/daily-coder-ecosystem/docs/operations.md`](../../agents/coding/daily-coder-ecosystem/docs/operations.md)
