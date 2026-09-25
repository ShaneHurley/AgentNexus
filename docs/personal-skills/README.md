# Personal skills operator guide

Skills-first layer for computer-engineering student daily work and career development. Six IDE orchestrators stay unchanged. No `/daily`, `/career`, or personal mega-agent in v1.

## Spec and maps

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Full Personal Daily Capability and Career Skill Expansion Specification |
| [glean-overlap.md](glean-overlap.md) | Glean plugin vs local skills |
| [always-on-rule.md](always-on-rule.md) | L1 preference rule text |
| [enforcement.md](enforcement.md) | Soft vs hard write authority |
| [overlap-matrix.md](overlap-matrix.md) | Agents, browser, skills, Glean |
| [phase0-checklist.md](phase0-checklist.md) | Phase 0 gate |
| [promotion-gates.md](promotion-gates.md) | Section 15 promotion review |
| [usage-diary.md](usage-diary.md) | Phase 1 diary template |

## Resident catalog (Phase 1)

| ID | Path |
|----|------|
| `study-hints` | [`agents/shared/skills/personal/study-hints/`](../../agents/shared/skills/personal/study-hints/) |
| `professor-email` | [`agents/shared/skills/personal/professor-email/`](../../agents/shared/skills/personal/professor-email/) |
| `writing-improver` | [`agents/shared/skills/shared/writing-improver/`](../../agents/shared/skills/shared/writing-improver/) |
| `career-tools` | [`agents/shared/skills/personal/career-tools/`](../../agents/shared/skills/personal/career-tools/) |

Conditional / on-demand: `lab-preflight`, `deadline-triage`, career modes `opportunity-review` and `interview-prep`.

## Quick commands

```bash
# Install agent-core (from repo root)
pip install -e agents/shared/agent-core

# Validate personal schemas / store helper
python -m agent_core.personal_store --help

# Writing lint (fail-closed for COMPLETE)
python -m agent_core.writing_lint punctuation path/to/artifact.md

# Registry stub
python -m agent_core validate-registry

# Personal skill tests
python -m unittest discover -s tests/personal-skills -v
python -m unittest discover -s tests/writing -v
python -m unittest discover -s tests/toolkit -v
```

## Career data

Private store default (Windows): `%USERPROFILE%\.config\personal-career\`

Never commit career files. See [enforcement.md](enforcement.md) and SPEC §7.2.

## Escalation

Enterprise or org research → `/plan-prep` (Glean-first) or `deep-research`. Repository mutations → `/daily-coder` via `ide-bridge`.
