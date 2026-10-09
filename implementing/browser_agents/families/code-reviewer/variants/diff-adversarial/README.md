# Variant `diff-adversarial` — Code Reviewer

**Default lens.** Same procedure as family main: hunk-ordered walk for bugs, regressions, security signals, and missing tests.

Use when you have a unified diff and want a general hostile pass (not PR-description-only or single-lens review).

Packet: `browser_variant: "diff-adversarial"`. Paste `AGENT_MESSAGE.md` in a **new chat** after code-crafter output.
