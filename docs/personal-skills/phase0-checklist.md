# Phase 0 checklist

Gate before Phase 1 pilots. Mark each item when done.

| Item | Owner | Status |
|------|-------|--------|
| Path matrix: live `agents/ide/` vs docs/CI | implementer | done |
| CI + docs install lines use `agents/ide/` | implementer | done |
| Baselines template (20–30 tasks) started | operator | template ready |
| Classify new IDs: orchestrator \| shared_subagent \| skill \| deterministic | implementer | done (overlap-matrix) |
| Freeze net-new shared roles after writing/data set | implementer | frozen for this slice |
| `agents/shared/agent-core/` stub + schemas listed | implementer | done |
| `glean-overlap.md` + `enforcement.md` published | implementer | done |
| Privacy DoD documented | implementer | done |

## Packaging SSOT

| Kind | Location |
|------|----------|
| Shared contracts | `agents/shared/agent-core/shared-agents/<role>/` |
| Style profiles | `agents/shared/agent-core/profiles/style/` |
| Deterministic services | `agents/shared/agent-core/services/` |
| Skill bodies | `agents/shared/skills/personal/`, `agents/shared/skills/shared/` |
| Personal schemas | `agents/shared/schemas/personal/` |
| Career PII | `%USERPROFILE%\.config\personal-career\` |

## Rejected for this slice

Full agent-core Phases 0–6 migration; personal-orchestrator; `/daily`; `/career`; seventh UF agent; forking Glean skills; monolithic spreadsheet agent.
