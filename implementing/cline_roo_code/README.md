# Cline & Roo Code — AgentNexus Integration Guide

**Cline** (VS Code extension) and **Roo Code** (Roo's fork with custom modes) both support autonomous terminal execution, tool use, and custom role definitions. This guide maps AgentNexus KEEP-6 orchestrators and delegates to Cline/Roo custom modes with strict tool allowlists.

---

## Quick Install

```bash
# VS Code Extension Marketplace:
# - Cline: "saoudrizwan.claude-dev"
# - Roo Code: "rooveterinaryinc.roo-cline"

# Or via CLI:
code --install-extension saoudrizwan.claude-dev
code --install-extension rooveterinaryinc.roo-cline
```

---

## Custom Modes (`.roomodes`)

Place `.roomodes` at your repo root. Roo Code reads this file to define agent personas with scoped tool permissions.

See `custom_modes.json` in this folder — it maps all KEEP-6 roles to Roo modes.

---

## `.clinerules` — Global Instruction File

Create `.clinerules` at your project root:

```markdown
# AgentNexus Cline Rules

## Identity
You are operating inside the AgentNexus agent ecosystem. Follow KEEP-6 role contracts strictly.

## Core Rules
1. Read files ONCE — use search tools to find exact lines before reading entire files
2. Never push to main/master — use feature branches only
3. Never run destructive commands (rm -rf, DROP TABLE, etc.)
4. Never read ~/.aws, ~/.ssh credential files
5. After any file change, output a unified diff summary
6. Delegate browser tasks by producing a filled TASK_PACKET markdown block

## Token Economy
- Grep before reading
- Batch edits — apply multiple changes in one tool call when possible
- Stop and report PARTIAL rather than fabricating results

## Role Modes
- researcher: read-only — Grep, Read, ListFiles only
- planner: read + write to plan files only — no code edits
- implementer: full tools — code changes require explicit approval gate
- reviewer: read-only — findings report only, no applied fixes
```

---

## KEEP-6 Mode Mapping

| KEEP-6 Role | Roo/Cline Mode | Allowed Tools | Forbidden |
|---|---|---|---|
| `researcher` | `researcher` | Read, Grep, ListFiles | Write, Edit, Execute |
| `plan-prep` | `planner` | Read, Grep, Write(plan files only) | Execute, Edit(src) |
| `daily-coder` | `implementer` | Full | git push main, rm -rf |
| `code-reviewer` | `reviewer` | Read, Grep | Write, Edit, Execute |
| `deep-research` | `researcher` + context | Read, Grep, WebSearch | Write, Execute |
| `use-master` | `orchestrator` | Full + approval gates | Destructive without confirm |

---

## Model Selection by Role

| Mode | Recommended Model | Reason |
|---|---|---|
| `researcher` | `deepseek/deepseek-chat` (free) | Cheap read-only scanning |
| `planner` | `google/gemini-2.0-flash` (free) | Long context planning |
| `implementer` | `anthropic/claude-sonnet-4-5` | Best coding accuracy |
| `reviewer` | `deepseek/deepseek-r1` (free) | Chain-of-thought review |
| `orchestrator` | `anthropic/claude-opus-4-5` | Complex orchestration |

---

## Browser Agent Handoff

When a task requires browser agents, Cline produces a task packet block:

````markdown
<!-- BROWSER_TASK_HANDOFF -->
```yaml
browser_family: research-desk
browser_variant: deep
host: claude
mode: RESEARCH
objective: "[your objective]"
in_scope: ["supplied files"]
out_of_scope: ["code changes"]
acceptance_criteria: ["sources cited", "contradiction audit"]
```
<!-- END: Copy everything between the yaml fences into a new browser chat session
     with the research-desk AGENT_MESSAGE.md prepended -->
````

---

## Verification

```bash
# Confirm .roomodes is valid JSON
python3 -c "import json; json.load(open('.roomodes')); print('✅ .roomodes is valid')"

# Confirm .clinerules is present
[ -f .clinerules ] && echo "✅ .clinerules present" || echo "❌ missing"

# Test researcher mode (Roo Code): switch to researcher mode in sidebar
# then ask: "List all agent files in agents/ide/agents/"
# Expected: file list only — no edits proposed
```
