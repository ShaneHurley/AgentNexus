# Variant `github-pr` — Writing Studio

Pull request description — summary, motivation, test plan, and rollout notes.

## When to use

- Turning a diff summary, issue link, and notes into a PR body before opening the PR.

## When not

- Repository README → `github-readme`.
- Bug report only → `github-issue`.

Paste `AGENT_MESSAGE.md` with packet field `browser_variant: "github-pr"`.

For send-critical output: run `document-reviewer` in a **new chat** after this variant.
