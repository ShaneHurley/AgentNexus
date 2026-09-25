# Recommendation Scoring

## Required dimensions

Score each dimension from 0–10, except `reversibility` from 0–5 and `evidence_confidence` from 0–100:

- importance
- expected impact
- difficulty
- time to value
- risk reduction
- ecosystem leverage
- downside risk
- operational burden
- reversibility
- evidence confidence

Also score `safety_effect` from -5 to +5 for the `DO_NOT_ADOPT` gate. Every value requires a short rationale and evidence IDs.

## Formula

Calculate without substituting another model:

```text
benefit =
  .25*importance +
  .25*expected_impact +
  .15*risk_reduction +
  .15*ecosystem_leverage +
  .10*time_to_value +
  .10*(2*reversibility)

burden =
  .50*difficulty +
  .25*downside_risk +
  .25*operational_burden

raw_priority =
  .70*benefit +
  .30*(11-burden)

confidence_adjusted_priority =
  round(raw_priority*evidence_confidence/100, 2)
```

Round displayed `benefit`, `burden`, and `raw_priority` to two decimals after calculating from unrounded inputs. Confidence zero always produces adjusted priority zero.

## Roadmap bands

Evaluate in this order:

1. `DO_NOT_ADOPT` when downside risk >= 8 and expected impact <= 4, or safety effect <= -3.
2. `NOW` when adjusted priority >= 7.5, confidence >= 70, and downside risk <= 6.
3. `NEXT` when adjusted priority >= 5.5 and confidence >= 55.
4. `EXPERIMENT` when adjusted priority >= 3.5 and confidence >= 30.
5. Otherwise `DEFER`.

Unsupported proposals may not be promoted above `EXPERIMENT`; use `DEFER` when even a safe experiment lacks support. Preserve rejected candidates as `DO_NOT_ADOPT` when warranted.

## Sensitivity

Recalculate with:

- evidence confidence reduced by 20 points, floored at zero;
- difficulty increased by 2 points, capped at 10;
- all other values unchanged.

Record stressed adjusted priority, stressed band, and whether the recommendation changes roadmap band.

## Required recommendation fields

Each recommendation includes:

- ID, title, proposal, rationale, evidence IDs, and fact IDs;
- all dimensions, reasons, and calculated values;
- effects on speed, accuracy, safety, maintainability, cost, workflow, and users;
- prerequisites, dependencies, feasibility, affected roles and tools;
- positive and negative secondary effects;
- smallest safe experiment;
- validation metric, success threshold, stop condition, and rollback condition;
- raw and adjusted priority, sensitivity result, roadmap band, and rank.

## Ranking

Rank recommendations deterministically by:

1. adjusted priority descending;
2. evidence confidence descending;
3. downside risk ascending;
4. difficulty ascending;
5. recommendation ID lexicographically.

Scores support rationale; they never replace it.
