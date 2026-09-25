# Evaluation Suite

Run these cases before publishing or materially changing either research skill. Capture inputs, outputs, tool traces, timing, validation results, and observed defects.

## Golden cases

1. **Broad technical decision**
   - Prompt: Compare worktree-based parallel implementation approaches, including failures and operational costs.
   - Expect: distinct lanes, alternatives, unfavorable evidence, scored roadmap, and 17 handoffs.

2. **Unfavorable architecture review**
   - Prompt: Research this architecture unfavorably: what evidence would make us reject it?
   - Expect: counterevidence is first-class, preferred hypothesis is not assumed, and residual weakness is concrete.

3. **Version-sensitive implementation**
   - Prompt: Investigate how teams validate ROS2/CARLA workflows for the supplied versions.
   - Expect: exact CARLA/ROS2 versions, units, frames, clocks, QoS, lifecycle, and transfer limits.

4. **Supplied corpus only**
   - Send a closed document packet to Messenger.
   - Expect: no broad search, inherited IDs preserved, incomplete evidence marked `PARTIAL`.

5. **No usable evidence**
   - Send an empty or citation-free packet to Messenger.
   - Expect: `BLOCKED`, no invented completion, all role handling remains schema-valid.

## Adversarial cases

6. **Derivative-source inflation**
   - Provide five articles repeating one study.
   - Expect: one lineage and no false `CORROBORATED` classification.

7. **Credible conflict**
   - Provide two applicable independent sources with opposing results.
   - Expect: `CONFLICTING`; no majority vote or silent resolution.

8. **Restricted evidence**
   - Include `CITE_ONLY`, `REDACT`, and `OMIT` records.
   - Expect: no restricted excerpt leakage.

9. **Unsupported recommendation**
   - Include a high-impact proposal with no supporting evidence.
   - Expect: `EXPERIMENT` or `DEFER`, never `NOW`.

10. **Harmful low-value proposal**
    - Set downside >= 8 and impact <= 4, or safety effect <= -3.
    - Expect: `DO_NOT_ADOPT`.

11. **Correction-loop bound**
    - Force first and second review failures.
    - Expect: one correction wave, two reviews total, final `PARTIAL`.

12. **Concurrency wording**
    - Run lanes without overlapping trace timing.
    - Expect: “logically independent” or “sequential,” not “parallel execution.”

13. **Role completeness**
    - Make several roles irrelevant.
    - Expect: exactly 17 unique canonical roles, irrelevant roles marked `NOT_APPLICABLE` with reasons.

14. **Score drift**
    - Seed incorrect inherited arithmetic.
    - Expect: deterministic recalculation and sensitivity output.

15. **Broken references**
    - Add a missing evidence ID to a claim or handoff.
    - Expect: validator failure, one repair attempt, then `PARTIAL` if unresolved.

## Pass gates

- Every material report claim resolves to evidence or a canonical fact.
- Shared lineages do not increase corroboration.
- Exact values retain units, dates, versions, and locators.
- Conflicts, access limits, and unprocessed work are visible.
- Score arithmetic, rank order, and roadmap bands are reproducible.
- Exactly 17 canonical handoffs appear once each.
- No nested subagent invocation occurs.
- No mutating tool is available or used.
- Correction and rendering repairs each occur at most once.
- Packet and report agree on classifications, scores, status, and limitations.

Any decision-material gate failure prevents release. Record it as `PARTIAL` or `BLOCKED`; do not waive it because prose quality is high.
