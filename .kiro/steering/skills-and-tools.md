# AgentNexus — Shared Skills & Tools

## Shared toolkit location

All cross-agent skills live in `agents/shared/skills/`. Personal skills live in `agents/shared/skills/personal/`.

## Available shared skills

### Writing tools
- `writing-lint` — CLI linter for prose style (run: `writing-lint <file>`)
- `agents/shared/skills/shared/` — shared skill definitions

### Agent-core library
The `agent-core` Python package (`agents/shared/agent-core/`) provides:
- `agent_core` — session management, personal store, profile loading
- `personal-store` CLI — read/write personal context store
- `writing-lint` CLI — prose linting

Install: `pip install -e agents/shared/agent-core/`

### Browser agent families
Pre-built browser agent packs in `implementing/browser_agents/families/`:
- `research-desk` — web research
- `code-crafter` — coding tasks
- `code-reviewer` — review + feedback
- `writing-studio` — document writing
- `document-reviewer` — doc review
- `thinking-lab` — reasoning tasks
- `mission-control` — general orchestration
- `learning-coach` — tutoring
- `plans-and-places` — planning
- `kitchen-cooking` — daily tasks

Quick-paste packs for each: `implementing/browser_agents/quick_paste_packs/`

## Personal skills

Personal skills are agent-specific overlays that customize behavior. Spec: `docs/personal-skills/SPEC.md`

- Schema definitions: `agents/shared/schemas/personal/`
- Skill catalog: `agents/shared/skills/personal-catalog.yaml`
- Usage diary template: `docs/personal-skills/usage-diary.md`

## Kiro-specific integration

The `implementing/kirocrew/` directory contains:
- `kirocrew_config.yaml` — workspace config for Kiro Crew
- `crewai_nexus.py` — Python integration with CrewAI
- `README.md` — Kiro integration guide

## Tool CLIs available after setup

```bash
# After: pip install -e agents/shared/agent-core/ && pip install -e .
agent-core          # agent session manager
personal-store      # personal context store
writing-lint        # prose linter
ide-bridge          # audited write gateway (agents/ide/bridge/)
```

## Research Forge

Full research pipeline in `agents/research/research-forge/`. Includes:
- Orchestrator, services, adapters
- Schemas, fixtures, tests
- Config profiles

Run: `python -m research_forge` (after installing from `agents/research/research-forge/`)
