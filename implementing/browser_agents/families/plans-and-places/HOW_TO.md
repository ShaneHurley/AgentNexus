# How to use Plans & Places

1. Fill `examples/task-packet.main.yaml` (or copy fields): objective, dates, locations, budget, dietary/accessibility **fixed constraints**, evidence refs.
2. Pick a variant (or use family main to classify):

| Need | `browser_variant` |
|------|-------------------|
| Day-by-day trip | `trip-itinerary` |
| What to pack | `packing-list` |
| Errand routing | `errand-route` |
| Event run-of-show | `event-run-of-show` |
| Menu vs allergies | `dietary-cross-check` |
| Find activities/events | `discover-events` |
| Rain/heat alternates | `weather-contingency` |
| Group conflict reconciliation | `group-constraints` |
| Budget tradeoffs | `budget-optimizer` |

3. Paste `variants/<slug>/AGENT_MESSAGE.md` (or family main) into a **new chat** with packet + tabs/attachments.
4. Treat bookings and prices as **PROPOSED** until you confirm. Re-run with corrections via `CORRECTION` follow-up class.

**Safety:** Allergies and medical needs are constraints, not preferences. Verify food and travel-critical items before relying on the plan.

**Legacy:** `everyday/compass/contextual-concierge` → this family; `experience-architect` event/diet → `event-run-of-show` / `dietary-cross-check`.
