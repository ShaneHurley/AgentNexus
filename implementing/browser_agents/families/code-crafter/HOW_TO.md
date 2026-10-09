# How to use Code Crafter

1. Supply repo path, mission, files, plan task ids, and acceptance criteria.
2. Variants:

| Need | Variant |
|------|---------|
| Default patch + self-review + bridge | `patch-draft` |
| Diagnose before fix | `debug-root-cause` |
| Test plan only | `test-checklist` |
| Rollback plan | `rollback-plan` |
| Hand off existing draft | `bridge-handoff` |
| Re-review same scope | `self-review-only` |

3. **SELF_REVIEW** is mandatory before final diff on `patch-draft` and main generalist coding path.
4. Run **code-reviewer** in a **separate chat** before ship when risk is high.
5. Mutations: use `HANDOFF_TO_IDE_BRIDGE` — chat alone does not execute git writes.

**Legacy:** `browser_idea: daily-coder` → `code-crafter` / `patch-draft`.
