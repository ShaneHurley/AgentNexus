# JetBrains Junie Guidelines for AgentNexus (.junie/guidelines.md)

## Repository Architecture
- **KEEP-6 Orchestrators**: `deep-research`, `research-messenger`, `plan-prep`, `use-master`, `daily-coder`, `researcher`.
- **Canonical Agents**: Edit only `agents/ide/canonical/*.md`, then run `python agents/ide/scripts/sync_ide_agents.py`.
- **Audited Writes**: Execute mutating changes via `ide-bridge daily-coder`.

## Testing & Verification
Run unit tests before completing any task:
```bash
PYTHONPATH=agents/shared/ai_agents_repo/src python3 -m unittest discover -s agents/ide/tests -v
```
