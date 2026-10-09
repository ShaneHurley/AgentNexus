# AgentNexus — macOS Quick Start Guide

This repository contains multi-agent frameworks, IDE orchestrators, and a web dashboard.

---

## 1. One-Command Setup & Launch

From the repository root (`AgentNexus`), run:

```bash
./start_mac.sh
```

### What this script does:
1. **Detects Python 3.10+**: Automatically finds a compatible Python runtime.
2. **Configures `.venv`**: Sets up the local virtual environment.
3. **Installs Local Packages**: Links `ai_agents_repo`, `agent-core`, and `ide-bridge`.
4. **Synchronizes IDE Agents**: Refreshes `.cursor/`, `.claude/`, and `.github/` agent definitions from canonical sources.
5. **Validates Repo Health**: Runs phase validation (`ai_agents_repo.validate --phase F0`).
6. **Launches the Dashboard**: Prompts you to launch the web dashboard immediately.

---

## 2. Quick Commands

### Start the GUI Dashboard Directly:
```bash
./start_mac.sh --gui
```
*Or via the GUI directory:*
```bash
cd gui
python start.py   # Opens http://127.0.0.1:8866/
```

### Run Repository Checks:
```bash
source .venv/bin/activate
python -m ai_agents_repo.validate --phase F0
python agents/ide/scripts/sync_ide_agents.py --check
```

### Test IDE Bridge / Agent Core:
```bash
source .venv/bin/activate
ide-bridge doctor
python -m agent_core validate-registry
```
