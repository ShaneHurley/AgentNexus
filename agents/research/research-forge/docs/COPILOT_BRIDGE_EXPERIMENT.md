# Copilot bridge experiment (REC-COP-BRIDGE)

**Band:** EXPERIMENT — optional interoperability, **not** a replacement for Daily Coder.

## Goal

Time-box a spike that drives **GitHub Copilot CLI / Agent SDK** as an external runtime via Daily Coder’s existing **`command`** (or **`http`**) provider, with **read-only** tools only. Compare cost, control, and auditability against the native orchestrator.

## What this is not

| Anti-pattern | Band |
|--------------|------|
| Copilot as primary orchestration engine | **DO_NOT_ADOPT** (`REC-COP-REPLACE`) |
| Embedding Copilot IDE inside Agent Dashboard | **DO_NOT_ADOPT** (`REC-COP-IDE`) |

## Smallest safe experiment

1. Install Copilot CLI / SDK per current GitHub docs (operator machine only).
2. Configure Daily Coder:

```json
{
  "provider": "command",
  "provider_command": "copilot"
}
```

Or set env `DAILY_CODER_PROVIDER_COMMAND` and enable the dashboard `command` option (requires config).

3. Start with **`--live`** only after confirming the command cannot write outside the jail without ToolBroker.
4. Run one **read-only** request (e.g. summarize `repository.status`).
5. Capture: wall time, token/cost if billed, whether PolicyGateway still mediates file access.

## Success / stop

| Metric | Success | Stop / rollback |
|--------|---------|-----------------|
| Dual-runtime overhead | < 2× native mock path for same task | Abandon bridge if > 3× with no quality gain |
| Policy bypass | Zero escapes past ToolBroker | Immediate stop if Copilot writes without broker |
| Operator clarity | Single documented path | Keep mock + Gemini/OpenRouter as defaults |

## Related

- Dashboard: `command` / `http` remain disabled until configured.
- Preferred live models remain **Gemini** / **OpenRouter**.
- Security checklist: [security-review-checklist.md](./security-review-checklist.md)
