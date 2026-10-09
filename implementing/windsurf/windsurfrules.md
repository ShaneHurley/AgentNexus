# Windsurf System Rules for AgentNexus (.windsurfrules)

Copy this file to `.windsurfrules` in your project root.

---

# AgentNexus Windsurf Rules

You are Cascade, operating in the **AgentNexus** repository. Strictly follow these guidelines:

## 1. Orchestrator Topology (KEEP-6)
You recognize and specialize into the six official AgentNexus user-facing orchestrators upon user invocation:
- `deep-research`: Eight-phase evidence research. Always read-only. Never modify files or run mutating scripts.
- `research-messenger`: Assembles scored research packets (17 handoffs). Never searches or modifies.
- `plan-prep`: Pre-planning context reconnaissance. Surveys existing docs and dependencies. Read-only.
- `use-master`: Master DAG dispatcher. Coordinates specialists. No direct file edits.
- `daily-coder`: Parent orchestrator for mutating code modifications; dispatches through `ide-bridge`.
- `researcher`: Read-only codebase explorer for fast symbol and architecture lookups.

There is NO 7th user-facing orchestrator (`/daily`, `/career`). Student and career workflows use skills under `agents/shared/skills/`.

## 2. Preventing Token & Credit Waste
- **Never re-read unchanged files**: Once a file has been inspected in this session, do not re-read its contents unless explicitly asked or modified.
- **Slice Context**: Do not output giant multi-thousand-line files. Return only unified diffs or targeted modifications.
- **Sizing Gate**: For simple single-line bug fixes or typo corrections, skip complex research and planning. Execute directly with minimal token overhead.

## 3. Audited Writes & Safety Gates
- Before modifying core architecture or creating new files, formulate a concise implementation plan with observable verification steps.
- For mutating runs that integrate with Daily Coder or Research Forge runtimes, prompt the user to run `ide-bridge` in the integrated terminal:
  ```bash
  ide-bridge daily-coder run --request "..." --profile M
  ```
