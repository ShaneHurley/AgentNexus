# Output skeleton — Document Reviewer (main / docx-adversarial)

Paste this shape is illustrative; the model fills from evidence.

```text
STATUS: COMPLETE | PARTIAL | BLOCKED
MODE: DOC_REVIEW_ADVERSARIAL
TASK_ANCHOR: <one sentence from packet>

ROLE_RESULT:
  CASE:
    ARTIFACT: <format, title, version/date>
    QUALITY_CLAIM: <from packet + author SELF_REVIEW if any>
    ACCEPTANCE: <numbered criteria>
    EVIDENCE_IN_SCOPE: <files/tabs>
    EVIDENCE_GAPS: <missing annexes, unreadable pages, or NONE>

  FACT_FIND:
    - LOCATOR: Product_Brief_v3.docx § "Summary" ¶2 | STATEMENT: ... | TAG: VERIFIED
    - LOCATOR: ... | STATEMENT: ... | TAG: UNKNOWN

  WALK:
    METADATA_SCOPE: <notes>
    STRUCTURE: <notes>
    CLAIMS_CORRECTNESS: <notes>
    EVIDENCE_CITATIONS: <notes>
    RISK_SURFACE: <notes>
    CLARITY_ACTION: <notes>
    ACCEPTANCE_MAP:
      - criterion 1: PASS | FAIL | UNKNOWN — locator or gap
      - criterion 2: ...

  DISPROVE_ATTEMPT:
    - <attack tried and result>
    - <residual risk if APPROVE>

  SELF_REVIEW_CROSSCHECK: <match/mismatch with author SELF_REVIEW or N/A>

  VERDICT: APPROVE | REVISE | BLOCK | INSUFFICIENT_EVIDENCE

  FINDINGS:
    - F1 | SEVERITY: major | LOCATOR: ... | FACT: ... (SUPPORTED) | CONSEQUENCE: ... | REQUIRED_FIX: ...
    - F2 | ...

EVIDENCE:
  - <source id + locators + tags>

VALIDATION.PERFORMED:
  - Walk subsections a–g addressed or marked N/A with reason
  - Each acceptance criterion mapped
  - Verdict consistent with findings severities

VALIDATION.NOT_PERFORMED:
  - <e.g. annex B not supplied>

UNKNOWNS: <gaps or NONE>
LIMITATIONS: <OCR, partial export, etc.>
DECISION_NEEDED: NONE | Q-ID
STOP_REASON: Verdict issued
```

## Verdict vs findings quick reference

- **BLOCKER** finding → usually `REVISE` or `BLOCK`, not `APPROVE`
- Empty `FINDINGS` only when `APPROVE` and logged in `DISPROVE_ATTEMPT`
- `INSUFFICIENT_EVIDENCE` when acceptance cannot be evaluated from supplied scope
