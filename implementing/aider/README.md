# Aider — AgentNexus Integration Guide

**Aider** is a terminal-based AI pair programmer with first-class git integration. Its `--architect` mode maps directly to AgentNexus's `plan-prep` → `daily-coder` two-step workflow.

---

## Quick Start

```bash
pip install aider-chat

# Run from repo root in architect mode (recommended for AgentNexus)
cd /path/to/your/project
aider --architect --model anthropic/claude-sonnet-4-5-20251001 \
      --editor-model anthropic/claude-haiku-4-5-20251001
```

---

## Architect Mode — KEEP-6 Alignment

Aider's `--architect` mode splits work into two AI calls:
1. **Architect** (big model) = AgentNexus `plan-prep` — designs the change
2. **Editor** (fast model) = AgentNexus `daily-coder` — applies the edit

This directly mirrors AgentNexus's delegation contract:
- `plan-prep` designs; `daily-coder` implements
- Cost: architect uses Sonnet/Opus; editor uses Haiku (10× cheaper)

```bash
# Optimal cost/quality split:
aider --architect \
  --model anthropic/claude-opus-4-5-20251001 \     # plan-prep tier
  --editor-model anthropic/claude-haiku-4-5-20251001  # daily-coder tier
```

---

## Configuration File (`.aider.conf.yml`)

See `.aider.conf.yml` in this folder. Key settings:
- `architect: true` — always use architect mode
- `model: anthropic/claude-sonnet-4-5-20251001` — default architect
- `editor-model: anthropic/claude-haiku-4-5-20251001` — default editor
- `conventions: CONVENTIONS.md` — style guide aider reads before each edit
- `gitignore: true` — respect .gitignore
- `auto-commits: false` — require explicit commit (matches AgentNexus audit requirement)

---

## `CONVENTIONS.md` (repo root)

See `CONVENTIONS.md` in this folder. Aider reads this automatically. It enforces:
- File naming and structure conventions
- Commit message format
- KEEP-6 role boundaries (which agent is allowed to change which files)
- Forbidden operations (pushing to main, modifying policy files)

---

## KEEP-6 Role Mapping

| AgentNexus Role | Aider Usage Pattern |
|---|---|
| `plan-prep` | `/architect` command — design only, no apply |
| `daily-coder` | Default `--architect` mode — architect designs, editor applies |
| `researcher` | `aider --no-auto-commits --map-refresh=always` + read-only chat |
| `code-reviewer` | `aider --read <files>` + `/ask` mode (no writes) |
| `deep-research` | Kimi/Gemini web (too large for aider context budget) |

---

## `/ask` Mode for Read-Only Work

```bash
# Start aider in ask-only mode (researcher role equivalent)
aider --no-auto-commits

# Inside aider, use /ask to query without applying changes:
/ask What does agents/ide/agents/daily-coder.md define as the KEEP-6 contract?

# Load a file into context read-only:
/read agents/shared/browser/_shared/CORE_AGENT_CONTRACT.md
```

---

## Browser Agent Handoff

When a task needs browser-based research:

```bash
# Inside aider:
/ask Generate a filled browser agent TASK_PACKET for researching [TOPIC]
# Copy the output, then open a new browser tab with the research-desk AGENT_MESSAGE.md
```

---

## Cost-Saving Patterns

### 1. Free-tier architect with paid editor

```bash
# Use free Gemini Flash as architect, cheap Haiku as editor
aider --architect \
  --model gemini/gemini-2.0-flash-exp \
  --editor-model anthropic/claude-haiku-4-5-20251001
```

### 2. DeepSeek R1 for adversarial review

```bash
# Deep chain-of-thought review at near-zero cost
aider --model deepseek/deepseek-r1 --no-auto-commits
/ask Review this diff for security issues: [paste diff]
```

### 3. Limit context with `--map-tokens`

```bash
# Cap repo map at 2048 tokens (saves ~$0.003/session)
aider --architect --map-tokens 2048
```

---

## Verification

```bash
# Check aider is installed
aider --version

# Dry run — show what files would be added to context
aider --dry-run agents/ide/agents/daily-coder.md

# Confirm .aider.conf.yml is valid YAML
python3 -c "import yaml; yaml.safe_load(open('.aider.conf.yml')); print('✅ config valid')"

# Confirm CONVENTIONS.md is present
[ -f CONVENTIONS.md ] && echo "✅ CONVENTIONS.md present" || echo "❌ missing"
```
