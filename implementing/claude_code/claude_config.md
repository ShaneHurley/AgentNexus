# Claude Code — Custom Instructions, Slash Commands & Tool Config

## Global Settings (`~/.claude/settings.json`)

```json
{
  "model": "claude-sonnet-4-5",
  "maxTokens": 8192,
  "theme": "dark",
  "verbose": false,
  "extendedThinking": false,
  "allowedTools": ["Read", "Write", "Edit", "MultiEdit", "Bash", "Glob", "Grep"],
  "disallowedTools": [],
  "permissions": {
    "allow": [
      "Bash(git status:*)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(pytest:*)",
      "Bash(python:*)",
      "Bash(npm test:*)"
    ],
    "deny": [
      "Bash(git push origin main:*)",
      "Bash(git push origin master:*)",
      "Bash(rm -rf:*)",
      "Bash(sudo rm:*)"
    ]
  }
}
```

---

## Project-level `CLAUDE.md` (place at repo root)

See `README.md` in this folder for the full template. Key sections:
- **Role Contract**: maps current session to KEEP-6 orchestrator
- **Delegation Rules**: read-only vs mutating tool permissions per role
- **Token Economy**: caching and batching rules to minimize API cost
- **Forbidden Operations**: protected branches, credential files, destructive commands

---

## Slash Command Reference

| Command | Agent Mapped | Tool Permissions |
|---|---|---|
| `/agents deep-research` | `deep-research` orchestrator | Read, Glob, Grep, WebFetch |
| `/agents plan-prep` | `plan-prep` specialist | Read, Glob, Grep (no writes) |
| `/agents code-reviewer` | `code-reviewer` delegate | Read, Glob, Grep (no writes) |
| `/agents researcher` | `researcher` delegate | Read, Glob, Grep only |
| `/agents daily-coder` | `daily-coder` orchestrator | Full (default) |
| `/clear` | — | Clears conversation context |
| `/compact` | — | Compacts context, preserves ledger |
| `/cost` | — | Shows token usage for session |

---

## Extended Thinking — When to Enable

Enable only for:
- `deep-research` complex multi-source synthesis
- `plan-prep` with >10 interdependent components
- Adversarial security review

```bash
# Enable for one session
claude --model claude-opus-4-5

# Or toggle in-session
/settings extendedThinking true
```

**Cost impact**: Extended thinking uses ~3–5x tokens. Use `claude-sonnet-4-5` for routine coding.

---

## Headless / CI Mode

```bash
# Non-interactive, print output only (zero token waste on UI)
claude --print "Run tests and summarize failures" --output-format json

# Pipe into scripts
claude --print "List TODO items in src/" | tee todos.txt

# With explicit model for cost control
claude --print --model claude-haiku-4-5 "Summarize CHANGELOG.md in 3 bullets"
```

---

## Multi-Session Research Handoff Protocol

When `deep-research` produces an artifact for `plan-prep`:

```bash
# Session 1: Research
claude --allowedTools "Read,Glob,Grep,WebFetch"
# ...conduct research, output to research_output.md...

# Session 2: Plan (read the artifact from Session 1)
claude --print "Read research_output.md and produce an implementation plan"
```

Never carry a multi-phase workflow inside one unbounded session — split phases to keep context fresh and costs bounded.

---

## Token-Saving Rules

1. **One read per file** — use Grep to find the exact lines you need before reading
2. **Compact early** — run `/compact` after completing each KEEP-6 phase
3. **Use `--print` for queries** — avoids interactive session overhead
4. **Haiku for summaries** — `claude-haiku-4-5` for log summarization, file indexing
5. **Sonnet for coding** — default for daily-coder tasks
6. **Opus only for adversarial review** — code-reviewer, claim-auditor, deep-research phd tier
