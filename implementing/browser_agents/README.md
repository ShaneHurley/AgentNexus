# AgentNexus Browser Agents Hub

Central distribution point for all **10 browser agent families** and **96 variants** from the AgentNexus v3 pack. Each family has a harness folder, a profile, and a ready-to-paste quick pack.

**Source**: `agents/shared/browser/` (do not edit source files here — this is a distribution copy)

---

## Quick Navigation

| Family | Variants | Primary Use | Quick Pack |
|---|---|---|---|
| [📚 Research Desk](#research-desk) | 11 | Evidence-backed research tiers | [→ quick_paste_packs/research-desk.md](./quick_paste_packs/research-desk.md) |
| [✍️ Writing Studio](#writing-studio) | 16 | Typed drafts with self-review | [→ quick_paste_packs/writing-studio.md](./quick_paste_packs/writing-studio.md) |
| [🎓 Learning Coach](#learning-coach) | 10 | Learning, study, quizzes | [→ quick_paste_packs/learning-coach.md](./quick_paste_packs/learning-coach.md) |
| [🧭 Plans & Places](#plans-and-places) | 9 | Travel, events, logistics | [→ quick_paste_packs/plans-and-places.md](./quick_paste_packs/plans-and-places.md) |
| [🍳 Kitchen Companion](#kitchen-cooking) | 8 | Recipes, meal plans, diet | [→ quick_paste_packs/kitchen-cooking.md](./quick_paste_packs/kitchen-cooking.md) |
| [🎯 Mission Control](#mission-control) | 9 | Phase-by-phase mission orchestration | [→ quick_paste_packs/mission-control.md](./quick_paste_packs/mission-control.md) |
| [⚙️ Code Crafter](#code-crafter) | 6 | Bounded patch drafts with self-review | [→ quick_paste_packs/code-crafter.md](./quick_paste_packs/code-crafter.md) |
| [🔎 Code Reviewer](#code-reviewer) | 5 | Adversarial code review — findings only | [→ quick_paste_packs/code-reviewer.md](./quick_paste_packs/code-reviewer.md) |
| [📄 Document Reviewer](#document-reviewer) | 7 | Document/plan adversarial review | [→ quick_paste_packs/document-reviewer.md](./quick_paste_packs/document-reviewer.md) |
| [🧠 Thinking Lab](#thinking-lab) | 4 | Stress tests, pre-mortem, risk cascade | [→ quick_paste_packs/thinking-lab.md](./quick_paste_packs/thinking-lab.md) |

---

## How to Use

### Method 1: Quick Paste Pack (fastest)
1. Open `quick_paste_packs/<family>.md`
2. Copy the entire file
3. Paste into any browser chat (ChatGPT, Claude.ai, Gemini, Kimi, DeepSeek)
4. Fill in the TASK_PACKET yaml fields
5. Send — the agent begins immediately

### Method 2: Harness + Task Packet (full control)
1. Open `harness/CORE_AGENT_CONTRACT.md` — the shared contract all families obey
2. Open `families/<family>/` — choose the family and variant
3. In your browser chat, paste: contract → variant profile → filled task packet → evidence

### Method 3: From IDE (Cline/Roo/Claude Code)
- Produce a filled TASK_PACKET from your IDE tool
- Copy to a new browser window with the family's quick pack prepended

---

## Harness Files

Core contracts and templates in `harness/`:

| File | Purpose |
|---|---|
| `CORE_AGENT_CONTRACT.md` | Master contract — all families obey this |
| `AUTHORITY.md` | Family ↔ IDE counterpart mapping, genre labels |
| `TASK_PACKET_TEMPLATE.md` | Filled task packet YAML template |
| `ROLE_SELECTION.md` | How to choose the right family and variant |
| `VALIDATION.md` | Acceptance criteria and evidence status rules |
| `PLATFORM_NOTES.md` | Per-host quirks (ChatGPT, Claude, Gemini, Kimi, DeepSeek) |
| `SOURCES.md` | Source ID and locator conventions |
| `CALL_TIMELINE.md` | Multi-session handoff and chaining patterns |
| `SECURITY_AND_RESTRICTED_ENVIRONMENTS.md` | Security rules for restricted/enterprise hosts |

---

## Family Summaries

### Research Desk
**IDE counterpart**: `/deep-research`  
**Use when**: You need multi-source evidence synthesis, document extraction, contradiction audits, or academic-style literature review.

Variants: `assemble-given`, `compare-options`, `contradiction-audit`, `deep`, `field-extract`, `gap-finder`, `literature-map`, `obligation-register`, `phd`, `quick`, `source-synthesis`

### Writing Studio
**IDE counterpart**: personal skills / style profiles  
**Use when**: You need typed, self-reviewed written output — emails, docs, GitHub PRs, resumes, study guides, marketing copy.

Variants: `ads-marketing`, `cover-letter`, `email`, `form-explain`, `github-issue`, `github-pr`, `github-readme`, `homework`, `meeting-notes`, `personal-project`, `resume`, `self-review-only`, `slack-update`, `study-guide`, `tech-doc`, `tone-match`

### Learning Coach
**IDE counterpart**: everyday runtime Compass/Atlas  
**Use when**: Teaching a topic, building study plans, creating flashcards, Socratic dialogue, rubric review, exam prep.

Variants: `exam-prep`, `flashcards`, `map-topic`, `mental-model`, `quiz`, `rubric-review`, `socratic`, `source-synthesis`, `study-plan`, `teach`

### Plans & Places
**IDE counterpart**: everyday runtime Compass  
**Use when**: Planning trips, events, errands, group logistics, packing, budget optimization.

Variants: `budget-optimizer`, `dietary-cross-check`, `discover-events`, `errand-route`, `event-run-of-show`, `group-constraints`, `packing-list`, `trip-itinerary`, `weather-contingency`

### Kitchen Companion
**IDE counterpart**: everyday runtime Compass  
**Use when**: Recipes, meal planning, dietary scanning, batch prep, leftover rescue, equipment-limited cooking.

Variants: `allergy-diet-scan`, `batch-prep`, `brainstorm`, `equipment-limited`, `leftover-rescue`, `meal-plan`, `recipe`, `vibe-cook`

### Mission Control
**IDE counterpart**: `/use-master`  
**Use when**: Coordinating multi-phase missions across browser sessions. Browser = paste phases only; full DAG orchestration requires IDE `/use-master`.

Variants: `phase-plan`, `phase-research`, `phase-implement`, `phase-review`, `phase-test`, `phase-document`, `phase-deploy`, `phase-close`, `phase-retrospective`

### Code Crafter
**IDE counterpart**: `/daily-coder` + ide-bridge  
**Use when**: Drafting bounded code patches in a browser chat. Produces PROPOSED diffs with self-review — audited writes require ide-bridge.

Variants: `patch-draft`, `diff-adversarial`, `test-gen`, `docstring-gen`, `refactor`, `scaffold`

### Code Reviewer
**IDE counterpart**: `/code-reviewer`  
**Use when**: Adversarial review of a diff or file — findings only, no rewrites. Always run in a fresh chat, separate from the author's session.

Variants: `diff-review`, `security-audit`, `performance-review`, `style-review`, `full-review`

### Document Reviewer
**IDE counterpart**: *(browser-first, no IDE equivalent)*  
**Use when**: Reviewing plans, specs, PRDs, policies, academic papers for accuracy, completeness, and risk. Word/PDF/wiki in any browser tab.

Variants: `accuracy-check`, `completeness-check`, `contradiction-audit`, `policy-review`, `spec-review`, `plan-review`, `plain-language`

### Thinking Lab
**IDE counterpart**: *(none)*  
**Use when**: Stress-testing plans, pre-mortem analysis, decision reversibility checks, cascade risk mapping.

Variants: `idea-stress-test`, `pre-mortem`, `decision-reversibility`, `cascade-risk`

---

## Legacy `browser_idea` → v3 Mapping

| Old `browser_idea` | v3 family/variant |
|---|---|
| `daily-coder` | `code-crafter/patch-draft` |
| `doc-reader` | `research-desk/assemble-given` |
| `deep-research` | `research-desk/deep` |
| `contextual-concierge` | `plans-and-places/trip-itinerary` etc. |
| `experience-architect` | `plans-and-places/event-run-of-show` etc. |
| `sous-chef-pantry-master` | `kitchen-cooking/recipe` etc. |
| `hyper-specific-learner` | `learning-coach/teach` etc. |
| `voice-tone-chameleon` | `writing-studio/tone-match` |
| `friction-generator` | `thinking-lab/idea-stress-test` |
| `asymmetric-risk-auditor` | `thinking-lab/cascade-risk` |

---

## Source Files

All agent definitions live in:
- `agents/shared/browser/` — profiles, shared contracts, scripts
- `agents/daily-task/browser/` — everyday lifestyle families
- `agents/coding/browser/` — code-crafter, code-reviewer
- `agents/research/browser/` — research-desk, document-reviewer

The quick paste packs in this hub are self-contained — they do not require access to the source tree.
