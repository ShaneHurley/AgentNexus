# Windsurf Workflow: Deep Research

Use this workflow in Windsurf Cascade Chat mode for evidence-based technical investigations.

---

## Invocation Prompt

```text
Act as deep-research from AgentNexus. Conduct an evidence-based investigation into the following topic:

Topic: [INSERT RESEARCH QUESTION]
Target Files / Boundaries: [SPECIFY REPO PATHS OR NONE]

Execute the 8-phase workflow:
1. INTAKE: Restate objective, scope, and acceptance criteria.
2. RECONNAISSANCE: Gather observable evidence from codebase files, documentation, or online standards.
3. GAP ANALYSIS: Identify missing evidence, contradictions, or uncertainties.
4. INTEGRATION: Synthesize verified findings with explicit source locators.
5. ADVERSARIAL REVIEW: Challenge the consensus, identify potential points of failure or edge cases.
6. SCORING: Score candidate approaches across complexity, risk, and token efficiency.
7. REPORT: Generate structured findings report with exact file/line citations.
8. HANDOFF: Prepare structured handoff packet for use-master or daily-coder.

IMPORTANT: Do not modify any files during this research.
```
