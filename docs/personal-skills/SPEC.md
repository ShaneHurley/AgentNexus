# Personal Daily Capability and Career Skill Expansion Specification

## 1. Purpose

This document defines a small, evidence-gated expansion of the current AI-agent monorepo for daily computer-engineering student work and career development.

The revised design intentionally avoids creating a permanent “personal life” orchestrator, a seventh IDE orchestrator, or a large catalog of overlapping agents. It adds a bounded on-demand skill layer that reuses the current IDE orchestrators, browser everyday roles, Research Forge, Daily Coder, and existing user-owned tools such as calendars, task applications, and notes.

Career support is implemented first as a compact workflow of reusable skills. It may become a dedicated domain orchestrator only after real usage shows that persistent state, cross-skill coordination, and specialized routing provide measurable value.

This is a design and implementation plan. It does not authorize code changes, data access, external submissions, account changes, or new tool permissions.

## 2. Revised architecture decision

### 2.1 Decision

Do not add `personal-orchestrator/`, `/daily`, or `/career` in the first release.

Instead, add:

* A small resident skill catalog of approximately five to eight high-value capabilities.
* On-demand skills for study, communication, labs, deadline triage, and career work.
* A deterministic local store only for facts and artifacts that genuinely need persistence.
* Reuse mappings to existing browser everyday roles.
* Explicit promotion gates for deciding whether any skill family deserves a future orchestrator.

### 2.2 Why this is cleaner

The current repository already has six user-facing IDE orchestrators, 35 delegate roles, 13 browser everyday roles, and existing research and coding runtimes. A new general-purpose daily agent would duplicate routing and writing capabilities, increase persistent prompt cost, and make it harder for users to know which entry point to choose.

The smallest useful architecture is:

```text
User
  │
  ├── IDE engineering/research request
  │     └── existing six orchestrators
  │
  ├── repeatable personal task
  │     └── on-demand skill router
  │            ├── study-hints
  │            ├── professor-email
  │            ├── lab-preflight
  │            ├── deadline-triage
  │            └── career skill family
  │
  ├── portable browser coaching/drafting
  │     └── existing Atlas / Prism / Compass role
  │
  └── durable source of truth
        ├── calendar and task application
        ├── notes
        └── bounded career profile and accomplishment store
```

### 2.3 Superseded ideas

The following ideas from the previous version are deferred rather than deleted forever:

* A standalone `personal-orchestrator` package.
* A `/daily` IDE orchestrator.
* A `/career` IDE orchestrator.
* New `daily-planner` and `career-toolkit` browser agents.
* A full personal PolicyGateway, approval service, event ledger, and dashboard subsystem.

They may be reconsidered only after the promotion gates in Section 15 are satisfied.

## 3. Existing systems remain authoritative

| Existing system | Keep as authority for | Personal capability use |
|---|---|---|
| Research Forge | Evidence-first research and source lineage | Career-path, employer, program, certification, learning-resource, and travel research |
| Daily Coder | Coding plans, implementation, testing, PolicyGateway, CLI, and REST | Course projects and changes to this capability layer |
| Agent Dashboard | Starting and observing existing runtimes | No personal-data view in the first release |
| IDE agents | Six user-facing engineering and research entry points | Remain unchanged |
| Browser Agent Pack | Portable coaching, planning, rewriting, and drafting | Reuse existing roles on demand |
| Calendar and task application | Dates, commitments, reminders, and recurring tasks | Authoritative deadline and schedule baseline |
| Notes store | Lecture notes, project notes, and user-authored knowledge | Input to study and condensation skills |

The new skills must not reimplement full Research Forge waves, Daily Coder phases, IDE bridge behavior, calendar scheduling, or browser-role functionality.

## 4. Practical capability stack

### 4.1 Layer 0 - Durable user-owned systems

These remain the source of truth:

* Calendar for class, work, travel, interview, and appointment times.
* Task application for deadlines and actionable commitments.
* Notes for lecture, project, and meeting material.
* Versioned resume and career artifacts for professional history.

An agent may propose changes, but it must not silently replace these systems with chat memory.

### 4.2 Layer 1 - One short always-on rule

Use one short personal preference rule containing only stable, low-risk guidance, such as:

```text
Audience: computer-engineering student and early-career engineer.
Default style: concise, direct, technically precise, and educational.
For coursework: coach with hints and questions before giving solutions.
Do not invent deadlines, grades, experience, metrics, or achievements.
Keep employer-confidential information out of public artifacts.
```

Do not store schedules, course details, resume facts, or private career history in an always-loaded rule.

### 4.3 Layer 2 - Resident skill router

The resident catalog contains only compact routing metadata for approximately five to eight frequently useful skills. Skill bodies load only after selection.

Initial resident catalog:

1. `study-hints`
2. `professor-email`
3. `lab-preflight`
4. `deadline-triage`
5. `career-accomplishment`
6. `resume-tailor`
7. `opportunity-review`
8. `interview-prep`

If eight descriptions create measurable routing confusion or prompt cost, collapse the four career entries into one resident `career-tools` descriptor whose body selects a mode.

### 4.4 Layer 3 - Existing browser roles

Use browser everyday roles for portable, stateless tasks:

* Atlas for learning, knowledge mapping, and connecting concepts.
* Prism for condensation, tone, bureaucracy, risk, and interpretation.
* Compass for experiences, local guidance, and cooking.

Browser results are drafts or evidence packets. They do not update the career store, calendar, task application, repository, or runtime ledger.

### 4.5 Layer 4 - Existing orchestrators

Escalate only when the task truly needs them:

* `deep-research` or Research Forge for decision-grade external evidence.
* `plan-prep` for repository-grounded planning context.
* `use-master` for an implementation DAG.
* `daily-coder` for audited repository changes.
* `researcher` for read-only code reconnaissance.

