# AgentNexus × Kiro Integration

This directory documents how to use **AgentNexus** agents inside **Kiro** (KiroCrew).

## How it works

Kiro uses `.kiro/steering/` markdown files that are injected into every session's context.
The AgentNexus steering files are at `.kiro/steering/` in the repo root.

| File | Content |
|------|---------|
| `.kiro/steering/agents.md` | Full agent roster and authority matrix |
| `.kiro/steering/shared-rules.md` | Universal rules (readonly, bridge, evidence) |
| `.kiro/steering/deep-research.md` | Deep Research orchestrator |
| `.kiro/steering/use-master.md` | Use Master dispatcher |
| `.kiro/steering/daily-coder.md` | Daily Coder bridge parent |
| `.kiro/steering/plan-prep.md` | Plan Prep context gatherer |
| `.kiro/steering/research-messenger.md` | Research Messenger packet assembler |
| `.kiro/steering/researcher.md` | Read-only codebase recon |
| `.kiro/steering/skills-and-tools.md` | Shared skills, CLIs, Research Forge |

## Quick start

1. Open this repo in Kiro (`set_project /path/to/AgentNexus`).
2. The steering files load automatically — all six user-facing agents are available.
3. Use slash-style references to invoke an agent:
   - `/deep-research <question>` — evidence research
   - `/use-master <mission>` — Master DAG orchestration
   - `/daily-coder <task>` — bridge-mediated code changes
   - `/plan-prep <topic>` — planning context report
   - `/research-messenger` — assemble packet into 17 handoffs
   - `/researcher <question>` — read-only codebase recon

## Prerequisites

```bash
# Install shared tools
pip install -e agents/shared/agent-core/

# Install ide-bridge (for use-master / daily-coder)
pip install -e agents/ide/bridge/

# Verify bridge
ide-bridge doctor
```

## Kiro Crew cron / background jobs

See `kirocrew_config.yaml` for the `nightly_audit` schedule:
- Runs at 02:00 UTC nightly
- Verifies IDE agent projections are in sync
- Runs unit tests via `daily-coder` agent

To add to Kiro Crew's scheduler, import the config or use the dashboard Schedule page.

## Regenerating IDE projections

After editing a canonical agent in `agents/ide/canonical/`, regenerate all IDE projections including these steering files:

```bash
python agents/ide/scripts/sync_ide_agents.py
```

The script updates `.cursor/agents/`, `.claude/agents/`, `.github/agents/`, and should also be extended to regenerate `.kiro/steering/` (see `agents/ide/scripts/` for the template system).

## Architecture notes

- **SSOT:** `agents/ide/canonical/` — do not edit projections directly.
- **Bridge:** All mutating work goes through `ide-bridge daily-coder`. Kiro sessions use this same bridge; the `IDE_BRIDGE_ACTIVE=1` env flag is set for child processes.
- **No Kiro-specific hooks:** Cursor uses Python hooks (`.cursor/hooks/`). Kiro relies on agent frontmatter `tools.deny` and the shared rules in `.kiro/steering/shared-rules.md`.
- **Memory:** Kiro Crew's persistent memory is separate from the `personal-store` CLI. Use `personal-store` for cross-IDE personal context; use Kiro memory for session continuity.

## Files in this directory

| File | Purpose |
|------|---------|
| `kirocrew_config.yaml` | Workspace config: memory backend, shared context, agent definitions, schedules |
| `crewai_nexus.py` | Python integration bridging CrewAI crew definitions to AgentNexus |
| `README.md` | This file |
