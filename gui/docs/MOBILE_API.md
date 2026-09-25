# Mobile API subset

**Recommendation ID:** `REC-DASH-MOBILE-API`

For phones and other clients that **do not** load the dashboard IDE (hidden ≤768px), use **only** the routes below. Do not depend on workspace, terminal, config overlay, docs browser, or OpenAPI from the mobile shell unless you intentionally expand scope.

Authentication: when the hub sets `auth_required`, send the same bearer token as the web UI (`Authorization: Bearer …`).

Base URL: hub origin (default `http://127.0.0.1:<port>`).

---

## `GET /api/health`

Liveness and config hint.

**Response (200):** `{ "ok": true, "service": "agent-dashboard", "agents": <count>, "auth_required": <bool> }`

---

## `GET /api/agents`

List registered agents.

**Response (200):** JSON array of agent summaries (adapter-defined fields; includes `id`, `name`, online/health hints).

---

## `GET /api/agents/{id}/runs`

List runs for one agent.

**Query:** `limit` (optional, server-capped).

**Response (200):** run list from the adapter.

---

## `POST /api/agents/{id}/runs`

Start a run.

**Body (JSON):**

```json
{ "request": "your task or prompt text" }
```

Additional keys may be passed through to the adapter; **`request` is required**.

**Response:** **202** with adapter result (includes `run_id` when accepted). **400** if `request` missing. **404** unknown agent.

---

## `GET /api/agents/{id}/metrics`

Agent-specific metrics blob, normalized for usage views when aggregated via `/api/usage`.

**Response (200):** adapter metrics object.

---

## `GET /api/usage`

Usage events and optional buckets.

**Query (all optional):**

| Param | Meaning |
|-------|---------|
| `from` | ISO timestamp lower bound |
| `to` | ISO timestamp upper bound |
| `agent_id` | Filter by agent |
| `bucket` | `hour` or `day` for aggregated counts |

**Response (200):** `{ "events", "buckets", "bucket", "metrics", "event_total" }`

Events are append-only rows `{ ts, event, agent_id, run_id, meta }` written on run lifecycle actions server-side.

---

## `GET /api/home/snapshot`

Compact dashboard snapshot for a home screen (server cache **5s TTL**, thread-safe).

**Response (200):** `{ "generated_at", "agents", "recent_runs", "recent_usage_events", "auth_required" }`

---

## Not in this document

The following exist on the hub for the full web app but are **omitted** from the mobile contract:

- `/api/workspace/*`
- `/api/terminal/*`
- `/api/docs/*`, `/api/config/overlay`, `/api/openapi.json`
- Agent steer/thread, approve/resume/cancel (use full [ARCHITECTURE.md](./ARCHITECTURE.md) if you need them)

There is **no** separate `start_run` route; use **`POST /api/agents/{id}/runs`** with `{ "request": "..." }`.