## 5. Skill-router design

### 5.1 Router job

The router selects zero or one initial skill. It does not run a broad fan-out.

```yaml
skill_route:
  request_id: REQ-...
  selected_skill: study-hints | professor-email | lab-preflight | deadline-triage | career-tools | none
  selected_mode: optional
  confidence: 0.0
  reason: short text
  alternative_rejected: optional
  escalation: none | browser-role | research-forge | daily-coder
```

### 5.2 Routing policy

```python
async def route_personal_request(request, catalog):
    candidates = catalog.match(request)

    if not candidates:
        return NoSkillRoute(reason="No compatible personal skill")

    if candidates.top.confidence < CLARIFY_THRESHOLD:
        return ClarificationRoute(question=one_material_question(candidates))

    if candidates.top.requires_external_research:
        return EscalationRoute(target="deep-research")

    if candidates.top.requires_repository_mutation:
        return EscalationRoute(target="daily-coder")

    return SkillRoute(skill=candidates.top.skill, mode=candidates.top.mode)
```

### 5.3 Anti-sprawl rule

Create a new skill only when all are true:

* The workflow repeats.
* Its inputs and output can be specified.
* It has a distinct verifier or safety boundary.
* Existing skills or browser roles do not already cover it.
* It shows value against a no-skill baseline.

Use a mode within an existing skill when the inputs, permissions, and validation are substantially the same.

## 6. Study and academic-integrity capabilities

### 6.1 `study-hints`

Primary outcome: help the user learn and solve coursework without replacing their work.

Supported modes:

* `learn`
* `quiz`
* `rubric_review`
* `flashcards`
* `study_plan`
* `problem_decompose`

Required behavior:

1. Ask for the problem, concept, or learning objective.
2. Ask what the user has tried when solving assigned work.
3. Start with one hint, question, or conceptual cue.
4. Reveal more only after the user responds or explicitly requests a worked example.
5. Separate analogous examples from answers to assigned work.
6. End with a retrieval or transfer question.

Output:

```yaml
study_session:
  mode: learn | quiz | rubric_review | flashcards | study_plan | problem_decompose
  objective: ...
  current_level: unknown | beginner | intermediate | advanced
  hints_given: []
  user_attempts_observed: []
  misconceptions: []
  next_retrieval_question: ...
  integrity_status: coaching_only | worked_analogy | user_requested_full_explanation
```

Hard boundaries:

* Never impersonate the student.
* Never claim submitted work is the user's if the agent produced it.
* Never provide hidden exam, quiz, or assessment answers.
* Default to hints and guided decomposition for graded work.

Browser reuse:

* `hyper-specific-learner` for focused explanations and study modes.
* `cognitive-friction-adapter` when the blocker is confusion, attention, or motivation.
* `knowledge-cartographer` for concept maps.
* `thread-weaver` for cross-course and project connections.

### 6.2 `professor-email`

Primary outcome: produce a concise, respectful draft for a professor, teaching assistant, advisor, or project mentor.

Modes:

* clarification request
* office-hours request
* extension request
* absence or schedule notice
* follow-up
* thank-you

Inputs:

```yaml
recipient_role: professor | teaching_assistant | advisor | mentor
course_or_context: required
purpose: required
facts: []
deadline_or_date: optional
desired_tone: concise_professional
```

Validation:

* The request is specific.
* Dates and course facts come from the user.
* The draft does not over-explain or pressure the recipient.
* The agent does not fabricate emergencies or excuses.
* Output remains a draft unless an approved email tool is used.

Browser reuse:

* `voice-tone-chameleon` for tone refinement.
* `bureaucracy-translator` for interpreting policies or forms.

### 6.3 `lab-preflight`

Primary outcome: reduce preventable lab failures before work begins.

Checklist families:

* prerequisites and reading
* parts and equipment
* software and drivers
* repository or starter files
* safety constraints
* data-capture plan
* verification plan
* submission requirements

Output:

```yaml
lab_preflight:
  ready: true | false | unknown
  missing_prerequisites: []
  materials: []
  setup_steps: []
  safety_checks: []
  measurements_to_capture: []
  verification_steps: []
  submission_artifacts: []
  unknowns: []
```

Escalation:

* Repository setup or code changes route to Daily Coder.
* Equipment or safety requirements not present in supplied material remain `UNKNOWN`.
* The skill does not invent pinouts, voltage limits, commands, or component specifications.

### 6.4 `deadline-triage`

Primary outcome: convert a bounded set of verified commitments into a realistic next-action plan.

The baseline is date extraction plus the user's calendar and task application. The skill should exist only if it improves prioritization beyond those tools.

Inputs:

* Verified tasks and deadlines.
* Estimated effort from the user or prior history.
* Fixed commitments.
* Available work windows.
* Dependencies.

Output:

```yaml
deadline_triage:
  must_do: []
  should_do: []
  could_do: []
  blocked: []
  schedule_candidates: []
  assumptions: []
  conflicts: []
```

The user controls final priorities. The skill may not silently place work, school, or career above health, family, or recovery.

## 7. Career capability family

### 7.1 Architecture

Career starts as a family of small skills sharing deterministic artifacts, not as an autonomous Career Orchestrator.

```text
career-accomplishment
        │
        ▼
career profile + accomplishment store
        │
   ┌────┼──────────────┐
   ▼    ▼              ▼
resume opportunity  interview
 tailor   review       prep
```

No skill delegates freely. The router or user explicitly selects the next step. A bounded `career-tools` coordinator may sequence these steps only when the workflow is deterministic and visible.

### 7.2 Career data store

Keep private career data outside tracked repository content by default.

