# IDE AI roadmap — live chat

**Recommendation ID:** `REC-DASH-IDE-AI-LIVE`

## Shipped in v1 (skeleton)

The IDE side rail includes an **AI** sub-tab that is intentionally non-functional:

- Banner: *“Preview — not connected. No model calls from this panel.”*
- Send control **disabled**
- **No `fetch`** — DOM-only placeholder (**G6**)

Agent steering remains on the **Agent** tab via `/api/agents/{id}/thread` and gate actions (approve/resume). Do not confuse the IDE preview with live steer.

See [IDE.md](./IDE.md).

## Problem

Developers want in-context help while editing allowlisted files. A disconnected skeleton avoids looking “broken” next to live steer but does not deliver value.

## Target (live chat)

| Piece | Direction |
|-------|-----------|
| Context | Optional: current file path (metadata), selection snippet, active agent/run ids — **never** exfiltrate out-of-jail paths |
| Backend | Reuse steer store + adapter thread, or a dedicated “IDE assistant” channel with explicit user consent |
| UX | Distinct from Agent tab: scoped to workbench session; clear label when connected |
| Safety | Same auth/token rules; rate limits; no auto-approve/resume without explicit user action |
| Streaming | Optional later; v1 live chat may be request/response like steer notes |

## Non-goals

- Replacing the Agent tab for run orchestration
- Hidden model calls from the skeleton panel (forbidden in v1)
- Cloud multi-tenant chat history in the hub data dir without a designed retention policy

## Dependencies

- IDE Explorer + file tabs (open path metadata only in layout)
- Poll/registry stability (G8) so AI panel does not compete with run/log pollers
- Product decision: shared thread vs separate `ide_thread` namespace per agent

## Success criteria

- User sends a message from IDE AI and sees it queued/delivered with visible connection state
- pytest proves IDE AI module performs no network I/O until feature flag or explicit “Connect” enables it
- Documentation updated in [ARCHITECTURE.md](./ARCHITECTURE.md) if new routes are added
