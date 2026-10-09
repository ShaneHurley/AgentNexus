# Document Reviewer (`document-reviewer`)

**Adversarial Doc Pass** — independent, fact-bound review of Word/PDF/wiki/non-code documents. Verdict + severity-ordered findings. Does not draft and does not execute fixes.

## Why this family exists

Browser RCC splits **production** from **independent review**:

| Layer | Who | What |
|-------|-----|------|
| Self-review | Writing Studio (author) | `SELF_REVIEW` before final draft; catches author mistakes |
| Independent review | Document Reviewer (this family) | Separate chat; tries to disprove; `APPROVE` / `REVISE` / `BLOCK` |

Code has the same split: **code-crafter** self-review → **code-reviewer** independent pass. Document Reviewer is the prose counterpart.

## Thought process (operator mental model)

1. **Anchor** on packet objective, acceptance criteria, and audience — not on “making the doc prettier.”
2. **Classify** main vs variant (PDF vs policy vs academic integrity, etc.).
3. **Establish the case** — what artifact, what “good enough” claim, what evidence is actually in the chat.
4. **Fact-find** with locators and epistemic tags — only from supplied material.
5. **Walk** the document in order (structure → claims → evidence → risk → clarity → acceptance map).
6. **Disprove** — actively hunt contradictions, unsupported claims, and compliance gaps.
7. **Verdict + findings** — author applies fixes; reviewer does not replace the document.

## vs Research Desk (especially assemble-given)

| | `research-desk` / assemble-given | `document-reviewer` |
|---|----------------------------------|---------------------|
| **Job** | Pull and locate what was given | Judge quality and risk |
| **Thinks?** | Minimal — no ship verdict | Yes — adversarial |
| **Output** | Extract + UNKNOWNs | `VERDICT` + `FINDINGS` |
| **Tone** | Neutral | Hostile second opinion |

**obligation-register** extracts must/should/may **without** compliance judgment. **policy-compliance** (here) compares the artifact to rules and emits a verdict.

If the user only wants “what does this PDF say?” → assemble-given. If they want “is this PDF good enough to send?” → document-reviewer.

## vs Writing Studio

| | `writing-studio` | `document-reviewer` |
|---|------------------|---------------------|
| **Job** | Author draft or rewrite | Independent review |
| **Output** | Draft + mandatory `SELF_REVIEW` | Verdict + findings only |
| **Chat** | Author thread | **New chat** after draft |

Writing Studio may set `READY_TO_SEND: yes` after self-review. Document Reviewer is allowed — and expected — to disagree.

## Variant catalog

| Variant | Why it exists |
|---------|----------------|
| `docx-adversarial` | Default long-form: structure, claims, evidence, clarity (main paste equals this walk). |
| `pdf-adversarial` | PDF/report: truncation, OCR, stale dates, unsupported figures. |
| `policy-compliance` | Obligations vs stated rules; missing must/should; responsible party gaps. |
| `claims-evidence` | Material claims mapped to in-doc citation or UNKNOWN. |
| `audience-clarity` | Jargon, ambiguity, missing ask/next step for intended reader. |
| `spec-completeness` | Requirements gaps, undefined terms, untestable shalls. |
| `academic-integrity` | Citation honesty, disclosure norms; **no** fabricated plagiarism certainty. |

## Files in this folder

| File | Purpose |
|------|---------|
| `AGENT_MESSAGE.md` | Default paste (docx-adversarial procedure) |
| `HOW_TO.md` | When/how to paste, variant picker, chains |
| `TECH.md` | Spec mirror for maintainers |
| `variants/<slug>/` | Specialized pastes |
| `examples/` | Sample packets and output skeleton |

Shared RCC profile slot: `agents/shared/browser/profiles/document-reviewer.profile.md`.