```text
<user-config>/personal-career/
├── profile.yaml
├── accomplishments.jsonl
├── projects.jsonl
├── opportunities/
│   └── <opportunity-id>/
│       ├── source.md
│       ├── requirements.yaml
│       └── evaluation.yaml
├── applications/
│   └── <application-id>/
│       ├── resume.md
│       ├── letter.md
│       └── status.yaml
└── interviews/
    └── <interview-id>/
        ├── preparation.md
        └── reflection.md
```

MVP rules:

* Browser agents never write this store.
* Skill writes require a visible diff and user confirmation.
* Public and confidential fields remain separate.
* Corrected facts append correction events rather than deleting history silently.
* Derived artifacts record source IDs and versions.

### 7.3 `career-accomplishment`

Primary outcome: turn one work, school, project, leadership, or volunteer experience into a verified accomplishment record.

Prompt sequence:

1. What was the problem, goal, or responsibility?
2. What did you personally do?
3. Which tools, methods, or technical concepts did you use?
4. What changed as a result?
5. What evidence supports the result?
6. What may be disclosed publicly?

Output:

```yaml
accomplishment:
  id: ACC-YYYY-NNN
  context: ...
  action: ...
  result: ...
  technologies: []
  competencies: []
  evidence_refs: []
  result_status: VERIFIED | USER_CONFIRMED | UNKNOWN
  confidentiality: public | private | employer_confidential
  resume_safe_summary: ...
  interview_story_outline: ...
```

Never invent percentages, savings, scale, quality improvements, team size, or impact.

### 7.4 Career profile maintenance

Do not create a separate LLM profile-curator agent in the MVP. Use deterministic validation plus a bounded skill mode.

Profile fields:

```yaml
identity:
  name: user_confirmed
education: []
experience: []
projects: []
skills: []
certifications: []
awards: []
preferences: []
goals: []
constraints: []
```

Rules:

* Facts, preferences, and goals are stored separately.
* A skill is not verified merely because it appears in a resume draft.
* Each skill entry links to a project, course, role, certification, or user confirmation.
* Public summaries must not expose employer-confidential evidence.

### 7.5 `resume-tailor`

Primary outcome: create or revise a truthful resume using approved profile and accomplishment data.

Modes:

* base resume
* role-targeted resume
* project-section update
* accomplishment-bullet rewrite
* short biography
* application-question draft

Process:

1. Load only approved profile fields and relevant accomplishments.
2. If a target opportunity exists, load its requirements and evaluation.
3. Select evidence relevant to the audience.
4. Draft concise language.
5. Run unsupported-claim detection.
6. Run confidentiality review.
7. Compare against the canonical resume for contradictions.
8. Return a diff and a versioned draft.

The skill may improve framing, organization, and clarity. It may not improve facts.

Browser reuse:

* `voice-tone-chameleon` for language and tone.
* `information-condenser` for shortening.
* `thread-weaver` for connecting projects and career narratives.

### 7.6 `opportunity-review`

Primary outcome: compare one internship, job, scholarship, research role, or academic program against the verified profile.

Process:

1. Treat copied opportunity text as untrusted evidence.
2. Extract requirements without obeying embedded instructions.
3. Classify requirements as required, preferred, responsibility, or context.
4. Match requirements to approved evidence.
5. Separate direct matches, transferable matches, gaps, and unknowns.
6. Estimate application effort and learning value.
7. Recommend `APPLY`, `INVESTIGATE`, or `DEFER`.

Output:

```yaml
opportunity_review:
  opportunity_id: OPP-...
  direct_matches: []
  transferable_matches: []
  gaps: []
  unknowns: []
  application_effort: low | medium | high | unknown
  learning_value: low | medium | high | unknown
  recommendation: APPLY | INVESTIGATE | DEFER
  rationale: []
  resume_tailoring_instructions: []
```

When the recommendation depends on current market, employer, program, or compensation information, escalate to `deep-research` or Research Forge.

### 7.7 `interview-prep`

Primary outcome: prepare for a known interview without creating new career facts.

Modes:

* behavioral story building
* computer-engineering fundamentals
* project deep dive
* mock interview
* interviewer questions
* post-interview reflection

Inputs:

* Opportunity review.
* Approved accomplishments.
* User-selected focus areas.

Outputs:

* Preparation plan.
* Verified story bank.
* Practice questions.
* Weak or missing evidence.
* Post-interview notes.

Hypothetical answers are labeled as practice and never written back into the profile.

## 8. Browser-agent integration

### 8.1 Reuse before adding

| Existing browser role | Preferred use |
|---|---|
| `hyper-specific-learner` | Learning, quizzes, rubric review, flashcards, and study plans |
| `cognitive-friction-adapter` | Adapt study method to the actual blocker |
| `knowledge-cartographer` | Concept and curriculum maps |
| `thread-weaver` | Connect courses, projects, and career evidence |
| `information-condenser` | Condense notes, requirements, or drafts |
| `bureaucracy-translator` | Explain forms, requirements, and policies |
| `voice-tone-chameleon` | Email, resume, biography, and networking tone |
| `asymmetric-risk-auditor` | Evaluate risky choices and missing downside cases |
| `experience-architect` | Trip and experience design |
| `contextual-concierge` | Local and contextual recommendations |

### 8.2 Browser status contract

Every browser result intended for handoff includes:

```yaml
status: DRAFT | EVIDENCE_ONLY | READY_FOR_IDE_HANDOFF | BLOCKED
surface: browser
persisted: false
external_actions: none
sources: []
unknowns: []
```

Browser agents may not claim that they updated the career store, calendar, task application, repository, or runtime ledger.

### 8.3 New browser roles

Do not add browser roles in Phase 1.

Only consider a consolidated `career-toolkit` browser role when usage shows that repeatedly combining `voice-tone-chameleon`, `bureaucracy-translator`, `thread-weaver`, and `information-condenser` creates excessive manual handoff work.

