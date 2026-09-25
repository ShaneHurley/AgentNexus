# Security review checklist (Research Forge + monorepo gates)

Use this before enabling **live research adapters**, **remote GitHub clone/API**, or **un-sandboxed experiment execution**. It maps to the live blockers in [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md).

## Filesystem and path boundaries

- [ ] All repo/file tools resolve paths under configured roots (`allowed_repo_roots`, package `config/`).
- [ ] Symlink escape attempts are rejected or normalized fail-closed.
- [ ] Artifact and ledger writes stay under workspace data directories (no arbitrary host paths).
- [ ] Experiment runner working directories are isolated and documented as **not** a secure sandbox today.

## URI, SSRF, and outbound fetch

- [ ] No adapter performs fetches to URLs not on an allowlist (scheme, host, port).
- [ ] Redirect following is disabled or bounded for any future HTTP adapters.
- [ ] `file://`, metadata endpoints, and link-local targets are denied by default.

## Credentials and secrets

- [ ] API keys and tokens live in OS-backed secret stores (Daily Coder `SecretStore`), not SQLite or dashboard JSON.
- [ ] Logs, CLI JSON, and REST responses redact `ghp_`, `github_pat_`, `x-access-token`, and provider API keys.
- [ ] `.env` and local secret files are gitignored; only `.env.example` documents variable names.

## Network surfaces (current vs planned)

| Surface | Status today | Gate |
|---------|----------------|------|
| Mock adapters | Shipped | No outbound network |
| Daily Coder live providers | Shipped behind `--live` / explicit opt-in | Credential + policy review |
| RF live search/code adapters | **Not shipped** | This checklist + Policy Gateway |
| GitHub clone into jail | **Shipped** (Daily Coder allowlist) | Checklist + URL allowlist + token scope matrix |
| GitHub read-only API tools | **Shipped** (Daily Coder read tools) | Prefer GitHub App installation tokens over broad PATs |
| GitHub PR / push writes | **DEFER** | Human approval + `external.write` policy |

## GitHub URL and token policy (REC-GH-CLONE / REC-GH-READ)

- [x] Clone/fetch URLs limited to `https://github.com/{owner}/{repo}` (configurable host allowlist).
- [x] Tokens from SecretStore / env only; redacted in errors (`ghp_`, `x-access-token`).
- [x] Clone targets land only under `allowed_repo_roots`.
- [ ] Rate limits and partial failure modes hardened for production multi-tenant use.
- [ ] PR/push writes remain **DEFER** (human approval + `external.write`).

## Research Forge CLI product gaps

- [x] Durable `RunState` persistence under `runs/wave1/<run_id>/state.json` (REC-01).
- [x] `research-forge resume` / `status` load persisted state (exit 2 when missing).
- [x] Live resume still requires the same live-mode decision gate as `run --live` (CLI + dashboard adapter; see agent-dashboard resume HTTP tests).

## Sign-off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Implementer | | | |
| Security reviewer | | | |
| Operator | | | |

**Related:** [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) · [docs hub truth table](../../docs/README.md#supported-today-truth-table)
