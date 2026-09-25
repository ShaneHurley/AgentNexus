# UI tabs — hash routes, session keys, polling

The dashboard shell is a **six-tab** app (`REC-DASH-TABS-SHELL`). Navigation uses the URL hash only (no History API paths in v1). Modules live under `agent_dashboard/web/`.

## App tabs and hash routes

| Tab (UI label) | `data-tab` | Default hash | Optional segments |
|----------------|------------|--------------|-------------------|
| Home | `home` | `#/home` | — |
| Agent | `agent` | `#/agent` | `#/agent/{agentId}` · `#/agent/{agentId}/{runId}` |
| Documentation | `docs` | `#/docs` | `#/docs/{docName}` (e.g. `#/docs/ARCHITECTURE.md`) |
| APIs & abilities | `apis` | `#/apis` | — |
| Usage | `usage` | `#/usage` | — |
| IDE | `ide` | `#/ide` | — |

**Router:** `router.js` exports `APP_TABS`, `parseHash()`, `hashFor()`, and `initRouter()`.

- Unknown first segment → redirect to `#/home` (`redirect: true`).
- Empty hash on load → `#/home`.
- Docs path: segments after `docs/` are joined and decoded (supports nested-looking names in the hash; server docs API still serves flat `docs/*.md` names).

**Boot:** `app.js` mounts one tab module into `#viewport` on hash change. Agent tab receives `agentId`, `runId`, and a `navigate()` helper that updates the hash.

**Hash sync:** When the app tab is already active, `app.js` calls `syncRoute(route)` on Agent and Docs modules so `#/agent/…` and `#/docs/…` deep links update without remounting.

**Agent UX:** Horizontal **peer agent switcher** (Daily Coder | Research Forge | Daily Task) plus collapsible session groups (5 newest, Show all, client archive). **Start work** calls `ensureBackend()` before `POST …/runs`. Composer chips: Agent / Model (from Setup runtimes) / Context / Thinking / Subagents. Type `/` in the prompt for skills & subagents. Configure providers and API keys under **APIs & abilities → Setup**.

After changing adapters or `agents.json`, **restart** the hub (`python start.py` from `gui/`). A stale process loads only the agents it started with.



**Mobile (G4):** At viewport width ≤768px, the IDE tab button is hidden (`styles.css`). Mobile clients should use the routes in [MOBILE_API.md](./MOBILE_API.md) only.

## Session storage keys

All keys are in `state.js` (`SESSION_KEYS`). Values are **metadata only** — never file bodies or log text (see [IDE.md](./IDE.md)).

| Key | Purpose |
|-----|---------|
| `ad_agent` | Last selected agent id (Agent tab). |
| `ad_run` | Last selected run id (Agent tab). |
| `ad_token` | API bearer token for `Authorization` (header field). |
| `ad_provider` | Daily Coder provider preference (`mock` default). |
| `ad_ide_layout` | IDE workbench layout v1 JSON (metadata-only). |
| `ad_archived_runs` | Client archive map in **localStorage** (`agentId:runId` → true). |
| `ad_rail_collapsed` | Session rail collapsed flag. |
| `ad_rail_agent_open` | Per-agent expand/collapse JSON. |
| `ad_composer_context` | Composer Context chip (UI pref). |
| `ad_composer_thinking` | Composer Thinking chip (UI pref). |
| `ad_show_archived` | Session rail “Show archived” toggle. |
| `ad_forced_subagents` | Per-agent forced subagent id list (JSON). |
| `ad_agent_sections` | Agent tab disclose open/closed map. |

**Quota:** `setItem()` catches `QuotaExceededError`, drops `ad_ide_layout`, and retries once. IDE layout writes also reject payloads >200KB.

## Polling and refresh rules

Polling must avoid request storms when the document is hidden or the wrong tab is active (**G8**). The locked design uses a central **`poll.js` registry** (T28): register/unregister tick handlers per feature; run ticks only when `document.visibilityState === "visible"` and the handler’s app tab is active.

| Source | When it runs | Interval / trigger | Endpoints (typical) |
|--------|----------------|----------------------|---------------------|
| Header health | App boot; manual **Refresh** | One-shot | `GET /api/health` |
| Home snapshot | Active tab `home`; visible document | ~5s (align with server TTL) | `GET /api/home/snapshot` |
| Agent tab | Active tab `agent`; mounted; visible | 6s + immediate tick on `visibilitychange` → visible | `GET /api/agents`, run/activity/approvals/thread as needed |
| Usage tab | Active tab `usage`; visible | On mount + manual refresh (charts may poll sparingly) | `GET /api/usage` |
| Docs / APIs | Those tabs active | On mount / navigation only | `GET /api/docs`, `GET /api/openapi.json` |
| IDE log shells | Active tab `ide`; **visible log-shell tab** in a pane | ~2–4s per session (budget when multiple shells) | `GET /api/terminal/sessions/{id}/log` |
| IDE file editor | No poll | Load/save only | `GET`/`PUT /api/workspace/file` |

**Guards (all pollers):**

- Skip tick if `document.hidden` or `!navigator.onLine`.
- Skip if the poller’s app tab is not the active shell tab.
- Use an in-flight guard so overlapping requests do not stack.

**Current implementation notes:** The Agent tab already uses a 6s interval with visibility and in-flight guards while mounted. Home snapshot polling and the shared `poll.js` registry are scheduled in the tabbed-shell plan; until the registry lands, do not assume Home or IDE pollers are wired from a single coordinator.

## Related docs

- [IDE.md](./IDE.md) — workbench panes and side rail
- [MOBILE_API.md](./MOBILE_API.md) — mobile-safe HTTP subset
- [ARCHITECTURE.md](./ARCHITECTURE.md) — gateway routes and adapters