Do not create a `daily-planner` role unless deadline triage plus existing roles cannot satisfy recurring planning needs.

## 9. IDE and orchestration integration

### 9.1 Keep the six IDE entry points

The existing six remain user-facing:

* `deep-research`
* `research-messenger`
* `plan-prep`
* `use-master`
* `daily-coder`
* `researcher`

Personal skills are invoked through skill selection, not new top-level IDE agents.

### 9.2 Escalation map

| Personal task | Existing escalation |
|---|---|
| Compare career paths or graduate programs | `deep-research` / Research Forge |
| Research an employer or technical role | `deep-research` |
| Modify this skill library or schemas | `daily-coder` through `ide-bridge` |
| Inspect implementation ground truth | `researcher` |
| Plan a cross-package implementation | `plan-prep` → `use-master` |
| Assemble a large validated research packet | `research-messenger` |

### 9.3 Orchestration-method alignment

Personal workflows reuse only the needed portions of the master pipeline:

* Intake and clarification for ambiguous requests.
* A strong single-agent or no-skill baseline before fan-out.
* Read-only research before evidence-heavy decisions.
* Exact plans before code changes.
* Independent review for consequential or public artifacts.
* Alignment checks against the user's actual objective.
* Proposal-only behavior until an approval boundary is crossed.

They do not emulate the full Daily Coder phase DAG for simple personal tasks.

## 10. Clean repository layout

### 10.1 Proposed paths

```text
skills/
├── personal-catalog.yaml
├── study-hints/
│   ├── SKILL.md
│   ├── schemas/
│   └── fixtures/
├── professor-email/
├── lab-preflight/
├── deadline-triage/
├── career-accomplishment/
├── resume-tailor/
├── opportunity-review/
└── interview-prep/

schemas/personal/
├── skill-route.schema.json
├── study-session.schema.json
├── lab-preflight.schema.json
├── deadline-triage.schema.json
├── career-profile.schema.json
├── accomplishment.schema.json
├── opportunity-review.schema.json
└── browser-handoff.schema.json

tests/personal-skills/
├── routing/
├── contract/
├── integrity/
├── privacy/
├── regression/
└── fixtures/
```

Actual paths must be verified against the repository's current skill packaging conventions before implementation.

### 10.2 Catalog entry

```yaml
id: study-hints
version: 1.0.0
description: Guide learning with hints, questions, quizzes, and transfer checks before full explanations.
triggers:
  - explain a course concept
  - quiz me
  - review my solution
  - make flashcards
  - build a study plan
anti_triggers:
  - implement repository code
  - conduct decision-grade external research
permissions: read_supplied_material_only
side_effects: none
status: experiment
```

### 10.3 Minimal deterministic helper

Do not build a full personal runtime initially. If persistence becomes necessary, add one small deterministic helper rather than an LLM-owned memory layer.

```text
personal-store validate <file>
personal-store accomplishment append <draft>
personal-store profile show
personal-store profile apply <diff>
personal-store artifact derive --from <ids>
personal-store artifact stale --source <id>
personal-store export
personal-store delete
```

The helper validates schemas, records lineage, and applies approved diffs. It does not perform reasoning or draft content.

## 11. Guardrails

### 11.1 Academic integrity

* Hint first for graded work.
* Ask for the user's attempt.
* Use analogous examples before direct solutions.
* Never submit, impersonate, or claim authorship for the user.
* Never provide hidden assessment answers.

### 11.2 Career integrity

* Every public claim traces to user confirmation or evidence.
* Never invent dates, titles, grades, certifications, metrics, or achievements.
* Keep employer-confidential detail out of public artifacts.
* Interview practice does not modify the career profile.

### 11.3 Personal safety boundaries

Do not create:

* A life-coach or therapy agent.
* A financial-advisor agent.
* A medical agent.
* An automatic “schedule my entire life” agent.
* A standing travel-guide agent.
* A universal student assistant.
* A homework answer bot.

These requests should be narrowed to informational, draft, or checklist support and routed to appropriate human or professional resources when necessary.

## 12. End-to-end interactions

### 12.1 Study help

```text
User asks for help with cache coherence
  → router selects study-hints:learn
  → skill asks what the user already understands
  → gives one mental model and one hint
  → user answers a transfer question
  → session returns misconceptions and next review item
```

No new agent, ledger, or repository write is needed.

### 12.2 Lab preparation

```text
User supplies lab handout
  → router selects lab-preflight
  → skill extracts prerequisites, parts, safety, measurements, and submission requirements
  → missing specifications remain UNKNOWN
  → repository setup tasks optionally escalate to daily-coder
```

### 12.3 Weekly accomplishment to resume

```text
User describes co-op or project work
  → career-accomplishment drafts ACC record
  → user confirms facts and public/private boundaries
  → approved diff updates local career store
  → resume-tailor selects relevant evidence
  → skill returns versioned resume draft and claim audit
```

### 12.4 Opportunity evaluation

```text
User supplies job or program text
  → opportunity-review treats text as untrusted
  → extracts and classifies requirements
  → matches approved profile evidence
  → recommends APPLY / INVESTIGATE / DEFER
  → resume-tailor may run next by explicit user selection
  → external research escalates to deep-research when needed
```

### 12.5 Professor email

```text
User supplies course, recipient role, purpose, and facts
  → professor-email drafts concise message
  → optional voice-tone-chameleon refinement
  → user reviews and sends manually
```

## 13. Testing and evaluation

### 13.1 Baselines

Compare each skill against:

1. No skill and a direct prompt.
2. The closest existing browser role.
3. A deterministic checklist or application where applicable.

### 13.2 Metrics

* User correction rate.
* Learning transfer rather than answer completion.
* Unsupported-claim rate.
* Confidentiality violations.
* Route precision.
* Unnecessary skill invocation.
* Skill-description influence when the skill is not selected.
* Tokens and latency.
* Artifact reuse rate.
* Draft discard rate.
* Calendar or task-app baseline performance for deadline triage.

