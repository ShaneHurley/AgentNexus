# AgentNexus Repository Conventions

This file is read by Aider before every edit. Follow these rules strictly.

---

## File Structure

```
agents/
  ide/
    agents/       <- KEEP-6 orchestrator definitions (read before any edit to these)
    contracts/    <- Delegation contracts (READ ONLY — do not modify without explicit user approval)
    policy/       <- Policy enforcement (READ ONLY — do not modify)
    tests/        <- Unit tests (always run after edits)
  shared/
    browser/      <- Browser agent pack (read-only for daily-coder; separate browser sessions only)
    skills/       <- Shared skills (read before using)
implementing/     <- This integration hub (generated docs — freely editable)
```

---

## KEEP-6 File Ownership

| Role | May Write To | Must Not Write To |
|---|---|---|
| `daily-coder` | `agents/coding/`, `agents/daily-task/`, `tests/` | `agents/ide/contracts/`, `agents/ide/policy/`, `agents/shared/browser/` |
| `plan-prep` | `docs/plans/*.plan.md`, `PLAN*.md` | Any source code |
| `researcher` | None | Everything |
| `code-reviewer` | None | Everything |
| `use-master` | Any (with approval gate) | Protected branches, credential files |

---

## Commit Message Format

```
<type>(<scope>): <concise description under 72 chars>

[optional body: what changed and why]

Agent: <role-name> (aider architect mode)
Scope: <list of changed files>
```

Types: `feat` | `fix` | `refactor` | `docs` | `test` | `chore`

Examples:
```
feat(daily-coder): add retry logic for API rate limits
fix(browser-agents): correct TASK_PACKET schema for v3 families
docs(implementing): add Zed integration guide
```

---

## Coding Style

- **Python**: PEP 8, type hints on all public functions, docstrings for public APIs
- **Markdown**: ATX headers (`#`), fenced code blocks with language tags, no trailing spaces
- **JSON**: 2-space indent, no trailing commas, keys in alphabetical order within objects
- **YAML**: 2-space indent, explicit string quotes for values containing `:` or `#`

---

## Test Requirements

- Run `python -m pytest agents/ide/tests/ -x -q` after any edit to `agents/ide/`
- Run `python agents/daily-task/driver.py --list` after any edit to `agents/daily-task/`
- All tests must pass before committing — do not commit with failing tests

---

## Forbidden Actions

- ❌ `git push origin main` or `git push origin master`
- ❌ `git push --force` to any protected branch
- ❌ Modifying `agents/ide/policy/SOFT_POLICY.py` without explicit user approval
- ❌ Reading `~/.aws/*`, `~/.ssh/id_rsa`, or other credential files
- ❌ `rm -rf` any directory without explicit confirmation
- ❌ Adding `# type: ignore` or `noqa` without an explanation comment

---

## Token Economy Rules

1. Read each file ONCE per session — cache your understanding
2. Use Grep/search to find exact lines before reading full files
3. Apply multiple related changes in one edit block
4. Prefer targeted edits over full file rewrites
5. Stop and ask if scope is ambiguous — never guess and overwrite
