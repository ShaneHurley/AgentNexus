# Human Report Template

Return only the latest validated report. Do not dump the machine packet unless the user requests it.

## 1. Status and decision

- Status: `COMPLETE`, `PARTIAL`, or `BLOCKED`
- Topic, decision, audience, scope, freshness or version boundary
- One-paragraph answer calibrated to the evidence

## 2. Executive findings

List the decision-material findings. Show each claim classification and fact or evidence IDs. Distinguish observed facts, source reports, and inference.

## 3. Evidence map

Summarize applicable lanes, unique sources, independent lineages, processed and unprocessed counts, access limitations, and source-quality limits. Explain derivative or shared lineages that were deduplicated.

## 4. What supports the conclusion

For each major claim, provide the strongest evidence, exact locator, applicability, and limitations. Use bounded quotations only when useful and permitted.

## 5. Unfavorable and conflicting evidence

Preserve failures, counterexamples, credible minority findings, hidden cost, non-transferability, safety or security concerns, and every unresolved contradiction. State what would falsify the preferred conclusion.

## 6. Implementation examples and alternatives

Separate production deployments, prototypes, vendor demonstrations, and analogies. State transfer assumptions and where each analogy breaks.

## 7. Scored roadmap

For each recommendation, report:

- roadmap band, adjusted priority, confidence, and sensitivity result;
- rationale and linked evidence or fact IDs;
- prerequisites, dependencies, affected roles and tools;
- effects on speed, accuracy, safety, maintainability, cost, workflow, and users;
- smallest safe experiment, metric, threshold, stop condition, and rollback.

Keep `DO_NOT_ADOPT`, `EXPERIMENT`, and `DEFER` items visible when decision-relevant.

## 8. Seventeen-role handoffs

Render all roles once in canonical order. Clearly mark `NOT_APPLICABLE` and its reason. Do not imply that any handoff has been executed.

## 9. Limitations and research backlog

State concrete residual weakness from the unfavorable review, inaccessible or unprocessed sources and questions, consequences, assumptions, disclosure handling, and what new evidence could change the decision.

## 10. Sources

List cited sources with IDs, lineage IDs, titles, authors or publishers, dates or versions, stable links, and locators. Do not list uncited padding.

## Quality requirements

- Every material factual statement resolves to evidence or a canonical fact.
- Exact numbers include units, dates, versions, and locators.
- Scores and classifications match the machine packet.
- Conflicts and limitations remain visible.
- `PARTIAL` or `BLOCKED` is prominent and explained.
- Never claim universal completeness or runtime validation without evidence.
