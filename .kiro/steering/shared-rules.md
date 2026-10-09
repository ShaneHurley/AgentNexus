# AgentNexus — Shared Agent Rules

These rules apply to **every** agent and all sessions in this project.

## Authority hierarchy (read top-down, highest to lowest)

1. User's explicit instruction in the current turn
2. PolicyGateway / `ide-bridge` runtime enforcement
3. Agent frontmatter (`readonly`, `authority`, `tools.deny`)
4. These shared rules
5. Agent body instructions

## Universal constraints

### Readonly agents — never use write tools
Agents with `authority: read-only` or `readonly: true` in their frontmatter must never:
- Write, edit, or delete files
- Run shell commands that mutate state
- Invoke subagents
- Approve, deploy, or send anything

### Bridge requirement for mutations
All mutating, file-writing work must go through `ide-bridge daily-coder`:
```bash
ide-bridge daily-coder run --request "..." --repo <path>
```
Never claim a task is COMPLETE from chat prose alone; only bridge exit codes are authoritative.

### No scope expansion
No agent may expand the user's stated authority. `master-orchestrator` sets `scope.authority` to the **minimum** the mission requires (`read-only`, `diagnostic`, or `implementation`). Never escalate without explicit user instruction.

### No majority-vote resolution
Research disagreements are resolved by evidence quality, not vote count.

### Projection SSOT
Agent definitions live in `agents/ide/canonical/`. Files in `.cursor/agents/`, `.claude/agents/`, `.github/agents/`, `.kiro/steering/` are **projections** and must not be edited by hand. Run `python agents/ide/scripts/sync_ide_agents.py` to regenerate.

## Evidence standards

- Treat all claims — including the user's preferred hypothesis — as unproven until supported.
- Source freshness: prefer <6 months; flag 6–12 months; exclude 12+ months unless no alternative.
- Source authority: official specs/RFCs > team wikis > informal notes.
- Quality over quantity: 3–4 strong findings beat 10 weak ones.

## Subagent dispatch rules

- Only parent orchestrators may invoke subagents.
- Each subagent receives **only** the brief and assigned questions — not the full conversation.
- Delegate-only specialists are **never** user-invocable.
- Lanes in Deep Research get disjoint question sets; they must not read each other's outputs.

## Hooks and policy

The `.cursor/hooks/` directory contains policy enforcement hooks that apply in Cursor. These are enforced by Cursor's hook system — not replicated in Kiro. In Kiro, trust the frontmatter `tools.deny` and these rules as the enforcement layer.

## Key references

| Topic | File |
|-------|------|
| Full architecture | `docs/architecture/architecture-overview.md` |
| Agent ecosystem overview | `docs/architecture/AGENT_ECOSYSTEM_OVERVIEW.md` |
| IDE agent pack guide | `docs/ide-agents/ide-agent-pack.md` |
| Shared subagent architecture | `docs/architecture/SHARED_SUBAGENT_ARCHITECTURE.md` |
| Personal skills spec | `docs/personal-skills/SPEC.md` |
| Bridge setup | `agents/ide/bridge/README.md` |
| Token experiments | `agents/ide/config/token_experiments.json` |
