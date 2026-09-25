# Requirements Traceability

| Requested capability | Implemented by |
|---|---|
| Fan-out research from all sides | `router.py`, bounded parallel `RESEARCH`, researcher role |
| Weak read-only researchers first | researcher prompt, tool ACL, broker deny-by-default |
| One master makes decisions | master role and phase ownership |
| Specialist-local model swapping | every `agents/<role>/model.json` |
| Exact no-wiggle-room changes | exact-change-planning skill and plan gate |
| Many low-token agents | sizing profiles, per-role budgets, cheap-tier defaults |
| Rare frontier logic | frontier advisor, `escalation.py`, one-call policy |
| Adaptive pipeline | S/M/L/XL sizing and conditional brainstorming/fan-out |
| Plan reviewer | independent adversarial `plan_reviewer` |
| Code reviewer | diff-first adversarial `code_reviewer` |
| Meaningful tests | test designer, independent test author/executor, negative-control contract |
| Documentation | docs-only documenter role |
| Out-of-the-box brainstormer | bounded brainstormer; no idea is a valid result |
| Prevent off-task drift | verbatim task anchor and alignment checker |
| Adversarial/unfavorable review | adversarial review skill and reviewer prompts |
| Full ecosystem tool catalog | `config/tools.json` |
| Safe role-scoped access | `ToolBroker`, deny-by-default ACLs, path jail |
| Human approval before writes | `PolicyGateway`, approvals ledger, CLI/REST/dashboard approval |
| Real repository tools | typed filesystem, repository, command, patch, and test handlers |
| Extensible skills | versioned `skills/*/SKILL.md` lifecycle |
| Token efficiency | bounded packets, context compaction, budgets, measured usage |
| Crash/replay safety | transactional SQLite and idempotency keys |
| Long tests without token burn | durable jobs, `WAITING_JOB`, duration history |
| Provider independence | OpenAI, Anthropic, Gemini, OpenRouter, local, command, HTTP adapters |
| Read-only web research | SSRF-safe URL fetch and configured Brave Search |
| Local/team operation | CLI plus authenticated REST service and dashboard |
| Future multi-host deployment | `RunRepository`/`JobQueue` contracts; distributed stubs fail closed |
| No uncontrolled self-improvement | one candidate per cycle, frozen/holdout gate, human promotion and rollback |

Enterprise search, email, calendar, external-write, and distributed-worker adapters remain disabled until credentials, schemas, policies, and worker identity are supplied.
