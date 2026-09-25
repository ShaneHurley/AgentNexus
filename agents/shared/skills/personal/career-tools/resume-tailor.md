---
name: resume-tailor
description: Create or revise truthful base resumes, role-targeted resumes, project sections, accomplishment bullets, short biographies, and application answers from approved career facts. Use when resume language or application material needs tailoring without invented claims.
---

# Resume Tailor

Load approved profile and accomplishment facts only. Select relevant evidence, draft concise language, check unsupported claims and confidentiality, compare with the canonical resume, and return a versioned draft plus change summary. Improve framing, not facts.

## Token and orchestration bounds

- **At most two LLM passes** for one tailoring request: (1) draft + claim/confidentiality review in this skill; (2) optional **one** style pass via `artifact-style-enforcer` with profile **`agent-core/profiles/style/resume.yaml` only**. Do not chain additional rewriter roles, browser condensers, or extra style profiles.
- **MUST NOT** invoke Daily Coder **`documenter`**, IDE **`documenter`**, **`daily-coder`**, **`documentation-curator`**, or any engineering UF orchestrator for résumé or application copy. Career artifacts stay in personal skills + `personal-store` (see ADR KEEP-6).
- Use **`claim-auditor`** (career mode) inside pass 1 as needed; it does not count as a separate style pass.

## Process (within the two-pass cap)

1. Load only approved profile fields and relevant accomplishments (and target opportunity text if supplied).
2. Draft concise language; run unsupported-claim and confidentiality checks.
3. Compare against the canonical resume; return diff + versioned draft.
4. If the user asked for tone/format polish, run **one** `artifact-style-enforcer` pass with the résumé profile only; otherwise skip pass 2.
