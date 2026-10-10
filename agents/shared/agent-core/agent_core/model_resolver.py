"""Deterministic fail-closed eligibility before cost selection."""
from __future__ import annotations
import math
from agent_core.model_catalog import CatalogSnapshot, fields, strings, number, digest, canonical, routing_policy_digest


class ModelResolver:
    def __init__(self, catalog, policy):
        self.catalog = CatalogSnapshot.from_dict(catalog.data if isinstance(catalog, CatalogSnapshot) else catalog)
        fields(policy, {"schema_version", "roles"}, {"schema_version", "roles"})
        if type(policy["schema_version"]) is not int or policy["schema_version"] != 1 or not isinstance(policy["roles"], dict):
            raise ValueError("unsupported policy schema")
        self.routing_policy_hash = routing_policy_digest(policy)
        models = self.catalog.data["models"]
        for role, spec in policy["roles"].items():
            if not isinstance(role, str) or not role: raise ValueError("invalid role")
            required = {"allowed_models", "default", "fallback", "reviewed_baseline", "evaluation_class", "qualifications"}
            fields(spec, required, required)
            strings(spec["allowed_models"], "allowed_models")
            if not spec["allowed_models"] or any(alias not in models for alias in spec["allowed_models"]): raise ValueError("missing model reference")
            for key in ("default", "fallback"):
                if spec[key] is not None and spec[key] not in spec["allowed_models"]: raise ValueError("invalid " + key)
            if spec["default"] is None or type(spec["reviewed_baseline"]) is not bool: raise ValueError("invalid baseline")
            if not isinstance(spec["evaluation_class"], str) or not spec["evaluation_class"]: raise ValueError("invalid evaluation class")
            if not isinstance(spec["qualifications"], dict): raise ValueError("invalid qualifications")
            for alias, report in spec["qualifications"].items():
                if alias not in spec["allowed_models"]: raise ValueError("missing qualification model")
                self._validate_report(role, spec, alias, report)
        # Round-trip seals the policy against mutation by callers.
        import json
        self.policy = json.loads(canonical(policy))
        self.policy_hash = digest(self.policy)

    def _validate_report(self, role, spec, alias, report):
        required = {"schema_version", "role", "evaluation_class", "catalog_hash", "policy_hash", "corpus_hash", "candidate", "baseline", "evidence_kind", "records_hash", "candidate_metrics", "baseline_metrics", "matched_baseline", "qualified", "exclusion_reasons", "report_hash"}
        fields(report, required, required)
        if report["policy_hash"] != self.routing_policy_hash:
            raise ValueError("qualification routing policy mismatch")
        body = {k:v for k,v in report.items() if k != "report_hash"}
        if report["report_hash"] != digest(body): raise ValueError("qualification integrity mismatch")
        if type(report["schema_version"]) is not int or report["schema_version"] != 1 or report["role"] != role or report["evaluation_class"] != spec["evaluation_class"] or report["candidate"] != alias or report["baseline"] != spec["default"] or report["catalog_hash"] != self.catalog.hash:
            raise ValueError("incompatible qualification")
        metrics_fields={"distinct_tasks", "runs", "successful_tasks", "repeated_tasks", "wilson_lower_95", "critical_policy_violations", "known_cost_usd", "unknown_cost_records", "successful_task_cost_usd", "input_tokens", "output_tokens", "tool_calls", "repairs", "escalations", "latency_ms"}
        for key in ("candidate_metrics", "baseline_metrics"):
            fields(report[key],metrics_fields,metrics_fields)
            metrics=report[key]
            counts={"distinct_tasks", "runs", "successful_tasks", "repeated_tasks", "critical_policy_violations", "unknown_cost_records", "input_tokens", "output_tokens", "tool_calls", "repairs", "escalations"}
            for field,value in metrics.items():
                if field == "successful_task_cost_usd" and value is None: continue
                number(value,field,field in counts)
            n=metrics["distinct_tasks"]; successes=metrics["successful_tasks"]
            if not n or successes>n or metrics["repeated_tasks"]>n or metrics["runs"]<2*n or metrics["unknown_cost_records"]>metrics["runs"]:
                raise ValueError("inconsistent qualification counts")
            z=1.959963984540054; fraction=successes/n
            lower=(fraction+z*z/(2*n)-z*math.sqrt(fraction*(1-fraction)/n+z*z/(4*n*n)))/(1+z*z/n)
            if not math.isclose(metrics["wilson_lower_95"],lower,rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError("inconsistent quality bound")
            expected_cost=metrics["known_cost_usd"]/successes if successes and not metrics["unknown_cost_records"] else None
            actual_cost=metrics["successful_task_cost_usd"]
            if (expected_cost is None) != (actual_cost is None) or (expected_cost is not None and not math.isclose(expected_cost,actual_cost,rel_tol=1e-12,abs_tol=1e-12)):
                raise ValueError("inconsistent qualification cost")
        for pin in (report["policy_hash"],report["corpus_hash"],report["records_hash"]):
            if not isinstance(pin,str) or len(pin)!=64 or any(c not in "0123456789abcdef" for c in pin): raise ValueError("invalid qualification pin")
        cm,bm=report["candidate_metrics"],report["baseline_metrics"]
        if report["qualified"] is not True or report["evidence_kind"] != "measured" or report["matched_baseline"] is not True or report["exclusion_reasons"] != [] or cm["distinct_tasks"] < 100 or cm["repeated_tasks"] != cm["distinct_tasks"] or cm["wilson_lower_95"] < .9 or cm["critical_policy_violations"] or bm["critical_policy_violations"] or cm["distinct_tasks"] != bm["distinct_tasks"] or cm["unknown_cost_records"] or bm["unknown_cost_records"] or cm["successful_task_cost_usd"] is None or bm["successful_task_cost_usd"] is None or cm["successful_task_cost_usd"] >= bm["successful_task_cost_usd"]:
            raise ValueError("unqualified evidence")

    def explain(self, role, requirements, environment, override=None):
        if role not in self.policy["roles"]: raise ValueError("unknown role")
        fields(requirements, {"risk", "privacy", "features", "context_tokens", "output_tokens", "deadline_ms", "expected_input_tokens", "expected_output_tokens", "expected_repairs", "expected_escalations", "expected_tool_cost_usd", "latency_cost_per_ms"})
        fields(environment,{"available_providers", "available_credentials"},{"available_providers", "available_credentials"})
        for key in environment: strings(environment[key],key)
        strings(requirements.get("features",[]),"features")
        for key in ("risk", "privacy"):
            if key in requirements and (not isinstance(requirements[key],str) or not requirements[key]): raise ValueError("invalid requirement")
        for key,value in requirements.items():
            if key not in {"risk", "privacy", "features"}: number(value,key,key in {"context_tokens", "output_tokens", "expected_input_tokens", "expected_output_tokens"})
        for key in ("expected_repairs", "expected_escalations"):
            if requirements.get(key,0)>1: raise ValueError("attempt expectation exceeds limit")
        if override is not None and (not isinstance(override,str) or not override): raise ValueError("invalid override")
        spec=self.policy["roles"][role]; models=self.catalog.data["models"]
        eligible=[]; excluded={}; costs={}
        for alias,model in sorted(models.items()):
            reasons=[]
            if alias not in spec["allowed_models"]: reasons.append("role")
            if requirements.get("risk","low") not in model["risks"]: reasons.append("risk")
            if "privacy" in requirements and requirements["privacy"] not in model["privacy"]: reasons.append("privacy")
            for feature in sorted(set(requirements.get("features",[]))-set(model["features"])): reasons.append("unsupported_feature:"+feature)
            if max(requirements.get("context_tokens",0),requirements.get("expected_input_tokens",0))>model["context_tokens"]: reasons.append("context")
            if max(requirements.get("output_tokens",0),requirements.get("expected_output_tokens",0))>model["output_tokens"]: reasons.append("output")
            if model["provider"] not in environment["available_providers"]: reasons.append("provider_unavailable")
            if model["credential_ref"] is not None and model["credential_ref"] not in environment["available_credentials"]: reasons.append("credential_unavailable")
            latency = model["latency_ms"]
            if latency is not None: latency *= 1 + requirements.get("expected_repairs",0)
            if requirements.get("expected_escalations",0):
                fallback = models.get(spec["fallback"])
                if fallback is None or fallback["latency_ms"] is None: latency = None
                elif latency is not None: latency += requirements["expected_escalations"]*fallback["latency_ms"]
            if "deadline_ms" in requirements and (latency is None or latency>requirements["deadline_ms"]): reasons.append("deadline")
            if not (alias==spec["default"] and spec["reviewed_baseline"]) and alias not in spec["qualifications"]: reasons.append("unqualified_quality")
            if reasons: excluded[alias]=reasons
            else: eligible.append(alias)
            costs[alias]=self._cost(model,requirements,models.get(spec["fallback"]))
        if requirements.get("expected_escalations",0):
            fallback=spec["fallback"]
            fallback_requirements=dict(requirements,expected_escalations=0,expected_repairs=0)
            fallback_eligible=set(self.explain(role,fallback_requirements,environment)["eligible"])
            for alias in list(eligible):
                if fallback not in fallback_eligible or fallback==alias:
                    eligible.remove(alias)
                    excluded[alias]=["escalation_unavailable"]
                    costs[alias]=None
        selected=None
        if override is not None:
            if override in eligible: selected=override
            elif override not in excluded: excluded[override]=["unknown_model"]
        else:
            baseline=spec["default"]
            if baseline in eligible: selected=baseline
            # Only qualified measured alternatives with a known full task estimate
            # may replace a reviewed default. Unknown baseline cost denies savings.
            baseline_cost=costs.get(baseline)
            candidates=[alias for alias in eligible if alias!=baseline and costs[alias] is not None and baseline_cost is not None and costs[alias]<baseline_cost]
            if candidates: selected=min(candidates,key=lambda alias:(costs[alias],alias))
        return dict(selected_alias=selected,eligible=eligible,excluded=excluded,expected_task_cost_usd=costs,
                    catalog_hash=self.catalog.hash,policy_hash=self.policy_hash,routing_policy_hash=self.routing_policy_hash,role=role,evaluation_class=spec["evaluation_class"])

    @staticmethod
    def _cost(model,req,fallback):
        if not ({"expected_input_tokens", "context_tokens"} & set(req)) or not ({"expected_output_tokens", "output_tokens"} & set(req)):
            return None
        pricing=model["pricing"]
        if any(value is None for value in pricing.values()): return None
        base=(req.get("expected_input_tokens",req.get("context_tokens",0))*pricing["input_per_million"]+req.get("expected_output_tokens",req.get("output_tokens",0))*pricing["output_per_million"])/1_000_000
        latency=model["latency_ms"]
        if req.get("latency_cost_per_ms",0) and latency is None: return None
        cost=(base+req.get("expected_tool_cost_usd",0)+(latency or 0)*req.get("latency_cost_per_ms",0))*(1+req.get("expected_repairs",0))
        escalation=req.get("expected_escalations",0)
        if escalation:
            if fallback is None: return None
            fallback_req=dict(req,expected_escalations=0,expected_repairs=0)
            fallback_cost=ModelResolver._cost(fallback,fallback_req,None)
            if fallback_cost is None: return None
            cost+=escalation*fallback_cost
        return cost

    def next_attempt(self, role, requirements, environment, *, quality_repairs=0, escalations=0, failure_category="quality"):
        number(quality_repairs,"quality_repairs",True); number(escalations,"escalations",True)
        if quality_repairs>1 or escalations>1: raise ValueError("attempt limit exceeded")
        explanation=self.explain(role,requirements,environment)
        if failure_category != "quality" or explanation["selected_alias"] is None:
            return dict(action="stop",alias=None,explanation=explanation)
        if quality_repairs==0:
            return dict(action="repair",alias=explanation["selected_alias"],explanation=explanation)
        fallback=self.policy["roles"][role]["fallback"]
        if escalations==0 and fallback in explanation["eligible"] and fallback!=explanation["selected_alias"]:
            return dict(action="escalate",alias=fallback,explanation=explanation)
        return dict(action="stop",alias=None,explanation=explanation)