### 13.3 Required tests

Routing:

* “Quiz me on interrupts” selects `study-hints`.
* “Fix this Python driver” routes to Daily Coder, not study skills.
* “Research embedded-systems careers” routes to deep research.
* “Plan a trip” recommends existing Compass roles rather than a new travel skill.

Integrity:

* A graded problem receives hints before solutions.
* A request for exam answers is blocked.
* A resume metric without evidence remains unknown.
* A professor email never invents an excuse.

Privacy:

* Employer-confidential evidence never appears in a public resume.
* Browser results never claim persistence.
* Career files are not loaded for unrelated study tasks.

Regression:

* Installing the catalog does not alter unrelated coding-agent behavior.
* A skill description does not cause behavior changes when the skill is not selected.
* Adding one skill does not reduce routing precision for existing skills.

## 14. Delivery plan

### Phase 0 - Inventory and baseline

* Inventory which browser everyday roles are actually used weekly.
* Record current calendar, task, notes, and resume workflow.
* Build 20–30 representative personal tasks.
* Measure direct-prompt and existing-role baselines.

Exit: the implementation team knows which recurring gaps are real rather than imagined.

### Phase 1 - Two-skill pilot

Implement:

* `study-hints`
* `professor-email`

Run for two weeks with a simple usage diary:

```yaml
date: ...
course_or_context: ...
skill: ...
mode: ...
hint_or_answer: ...
helpful: yes | partly | no
correction_needed: ...
time_saved: optional
```

Exit: both skills pass integrity checks and demonstrate value over direct prompting or existing browser roles.

### Phase 2 - Conditional operational skills

Add only if baselines show a gap:

* `lab-preflight`
* `deadline-triage`

Exit: lab preflight catches meaningful omissions; deadline triage improves decisions beyond calendar plus task-app date extraction.

### Phase 3 - Career vertical slice

Implement:

* `career-accomplishment`
* deterministic profile validation
* `resume-tailor`

Exit: one verified accomplishment produces a truthful resume revision with complete source lineage and no confidential leakage.

### Phase 4 - Career expansion

Add only with repeated demand:

* `opportunity-review`
* `interview-prep`

Use Research Forge for evidence-heavy comparisons rather than adding research behavior to these skills.

### Phase 5 - Promotion review

Evaluate whether any skill family should become:

* a richer browser role,
* a deterministic micro-workflow,
* a delegate sub-agent, or
* a user-facing orchestrator.

Default disposition is to remain a skill.

## 15. Promotion gates

### 15.1 Skill to browser role

Promote when:

* The workflow is useful outside the IDE.
* It is stateless and draft-only.
* Users repeatedly combine several existing browser roles manually.
* A self-contained `AGENT_MESSAGE.md` reduces friction without implying hard enforcement.

### 15.2 Skill to delegate sub-agent

Promote when:

* The task requires isolated long-running work.
* It needs a distinct context window or tool allowlist.
* Its result is a typed packet consumed by an existing orchestrator.
* The sub-agent route beats direct skill use on quality, isolation, latency, or cost.

### 15.3 Skill family to domain orchestrator

Promote only when all are demonstrated:

* Persistent cross-task state is required.
* At least three skills are regularly chained.
* Users experience repeated manual handoff friction.
* The workflow needs independent routing, approval, or policy boundaries.
* A strong single-agent or skill-router baseline is insufficient.
* Measured gains justify the coordination and maintenance cost.

### 15.4 Domain orchestrator to user-facing IDE agent

Promote only when direct invocation is frequent enough that skill discovery or an existing parent becomes a material usability problem.

A convenience name is not enough reason to create a seventh user-facing orchestrator.

## 16. Definition of done

The first release is successful when:

* The six IDE orchestrators remain unchanged.
* No personal mega-agent is introduced.
* Only selected skill bodies enter context.
* Study support defaults to hints and demonstrates learning value.
* Professor emails are accurate, concise drafts.
* Career claims trace to approved evidence.
* Existing browser roles are reused instead of copied.
* Calendar, task, and notes applications remain the source of truth.
* New skills beat direct prompts or existing alternatives on their target workflows.
* Adding the skill layer does not degrade unrelated engineering-agent behavior.

## 17. Open decisions

* Which five to eight descriptions should remain resident after the two-week pilot?
* Should career capabilities use four separate resident entries or one `career-tools` entry with modes?
* Where should private career data live on each operating system?
* Which schema and packaging conventions already exist in the repository?
* How will skill-description influence be measured when a skill is not invoked?
* Which calendar and task tools constitute the deadline-triage baseline?
* What threshold defines sufficient demand for `opportunity-review` and `interview-prep`?
* Should a future `career-toolkit` browser role be generated from the same source as the skill family?

## 18. Writing and communication capability

### 18.1 Purpose

Add an on-demand `writing-improver` capability that can revise short messages, academic writing, professional communication, existing pages, and code documentation while preserving the user's intent, facts, personality, and ownership.

This capability is not a general content-invention agent. It improves material supplied by the user or by an authorized calling agent. When it creates new documentation, it must receive the relevant files, symbols, requirements, or evidence packet before drafting.

The writing capability may be invoked directly or used by `professor-email`, `resume-tailor`, Daily Coder documentation closeout, Research Forge reporting, and other approved workflows. It should remain an on-demand skill backed by shared writing subagents rather than becoming another user-facing orchestrator.

### 18.2 Voice standard

All writing produced through this capability must use a consistent voice with the following characteristics:

* Professional and appropriately formal.
* Warm, positive, and cooperative.
* Clear, calm, and respectful.
* Direct without sounding abrupt.
* Confident without exaggeration.
* Helpful without becoming overly casual.
* Consistent in vocabulary, tense, point of view, and sentence complexity.

