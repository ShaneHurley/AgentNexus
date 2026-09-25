# Variant `self-review-only` — Writing Studio

Self-review an existing draft without re-authoring the whole piece.

## When to use
- You already have a draft and want the mandatory SELF_REVIEW gate only.

## When not
- Independent hostile review → document-reviewer in a new chat. New draft from scratch → pick a writing type variant.

Paste `AGENT_MESSAGE.md` with packet field `browser_variant: "self-review-only"`.

For send-critical output: run `document-reviewer` in a **new chat** after this variant.
