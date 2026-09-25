# Messenger Output Contract

Return two distinct artifacts when the interface supports structured attachments:

1. a machine packet conforming to `research-intelligence-packet/1.0`;
2. a human-readable report derived only from that packet.

Otherwise return the human report and state that the machine packet is available on request. Do not interleave raw JSON with the report by default.

## Machine packet

Required top-level content:

- schema version, status, topic, decision, audience, scope, freshness boundary;
- processed source, independent lineage, and unprocessed-item counts;
- disclosure and output-handling controls;
- source, evidence, claim, fact, contradiction, example, and gap ledgers;
- scored, ranked, and qualified recommendations;
- exactly 17 canonical role handoffs;
- limitations, exact unprocessed items, and unfavorable-review result.

All IDs must be unique within their ledger. Every evidence item resolves to a source. Every claim, fact, contradiction, recommendation, and handoff reference resolves. Source counts and lineage counts must match the ledgers.

## Human report

Use this order:

1. Status and decision
2. Executive findings
3. Evidence map and corpus coverage
4. Supporting evidence
5. Unfavorable and conflicting evidence
6. Examples, alternatives, and transfer limits
7. Scored roadmap
8. Seventeen-role handoffs
9. Limitations and research backlog
10. Sources

Every material factual statement identifies fact or evidence IDs. Show claim classifications, recommendation bands, adjusted priorities, confidence, and sensitivity without changing packet values.

## Status rules

- `COMPLETE`: usable evidence supports the bounded decision and validation passes. Residual weakness still remains visible.
- `PARTIAL`: usable evidence exists, but access, coverage, correction, validation, or rendering defects remain.
- `BLOCKED`: no usable evidence supports assembly, or contract/disclosure defects make safe output impossible.

Do not use `COMPLETE` after a non-PASS unfavorable review or failed post-repair validation.

## Consistency gate

Reject and repair once if the report:

- introduces an uncited fact;
- changes a classification, score, rank, status, or recommendation;
- omits a contradiction, material limitation, or unprocessed item;
- violates disclosure handling;
- omits or duplicates a canonical role.

A second failure forces `PARTIAL` or `BLOCKED`. Return only the latest report.
