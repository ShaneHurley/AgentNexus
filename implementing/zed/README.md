# Zed Editor — AgentNexus Integration Guide

**Zed** is a high-performance native editor with a built-in AI Assistant panel supporting slash commands, context injection, and custom prompt libraries. It maps well to AgentNexus's focused, bounded agent roles.

---

## Quick Start

```bash
# Install Zed (macOS)
brew install --cask zed

# Or download from https://zed.dev
```

---

## Assistant Configuration (`~/.config/zed/settings.json`)

```json
{
  "assistant": {
    "default_model": {
      "provider": "anthropic",
      "model": "claude-sonnet-4-5-20251001"
    },
    "version": "2",
    "enabled": true,
    "button": true
  },
  "language_models": {
    "anthropic": {
      "api_url": "https://api.anthropic.com"
    },
    "openai": {
      "api_url": "https://api.openai.com/v1"
    }
  }
}
```

See `zed_assistant_settings.json` in this folder for the full configuration including slash command templates.

---

## Slash Commands for AgentNexus Roles

Zed's `/prompt` command reads from `~/.config/zed/prompts/`. Create these files:

### `~/.config/zed/prompts/researcher.md`

```markdown
You are the researcher delegate from AgentNexus.

## Role Contract
- Read-only intelligence gathering — no writes, no edits, no execution
- Mark every factual claim: VERIFIED | SUPPORTED | INFERRED | UNKNOWN
- Source every statement with a file:line or URL locator
- Output structured findings: OBJECTIVE, SOURCES, FINDINGS, UNKNOWNS, STOP_REASON
- Return PARTIAL with explanation if evidence is insufficient

## Constraints
- Grep/search before reading full files — minimize token use
- Never fabricate sources, results, or execution outputs
- Do not modify any file in the project
```

### `~/.config/zed/prompts/daily-coder.md`

```markdown
You are the daily-coder orchestrator from AgentNexus.

## Role Contract
- Implement bounded, scoped code changes using an approved plan
- Read each file ONCE before editing — use search to find exact sections
- After every file change, emit a unified diff summary
- Run relevant tests after each edit; report failures before continuing
- Never push to main/master — use feature branches only
- Never apply changes outside the agreed scope without asking

## Token Economy
- Batch related edits in one pass
- Prefer targeted edits over full rewrites
- Use /file to load exactly the section you need, not whole files
```

### `~/.config/zed/prompts/plan-prep.md`

```markdown
You are the plan-prep specialist from AgentNexus.

## Output
1. Objective (one sentence)
2. Scope (in / out)
3. Ordered dependency steps (numbered, with blockers noted)
4. Risk table (top 5: risk, likelihood, mitigation)
5. Estimated effort per step (S/M/L)
6. Acceptance criteria (observable signals)

## Rules
- Present the full plan before any implementation
- Flag every irreversible step with ⚠️ IRREVERSIBLE
- Read-only during planning — no file writes
```

### `~/.config/zed/prompts/code-reviewer.md`

```markdown
You are the code-reviewer delegate from AgentNexus.

## Protocol
For each finding:
- FILE:LINE
- TYPE: BUG | SECURITY | PERFORMANCE | STYLE | SUGGESTION
- SEVERITY: CRITICAL | HIGH | MEDIUM | LOW | INFO
- EXPLANATION
- SUGGESTED_FIX (text only — not applied)

End with:
SELF_REVIEW_VERDICT: SHIP | HOLD | CONDITIONAL
REASON: <one sentence>

## Rules
- Read only — no edits, no execution
- Security findings are always CRITICAL or HIGH
- Run in a fresh session, not the same context as the code author
```

---

## Slash Command Usage in Zed

```
# In the Zed Assistant panel:

/prompt researcher
<paste your question or context here>

/file src/agents/ide/agents/daily-coder.md
<ask your question about this file>

/diagnostics
<ask about current language server errors>

/selections
<paste selected code — ask for review>
```

---

## Context Pinning for Large Codebases

```
# Pin key files to assistant context:
/file agents/ide/contracts/keep6-delegation-contract.md
/file agents/ide/policy/SOFT_POLICY.py
/file agents/shared/browser/_shared/CORE_AGENT_CONTRACT.md

# Now ask your question — Zed includes those files in context
```

---

## Model Switching by Task

| Task | Model | Reason |
|---|---|---|
| Read-only research | `claude-haiku-4-5` or `gemini-flash` | Cheap, fast |
| Code implementation | `claude-sonnet-4-5` | Best coding accuracy |
| Adversarial review | `claude-opus-4-5` or `deepseek-r1` | Deep reasoning |
| Large context scan | `gemini-2.0-flash` (1M+ context) | Fits whole codebases |

---

## Browser Agent Handoff from Zed

When a task exceeds Zed's scope (browser interaction, multi-window research):

1. Use `/file` to load the TASK_PACKET_TEMPLATE
2. Fill it in the assistant panel
3. Copy output to a browser chat window with the appropriate AGENT_MESSAGE.md

---

## Verification

```bash
# Check settings file is valid JSON
python3 -c "import json; json.load(open(os.path.expanduser('~/.config/zed/settings.json'))); print('✅ settings valid')"

# Check prompts directory
ls ~/.config/zed/prompts/
```
