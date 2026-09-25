# Architecture — Agent Dashboard

This package is the **shared control plane UI + gateway**. Agent runtimes stay in their own repos. The dashboard never owns Daily Coder SQLite or Research Forge ledgers; it talks through **adapters**.

## Goals

- One place to see and steer every orchestration agent
- Simple now; easy to improve or replace later
- Agent-specific logic stays out of the HTML

## Layers (replace any one without rewriting the rest)

| Layer | Location | Replace when… |
|---|---|---|
| Static UI | `agent_dashboard/web/` | You want React/Vue/etc. Keep calling the same `/api/*` routes. |
| HTTP gateway | `agent_dashboard/server.py` + `agent_dashboard/routes/` | You want FastAPI/Starlette. Reuse `Registry` + adapters. |
| Registry / config | `config/agents.json` + `registry.py` | New agent discovery or secrets layout. |
| Adapters | `agent_dashboard/adapters/*.py` | New agent, or deeper integration with an existing one. |
| Steer store | `steer_store.py` | You want SQLite or remote threads. Same message shape. |

## HTTP routing

`_Handler` in `server.py` authenticates, parses JSON, and delegates to `agent_dashboard/routes/dispatch.py`:

- **GET** → `meta`, `agents`, `setup`, `usage_route`, `home`, `docs`, `config_route`, `workspace`, `terminal` (first match wins)
- **POST** → `agents`, `setup`, `config_route`, `terminal`
- **PUT** → `workspace` (file write)

Hub-owned paths are listed in `routes/meta.py` (`HUB_OPENAPI_PATHS`) and exposed at `GET /api/openapi.json` for parity tests (G5).

## Unified API — agents (stable surface for the UI)

- `GET /api/health`
- `GET /api/agents`
- `GET /api/agents/{id}`
- `GET /api/agents/{id}/runs`
- `POST /api/agents/{id}/runs` body: `{ "request": "...", ... }` → **202**; usage event `run_start`
- `GET /api/agents/{id}/runs/{run_id}`
- `GET /api/agents/{id}/runs/{run_id}/activity`
- `POST /api/agents/{id}/runs/{run_id}/approve|resume|cancel` → usage events `approve` / `resume` / `cancel`

### Resume (Research Forge adapter, fail-closed)

`POST …/runs/{run_id}/resume` proxies to the adapter only — no second orchestrator. The gateway maps adapter results to HTTP status so **`accepted: false` is never returned with HTTP 202**:

| HTTP | Meaning |
|------|---------|
| **202** | Resume accepted; Wave 1 state was loaded and orchestration ran (or paused again). Body includes `"accepted": true`. |
| **404** | No persisted Wave 1 state (`error.code` = `NOT_FOUND`). |
| **403** | Persisted run was created in live mode but `wave_1_live` decision gate denies (`error.code` = `POLICY_DENIED`). |
| **502** | Other adapter failure (`accepted: false`, e.g. `INTERNAL_ERROR`). |

Structured errors use Research Forge `ForgeError` JSON shape in the `error` field (`code`, `message`, `details`).

`POST …/thread/apply` with `also_resume: true` uses the same mapping: if resume fails, the response status is 404/403/502 (not 200) and the body includes `resume` plus any notes already applied.
- `GET /api/agents/{id}/approvals`
- `GET /api/agents/{id}/activity?run_id=`
- `GET /api/agents/{id}/metrics`
- `GET /api/agents/{id}/thread?run_id=`
- `POST /api/agents/{id}/thread` body: `{ "text": "...", "run_id": "" }`
- `POST /api/agents/{id}/thread/apply` — mark queued notes applied; optional `also_approve` / `also_resume`
- `GET /api/agents/{id}/backend` · `POST /api/agents/{id}/backend` — Daily Coder backend control when supported (`action`: `start|stop|restart|set_token|set_provider`)

## Hub API extensions (v1)

These routes are implemented in `agent_dashboard/routes/*` and are part of the tabbed dashboard shell. They use the same auth gate as agent routes when enabled.

### Usage (`REC-DASH-USAGE`)

- `GET /api/usage?from=&to=&bucket=&agent_id=` — reads `{data_dir}/usage.jsonl`, optional `hour`/`day` buckets, plus per-agent normalized metrics
- Writers (server-side only): append on `POST …/runs`, `…/approve`, `…/resume`, `…/cancel`, and failed resume via `thread/apply`

### Home (`REC-DASH-HOME`)

- `GET /api/home/snapshot` — agents list, recent runs preview, last usage events; **5s TTL** cache with lock (`routes/home.py`)

### Documentation browser (`REC-DASH-DOCS`)

- `GET /api/docs` — whitelist of `docs/*.md` names under the project tree
- `GET /api/docs/{name}` — raw markdown text (UI renders via safe subset)

### Config overlay

