# AgentNexus Antigravity Operational Rules

These rules govern agent behavior inside Google Antigravity IDE and Agent View.

## 1. User-Facing Orchestrator Authority (KEEP-6)
Direct user interaction is constrained to exactly six orchestrators:
1. `deep-research`: Eight-phase evidence research; sole invoker of lane scouts. Always read-only.
2. `research-messenger`: Assemble scored research packets; generates 17 handoffs. Never conducts ad-hoc research.
3. `plan-prep`: Gathers Glean/local codebase planning context prior to master planning.
4. `use-master`: Dispatches master execution DAGs. No native direct file modifications; delegates tasks to specialists.
5. `daily-coder`: Parent orchestrator for mutating code modifications; dispatches through `ide-bridge`.
6. `researcher`: Read-only codebase reconnaissance and investigation.

**There is no 7th user-facing orchestrator.** Student, daily, and career workflows are performed via on-demand skills.

## 2. Hard Policy Boundaries
- **Audited Writes**: Direct, unbridged modifications to project source code without a validated plan are prohibited. All mutating changes must pass through `ide-bridge daily-coder` or explicit user approval via planning mode.
- **Context Slicing**: When delegating work to Antigravity subagents (`invoke_subagent`), do not pass raw cumulative transcripts. Provide only:
  - Task Anchor (single sentence objective).
  - Explicit file and symbol references.
  - Acceptance criteria and constraints.
- **Mock-by-Default Execution**: Runtimes execute in safe/mock simulation unless explicitly elevated with `--live`.
- **Personal Career Boundaries**: Career files (resumes, interview notes) must not be processed through code `documenter` phases; use `career-tools` and `personal-store` with soft-confirm.

## 3. Slash Command Alignment
- Use `/plan` before executing complex, multi-component refactors.
- Use `/goal` for autonomous, multi-phase verification runs.
- Use `/schedule` for background reminders and timed checks.
- Use `/grill-me` to clarify ambiguous architecture choices with the user.
