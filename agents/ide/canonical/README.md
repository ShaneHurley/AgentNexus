# Canonical agents (SSOT)

Add one `{agent-name}.md` per agent here. Each file must include YAML frontmatter (`name`, `description`, authority, tool policy) and a thin body that `#file:`-links logical `ide-agents/contracts/` where possible (resolved at runtime to `agents/ide/contracts/` via `ai_agents_repo.resolve_ref`).

After edits, from the repo root:

```bash
python agents/ide/scripts/sync_ide_agents.py
# or dry-run:
python agents/ide/scripts/sync_ide_agents.py --check
```

Do not hand-edit generated projections under `.cursor/agents/`, `.claude/agents/`, or `.github/agents/`.
