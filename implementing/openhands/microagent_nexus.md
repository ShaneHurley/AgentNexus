---
name: agentnexus-repo
type: repo
agent: CodeActAgent
---

# AgentNexus Repository Microagent

You are operating inside the AgentNexus repository.

1. **User-Facing Orchestrators (KEEP-6)**: Respect the six orchestrators (`deep-research`, `research-messenger`, `plan-prep`, `use-master`, `daily-coder`, `researcher`).
2. **Audited Mutations**: Before making multi-file edits, formulate a plan and run `ide-bridge daily-coder` with `IDE_BRIDGE_ACTIVE=1`.
3. **Projections**: Never hand-edit `.cursor/agents/`, `.claude/agents/`, or `.github/agents/`. Edit `agents/ide/canonical/` and run `python agents/ide/scripts/sync_ide_agents.py`.
