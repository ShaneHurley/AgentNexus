# Agents hub

All **agent material** lives under this folder: IDE orchestrators, research and coding engines, browser paste harnesses, and shared skills/schemas.

| Folder | Open when you… |
|--------|----------------|
| [`ide/`](ide/) | Edit canonical IDE agents, run sync/import, install `ide-bridge`, or change PolicyGateway hooks |
| [`research/`](research/) | Work on Research Forge waves, research browser families, or RF agent SSOT |
| [`coding/`](coding/) | Work on Daily Coder phases, coding browser families, or DC agent SSOT |
| [`daily-task/`](daily-task/) | Route lifestyle browser families (`driver.py`) or mission-control paste sequences |
| [`shared/`](shared/) | Personal/shared skills, JSON schemas, `agent-core`, browser harness `_shared`, repo layout tooling |

**Run the stack:** use [`../gui/`](../gui/) (dashboard). **Learn:** [`../docs/`](../docs/). **Verify:** [`../tests/`](../tests/), `pip install -e ./agents/shared/ai_agents_repo`, then `python -m ai_agents_repo.validate --phase F0`.

IDE projections (Cursor / Claude / Copilot) stay at the **repository root** (`.cursor/`, `.claude/`, `.github/`) for editor discovery — generated from [`ide/canonical/`](ide/canonical/).
