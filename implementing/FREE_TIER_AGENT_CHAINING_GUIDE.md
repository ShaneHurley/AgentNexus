# Zero-Cost Free-Tier Agent Chaining Guide

**Run an enterprise-grade research-to-code pipeline at $0.00 using free tiers of Kimi, DeepSeek R1, Google Gemini / Antigravity, Bolt.new, Windsurf, Zhipu GLM, and Claude.**

---

## The Core Principle

No single free model can do everything — but you can **daisy-chain** them by treating each model's output as the input for the next. The key is:

1. **Slice context deliberately** — pass only what the next model needs, not your whole history
2. **Match model strengths to phases** — massive context → Kimi/Gemini, reasoning → DeepSeek R1, coding → Windsurf/Cursor free, prototyping → Bolt.new
3. **Use browser agents as context-free workers** — the quick paste packs in `implementing/browser_agents/quick_paste_packs/` are stateless; reset the chat between phases

---

## Free Tier Quick Reference

| Platform | Model | Context | Free Limit | Best For |
|---|---|---|---|---|
| [Kimi (kimi.ai)](https://kimi.ai) | Kimi K2 / 2M | 2M tokens | Generous daily | Massive doc ingestion, full-repo scan |
| [Google Gemini](https://gemini.google.com) | Gemini 2.0 Flash | 1M tokens | 15 RPM / 1500 RPD | Long context, research, summaries |
| [Google Antigravity](https://labs.google.com) | Gemini 2.0 Flash | 1M tokens | Varies | IDE + agent view, planning |
| [DeepSeek](https://chat.deepseek.com) | R1 (reasoning) | 64K | Generous web | Chain-of-thought review, adversarial audit |
| [Claude.ai](https://claude.ai) | Claude Sonnet (free) | 200K | ~10 msgs/day | Writing, planning, code review |
| [Bolt.new](https://bolt.new) | GPT-4o / Sonnet | N/A (web IDE) | ~10 prompts/day | Full-stack UI prototyping, instant sandbox |
| [Windsurf](https://codeium.com/windsurf) | Cascade (Sonnet) | 64K | Free tier credits | Contained code implementation in local IDE |
| [Cursor](https://cursor.com) | GPT-4o / Sonnet | 64K | Hobby tier free | Code implementation, cursor tab |
| [Zhipu GLM](https://chatglm.cn) | GLM-4 Free | 128K | Daily quota | Structured extraction, bilingual docs |
| [Aider](https://aider.chat) | Gemini Flash API | 1M | $0 (API) | Terminal pair programming at near-$0 |

---

## The 8-Phase Zero-Dollar Pipeline

```
Phase 1: RECON          → Kimi / Gemini (massive context ingestion)
Phase 2: PLANNING       → Antigravity IDE / Claude web (planning + architecture)
Phase 3: ADVERSARIAL    → DeepSeek R1 (reasoning-based plan review)
Phase 4: PROTOTYPING    → Bolt.new (full-stack sandbox)
Phase 5: IMPLEMENTATION → Windsurf / Cursor free tier (contained coding)
Phase 6: CODE REVIEW    → DeepSeek R1 + Claude web (adversarial review)
Phase 7: TESTING        → Local Python / ide-bridge ($0 compute)
Phase 8: DOCS & CLOSE   → GLM-4 / Kimi web (bilingual docs, structured cleanup)
```

---

## Phase 1: Massive Recon & Document Ingestion

**Goal**: Ingest large codebases, PDFs, or research corpora and extract a compressed evidence packet.

**Tool**: Kimi.ai (2M context) or Google Gemini (1M context via [AI Studio](https://aistudio.google.com))

**How to**:
1. Open Kimi.ai or Gemini in a browser tab
2. Paste the `research-desk/assemble-given` quick paste pack from `implementing/browser_agents/quick_paste_packs/research-desk.md`
3. Paste your documents, files, or URLs
4. Fill `browser_variant: "assemble-given"` in the TASK_PACKET
5. Copy the structured output to `phase1_findings.md`

**Context Slice to pass forward**:
```markdown
## Phase 1 Output (pass to Phase 2)
- KEY_FINDINGS: [bullet list, under 500 words]
- SOURCE_REFS: [file names or URLs, no content]
- UNKNOWNS: [what we couldn't determine]
- NEXT_QUESTION: [the planning question Phase 2 should answer]
```

**Rate limit fallback**: If Kimi rate-limits, switch to Gemini Flash via AI Studio (15 RPM free). If both hit limits, split documents across 2-3 separate Kimi sessions with overlapping summaries.

---

## Phase 2: Planning & Architecture

**Goal**: Produce a structured implementation plan from Phase 1 findings.

**Tool**: Google Antigravity IDE, or Claude.ai free tier (web)

**How to (Antigravity)**:
1. Open a new Antigravity chat
2. Paste your AGENT SYSTEM PROMPT from `implementing/antigravity/rules.md`
3. Paste Phase 1 output (500 words max)
4. Ask: *"Produce an implementation plan following the plan-prep protocol"*
5. Use the Antigravity Agent View to review sub-steps

**How to (Claude.ai)**:
1. Open Claude.ai (free account)
2. Paste the `plan-prep` prompt from `implementing/claude_code/README.md`
3. Paste Phase 1 findings
4. Ask for a structured plan

**Context Slice to pass forward**:
```markdown
## Phase 2 Output (pass to Phase 3)
- OBJECTIVE: [one sentence]
- KEY_STEPS: [numbered, under 10 items]
- DEPENDENCIES: [critical blockers]
- RISK_FLAGS: [top 3 risks]
- IRREVERSIBLE_STEPS: [explicitly flagged]
```

---

## Phase 3: Adversarial Plan Review

**Goal**: Find flaws, missing assumptions, and risks in the Phase 2 plan using deep chain-of-thought reasoning.

**Tool**: [DeepSeek R1](https://chat.deepseek.com) (free, reasoning mode)

**How to**:
1. Open DeepSeek chat, confirm you're using R1 (reasoning icon visible)
2. Paste the adversarial review harness from `implementing/deepseek/r1_adversarial_reviewer.md`
3. Paste Phase 2 output (the plan)
4. Ask: *"Apply the adversarial review protocol. Try to disprove this plan."*
5. DeepSeek R1 will show its reasoning chain — read it for hidden assumptions

**Key prompt to include**:
```
For each step in the plan, answer:
1. What assumption does this step rely on that could be false?
2. What is the worst realistic failure mode?
3. Is this step reversible? If not, what's the gate?
4. Rate confidence: HIGH / MEDIUM / LOW / UNKNOWN
```

**Context Slice to pass forward**:
```markdown
## Phase 3 Review (pass to Phase 5)
- APPROVED_STEPS: [steps that passed adversarial review]
- REVISED_STEPS: [steps with required changes]
- BLOCKED_STEPS: [steps that need human decision]
- ADDED_RISKS: [risks DeepSeek R1 found that Phase 2 missed]
```

---

## Phase 4: Rapid Full-Stack Prototyping (Optional)

**Goal**: Build and test a working UI or full-stack MVP in a sandboxed environment — zero local setup.

**Tool**: [Bolt.new](https://bolt.new) (free sandbox)

**How to**:
1. Open bolt.new
2. Paste the Bolt prompt from `implementing/bolt/bolt_prompt_templates.md`
3. Fill in your stack (React, Next.js, Svelte, etc.) and feature list
4. Bolt builds in a sandboxed WebContainer — test in the preview pane
5. When satisfied, export to GitHub or download the ZIP

**Token conservation**:
- Be precise in your first prompt — Bolt's free tier is ~10 prompts/day
- One focused prompt beats 5 iterative small ones
- Describe UI + data model + API routes in a single structured prompt

**Context Slice to pass forward**:
```markdown
## Phase 4 Prototype (pass to Phase 5)
- COMPONENTS_BUILT: [list]
- API_ROUTES_DEFINED: [list]
- WHAT_WORKS: [confirmed in sandbox]
- WHAT_NEEDS_LOCAL_TESTING: [list]
- EXPORT_LOCATION: [GitHub URL or local path]
```

---

## Phase 5: Contained Code Implementation

**Goal**: Implement the approved plan steps in your local repository.

**Tool**: Windsurf (free Cascade credits) or Cursor (Hobby tier) — or Aider with Gemini Flash API

**Windsurf how to**:
1. Open Windsurf in your project directory
2. Paste the `.windsurfrules` from `implementing/windsurf/windsurfrules.md`
3. Start with: *"I have an approved plan. Implement Step 1: [paste step from Phase 3 approved list]"*
4. Each step = one Cascade conversation — don't chain all steps in one session (blows context)

**Aider (true $0) how to**:
```bash
# Get free Gemini API key from AI Studio (no credit card)
export GEMINI_API_KEY=your_key_here
aider --model gemini/gemini-2.0-flash-exp --architect \
  --editor-model gemini/gemini-1.5-flash-latest \
  --map-tokens 2048
```

**Context conservation rules**:
- One implementation step per Windsurf/Cursor session
- Use `/compact` or start a new chat after each step
- Paste only the relevant file sections, not whole files

---

## Phase 6: Adversarial Code Review

**Goal**: Find bugs, security issues, and regressions before testing.

**Tool**: DeepSeek R1 (reasoning) for logic/security + Claude.ai free for style/docs

**How to**:
1. Run `git diff HEAD~1..HEAD > review.diff` to get the diff
2. Open DeepSeek R1: paste `code-reviewer` quick pack + the diff
3. DeepSeek R1's reasoning shows the attack chain — note CRITICAL findings
4. Open Claude.ai (new chat): paste same quick pack + diff for a second opinion on HIGH/MEDIUM

**Context Slice to pass forward**:
```markdown
## Phase 6 Review (pass to Phase 7)
- CRITICAL_FINDINGS: [must fix before test]
- HIGH_FINDINGS: [fix before ship]
- MEDIUM_FINDINGS: [fix in follow-up]
- TEST_GAPS: [what the tests should cover]
```

---

## Phase 7: Testing ($0 — Local Compute)

**Goal**: Execute tests on your local machine — zero API cost.

```bash
# Run from repo root
PYTHONPATH=agents/shared/ai_agents_repo/src python3 agents/daily-task/driver.py --list
python -m pytest agents/ide/tests/ -x -q
```

Fix any failures using Windsurf/Aider with the CRITICAL findings list from Phase 6.

---

## Phase 8: Documentation & Close

**Goal**: Generate docs, release notes, and structured summaries.

**Tool**: Zhipu GLM-4 (free daily quota) or Kimi (2M context for large codebase docs)

**How to**:
1. Open [chatglm.cn](https://chatglm.cn)
2. Paste `implementing/glm/structured_data_extractor_prompt.md`
3. Paste the code/commit summary
4. GLM-4 outputs structured markdown docs, typed fact tables with provenance

---

## Context Slicing Protocol

**The cardinal rule**: Never paste more than **800 words** as context to the next phase. More context = higher chance of hitting the free tier's message limit.

Format your handoff packets as:
```markdown
---
FROM_PHASE: <N>
TO_PHASE: <N+1>
MISSION_ID: <your-project-slug>
DATE: <today>
---
[600-800 words of essential context only]
---
NEXT_TASK: <one sentence — what Phase N+1 should do first>
```

---

## Rate Limit & Session Handoff Cheat Sheet

| When | Do This |
|---|---|
| Kimi rate-limited | Switch to Gemini Flash (AI Studio) for Phase 1 |
| DeepSeek R1 rate-limited | Wait 30 min, or use Claude.ai free for Phase 3 (less deep reasoning but good) |
| Claude.ai daily limit hit | Use Gemini 2.0 Flash for Phase 2 planning |
| Bolt.new prompts exhausted | Use a local Vite + React scaffold manually, or resume tomorrow |
| Windsurf credits gone | Switch to Aider + Gemini Flash API (true $0) |
| All rate-limited | Queue tasks in `HEARTBEAT.md`, resume the next morning |

---

## Token Minimization Tactics

1. **Summarize, don't paste** — summarize Phase N output in 200 words before passing to Phase N+1
2. **One question per session** — each free-tier session should answer one bounded question
3. **Pre-format for the model** — Kimi handles markdown tables well; DeepSeek R1 does better with numbered lists
4. **Use the quick paste packs** — they're already tuned to minimize unnecessary context
5. **New chat = new budget** — always start a new chat session between phases; never continue in the same thread

---

## Example: Full Research-to-Code Run at $0

```
Day 1 (30 min)
  Phase 1: Kimi.ai — ingest 3 PDFs + codebase scan → findings packet
  Phase 2: Antigravity — produce 5-step implementation plan

Day 2 (20 min)
  Phase 3: DeepSeek R1 — adversarial plan review → 2 plan revisions
  Phase 5 Step 1: Windsurf free → implement Step 1

Day 3 (20 min)
  Phase 5 Steps 2-3: Aider + Gemini Flash API → implement Steps 2-3 ($0)
  Phase 6: DeepSeek R1 → code review → 1 CRITICAL fix

Day 4 (10 min)
  Phase 7: Local pytest → all passing
  Phase 8: GLM-4 → docs generated

TOTAL COST: $0.00
```

---

## Model Substitution Matrix

If your first choice is unavailable, use these fallbacks:

| Primary | Fallback 1 | Fallback 2 |
|---|---|---|
| Kimi 2M | Gemini Flash 1M (AI Studio) | Split across 3 × Claude free sessions |
| DeepSeek R1 | Claude.ai Sonnet free | Gemini 2.0 Flash with "think step by step" prompt |
| Antigravity IDE | Cursor free Hobby | Windsurf free |
| Bolt.new | StackBlitz.com (free) | Replit (free tier) |
| Windsurf free | Cursor Hobby free | Aider + Gemini Flash API ($0) |
| GLM-4 | Kimi web | Gemini Flash (AI Studio) |

---

## What You Need (One-Time Setup)

- [ ] Account at kimi.ai (free)
- [ ] Google account for Gemini / AI Studio (free)
- [ ] DeepSeek account at chat.deepseek.com (free)
- [ ] Claude.ai account (free)
- [ ] Bolt.new account (free)
- [ ] Windsurf installed (free tier)
- [ ] Zhipu account at chatglm.cn (free)
- [ ] Python 3.8+ and aider-chat installed locally (free)
- [ ] Gemini API key from AI Studio (free, no credit card)

**Total setup time**: ~20 minutes  
**Ongoing cost**: $0.00
