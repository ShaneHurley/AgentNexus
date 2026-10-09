# Exposing AgentNexus Skills to Antigravity

Antigravity features a native **Skills** system that loads instructions and workflows from `SKILL.md` folders.

AgentNexus comes with rich personal and shared skills under `agents/shared/skills/`.

## 1. Skill Inventory

### Personal Skills
Located in [`agents/shared/skills/personal/`](../../agents/shared/skills/personal/):
- **`career-tools`**:
  - `resume-tailor.md`: Tailors resumes against job specs using truth-preserving claim checks.
  - `interview-prep.md`: Generates adversarial behavioral and technical mock interviews.
  - `opportunity-review.md`: Evaluates job roles against personal criteria.
- **`deadline-triage`**: Prioritizes urgent deliverables and calculates risk.
- **`lab-preflight`**: Checklist verification before running scientific or lab experiments.
- **`professor-email`**: Drafts high-diplomacy academic correspondence.
- **`study-hints`**: Formulates hints rather than direct solutions for learning.

### Shared Toolkit Skills
Located in [`agents/shared/skills/shared/`](../../agents/shared/skills/shared/):
- **`claim-auditor`**: Verifies claims against source documents; marks claims `VERIFIED`, `SUPPORTED`, `INFERRED`, or `UNKNOWN`.
- **`datasheet-extractor`**: Extracts dense tabular and electrical/spec parameters into structured JSON.
- **`structured-data-evaluator`**: Validates calculations, totals, and statistical accuracy.
- **`visualization-specifier`**: Formulates chart and graph specifications (Mermaid, ChartJS, Vega-lite).
- **`writing-improver`**: Enforces consistent style profiles (`academic`, `executive`, `technical_docs`, `casual`).

---

## 2. Linking Skills into Antigravity

Antigravity checks both global skills (`~/.gemini/antigravity/skills/` or builtin) and workspace skills.

To enable AgentNexus skills in your Antigravity session, run:
```bash
# Link all shared skills into the Antigravity user directory
mkdir -p ~/.gemini/antigravity/skills

for skill_dir in agents/shared/skills/shared/*; do
  if [ -d "$skill_dir" ]; then
    skill_name=$(basename "$skill_dir")
    ln -sfn "$(pwd)/$skill_dir" ~/.gemini/antigravity/skills/"$skill_name"
    echo "Linked skill: $skill_name"
  fi
done

for skill_dir in agents/shared/skills/personal/*; do
  if [ -d "$skill_dir" ]; then
    skill_name=$(basename "$skill_dir")
    ln -sfn "$(pwd)/$skill_dir" ~/.gemini/antigravity/skills/"$skill_name"
    echo "Linked personal skill: $skill_name"
  fi
done
```

Once linked, Antigravity will automatically present these skills in its available skill roster.
