# GitHub Copilot Instructions for AgentNexus

You are assisting a developer in the **AgentNexus** repository. Strictly follow these project conventions:

## 1. User-Facing Orchestrator Architecture (KEEP-6)
Direct interactions are governed by six primary orchestrators:
- `deep-research`: Eight-phase evidence research; read-only.
- `research-messenger`: Assembles scored research packets into 17 standard handoffs; read-only.
- `plan-prep`: Codebase reconnaissance and context report generation; read-only.
- `use-master`: Formulates master execution DAGs and coordinates specialists; no native file writes.
- `daily-coder`: Mutating engineering parent; dispatches changes via `ide-bridge`.
- `researcher`: Read-only codebase explorer.

There is NO 7th orchestrator (`/daily`, `/career`). Student and career workflows use skills under `agents/shared/skills/`.

## 2. File Modification Boundaries
- Never overwrite project source code without a structured plan and explicit human review.
- Mutating runs intended for testing, building, or ledger registration must be executed via `ide-bridge daily-coder` in the terminal.
- Never edit files under `.cursor/agents/`, `.claude/agents/`, or `.github/agents/` directly; these are generated projections from `agents/ide/canonical/`. Run `python agents/ide/scripts/sync_ide_agents.py` after editing canonical sources.

## 3. Context & Token Thrift
- Reference specific line ranges and symbols rather than reading entire large files.
- Keep responses concise and factual, adhering to structured Markdown schemas.
