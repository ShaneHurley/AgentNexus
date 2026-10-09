# Trae IDE Workspace Rules for AgentNexus

Copy this file to `.trae/rules/project_rules.md`.

---

# AgentNexus Rules

1. **KEEP-6 Orchestrators**: Only `deep-research`, `research-messenger`, `plan-prep`, `use-master`, `daily-coder`, and `researcher` are user-facing entry points.
2. **Read-Only Default in Chat**: Never suggest mutating code edits during `deep-research` or `researcher` sessions.
3. **Audited Builder Runs**: In Builder Mode, route project mutations through `ide-bridge daily-coder` so `PolicyGateway` and the SQLite ledger verify the `plan_hash`.
4. **Token Conservation**: Reference `#File` or `#Symbol` rather than reading entire directories.
