# Variant `regression-hunt` — Code Reviewer

Before/after behavior and **blast radius**: public API deltas, schema changes, renamed exports, migration partiality. Caller impact is **INFERRED or UNKNOWN** unless supplied — never fabricated.

Use for refactors, library changes, flag rollouts, or bug fixes where compatibility matters.

Packet: `browser_variant: "regression-hunt"`.
