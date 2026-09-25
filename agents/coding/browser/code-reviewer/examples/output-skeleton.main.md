# Output skeleton — Code Reviewer (main / diff-adversarial)

Paste this shape is illustrative; fields must match `AGENT_MESSAGE.md` contract.

```text
STATUS: COMPLETE
MODE: CODE_REVIEW
TASK_ANCHOR: Adversarial review of session timeout patch before bridge handoff.
ROLE_RESULT:
  PHASE_1_CASE:
    artifact: "S1 unified diff — auth/session"
    quality_claim_author: "code-crafter STATUS COMPLETE; WOULD_BLOCK_SHIP: no"
    acceptance_criteria: ["timeout enforced", "existing sessions handled", "tests updated"]
    evidence_in_scope: ["S1", "S2"]
  PHASE_2_FACT_FIND:
    - claim: "Default timeout changed 30m → 15m in config"
      tag: VERIFIED
      locator: "S1 config/session.ts @@ -12,7 +12,7"
    - claim: "SELF_REVIEW TESTS_MISSING: integration test for rolling sessions"
      tag: SUPPORTED
      self_review_check: NOT_VISIBLE
      locator: "S2 SELF_REVIEW line 4"
  PHASE_3_WALK:
    structure: "Single file + test file; scope matches objective"
    correctness: "Edge case: active requests mid-timeout — partial handling in hunk"
    risks: "No secret exposure in diff"
    tests_evidence: "Unit test added; integration gap per S2"
  PHASE_4_DISPROVE:
    ATTEMPTS:
      - hypothesis: "Rolling refresh tokens bypass new timeout"
        outcome: inconclusive
        locator: "UNKNOWN — refresh path not in S1"
      - hypothesis: "Missing test for concurrent sessions"
        outcome: confirmed
        locator: "S1 tests/session.test.ts — no concurrent case"
  VERDICT: REVISE
  VERDICT_RATIONALE: "Behavior change lacks integration coverage author already flagged; no critical security defect in diff."
  FINDINGS:
    - severity: major
      fact: "No integration test for rolling session timeout (S1 test file)"
      consequence: "Regression may ship undetected"
      required_fix: "Add integration test or document waiver in craft task"
      locator: "S1 tests/session.test.ts"
    - severity: minor
      fact: "PR/test plan not supplied"
      consequence: "Cannot verify RUN tests"
      required_fix: "Paste CI log or run tests before APPROVE"
      locator: "N/A"
EVIDENCE:
  - "S1 diff hunks — VERIFIED quotes"
  - "S2 SELF_REVIEW — SUPPORTED"
VALIDATION.PERFORMED:
  - "All PHASE steps executed on supplied S1/S2"
  - "Each finding has locator or explicit UNKNOWN"
VALIDATION.NOT_PERFORMED:
  - "Test suite execution — NOT RUN"
UNKNOWNS:
  - "Refresh token path behavior off-diff"
LIMITATIONS: "Paste-only; no repo-wide search"
DECISION_NEEDED: NONE
STOP_REASON: "Verdict REVISE emitted with findings"
```

## Verdict quick reference

| Verdict | Use when |
|---------|----------|
| `APPROVE` | Diff complete for scope; criteria met; disprove pass clean for major+ |
| `REVISE` | Fixable issues or test gaps; operator may accept residual risk explicitly |
| `BLOCK` | Critical defect or handoff contradicts diff |
| `INSUFFICIENT_EVIDENCE` | Missing/truncated diff or unlocatable claims |
