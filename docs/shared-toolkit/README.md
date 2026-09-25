# Shared toolkit

| ID | Job | Kind |
|----|-----|------|
| datasheet-extractor | Extract pinouts/voltages/registers/timing from supplied PDFs; UNKNOWN when missing | skill |
| structured-data-evaluator | Interpret measurements after deterministic calc | skill |
| visualization-specifier | Chart/table-ready specs from evaluated data | skill / prompt |
| claim-auditor | VERIFIED / USER_CONFIRMED / UNKNOWN / UNSUPPORTED | skill (career claim mode) |
| writing-lint | Em dash, repetition, terminology, links, structure | deterministic |
| source-inspector | Source-bound facts with locators | shared subagent |
| artifact-style-enforcer | Conform to style profile without semantic change | shared subagent |
| documentation-curator | Docs only after accepted evidence | shared subagent |

See [ADR 0002](../decisions/0002-split-data-workflow.md): extract ≠ calc ≠ eval ≠ viz.

Operational writing guide: [writing-improver.md](writing-improver.md). Formality: [style-profiles.md](style-profiles.md).
