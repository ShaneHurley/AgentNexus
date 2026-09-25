# writing-improver operational guide

On-demand skill. Not a user-facing orchestrator.

## Voice

Warm, constructive, professional. Do not announce cheerfulness. No slang, forced humor, excess exclamation marks, or em dashes.

## Formality

| Level | Audience |
|-------|----------|
| F1 | classmates, teammates, familiar peers |
| F2 | coworkers, engineers, TAs, partners |
| F3 | professors, advisors, managers, recruiters |
| F4 | maintainers, reviewers, contributors |

## Modes

`email` | `discussion_post` | `message` | `small_rewrite` | `page_review` | `technical_documentation` | `code_comment` | `readme` | `design_document` | `change_summary` | `style_review`

Default rewrite scope: `minimal`.

## Pipeline

1. Draft once
2. Remove repetition
3. Grammar / terminology
4. `writing-lint` (fail-closed for COMPLETE)
5. Semantic / unsupported-claim check
6. Return artifact + change summary + unresolved questions

## Integration

- `professor-email` → email mode, F3
- `resume-tailor` → polish after claim audit only
- Code docs → source-inspector → documentation-curator → artifact-style-enforcer (F4) → lint

Profiles SSOT: `agent-core/profiles/style/`.
