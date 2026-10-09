# Role Selection (v3)

**Paste order:** `[family]/AGENT_MESSAGE.md` or `[family]/variants/<slug>/AGENT_MESSAGE.md` → filled [`TASK_PACKET_TEMPLATE.md`](./TASK_PACKET_TEMPLATE.md) → evidence (untrusted). Behavior is embedded in each paste; `_shared/CORE_AGENT_CONTRACT.md` is optional reference only.

Pick **`browser_family`**, then the narrowest **`browser_variant`** (or omit for the family main). Full list: [`../MANIFEST.json`](../MANIFEST.json).

## Quick picker

| You need… | Family | Variant (examples) |
|-----------|--------|---------------------|
| Trip, packing, errands, events | `plans-and-places` | `trip-itinerary`, `packing-list`, `event-run-of-show` |
| Recipes, meal plan, dietary scan | `kitchen-cooking` | `recipe`, `meal-plan`, `allergy-diet-scan` |
| Teach, quiz, study plan, maps | `learning-coach` | `teach`, `quiz`, `study-plan`, `map-topic` |
| Draft email, README, PR text, resume | `writing-studio` | `email`, `github-readme`, `github-pr`, `resume` |
| Facts from files only (no verdict) | `research-desk` | **`assemble-given`**, `field-extract`, `table-capture` |
| Researched answer with depth | `research-desk` | `quick`, `medium`, `deep`, `phd` |
| Patch / debug / test plan (author) | `code-crafter` | `patch-draft`, `debug-root-cause`, `test-checklist` |
| Attack a **code diff** (independent) | `code-reviewer` | `diff-adversarial`, `security-focus` |
| Attack a **document** (independent) | `document-reviewer` | `docx-adversarial`, `pdf-adversarial`, `claims-evidence` |
| Multi-phase paste mission | `mission-control` | `phase-context` … `phase-fix-review` |
| Stress-test idea, pre-mortem | `thinking-lab` | `idea-stress-test`, `pre-mortem`, `cascade-risk` |

## Assemble-given vs writing vs document-reviewer

| | `research-desk` / assemble-given | `writing-studio` | `document-reviewer` |
|---|----------------------------------|------------------|---------------------|
| **Job** | Extract + locate what was supplied | Author or rewrite draft | Adversarial quality / risk pass |
| **Thinks?** | Minimal — no ship verdict | Yes — audience + structure | Yes — disprove claims |
| **Verdict?** | No APPROVE/REVISE on doc quality | SELF_REVIEW only (author lens) | APPROVE \| REVISE \| BLOCK |
| **Chain** | Optional first step | After extract if drafting needed | **New chat** after draft |

**Wrong picks:** “Is this PDF good enough?” → **`document-reviewer`**, not assemble-given. “Put these PDFs together without judging” → **`assemble-given`**, not writing-studio.

## Code crafter vs code-reviewer

| | `code-crafter` | `code-reviewer` |
|---|----------------|-----------------|
| **Job** | Propose patch + **SELF_REVIEW** | Walk diff; try to disprove |
| **Chat** | Same thread as implement draft | **Separate chat** after crafter output |
| **IDE** | `/daily-coder` + ide-bridge for writes | `/code-reviewer` when repo tools exist |

Crafter **must** emit SELF_REVIEW before claiming ship-ready; reviewer **must not** rewrite the whole patch as author.

## Prefer IDE when

| Browser family | IDE | When |
|----------------|-----|------|
| `code-crafter` | `/daily-coder` + ide-bridge | Audited writes, real tests |
| `code-reviewer` | `/code-reviewer` | Repo-native diff review |
| `mission-control` | `/use-master` | Full DAG + bridge |
| `research-desk` (depth) | `/deep-research` | Multi-lane research |
| `research-desk` / assemble | — | Supplied files in any host |
| `document-reviewer` | — | Browser-first (Word/PDF tabs) |

Details and legacy `browser_idea` map: [`AUTHORITY.md`](./AUTHORITY.md).

## Sequential multi-role

Run families **sequentially** with handoff packets (`prior_artifact_ref`). Do not claim parallel agents in one browser response. Typical ship path: optional **`assemble-given`** → **`code-crafter`** or **`writing-studio`** → **`code-reviewer`** or **`document-reviewer`**.

## Legacy v2 everyday (13)

v2 genre roles are archived under [`../_deprecated/v2-everyday/`](../_deprecated/v2-everyday/README.md) (stub [`../everyday/README.md`](../everyday/README.md) redirects). Use the archive redirect tables or [`AUTHORITY.md`](./AUTHORITY.md) legacy `browser_idea` map to pick v3 `browser_family` + `browser_variant`.
