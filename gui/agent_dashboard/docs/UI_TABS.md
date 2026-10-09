# Workspace shell, sessions, and polling

The dashboard uses a workspace shell rather than the retired six-app-tab/hash-router layout. The shell is defined in `agent_dashboard/web/index.html`; `app.js` restores the compatibility API token and boots `workspace.js`.

## Shell regions

| Region | Stable element | Behavior |
|--------|----------------|----------|
| Top bar | `wsTopbar` | Branding, agent launch controls, health, refresh, settings |
| Workspace body | `wsBody` | Sidebar, chat area, and optional panel dock |
| Sidebar | `wsSidebar` | Session rail and daily tasks |
| Chat area | `wsChatArea` | Active session tab strip and chat panel |
| Session tabs | `wsSessionTabs` | One tab per active agent run; not URL hash routes |
| Panel dock | `wsPanelDock` | Optional browser, code, and plan panels |
| Status bar | `wsStatusbar` | Agent, session, panel, and clock status |

`workspace.js` initializes these regions, loads agents, restores session metadata, wires resize handles and shortcuts, and manages chat/dock/sidebar rendering. `index.html` loads `/app.js` as an ES module. UI tests should assert stable shell IDs, accessible roles, and that referenced modules exist; they should not assert retired `data-tab` values or `#viewport`.

After changing adapters or `agents.json`, restart the hub (`python start.py` from `gui/`) so the registry is reloaded.

## Session storage keys

All keys are in `state.js` (`SESSION_KEYS`). Values are **metadata only** — never file bodies or log text (see [IDE.md](./IDE.md)).

| Key | Purpose |
|-----|---------|
| `ad_agent` | Last selected agent id (Agent tab). |
| `ad_run` | Last selected run id (Agent tab). |
| `ad_run_by_agent` | Per-agent active run IDs, with `ad_run` retained as a legacy fallback. |
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

**Quota:** `setItem()` catches `QuotaExceededError`, drops `ad_ide_layout`, and retries once. IDE layout writes also reject payloads >200KB. These keys store metadata only; archived-run flags use `localStorage`, other session state uses `sessionStorage`.

## Polling and refresh rules

Polling is coordinated by `poll.js`. A poller runs only when the document is visible, the browser is online, its declared app area is active, and that poller has no request in flight. The registry ticks every six seconds and requests an immediate tick when visibility returns. `workspace.js` registers the `workspace-tick` poller for the `workspace` area.

| Source | When it runs | Interval / trigger | Endpoints (typical) |
|--------|----------------|----------------------|---------------------|
| Workspace refresh | `workspace` active; page visible and online | 6s + visibility restoration | `GET /api/agents`, agent activity, session/sidebar data |
| User actions | On demand | Click or submit | Relevant `/api/*` endpoint |
| Workspace edits | On demand | Load/save only | Workspace file endpoints |

**Guards (all pollers):**

- Skip tick if `document.hidden` or `!navigator.onLine`.
- Skip if the poller’s app tab is not the active shell tab.
- Use an in-flight guard so overlapping requests do not stack.

**Current implementation notes:** `poll.js` provides the shared visibility/online/active-area/in-flight guards. `workspace.js` registers the workspace refresh callback; individual user actions remain on-demand.

## Related docs

- [IDE.md](./IDE.md) — workbench panes and side rail
- [MOBILE_API.md](./MOBILE_API.md) — mobile-safe HTTP subset
- [ARCHITECTURE.md](./ARCHITECTURE.md) — gateway routes and adapters
