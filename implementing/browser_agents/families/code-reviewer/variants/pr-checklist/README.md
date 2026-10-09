# Variant `pr-checklist` — Code Reviewer

PR-shaped review: title/body, checklist, and **test plan honesty** vs the actual diff. Catches overclaiming (“adds tests” with no test hunks) and under-disclosure (behavior change without plan).

Pair with PR description paste + diff. Not a substitute for `diff-adversarial` when you need deep hunk logic review — run both in separate passes if needed.

Packet: `browser_variant: "pr-checklist"`.
