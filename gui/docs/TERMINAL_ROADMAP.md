# Terminal roadmap — interactive PTY

**Recommendation ID:** `REC-DASH-TERMINAL-PTY`

## Shipped in v1 (log shell)

The dashboard ships **log shells**, not interactive terminals:

- Profiles: `config/terminal_profiles.json` · `GET /api/terminal/profiles`
- Spawn detached processes with log files under `{data_dir}/terminal_sessions/`
- Poll log tail · stop session via HTTP
- UI: **“Log shell (read-only)”** — no stdin, no WebSocket

See [IDE.md](./IDE.md) and hub routes in [ARCHITECTURE.md](./ARCHITECTURE.md).

## Problem

Log tails are enough for batch commands and CI-style tasks. They are **not** enough for REPLs, pagers, password prompts, or full-screen TUIs. Users expect a real terminal when the product says “terminal.”

## Target (PTY sidecar)

| Piece | Direction |
|-------|-----------|
| Process | PTY-backed child (platform-specific: ConPTY on Windows, `openpty` elsewhere) |
| Transport | WebSocket or SSE from a **small sidecar** next to the stdlib hub (hub stays CSP-friendly) |
| UI | xterm.js (or similar) in an IDE pane; distinct from log-shell tabs |
| Security | Same auth as hub; session allowlist; idle timeout; max sessions; no arbitrary command injection from other LAN clients |
| Lifecycle | Spawn/profile parity with log shell registry where possible |

## Non-goals for PTY milestone

- Replacing SSH or system-wide shell access
- Embedding PTY inside `ThreadingHTTPServer` without a sidecar (keep hub simple)
- stdin for v1 log shells (remain read-only)

## Dependencies

- Stable log-shell spawn/stop (`REC-DASH-TERMINAL-SPAWN`) and G9 auth tests
- IDE pane model + poll registry (G8) for multiple sessions
- CSP review for any new static vendor script (prefer vendored xterm bundle under `web/`)

## Success criteria

- User can run an interactive program (e.g. Python REPL) from the IDE with keystrokes round-tripped
- Stop/kill reliably on Windows (`CREATE_NEW_PROCESS_GROUP` semantics documented)
- Hub OpenAPI documents only HTTP; PTY sidecar documents its own small API
