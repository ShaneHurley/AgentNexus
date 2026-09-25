QUALIFYING_TRIGGERS={"high_risk_irreversible","unresolved_architecture_choice","contradictory_verified_evidence","two_failed_repair_cycles"}

def authorize_frontier(trigger, lower_tier_attempts, calls_used, max_calls=1):
    if trigger not in QUALIFYING_TRIGGERS: return False, "trigger_not_qualified"
    if lower_tier_attempts < 1: return False, "lower_tier_not_attempted"
    if calls_used >= max_calls: return False, "frontier_budget_exhausted"
    return True, "authorized"

def compress_decision_brief(question, options, evidence, constraints, criterion):
    return {"question":question,"options":options,"evidence":evidence,"constraints":constraints,"decision_criterion":criterion}