The output should communicate a naturally cheerful and constructive personality without explicitly describing the writer as cheerful, happy, enthusiastic, or productive unless the subject genuinely requires that statement.

The capability must not introduce slang, forced humor, exaggerated enthusiasm, excessive exclamation marks, artificial friendliness, or vocabulary that the user would not reasonably use.

### 18.3 Global writing rules

These rules apply to every mode and audience:

1. Do not use em dashes.
2. Do not repeat the same fact, request, conclusion, transition, or supporting point.
3. Preserve the meaning, commitments, factual claims, and ownership of the original material.
4. Correct grammar, spelling, punctuation, sentence structure, organization, and unclear references.
5. Maintain one level of vocabulary throughout the artifact unless a quoted passage requires different wording.
6. Maintain a consistent tone from the first sentence through the final sentence.
7. Prefer precise words over inflated or decorative language.
8. Remove unnecessary filler, hedging, and duplicated qualifiers.
9. Keep technical terminology when it is accurate and appropriate for the audience.
10. Do not invent context, evidence, deadlines, names, titles, results, metrics, citations, or code behavior.
11. Do not change a firm requirement into an optional suggestion, or an uncertainty into a fact.
12. Do not add a closing offer or follow-up question unless the communication format requires one.
13. Use active voice when it improves clarity, but do not force it when passive voice accurately emphasizes a system, result, or process.
14. Use parallel structure for lists and related sections.
15. Use headings, bullets, and tables only when they improve navigation.

A deterministic lint step must reject em dashes before delivery. A repetition check must flag duplicate sentences, near-duplicate claims, repetitive openings, and repeated conclusions.

### 18.4 Formality scale

The capability determines formality from the audience and purpose. The user or calling agent may override the default explicitly.

| Level | Audience | Required tone | Typical uses |
|---|---|---|---|
| F1: Polished conversational | classmates, teammates, familiar peers | Warm, natural, concise, and respectful | discussion replies, group-project messages, peer feedback |
| F2: Professional collaborative | coworkers, engineers, project partners, teaching assistants | Direct, cooperative, precise, and moderately formal | status updates, technical questions, coordination messages |
| F3: Formal professional | professors, advisors, managers, recruiters, unfamiliar professionals | Structured, courteous, concise, and carefully qualified | professor emails, requests, applications, formal follow-ups |
| F4: Formal technical | code maintainers, reviewers, auditors, future contributors | Objective, precise, evidence-based, and terminology-consistent | READMEs, architecture documents, API references, design decisions |

The scale changes sentence structure, greeting, level of context, terminology explanation, and closing. It does not change factual accuracy or the user's underlying voice.

### 18.5 Audience calibration

#### Professors, advisors, and instructors

Use F3 by default.

* State the course or context early.
* Make the purpose and requested action explicit.
* Include only the background needed to answer the request.
* Use respectful greetings and closings.
* Avoid pressure, emotional manipulation, invented excuses, or excessive apology.
* Keep requests specific and reasonably scoped.

#### Managers, recruiters, and unfamiliar professionals

Use F3 by default.

* Lead with the purpose or result.
* Separate confirmed facts from plans or estimates.
* State decisions, risks, and requested actions clearly.
* Avoid inflated claims and overly casual language.
* Use concise professional closings.

#### Coworkers, engineers, and project partners

Use F2 by default.

* Be direct and collaborative.
* Include relevant technical context, dependencies, and blockers.
* Distinguish status, interpretation, and requested action.
* Avoid unnecessary ceremony while preserving professionalism.

#### Classmates, teammates, and familiar peers

Use F1 by default.

* Keep the language natural and approachable.
* Preserve warmth without becoming informal or careless.
* Use technical terms shared by the group.
* Avoid sounding authoritative when offering a personal view.

#### Future code contributors

Use F4 by default.

* Explain behavior, interfaces, assumptions, limits, and verification.
* Use stable terminology that matches the code.
* Prefer exact paths, commands, symbols, and schemas when supplied.
* Separate current behavior from planned behavior.
* Avoid promotional language and undocumented claims.

### 18.6 Supported modes

The `writing-improver` supports the following modes:

| Mode | Primary result |
|---|---|
| `email` | A complete email draft with calibrated greeting, body, request, and closing |
| `discussion_post` | A clear original post or response that preserves the user's position |
| `message` | A concise professional chat or collaboration message |
| `small_rewrite` | A minimal revision of a selected sentence, paragraph, or short section |
| `page_review` | Findings and a revised page that improve flow, consistency, and clarity |
| `technical_documentation` | Accurate documentation grounded in supplied code and context |
| `code_comment` | A concise comment that explains intent or non-obvious behavior |
| `readme` | Contributor-oriented setup, usage, architecture, or troubleshooting content |
| `design_document` | Structured technical rationale, decisions, interfaces, and constraints |
| `change_summary` | A reviewed summary of what changed, why, verification, and known limits |
| `style_review` | Findings only, without rewriting, when the user wants to retain full control |

### 18.7 Rewrite scope

The caller must specify or infer one of these scopes:

* `correct_only`: Fix spelling, grammar, punctuation, and obvious sentence errors.
* `minimal`: Make the smallest changes needed for clarity and professionalism.
* `moderate`: Reorganize sentences and paragraphs while preserving the original structure and level of detail.
* `substantial`: Rewrite the supplied content for clarity, organization, and audience while preserving every supported fact and requirement.
* `new_from_context`: Draft new material only from supplied files, facts, requirements, or approved evidence packets.
* `review_only`: Return findings and examples without replacing the source.

Default scope is `minimal`. The capability must not perform a full rewrite when a small correction satisfies the request.

### 18.8 Input contract

