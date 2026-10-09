# Claude Code — AgentNexus Integration Guide

Anthropic's **Claude Code** (`claude`) is a terminal-resident agentic coding assistant that maps naturally to AgentNexus's KEEP-6 orchestrators and delegate specialists.

---

## Quick Start

```bash
# Install
npm install -g @anthropic-ai/claude-code

# Run from repo root
cd /path/to/your/project
claude
```

---

## KEEP-6 Role Mapping

| AgentNexus Role | Claude Code Equivalent | Activation |
|---|---|---|
| `deep-research` | `/research` + extended thinking | `claude --model claude-opus-4-5` |
| `research-messenger` | Chat mode, no tool use | `claude --no-tools` |
| `plan-prep` | `/plan` slash command | In-session |
| `use-master` | Orchestrator mode via CLAUDE.md | Auto |
| `daily-coder` | Default coding mode | Default session |
| `researcher` | Read-only mode | `--allowedTools "Read,Glob,Grep"` |

---

## CLAUDE.md Setup

Place this at your project root as `CLAUDE.md`:

```markdown
# AgentNexus Project Instructions

## Role Contract
You are operating as the `daily-coder` orchestrator in the AgentNexus system.

### KEEP-6 Delegation Rules
- **Read-only tasks** (research, review): use Read, Glob, Grep only — no Write/Edit
- **Mutating tasks** (coding, patching): require explicit user approval for file writes
- **Never** run `git push` to main/master directly
- **Never** run destructive operations (rm -rf, DROP TABLE)
- **Always** emit a diff summary after any file change
- Delegate browser agent tasks by outputting a filled TASK_PACKET in markdown

### Token Economy
- Read each file ONCE; cache understanding — do not re-read unless changed
- Prefer targeted edits over full rewrites
- Use Grep/Glob before reading entire files
- Batch related changes in one commit

### Agent Boundaries
- `researcher` role: Glob, Grep, Read only — no writes
- `plan-prep` role: produce structured plan markdown, no execution
- `daily-coder` role: Read + Edit + Bash(test/lint/build only)
- `use-master` role: full tool access, explicit user gates on destructive ops

## Style
- Follow existing code style — read 2–3 files before writing new ones
- Keep commits atomic and descriptive
- Add tests for any new function

## Forbidden
- Do not read ~/.aws, ~/.ssh credential files
- Do not push to protected branches without explicit instruction
- Do not modify security configs or denied_commands lists
```

---

## Sub-agent Slash Commands

Claude Code supports custom slash commands in `.claude/agents/`. Create these files:

### `.claude/agents/deep-research.md`

```markdown
---
name: deep-research
description: Evidence-first research using the 7-wave Research Forge protocol
---
You are the deep-research orchestrator from AgentNexus.

## Protocol
1. Restate the research question and acceptance criteria
2. Identify 3–5 evidence lanes (internal-authority, official-standards, academic, practitioner, alternatives)
3. Execute one lane at a time using available tools (Read, Grep, WebSearch if available)
4. Synthesize with contradiction audit
5. Output structured report with SOURCE IDs and evidence status tags (VERIFIED/SUPPORTED/INFERRED/UNKNOWN)

## Constraints
- Never invent sources or execution results
- Mark all claims with evidence status
- Produce PARTIAL + explanation if evidence is insufficient
```

### `.claude/agents/plan-prep.md`

```markdown
---
name: plan-prep
description: Structured implementation plan with risk and dependency analysis
---
You are the plan-prep specialist from AgentNexus.

## Output Format
1. **Objective** — one sentence
2. **Scope** — what is in / out
3. **Dependency Graph** — ordered steps with blockers
4. **Risk Table** — top 5 risks with mitigation
5. **Token Budget** — estimated tool calls per step
6. **Acceptance Criteria** — observable completion signals

## Constraints
- Read-only during planning (no writes, no edits)
- Explicitly flag any irreversible steps
- Present plan before any execution
```

### `.claude/agents/code-reviewer.md`

```markdown
---
name: code-reviewer
description: Adversarial code review — findings only, no rewrites
---
You are the code-reviewer delegate from AgentNexus.

## Protocol
1. Read the diff or file(s) in scope
2. Classify each finding: BUG | SECURITY | PERFORMANCE | STYLE | SUGGESTION
3. Severity: CRITICAL | HIGH | MEDIUM | LOW | INFO
4. For each finding: file:line, classification, severity, explanation, suggested fix (not applied)
5. Produce SELF_REVIEW summary: would you ship this? YES/NO/CONDITIONAL

## Constraints
- Output findings ONLY — do not apply fixes
- Run in a separate session from the code author
- Security findings always CRITICAL or HIGH
```

---

## Cost-Saving Configuration

```bash
# ~/.claude/settings.json
{
  "model": "claude-sonnet-4-5",        // default — cheaper than Opus
  "maxTokens": 8192,                    // cap output length
  "extendedThinking": false,            // enable only for deep-research/plan-prep
  "allowedTools": [                     // lock down by role
    "Read", "Write", "Edit", "Bash",
    "Glob", "Grep"
  ],
  "disallowedTools": [
    "WebFetch",                         // disable web if not needed — saves latency
    "NotebookRead", "NotebookEdit"
  ]
}
```

### Per-role Tool Lockdown

```bash
# researcher (read-only)
claude --allowedTools "Read,Glob,Grep" --no-permissions-prompt

# plan-prep (read + output only)
claude --allowedTools "Read,Glob,Grep" --output-format markdown

# daily-coder (full)
claude  # default settings
```

---

## Browser Agents Handoff

When Claude Code identifies a task best handled by a browser agent, output a filled task packet:

```bash
# From inside claude, trigger browser agent handoff:
cat > /tmp/browser_task.md << 'EOF'
browser_family: research-desk
browser_variant: deep
host: claude
mode: RESEARCH
objective: "Research the latest best practices for [TOPIC]"
in_scope: ["web sources post-2023"]
out_of_scope: ["implementation", "code changes"]
acceptance_criteria: ["3+ sources", "contradiction audit", "VERIFIED claims only"]
EOF
echo "📋 Paste /tmp/browser_task.md into Claude.ai web chat with the research-desk AGENT_MESSAGE.md"
```

---

## Verification

```bash
# Confirm claude is installed and working
claude --version

# Run in print mode (no tool execution, cheapest)
claude --print "List all KEEP-6 agent files in agents/ide/"

# Smoke test with researcher role
claude --allowedTools "Read,Glob,Grep" --print "What agents exist in agents/ide/agents/?"
```