- `GET /api/config/overlay` — read `{data_dir}/config_overlay.json`
- `POST /api/config/overlay` — allowlisted key **`workspace_roots` only** (`host` / `port` / `auth_required` rejected); unknown keys **400**; restart banner in UI (G10)

### Workspace jail (`REC-DASH-EDITOR-JAIL`)

Roots come from config merged with overlay — clients cannot invent roots.

- `GET /api/workspace/roots`
- `GET /api/workspace/tree?root=&path=&depth=` (depth 1–4)
- `GET /api/workspace/file?root=&path=`
- `PUT /api/workspace/file?root=&path=` body `{ "content": "..." }` — max **1 MiB**; skips `.git`, `node_modules`, `.venv*`

### Log shell / terminal registry (`REC-DASH-TERMINAL-SPAWN`)

Not interactive PTY — see [TERMINAL_ROADMAP.md](./TERMINAL_ROADMAP.md).

- `GET /api/terminal/profiles`
- `GET /api/terminal/sessions` · `POST /api/terminal/sessions` body `{ "profile_id", "cwd?" }`
- `GET /api/terminal/sessions/{session_id}` · `GET …/log` · `POST …/stop`

Sessions and logs live under `{data_dir}/terminal_sessions/`.

### Mobile subset

Phone-oriented clients should call only the routes in [MOBILE_API.md](./MOBILE_API.md) (no workspace/terminal).

### UI shell docs

- [UI_TABS.md](./UI_TABS.md) — hash routes, session keys, polling
- [IDE.md](./IDE.md) — workbench panes and persistence

## Adapter contract

Implement a class with:

- `id`, `name`, `description`
- `capabilities() -> list[str]`
- `health()`, `list_runs()`, `get_run()`, `start_run()`, `approve()`, `resume()`, `cancel()`, `pending_approvals()`, `activity()`, `metrics()`

Register it in `adapters/__init__.py` `ADAPTERS` map and add an entry to `config/agents.json`.

### Current adapters

| id | Module | Backend |
|---|---|---|
| `daily-coder` | `daily_coder.py` | HTTP proxy to `daily-coder serve` (sole LLM runtime) |
| `research-forge` | `research_forge.py` | Filesystem + optional package imports; inbox under `{data_dir}/research-forge/` |
| `daily-task` | `daily_task.py` | Browser RCC paste families; inbox under `{data_dir}/daily-task/` |

### Setup (providers + palette)

- `GET /api/setup/runtimes` — providers available to the composer (configured keys / mock / local)
- `GET|POST /api/setup/secrets` — proxy to Daily Coder secrets (never echoes values)
- `GET /api/setup/palette?agent_id=` — skills + subagents for slash `/` picker
- `GET /api/setup/expected-agents` — config vs loaded ids (stale-hub banner)

## Steering model (v1)

Messages live in the dashboard (`{data_dir}/threads.jsonl`, where `data_dir` comes from `resolve_data_dir()` / `AGENT_DASHBOARD_DATA`), not inside agent models.

1. User sends a note → status `queued`
2. At a safe checkpoint, **Mark applied (local)** only marks notes applied in the dashboard. **Approve** on a waiting run merges queued steer notes into the agent approval note (and optionally you can resume after applying).
3. Adapter receives the combined note on approve, or you resume after applying

This matches “steer at gates,” not interrupting an in-flight model call.

## Adding another agent (checklist)

1. Create `agent_dashboard/adapters/my_agent.py`
2. Add `"my_agent": MyAgentAdapter` to `ADAPTERS`
3. Append a block to `config/agents.json` with `adapter: "my_agent"` and options
4. Restart the dashboard (`python start.py` from `gui/`) — peer switcher and composer Agent drawer read `GET /api/agents`

## Replacing the website

Delete or ignore `agent_dashboard/web/` and point any front end at the same API. Or change `WEB_ROOT` in `server.py`. Keep CSP/auth headers in mind if you host elsewhere.

## Security / privacy defaults

- Binds to `127.0.0.1` by default
- `auth_required` is false locally; set true in config and pass `--token` for a shared LAN
- **API tokens are memory-only** — never written under `gui/` or into `config/`
- Runtime data (`data_dir`) is forced **outside** the project tree (temp dir or `AGENT_DASHBOARD_DATA`)
- Do not commit `.env`, `*.token`, or absolute machine paths

## Future (intentionally not in v1)

- Cloud deploy / multi-user auth
- Automatic cross-agent delegation
- Live token streaming chat into model contexts mid-call
- Heavy plugin framework
- Interactive PTY sidecar — [TERMINAL_ROADMAP.md](./TERMINAL_ROADMAP.md) (`REC-DASH-TERMINAL-PTY`)
- IDE AI live chat — [IDE_AI_ROADMAP.md](./IDE_AI_ROADMAP.md) (`REC-DASH-IDE-AI-LIVE`)

Document extensions here as you add them so the next agent can plug in without archaeology.
