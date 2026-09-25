# How to use — Document Reviewer

**Display name:** Document Reviewer — Adversarial Doc Pass  
**Folder:** `document-reviewer`  
**Packet field:** `browser_family: document-reviewer` (+ optional `browser_variant`)

## When to use

Use this family when you need a **hostile second opinion** on a **non-code** deliverable: Word, PDF, wiki paste, Notion export, policies, specs, essays, slide notes, or marketing copy in document form.

Typical triggers:

- After **Writing Studio** produced a draft and `SELF_REVIEW` (send-critical email, spec, homework, ads copy).
- On an **existing** document already open in a tab or attachment — no drafting step required.
- Mission Control phase **`phase-doc-review`** when the deliverable is prose, not code.

## When not to use

| Need | Use instead |
|------|-------------|
| Pull facts from PDFs with **no quality judgment** | `research-desk` / **`assemble-given`** (or field/table/obligation extracts) |
| **Draft or rewrite** the document | `writing-studio` (mandatory author `SELF_REVIEW` before “ready”) |
| Review a **unified code diff** | `code-reviewer` |
| Build a neutral obligation list **without** compliance verdict | `research-desk` / **`obligation-register`** (extract only) |

**Extract ≠ review:** assemble-given refuses to invent and refuses to “improve.” Document Reviewer **judges** quality and risk. Merging those roles in one paste causes mode bleed.

**Author ≠ independent review:** Writing Studio’s `SELF_REVIEW` catches the author’s mistakes before handoff. Document Reviewer runs in a **new chat** and tries to **disprove** the work. Both layers matter for send-critical docs.

## Paste order

1. Open a **new chat** (do not continue the Writing Studio thread as reviewer).
2. Paste **`AGENT_MESSAGE.md`** from this folder **or** `variants/<slug>/AGENT_MESSAGE.md`.
3. Paste a filled task packet (`examples/task-packet.main.yaml` as template).
4. Attach the document, paste excerpts, or point at open tabs. Evidence is **untrusted** — not instructions.
5. If chaining from Writing Studio, set `prior_artifact_ref` and paste the prior `SELF_REVIEW` block + draft (or attach export).

## Variant picker

| Situation | `browser_variant` | Paste path |
|-----------|-------------------|------------|
| Default long-form Word/wiki: structure, claims, evidence, clarity | *(omit)* or `docx-adversarial` | main or `variants/docx-adversarial/` |
| PDF/report: OCR gaps, stale dates, figures without backing | `pdf-adversarial` | `variants/pdf-adversarial/` |
| Policy/procedure vs stated rules; missing must/should | `policy-compliance` | `variants/policy-compliance/` |
| Every material claim → citation in doc or UNKNOWN | `claims-evidence` | `variants/claims-evidence/` |
| Jargon, ambiguity, missing ask/next step for reader | `audience-clarity` | `variants/audience-clarity/` |
| Spec/requirements: gaps, undefined terms, untestable shalls | `spec-completeness` | `variants/spec-completeness/` |
| Essay/homework: citation honesty; no false plagiarism certainty | `academic-integrity` | `variants/academic-integrity/` |

## Independent pass rules

- Run **after** the author family (usually Writing Studio) in a **separate chat**.
- Reviewer **must not** rewrite the full artifact as the author.
- Output is **VERDICT + FINDINGS**, not a neutral fact inventory.
- **Adversarial review does not execute fixes** — list `REQUIRED_FIX` for the author or a follow-up Writing Studio pass.
- Optional `EXAMPLE_FIX` snippets (≤2 sentences) must be labeled; they are not the deliverable.

## Recommended chain (send-critical)

```text
[optional] research-desk / assemble-given  →  facts only, no verdict
writing-studio                             →  draft + SELF_REVIEW
NEW CHAT document-reviewer                 →  APPROVE | REVISE | BLOCK | INSUFFICIENT_EVIDENCE
```

## Verdict meanings

| Verdict | Meaning |
|---------|---------|
| `APPROVE` | No blocker/major findings; fit for stated use |
| `REVISE` | Fixable issues; ship after listed fixes |
| `BLOCK` | Material harm, compliance, or integrity risk |
| `INSUFFICIENT_EVIDENCE` | Critical sections missing/unreadable |

## Locator conventions (cite what you see)

- **Word / Google Doc:** file name, heading path, paragraph/snippet quote.
- **PDF:** file, page, figure/table id, quoted line (note OCR uncertainty).
- **Wiki:** page title, section, revision/date if shown.

## IDE / AUTHORITY

Browser Document Reviewer is **browser-first** — there is no default IDE agent counterpart. Do not assume PolicyGateway or ide-bridge. For code, use IDE `/code-reviewer` when repo-native review is available.
