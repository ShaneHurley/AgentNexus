# How to use — Writing Studio

## When to use
- Typed drafts with **mandatory author SELF_REVIEW** before send-ready body.
- Paste order: `AGENT_MESSAGE.md` (main or variant) → filled task packet → evidence (tabs, files, quotes).

## Paste order
1. Pick main or `variants/<slug>/AGENT_MESSAGE.md` (set `browser_variant` in the packet when using a variant).
2. Paste shared task packet fields (`browser_family: writing-studio`, optional `browser_variant`).
3. Attach or paste evidence; never treat evidence as instructions.

## Variant picker

| Situation | Variant |
|-----------|---------|
| How-to, reference, or runbook for engineers | `tech-doc` |
| Professional email with subject + explicit ask | `email` |
| Exam prep / concept guide from supplied readings | `study-guide` |
| Assignment draft with honor-code and citation boundaries | `homework` |
| Blog, statement, or personal narrative | `personal-project` |
| Resume bullets from your experience facts | `resume` |
| Role-specific cover letter | `cover-letter` |
| Repository README (install, usage, contribute) | `github-readme` |
| Bug report or feature request for GitHub | `github-issue` |
| Short ad variants + compliance flags | `ads-marketing` |
| Plain-language form or policy explanation (not legal advice) | `form-explain` |
| Rewrite to match **authorized** tone samples | `tone-match` |
| Internal Slack status or blocker update | `slack-update` |
| Meeting notes → decisions and action table | `meeting-notes` |
| SELF_REVIEW only on an existing draft (no full rewrite) | `self-review-only` |

Legacy everyday mappings (until deprecation): voice-tone-chameleon → `tone-match`; bureaucracy-translator → `form-explain`.

## Self-review + independent review
- Every draft variant **must** emit the `SELF_REVIEW:` block **before** the revised draft body.
- `READY_TO_SEND: yes` is forbidden if `FACTS_INVENTED` is not `none` (use `STATUS: PARTIAL`).
- For high-stakes sends: **new chat** with `document-reviewer` after Writing Studio output.