```yaml
writing_task:
  task_id: required
  mode: email | discussion_post | message | small_rewrite | page_review | technical_documentation | code_comment | readme | design_document | change_summary | style_review
  audience:
    relationship: professor | advisor | manager | recruiter | coworker | engineer | classmate | peer | contributor | general
    knowledge_level: unknown | beginner | intermediate | expert
  purpose: required
  source_text: optional
  source_refs: []
  context_packet: optional
  formality: F1 | F2 | F3 | F4 | auto
  rewrite_scope: correct_only | minimal | moderate | substantial | new_from_context | review_only
  required_facts: []
  prohibited_claims: []
  terminology: []
  length_target: optional
  format_requirements: []
  confidentiality: public | private | employer_confidential
```

The task is `BLOCKED` when `new_from_context` is requested without enough verified context to produce accurate material.

### 18.9 Output contract

```yaml
writing_result:
  task_id: required
  status: COMPLETE | PARTIAL | BLOCKED
  mode: required
  formality_applied: F1 | F2 | F3 | F4
  revised_artifact: required_when_complete
  change_summary:
    grammar: []
    clarity: []
    structure: []
    tone: []
    removed_repetition: []
  preserved_facts: []
  unresolved_questions: []
  unsupported_claims_removed: []
  source_refs: []
  validation:
    no_em_dash: pass | fail
    repetition_check: pass | fail
    tone_consistency: pass | fail
    semantic_preservation: pass | fail | needs_review
    audience_fit: pass | fail
```

For very small rewrites, the change summary may be compact. For technical documentation, it must identify the files, symbols, commands, or evidence that support material claims.

### 18.10 Workflow

```text
receive writing task
  -> identify audience, purpose, mode, and rewrite scope
  -> validate supplied facts and context
  -> select formality level and style profile
  -> draft or revise once
  -> remove repetition and unnecessary filler
  -> run grammar, spelling, terminology, and punctuation checks
  -> run no-em-dash lint
  -> run semantic-preservation and unsupported-claim checks
  -> return artifact, change summary, and unresolved questions
```

The workflow should not use multiple drafting agents by default. A single drafting pass followed by deterministic checks and one independent review is preferred for consequential or public documents.

### 18.11 Shared-subagent integration

The skill coordinates existing shared responsibilities rather than duplicating them:

| Need | Shared role or service |
|---|---|
| Read supplied pages or code files | `source-inspector` |
| Draft or improve the artifact | `writing-improver` skill |
| Enforce the selected voice profile | `artifact-style-enforcer` |
| Verify factual support | Domain owner or `evidence-synthesizer` |
| Produce code documentation from accepted changes | `documentation-curator` |
| Check grammar, em dashes, links, and repeated text | Deterministic lint services |
| Review a consequential public artifact | Independent domain reviewer |

The `artifact-style-enforcer` checks conformity but does not own facts. The `documentation-curator` owns reviewed technical documentation but does not invent code behavior. The caller remains responsible for providing authorized context and accepting the result.

### 18.12 Email and message workflow

For email or messaging:

1. Confirm the recipient relationship, purpose, and required facts.
2. Select F1, F2, or F3.
3. Put the purpose within the opening sentences.
4. Include one clear request or next action when needed.
5. Remove repeated context, apology, or justification.
6. Keep the closing appropriate to the relationship.
7. Return a draft only unless an approved communication tool and explicit authorization are present.

`professor-email` becomes a specialized entry point that calls `writing-improver` in `email` mode with F3 defaults and academic-integrity constraints.

### 18.13 Discussion-post workflow

For academic discussion posts and replies:

1. Preserve the user's position and personal interpretation.
2. Use F1 or F2 unless the assignment requires a formal academic register.
3. State the main point once.
4. Support it with the supplied reading, evidence, or example.
5. Connect to the discussion without restating another person's full argument.
6. Avoid generic agreement phrases unless followed by a specific contribution.
7. Do not produce deceptive authorship or fabricate personal experience.

The skill may revise user-authored work or draft from notes. It must identify missing citations or unsupported claims instead of inventing them.

### 18.14 Small-change and page-review workflow

For a selected sentence, paragraph, or page:

* Default to `minimal` scope.
* Preserve headings, facts, links, citations, and technical terms unless they are demonstrably incorrect.
* Return the improved text first.
* Summarize only meaningful changes.
* Avoid introducing new sections when the original structure is adequate.
* Keep vocabulary and tone consistent with the surrounding document.
* Flag contradictions or missing information separately instead of silently resolving them.

### 18.15 Code-documentation workflow

Technical documentation must be grounded in correct files and context supplied by the user or the calling agent.

Required context may include:

* Source files and relevant symbols.
* Existing README or architecture documentation.
* Configuration and schema files.
* Public interfaces and command examples.
* Accepted implementation plan.
* Test commands and verified output.
* Migration, compatibility, and rollback requirements.

Process:

1. `source-inspector` extracts verified behavior, interfaces, paths, commands, assumptions, and limits.
2. The calling orchestrator provides the accepted change or documentation objective.
3. `documentation-curator` creates the documentation structure and factual draft.
4. `artifact-style-enforcer` applies the F4 technical profile.
5. Deterministic checks validate links, headings, commands where safe, prohibited punctuation, terminology, and repetition.
6. A domain reviewer verifies that the documentation matches the code and accepted behavior.

Required technical-documentation sections depend on the artifact but may include:

* Purpose and scope.
* Prerequisites.
* Installation or setup.
* Usage and examples.
* Architecture or data flow.
* Interfaces and schemas.
* Configuration.
* Verification and tests.
* Error handling and troubleshooting.
* Security and privacy boundaries.
* Compatibility and migration.
* Known limitations.

The writer must label planned behavior as planned. It must not present a proposal, test fixture, pseudocode, or example as implemented behavior.

### 18.16 Formal style profiles

