# IDE workbench

**Recommendation ID:** `REC-DASH-IDE`

The **IDE** app tab is a **workbench**, not a full IDE: allowlisted folder browse, plain-text edit, and **log shell (read-only)** panes. Product copy and UI labels must stay honest (**C4** in the tabbed-shell plan).

## Scope (v1)

| In scope | Out of scope (roadmap) |
|----------|-------------------------|
| Six pane layout presets | Drag-resize panes, drag-reorder tabs |
| File tabs + log-shell tabs | Interactive PTY ([TERMINAL_ROADMAP.md](./TERMINAL_ROADMAP.md)) |
| Explorer + open-tabs list | CodeMirror / LSP |
| Side rail: **Explorer** \| **AI** (skeleton) | Live AI chat ([IDE_AI_ROADMAP.md](./IDE_AI_ROADMAP.md)) |
| Server jail FS + terminal spawn APIs | Client-invented workspace roots |

Entry hash: `#/ide`. Hidden on viewports ≤768px; use [MOBILE_API.md](./MOBILE_API.md) for remote control without the workbench.

## Layout presets

CSS grid classes (see `styles.css`):

| Preset id | Pane count | Grid class |
|-----------|------------|------------|
| `single` | 1 | `ide-preset-single` |
| `split-h` | 2 | `ide-preset-split-h` |
| `split-v` | 2 | `ide-preset-split-v` |
| `halves-h` | 2 | `ide-preset-halves-h` |
| `halves-v` | 2 | `ide-preset-halves-v` |
| `quarters` | 4 | `ide-preset-quarters` |

Toolbar **Layout ▾** switches preset (`ide/layout.js` when implemented).

## Tab redistribution algorithm

When the preset changes, let **N** = new pane count. **Do not drop tabs.**

1. Flatten all document tabs in **pane order** (pane index 0, then 1, …), preserving order within each pane.
2. Assign tab at flat index **i** → pane **`i % N`** (round-robin).
3. If `activePaneId >= N`, set `activePaneId = 0`.
4. Per pane: keep `activeTabId` if that tab still lives in the pane; otherwise select the first tab in the pane.
5. Log-shell tabs: poll targets rebind by **session id** (unchanged across moves).

### Test vectors (documented for unit tests)

**Vector A — single → split-h (N=2)**  
Panes: P0 `[f1, f2]`, P1 `[f3]`. Flatten → `[f1, f2, f3]`. Assign → P0 `[f1, f3]`, P1 `[f2]`.

**Vector B — quarters → single (N=1)**  
Four panes with one tab each: `[a], [b], [c], [d]`. Flatten → `[a, b, c, d]`. Assign → P0 `[a, b, c, d]`.

**Vector C — active pane clamp**  
`activePaneId = 3`, switch to `split-h` (N=2) → `activePaneId = 0`.

**Vector D — active tab survival**  
Tab `f2` was active in P0; after move to P1, if `f2` is in P1, P1’s active tab stays `f2`.

## Document tabs

Types: **`file`** | **`logshell`**.

| Action | Behavior |
|--------|----------|
| New file | Empty file tab; save via workspace PUT |
| Open (Explorer) | Open allowlisted path in active or chosen pane |
| New log shell | Pick profile → spawn session → logshell tab |
| Close file | Confirm if dirty |
| Reorder | **Move left / move right** only (v1; no drag) |

File editor: textarea + `GET`/`PUT /api/workspace/file`. v1 is **last-write-wins**; show server `mtime` when present.

## Side rail — Explorer and AI

- Collapse/expand persisted via layout metadata (`sideCollapsed`, `sideTab`: `explorer` | `ai`).
- **Explorer:** tree from `GET /api/workspace/tree`; roots from `GET /api/workspace/roots` only (config + overlay). **Open tabs** list focuses pane + tab.
- **AI:** skeleton only (**G6**). Banner: *“Preview — not connected. No model calls from this panel.”* Send disabled; **zero `fetch`** from the AI panel. Distinct from Agent tab steer/thread.

## Log shell vs PTY

v1 **log shell** ( `REC-DASH-TERMINAL-SPAWN` ):

- UI label: **“Log shell (read-only)”**
- Spawn: `POST /api/terminal/sessions` with `profile_id`
- Tail: `GET /api/terminal/sessions/{id}/log`
- Stop: `POST /api/terminal/sessions/{id}/stop`
- No stdin API; no WebSocket

Interactive terminal: [TERMINAL_ROADMAP.md](./TERMINAL_ROADMAP.md).

## Metadata-only persistence

Session key: **`ad_ide_layout`** (`state.js`), schema **`version: 1`**.

**Store:**

- Preset id, pane ids, active pane
- Per pane: tab list with `{ id, type, label, path? | sessionId?, dirty? }`
- Side rail: collapsed flag, active sub-tab

**Never store:** file contents, log text, terminal output, steer messages.

On `QuotaExceededError`, layout may be evicted before other keys (see `setItem` in `state.js`).

## Module map (target)

| Module | Role |
|--------|------|
| `tabs/ide.js` | Mount workbench shell |
| `ide/layout.js` | Presets + redistribution |
| `ide/panes.js` | Tab model + persist |
| `poll.js` | Log-shell poll registration (G8) |

Stub UI may appear in `tabs/ide.js` until later phases land; behavior above is the contract for G12.

## Security

Workspace and terminal routes use the **same auth** as `/api/agents/*` when `auth_required` is enabled. Paths are jail-checked server-side (`workspace_jail.py`).
