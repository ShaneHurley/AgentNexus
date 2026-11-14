# Model routing

Defaults are in `.simpleide/models.json`. Planner: strong tier. Worker: cheapest tier that can complete the brief. Tester: independent capable tier. Reviewer: above worker tier. Scout: cheapest tier. On a failed brief: correct it and retry once; then move that piece one tier up; then main session handles it or asks the user. Never retry the same brief a third time. Verify the actual model used in live sessions; configuration is not proof.
