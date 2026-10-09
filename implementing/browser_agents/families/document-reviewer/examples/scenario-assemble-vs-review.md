# Scenario — assemble-given vs document-reviewer

## User ask A (extract)

> “I have these three PDFs. List every deadline and owner mentioned — don’t tell me if the memo is good.”

**Family:** `research-desk`  
**Variant:** `assemble-given` (or `field-extract` if only named fields)  
**Output:** Locator-backed facts, facts vs interpretation, conflicts logged — **no** `VERDICT`.

## User ask B (review)

> “Is this memo ready to send to the board?”

**Family:** `document-reviewer`  
**Variant:** main or `pdf-adversarial` if PDF-only  
**Output:** `VERDICT` + `FINDINGS` — **not** a neutral inventory.

## User ask C (draft then review)

> “Draft a board memo from these PDFs, then sanity-check before I send.”

**Chain:**

1. Optional `assemble-given` — facts only.  
2. `writing-studio` — draft + `SELF_REVIEW` (`READY_TO_SEND`).  
3. **New chat** `document-reviewer` — independent pass; may overturn `READY_TO_SEND`.

Document Reviewer must **not** skip step 2 and rewrite the memo as “review.”
