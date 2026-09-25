# GUI (`gui/`)

Shared local GUI for all agent orchestration in this workspace (Python package **`agent_dashboard`**). Talk to agents, watch runs, approve gates, and queue steering notes — without baking UI into each agent package.

## Quick start (Windows / macOS / Linux)

**Requirements:** Python 3.10+

From this folder (`gui/`):

| Platform | Command |
|---|---|
| Windows (double-click or cmd) | `start.bat` |
| Windows (PowerShell) | `.\start.ps1` |
| macOS / Linux | `./start.sh` |
| Any OS | `python start.py` |

The launcher creates `.venv` if needed, installs this package editable, and opens **http://127.0.0.1:8866/**.

Optional flags (all scripts forward extras to `start.py`):

```bash
python start.py --port 8866
python start.py --host 127.0.0.1 --no-browser
python start.py --config config/agents.json
```

### Daily Coder & Setup

Configure providers and API keys under **APIs & abilities → Setup** (proxied to Daily Coder SecretStore). **Start work** auto-starts the Daily Coder backend when needed (default provider: `mock`). Only **available** runtimes appear in the Model chip. Live providers still require confirm. Use **Restart** / **Stop** in the session rail overflow (⋯) for power users.

If Daily Task (or any agent) is missing from the peer switcher, **restart the hub** after pulling adapter changes:

```bash
cd gui
python start.py --no-browser
```

If you started Daily Coder yourself in another terminal, either:
- click **Restart** in the session rail (takes over the port), or
- paste that process's `api_token` into **Save agent token** when the status says unauthorized.

## What you get (v1)

- Peer agent switcher (Daily Coder, Research Forge, Daily Task)
- Session rail (newest runs, Open, client-side archive)
- Composer chips + `/` skill/subagent palette + forced subagents
- Setup tab for providers/API keys
- Start work (auto-starts backend), list runs, resume / cancel
- Approvals at human gates
- Activity feed (events / artifacts)
- Steer / talk: messages queue until you **Apply** (checkpoint-style; no mid-flight interrupt)

## Layout

```
gui/
  start.py / start.bat / start.ps1 / start.sh   # cross-platform launchers
  config/agents.json                           # register agents
  docs/ARCHITECTURE.md                         # how to extend / replace pieces
  agent_dashboard/
    server.py                                  # unified API + static host
    registry.py                                # loads adapters
    steer_store.py                             # conversation JSONL
    adapters/                                  # one module per agent
    web/                                       # replaceable static UI
```

## Privacy

- API tokens for agent backends are kept **in memory only** while the hub process runs. They are not written under `gui/`.
- Runtime notes/inbox files go to an OS temp location outside this repo (`AGENT_DASHBOARD_DATA` to override), never into the project folder.
- Do not put secrets in `config/agents.json`.

## Docs

**SSOT:** [`gui/docs/`](docs/) — prefer editing here. `gui/agent_dashboard/docs/` is a duplicate; do not maintain both.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for adapter contracts, how to add an agent, and how to swap the UI.
