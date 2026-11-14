# simpleIDE

A standard-library CLI and SQLite ledger for lightweight work in Claude Code, Cursor, Codex and Antigravity. It installs one short rule, two on-demand skills, existing role definitions, and `.simpleide/sx.py`. Native permissions remain authoritative.

The [November 11 repair plan](docs/repair-plan-2026-11-11.md) is implemented locally; see the [issue/fix/test checklist and verification](docs/repair-completion-2026-11-11.md). Host qualification and the real-task comparison are separate, partially outstanding work.

## Install and update

```sh
python3 simpleIDE/install.py --target /path/to/project --tools codex,cursor --dry-run
python3 simpleIDE/install.py --target /path/to/project --tools codex,cursor
python3 simpleIDE/install.py --target /path/to/project --tools codex --hooks
python3 simpleIDE/install.py --target /path/to/project --tools cursor --uninstall
```

Use `--global` for user-level installation, in a home you intend to modify. Restart the host. First hook registration is opt-in; updates preserve existing enabled state. Review new/changed hooks through the host's native trust UI. The installer never changes sandbox, approval, trust or model-default settings. `--models FILE` supplies nonempty per-host role mappings; unspecified roles in a partial custom map explicitly inherit. Confirm actual model availability in the host.

The manifest tracks consumers, hashes and exact hook entries. Partial uninstall retains assets used by remaining hosts. Unknown/edited collisions stop before writes, user additions survive, and an apply failure restores the prior installation. Memory stays on uninstall. Read [migration and rollback instructions](docs/migrations-and-recovery.md) before upgrading an existing store.

| Host | Skills | Roles |
|---|---|---|
| Claude Code | `.claude/skills/` | `.claude/agents/sx-*.md`, except scout |
| Cursor | `.agents/skills/` | `.cursor/agents/sx-*.md`, except scout |
| Codex | `.agents/skills/` | `.codex/agents/sx-*.toml` |
| Antigravity | `.agents/skills/` | `.agents/agents/sx-*.md` |

Local rules occupy one managed block in `AGENTS.md`; Claude gets an import. Both skills and hooks render the same shell-quoted runtime locator, which works from subdirectories and paths with spaces. Global installs render an absolute command. The following shorter examples assume the execution root; `.simpleide/mem.py` remains a compatibility wrapper.

## Task and evidence commands

```sh
python3 .simpleide/sx.py mem search 'export timeout' --host codex --session SESSION
python3 .simpleide/sx.py mem add goal 'Fix export' --task export --size MEDIUM --request P1
python3 .simpleide/sx.py mem add criteria 'CSV is complete' --task export --body 'Include all rows in order'
python3 .simpleide/sx.py task bind export --request P1
python3 .simpleide/sx.py check --task export
python3 .simpleide/sx.py scope --base HEAD --allow 'src/**' --allow 'tests/**'
python3 .simpleide/sx.py pack --task export --base HEAD
python3 .simpleide/sx.py mem add result 'Delivered; checks inspected' --task export --refs 'artifact paths'
python3 .simpleide/sx.py task close export --outcome accepted --result P7 --by assistant --refs 'observed evidence'
python3 .simpleide/sx.py mem export --task export --out .simpleide/artifacts/export/final.md
python3 .simpleide/sx.py stats --task export
python3 .simpleide/sx.py doctor
```

Substitute actual captured request/result IDs from command output. If no capture exists, omit `--request`, then deliberately bind with `task bind export --host codex --session SESSION`. A new session never selects another session's newest task. Results do not close tasks. Closure requires accepted/failed/abandoned, the task's result ID, actor and evidence. `--by user` is attribution, not proof: reference the actual user's judgment. Blocked remains open. Completed slugs are immutable; use a fresh slug and optional `--retry-of export`.

First `check` proposes `.simpleide/config.json`; inspect and set `confirmed: true`. Logs stream to unique durable artifacts. Summaries include every configured check and distinguish failed, missing, interrupted, stale and unknown freshness. Accepted closure requires current checks, or an explicit task decision referenced by `--exception Pn`. Non-code tasks without configured checks can close using recorded evidence. See the documented fingerprint exclusions and rollback limits.

`stats --task` filters before aggregation, separates user-attributed, assistant and legacy-unverified acceptance, and prints token/cost coverage. Record observed usage with `stats --task export --tokens 123 --cost 0.01 --usage-source 'actual observation'`; missing usage remains unknown. Failed attempts remain in task totals.

## Worktrees and memory

```sh
python3 .simpleide/sx.py worktree add export parser
python3 .simpleide/sx.py worktree merge export
python3 .simpleide/sx.py check --task export
python3 .simpleide/sx.py worktree clean export
python3 .simpleide/sx.py worktree reconcile export
```

Commit the local runtime, manifest and host assets before adding workers, or verify a global installation. Worker checks run in the worker checkout and save to the parent ledger/artifacts via an ignored, validated context pointer. `pack` produces a versioned Markdown request/criteria artifact readable by planners without shell tools. Preflight covers all pieces before removal; ignored legacy evidence is archived and branches retained. Unmerged work requires a deliberate `--discard`. See recovery instructions for interrupted operations and moved stores.

Project records live in `.simpleide/project.db`. Shared lessons live in `~/.simpleide/shared.db` (`SIMPLEIDE_HOME` overrides that directory). `SIMPLEIDE_STORE` selects an existing evidence store; `SIMPLEIDE_PROJECT` still selects execution. Stores have persistent IDs, and future record numbers are never reused after deletion. Before first migration both project and shared databases receive SQLite backups.

`mem lesson ... --local` keeps a lesson local. Saving it again without --local promotes it or visibly queues it; `mem sync` retries. Search deduplicates by record identity and applies one total displayed limit. Use consistent --host/--session on search/show, optionally --search-id for an ambiguous search. Opening unrelated records, or opening without host/session or an explicit matching search ID, gets no search credit. Resolve questions explicitly with `mem resolve Pquestion --decision Pdecision`; references alone leave them open. Export retrieves every criterion and body; resume supplies a five-line retrieval pointer.

## Hooks and qualification

`--hooks` configures Claude, Cursor and Codex handlers. Antigravity hooks remain deferred. Stable blocking admission events reserve worker slots atomically; lifecycle starts become observations only when actually seen. Correlation requires matching host/session/call identity. Current documented Codex SubagentStart payloads do not provide the PreToolUse call ID; unmatched starts remain uncorrelated, pending reservations remain visible, and SubagentStart is advisory. Use `task dispatches` and explicit evidence-backed reconciliation, or perform roles in one parent session.

The shell guard covers common command forms, not arbitrary shell programs. Doctor establishes file/config/store health, not live registration or enforcement. [Observed host trials](docs/verified.md) separate actual command results from model reports, fixtures and unavailable evidence. [Comparison tasks](docs/comparison.md), user judgments, and keep/port/retire decisions remain pending; no comparison costs or acceptance are inferred.

Run local verification from the repository root:

```sh
python3.12 -m unittest discover -s simpleIDE/tests -v
python3.12 simpleIDE/docs/evidence/repair_verify.py --out /tmp/simpleide-repaired-audits.json
```

The independent CI step runs on the repository's existing Python 3.10/macOS and 3.11/Ubuntu matrix. Python 3.10 skips TOML parsing; 3.11+ parses generated TOML. Historical audit scripts/JSON are preserved and describe the prior CLI; use the repaired unittest cases for current release gates.