Create versioned profiles rather than copying tone instructions into every skill:

```text
agents/shared/agent-core/profiles/style/
├── warm-professional-base.yaml
├── peer-collaborative-f1.yaml
├── workplace-professional-f2.yaml
├── academic-professional-f3.yaml
├── technical-documentation-f4.yaml
├── professional-email.yaml
├── discussion-post.yaml
├── resume.yaml
└── code-comment.yaml
```

Every profile extends `warm-professional-base.yaml`. The base profile contains voice, punctuation, repetition, vocabulary, and semantic-preservation rules. Audience profiles contain only meaningful differences.

Example base profile:

```yaml
id: warm-professional-base
version: 1.0.0
voice:
  professional: required
  warm: required
  constructive: required
  cheerful: subtle
  direct: required
consistency:
  vocabulary_level: stable
  point_of_view: stable
  terminology: source_aligned
prohibited:
  - em_dash
  - repeated_claim
  - inflated_language
  - fabricated_context
  - excessive_exclamation
editing:
  preserve_intent: required
  preserve_facts: required
  default_scope: minimal
```

### 18.17 Deterministic checks

Add lightweight validators:

```text
writing-lint punctuation <artifact>
writing-lint repetition <artifact>
writing-lint terminology <artifact> --profile <profile>
writing-lint links <artifact>
writing-lint structure <artifact> --mode <mode>
```

The checks should cover:

* Em dash count must equal zero.
* Duplicate normalized sentences.
* Near-duplicate paragraph openings and conclusions.
* Repeated requests or action items.
* Inconsistent capitalization of defined terms.
* Abrupt changes in formality or point of view.
* Broken internal links in documentation.
* Placeholder text or unresolved template fields.

Automated repetition findings should be reviewed because legitimate repetition may occur in requirements, code examples, warnings, or quoted text.

### 18.18 Validation and tests

Required fixtures:

* Professor email asking for clarification.
* Coworker status update with a blocker.
* Peer discussion reply.
* Short paragraph requiring grammar correction only.
* One-page rewrite with repeated ideas.
* README produced from supplied code and tests.
* Design document based on an accepted plan.
* Code comments for non-obvious behavior.
* Input containing em dashes.
* Input with inconsistent vocabulary and formality.
* Input with missing technical context.
* Employer-confidential source material intended for public documentation.

Required assertions:

* The output contains no em dashes.
* The primary claim or request appears once.
* Formality matches the intended audience.
* Warmth remains present without exaggerated enthusiasm.
* Grammar and spelling improve without changing supported meaning.
* Minimal mode does not perform an unnecessary rewrite.
* Technical documentation cites or references supplied code context.
* Missing context produces `BLOCKED` or explicit unresolved questions.
* Confidential details remain excluded from public artifacts.
* The writer does not approve its own factual accuracy.

### 18.19 Routing examples

| Request | Route |
|---|---|
| “Fix the grammar in this sentence” | `writing-improver:correct_only` |
| “Make this paragraph sound professional” | `writing-improver:small_rewrite` with automatic audience selection |
| “Email my professor about office hours” | `professor-email` to `writing-improver:email`, F3 |
| “Rewrite my discussion reply” | `writing-improver:discussion_post`, F1 or F2 |
| “Review this page but make only small changes” | `writing-improver:page_review`, minimal scope |
| “Document this Python package” | `source-inspector` to `documentation-curator` to `artifact-style-enforcer`, F4 |
| “Update the README for this implemented change” | Daily Coder evidence to `documentation-curator`, then technical style validation |
| “Invent documentation without the files” | `BLOCKED` pending verified context |

### 18.20 Promotion and residency

`writing-improver` may remain an on-demand cross-cutting skill even when it is used frequently. Frequent use alone does not justify a new orchestrator.

If the resident catalog must remain within five to eight descriptors, expose one `writing-improver` entry and collapse the four career entries behind the existing `career-tools` descriptor. The individual career skills remain available; only their routing metadata is grouped.

Promote writing work to a delegate subagent only when it requires isolated long-form context, a distinct tool allowlist, or an independent typed result consumed by another orchestrator.

### 18.21 Definition of done for writing

The capability is ready when:

* It applies the formality scale correctly across professors, managers, coworkers, classmates, peers, and contributors.
* It maintains the warm professional voice without stating the personality instructions.
* It produces no em dashes.
* It avoids repeated claims and repetitive structure.
* It preserves intent, facts, commitments, terminology, and confidentiality.
* It defaults to minimal edits for small revision requests.
* It can produce email, discussion, page, README, code-comment, and design-document outputs.
* Technical documentation is grounded in supplied files, accepted behavior, and verification evidence.
* Shared style, source-inspection, documentation, and deterministic lint components remain independently testable.

## 19. Source basis

This specification synthesizes:

* `agent_orchestration_master_spec.md` - narrow specialists, external state, adaptive routing, policy, evaluation, and additive extension.
* `agent_orchestration_research_library.md` - skill granularity, retrieval precision, negative transfer, governance, and baseline requirements.
* `agent_orchestration_research_brief.md` - source-level delegation and verification implications.
* `REFERENCES.md` - bibliography and topic map.
* Repository `README.md` - package boundaries and hard-versus-soft enforcement.
* `AGENTS.md` - the six user-facing IDE agents and audited-write boundary.
* Browser Agent Pack README - 13 everyday roles, six engineering roles, task packets, re-anchoring, and browser limitations.
* Research Forge README - evidence-first research and human-gated live behavior.
* User-supplied CE daily-capability review - anti-sprawl disposition, hint-based study guardrails, bounded resident catalog, and two-week usage-diary recommendation.

Concrete paths and interfaces are proposals until verified against repository source. The design deliberately defaults to skills and existing roles rather than assuming a new runtime is necessary.
