# Glean Agent Builder Blueprint

## Build choice and authority

Build `Evidence-First Research Orchestrator` in Workflow mode. Workflow steps are ordered; the six evidence calls are logically independent lanes, not guaranteed concurrent execution. Claim concurrency only when Preview or Debug timing proves overlap.

Enable only the read-oriented search and document tools required by the bounded topic. Do not enable write, send, update, delete, approval, deployment, or execution actions. Verify least privilege in Preview and Debug.

For every reusable sub-agent, explicitly select the newest supported Sol or Opus model rather than inheriting a weaker default. Use the highest available reasoning tier: Sol for repository evidence, technical integration, scoring, and validation; Opus for framing, broad evidence synthesis, alternatives, and adversarial review. Use very-high/xhigh depth for exhaustive, high-risk, cross-domain, or contradiction-heavy work and high depth for bounded substantive work. Do not reduce model quality merely for cost or latency.

## Inputs

- Research topic — required
- Decision to support — required
- Audience — required
- Source scope — Internal, External, or Mixed
- Freshness or version boundary — optional
- Required source classes — optional
- Constraints and exclusions — optional
- Depth — Rapid, Standard, or Exhaustive
- Desired output — Decision brief, Full report, or Engineering ecosystem packet
- Provided documents or URLs — optional

## Ordered workflow

1. **Frame research** — Think step; trigger input only; produce `research_brief`.
2. **Internal Authority Scout** — reusable sub-agent; no prior outputs; brief and assigned questions only.
3. **Official and Standards Scout** — same isolation.
4. **Academic Evidence Scout** — same isolation.
5. **Practitioner and Implementation Scout** — same isolation.
6. **Failure and Unfavorable Evidence Scout** — same isolation.
7. **Alternatives and Analogy Scout** — same isolation.
8. **Evidence integration** — no prior memory; brief plus six lane results only; produce `research_draft_v1`.
9. **Adversarial review** — no prior memory; brief plus draft; produce `review_v1`.
10. **Correction branch**:
    - `REVISE`: one Targeted Gap Researcher call using only failed IDs and missing source classes; reintegrate and re-review once.
    - `INSUFFICIENT_EVIDENCE`: force `PARTIAL` and retain backlog.
    - `PASS`: forward the draft unchanged.
    - A second non-PASS verdict forces `PARTIAL`; never add a third review.
11. **Recommendation scoring** — corrected draft and final review only; produce `scored_packet`.
12. **Contract validation** — check schema, links, arithmetic, disclosure, counts, contradictions, and 17 handoffs. One repair only.
13. **Glean Research Messenger** — pass only the selected validated packet, audience, and output preference in `ECOSYSTEM` or `COMBINED` mode.
14. **Report rendering** — validated packet only; follow the output template.
15. **Human/machine consistency gate** — one rendering repair; second failure forces `PARTIAL`.
16. **Respond** — latest validated report only.

## Memory and payload discipline

Each lane has no prior outputs and references only the trigger constraints and `research_brief`. Use targeted step-output references at fan-in rather than all-memory mode. Subagents return compact ledgers with URLs, locators, quotations, lineage IDs, dates, access classes, and confidence reasons.

Budgets per lane:

- Rapid: at most 4 calls and 3–5 useful sources.
- Standard: at most 8 calls and 5–10 useful sources.
- Exhaustive: at most 12 calls and 8–15 useful sources.
- Correction wave: at most 6 calls total.

Paginate only while a page adds an independent lineage or closes a named gap. Stop after two pages add neither. A tool, payload, permission, or context ceiling forces `PARTIAL`, processed and unprocessed counts, exact remaining items, and consequences.

## Release verification

In Preview and Debug verify:

- lane isolation and lack of nested sub-agent calls;
- source links and lineage IDs survive integration;
- derivative sources do not increase corroboration;
- the correction branch runs at most once;
- Messenger receives the selected post-review packet;
- restricted evidence follows output handling;
- exactly 17 canonical handoffs are present;
- tool and context usage remain within limits;
- no true-concurrency claim appears without trace evidence.

Run the evaluation suite before publishing or materially changing the workflow. Promote gradually from personal testing to UAT or production.
