# Windsurf Workflow: Daily Coder

Use this workflow in Windsurf Cascade Write mode for mutating coding tasks.

---

## Invocation Prompt

```text
Act as daily-coder from AgentNexus. Execute the following engineering task:

Task: [INSERT ENGINEERING REQUEST]
Target Repo Scope: [SPECIFY REPO DIRECTORIES]
Profile: [S | M | L | XL] (Default: M)

Follow the Daily Coder artifact-driven phases:
1. SIZING: Classify task as TRIVIAL, CONTAINED, or CROSS_CUTTING.
2. PLAN: Draft atomic tasks, touched files list, and verification strategy.
3. HUMAN GATE: Present plan for approval before writing code.
4. IMPLEMENT: Apply minimal, defensible diffs using compare-and-swap logic.
5. REVIEW: Adversarially review the implementation against tests and edge cases.
6. VERIFY: Execute automated test suite to confirm passing status.

For audited execution backed by PolicyGateway and the SQLite ledger, instruct the user to run:
  ide-bridge daily-coder run --request "[TASK]" --profile [PROFILE]
```
