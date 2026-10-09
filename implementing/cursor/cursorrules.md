# Cursor Rules for AgentNexus (.cursorrules / .cursor/rules/)

Copy this file to `.cursorrules` or `.cursor/rules/agentnexus.mdc`.

---

# AgentNexus Cursor Rules

You are working within the **AgentNexus** repository. Strictly adhere to these operational and architectural rules:

## 1. User-Facing Orchestrators (KEEP-6)
Direct user interaction is permitted ONLY through these six orchestrators:
- `/deep-research` or `@deep-research`: Eight-phase evidence research. Always read-only.
- `/research-messenger` or `@research-messenger`: Assembles scored research packets (17 handoffs). Never performs ad-hoc research.
- `/plan-prep` or `@plan-prep`: Context scout before master planning. Read-only.
- `/use-master` or `@use-master`: Formulates master DAGs and delegates to specialists. No direct file writes.
- `/daily-coder` or `@daily-coder`: Parent for mutating code tasks. Must dispatch via `ide-bridge`.
- `/researcher` or `@researcher`: Targeted read-only codebase reconnaissance.

Do NOT invent a 7th user-facing orchestrator (e.g. `/daily`, `/career`). Student and career workflows use skills under `agents/shared/skills/`.

## 2. Mutating File Edits & Audited Writes
- Soft hooks are active under `.cursor/hooks.json`. Mutating tools (`Write`, `StrReplace`, `Delete`, and destructive shell commands) are automatically blocked for read-only agents and unknown agents.
- For audited Daily Coder and Research Forge runs, always execute through `ide-bridge` in the terminal:
  ```bash
  ide-bridge daily-coder run --request "..." --profile M
  ```
  This exports `IDE_BRIDGE_ACTIVE=1` and registers actions in the PolicyGateway ledger.

## 3. Context Conservation & Token Thrift
- Never dump whole files into the chat context.
- Use `@SymbolName` to target specific classes or functions.
- Pass typed markdown state packets between phases rather than raw cumulative chat transcripts.
- Sizing gate: For trivial or single-line fixes, skip deep research and brainstorm phases.
