"""Budget enforcement.

Budgets are enforced by the runtime, never by the model. Every provider call must pass
`reserve()` first, so parallel research lanes cannot burst past a profile cap.
"""
from __future__ import annotations
import datetime, math, threading, time, uuid
from collections.abc import Mapping
from agent_core.rate_limiter import RateLimiter, RateLimiterConfig, RateLimitExceeded

class BudgetExceeded(RuntimeError): pass
class DailyCapExceeded(RuntimeError): pass

DEFAULT_THRESHOLDS={"warn_fraction":0.7,"checkpoint_fraction":0.8,"hard_stop_fraction":0.9,"reserve_fraction":0.1}

def _today()->str: return datetime.date.today().isoformat()

class BudgetManager:
    def __init__(self,config,state,pricing=None,limits=None,*,subscription_models=(),provider_name=None,billing_kind=None):
        # Only trusted provider setup may supply this exact allowlist. Pricing
        # metadata and role/model output cannot select an accounting mode.
        if isinstance(subscription_models,(str,bytes,Mapping)) or subscription_models is None:
            raise ValueError("subscription_models must be an iterable of exact model names")
        try:
            models=tuple(subscription_models)
        except TypeError as exc:
            raise ValueError("subscription_models must be an iterable of exact model names") from exc
        if any(not isinstance(model,str) or not model or any(c.isspace() or c in "*?" for c in model) for model in models):
            raise ValueError("subscription_models must contain nonempty exact model names without whitespace or wildcards")
        self.subscription_models=frozenset(models)
        self.config=config; self.state=state; self.pricing=pricing or {}; self.limits=dict(limits or {})
        self.daily_limit_source="default"
        self.codex_trial_override=False
        override="codex_subscription_max_tokens_per_day"
        if override in self.limits:
            value=self.limits[override]
            if value is not None and (type(value) is not int or value<=0):
                raise ValueError("invalid Codex subscription daily token limit")
            if provider_name=="codex_cli":
                if billing_kind!="chatgpt_subscription" or not self.subscription_models:
                    raise ValueError("Codex trial limit requires trusted subscription accounting")
                self.limits["max_tokens_per_day"]=value
                self.daily_limit_source=override
                self.codex_trial_override=True
        self._lock=threading.RLock(); self._reserved={}; self._reserved_calls={}; self._reservation_ids={}; self.events=[]
        self.rate_limiter=RateLimiter(RateLimiterConfig.disabled())

    def activate_rate_limiter(self, profile):
        """Called when a run starts; activates rate limiter from profile config."""
        cap = self._cap(profile)
        cfg = RateLimiterConfig.from_profile(cap)
        self.rate_limiter = RateLimiter(cfg)

    def _thresholds(self):
        t=dict(DEFAULT_THRESHOLDS); t.update(self.config.get("thresholds",{})); return t
    def _cap(self,profile):
        p=self.config["profiles"]; return p[profile] if profile in p else p["M"]
    def usable_tokens(self,profile,reserve=True):
        cap=self._cap(profile); t=self._thresholds()
        profile_limit=int(cap["total_tokens"]*(1-t["reserve_fraction"])) if reserve else int(cap["total_tokens"])
        return min(profile_limit,int(self.limits["max_tokens_per_run"])) if "max_tokens_per_run" in self.limits else profile_limit
    def validate_model_pricing(self,model):
        rate=self.pricing.get(model)
        if not isinstance(rate,dict):
            raise BudgetExceeded({"reason":"unpriced_model","model":model})
        try:
            input_rate=float(rate["input_per_1k"])
            output_rate=float(rate["output_per_1k"])
        except (KeyError,TypeError,ValueError) as exc:
            raise BudgetExceeded({"reason":"invalid_model_price","model":model}) from exc
        if not math.isfinite(input_rate) or not math.isfinite(output_rate) or input_rate<0 or output_rate<0:
            raise BudgetExceeded({"reason":"invalid_model_price","model":model})
        return input_rate,output_rate
    @staticmethod
    def _subscription_accounting():
        return {"accounting_mode":"subscription","known_api_cash_usd":0.0,
                "total_cost_usd":None,"total_cost_status":"unknown"}

    def validate_model_accounting(self,model):
        """Validate API pricing or an exact model enabled by trusted setup.

        Zero known API cash for a subscription is never its total dollar cost.
        validate_model_pricing and price remain strict API pricing interfaces.
        """
        if self.codex_trial_override and model not in self.subscription_models:
            raise BudgetExceeded({"reason":"codex_trial_requires_subscription_model"})
        if not isinstance(model,str) or not model:
            raise BudgetExceeded({"reason":"invalid_accounting_model","model":model})
        if model in self.subscription_models:
            return self._subscription_accounting()
        input_rate,output_rate=self.validate_model_pricing(model)
        return {"accounting_mode":"api","input_per_1k":input_rate,"output_per_1k":output_rate}

    @staticmethod
    def _validate_subscription_cash(value,model):
        if value is None:
            return
        try:
            cash=float(value)
        except (TypeError,ValueError) as exc:
            raise BudgetExceeded({"reason":"invalid_subscription_cash","model":model}) from exc
        if not math.isfinite(cash) or cash!=0:
            raise BudgetExceeded({"reason":"invalid_subscription_cash","model":model})

    def price(self,model,input_tokens,output_tokens):
        input_rate,output_rate=self.validate_model_pricing(model)
        return round(input_tokens/1000.0*input_rate+output_tokens/1000.0*output_rate,6)
    def _used(self,run_id):
        u=self.state.total_usage(run_id)
        if hasattr(self.state,"active_budget_reservations"):
            reserved=self.state.active_budget_reservations(run_id)
            return {"tokens":u["tokens"]+reserved["tokens"],"calls":u["calls"]+reserved["calls"]}
        return {"tokens":u["tokens"]+self._reserved.get(run_id,0),"calls":u["calls"]+self._reserved_calls.get(run_id,0)}

    def check(self,run_id,profile,reserve=True):
        cap=self._cap(profile); used=self._used(run_id); usable=self.usable_tokens(profile,reserve)
        if used["calls"]>=cap["max_calls"] or used["tokens"]>=usable: raise BudgetExceeded({"used":used,"cap":cap})
        return {"used":used,"cap":cap,"usable_tokens":usable,"level":self.level(run_id,profile)}

    def level(self,run_id,profile):
        t=self._thresholds(); cap=self._cap(profile)
        frac=self._used(run_id)["tokens"]/max(1,cap["total_tokens"])
        if frac>=t["hard_stop_fraction"]: return "hard_stop"
        if frac>=t["checkpoint_fraction"]: return "checkpoint"
        if frac>=t["warn_fraction"]: return "warn"
        return "ok"

    def check_daily(self):
        day=_today(); spent=self.state.spend(day)
        mt=self.limits.get("max_tokens_per_day"); mu=self.limits.get("max_spend_usd")
        if mt is not None and spent["tokens"]>=mt: raise DailyCapExceeded({"day":day,"spent":spent,"max_tokens_per_day":mt})
        # At an exact API cash ceiling a trusted subscription can still reserve
        # zero additional cash. Per-call reservations enforce positive API cash.
        at_cash_cap=mu is not None and spent["est_usd"]>=mu
        if at_cash_cap and (not self.subscription_models or spent["est_usd"]>mu):
            raise DailyCapExceeded({"day":day,"spent":spent,"max_spend_usd":mu})
        return spent

    def reservation_diagnostics(self,run_id,profile,next_estimate):
        cap=self._cap(profile); day=_today(); usage=self.state.total_usage(run_id)
        active=self.state.active_budget_reservations(run_id)
        daily=self.state.daily_reservations(day) if hasattr(self.state,"daily_reservations") else {"tokens":0,"calls":0}
        spent=self.state.spend(day); ceiling=self.limits.get("max_tokens_per_day")
        return {"schema_version":1,"scope":"native_provider_ledger","run_grant_tokens":self.limits.get("max_tokens_per_run",cap["total_tokens"]),
            "consumed_tokens":usage["tokens"],"active_provider_reservations":active,"next_call_estimate":next_estimate,
            "profile_tokens":cap["total_tokens"],"effective_run_tokens":self.usable_tokens(profile),
            "daily_ceiling":ceiling,"daily_limit_source":self.daily_limit_source,"daily_consumed_tokens":spent["tokens"],"daily_provider_reservations":daily,
            "daily_headroom":None if ceiling is None else max(0,ceiling-spent["tokens"]-daily["tokens"]),
            "reservation_relationship":"Supervisor task reservations are parents of provider reservations, not additive usage",
            "note":"Diagnostic snapshot only; atomic reservation checks remain authoritative"}

    def reserve(self,run_id,profile,estimated_tokens,*,model=None,estimated_usd=None,reservation_id=None):
        """Atomically reserve headroom before a provider call."""
        self.rate_limiter.acquire()  # Rate-limit gate (cheap mode)
        deadline=self.limits.get("deadline")
        if deadline is not None and time.time()>=deadline:
            from agent_core.lifecycle import ReconciliationRequired
            self.state.request_cancel(run_id)
            raise ReconciliationRequired("supervised deadline reached before provider reservation")
        reservation_id=reservation_id or str(uuid.uuid4())
        accounting=self.validate_model_accounting(model) if model is not None or self.codex_trial_override else {}
        subscription=accounting.get("accounting_mode")=="subscription"
        if subscription:
            self._validate_subscription_cash(estimated_usd,model)
            estimated_usd=0.0  # Persist only known API cash exposure.
        elif model is not None and estimated_usd is None:
            estimated_usd=max(accounting["input_per_1k"],accounting["output_per_1k"])*estimated_tokens/1000.0
        public_accounting={**accounting,"estimated_usd":None,"est_usd":None} if subscription else {}
        estimated_usd=float(estimated_usd or 0.0)
        if not math.isfinite(estimated_usd) or estimated_usd<0:
            raise BudgetExceeded({"reason":"invalid_estimated_price","model":model})
        if hasattr(self.state,"reserve_budget"):
            cap=self._cap(profile)
            try:
                reservation=self.state.reserve_budget(
                    run_id,reservation_id,_today(),estimated_tokens,estimated_usd,
                    run_token_limit=self.usable_tokens(profile),run_call_limit=int(cap["max_calls"]),
                    daily_token_limit=self.limits.get("max_tokens_per_day"),
                    daily_usd_limit=self.limits.get("max_spend_usd"),run_usd_limit=self.limits.get("max_spend_usd_per_run"))
            except ValueError as exc:
                raise BudgetExceeded({"reason":"persistent_budget_cap","detail":str(exc),"diagnostics":self.reservation_diagnostics(run_id,profile,estimated_tokens)}) from exc
            with self._lock:
                self._reserved[run_id]=self._reserved.get(run_id,0)+estimated_tokens
                self._reserved_calls[run_id]=self._reserved_calls.get(run_id,0)+1
                self._reservation_ids.setdefault((run_id,estimated_tokens),[]).append(reservation_id)
            lvl=self.level(run_id,profile)
            if lvl!="ok": self.events.append({"run_id":run_id,"level":lvl,"used":self._used(run_id)})
            return {"reserved":estimated_tokens,"estimated_usd":estimated_usd,"level":lvl,
                    "reservation_id":reservation_id,**reservation,**public_accounting}
        with self._lock:
            cap=self._cap(profile); used=self._used(run_id); usable=self.usable_tokens(profile)
            if used["calls"]+1>cap["max_calls"]: raise BudgetExceeded({"reason":"call_cap","used":used,"cap":cap})
            if used["tokens"]+estimated_tokens>usable: raise BudgetExceeded({"reason":"token_cap","used":used,"cap":cap,"requested":estimated_tokens})
            self._reserved[run_id]=self._reserved.get(run_id,0)+estimated_tokens
            self._reserved_calls[run_id]=self._reserved_calls.get(run_id,0)+1
            self._reservation_ids.setdefault((run_id,estimated_tokens),[]).append(reservation_id)
            lvl=self.level(run_id,profile)
            if lvl!="ok": self.events.append({"run_id":run_id,"level":lvl,"used":self._used(run_id)})
            return {"reserved":estimated_tokens,"level":lvl,"reservation_id":reservation_id,**public_accounting}

    def release(self,run_id,estimated_tokens,reservation_id=None):
        if reservation_id is None:
            ids=self._reservation_ids.get((run_id,estimated_tokens),[])
            reservation_id=ids[0] if ids else None
        if reservation_id and hasattr(self.state,"release_budget_reservation"):
            self.state.release_budget_reservation(reservation_id)
        with self._lock:
            ids=self._reservation_ids.get((run_id,estimated_tokens),[])
            if reservation_id in ids:
                ids.remove(reservation_id)
                if not ids: self._reservation_ids.pop((run_id,estimated_tokens),None)
            tokens=max(0,self._reserved.get(run_id,0)-estimated_tokens)
            calls=max(0,self._reserved_calls.get(run_id,0)-1)
            if tokens: self._reserved[run_id]=tokens
            else: self._reserved.pop(run_id,None)
            if calls: self._reserved_calls[run_id]=calls
            else: self._reserved_calls.pop(run_id,None)

    def settle(self,run_id,estimated_tokens,model,input_tokens,output_tokens,reservation_id=None,*,reported_usd=None):
        # Validate membership even when provider-reported dollars are supplied;
        # reported_usd must never make an unpriced model implicitly acceptable.
        accounting=self.validate_model_accounting(model)
        subscription=accounting["accounting_mode"]=="subscription"
        if subscription:
            self._validate_subscription_cash(reported_usd,model)
            usd=0.0
        else:
            usd=self.price(model,input_tokens,output_tokens) if reported_usd is None else float(reported_usd)
        if not math.isfinite(usd) or usd<0: raise ValueError("invalid reported usage")
        if reservation_id is None:
            ids=self._reservation_ids.get((run_id,estimated_tokens),[])
            reservation_id=ids[0] if ids else None
        if reservation_id and hasattr(self.state,"settle_budget_reservation"):
            self.state.settle_budget_reservation(reservation_id,input_tokens+output_tokens,usd)
            self.release(run_id,estimated_tokens,reservation_id)
        else:
            self.release(run_id,estimated_tokens,reservation_id)
            self.state.add_spend(_today(),input_tokens+output_tokens,usd)
        return self._subscription_accounting() if subscription else usd

    def frontier_allowed(self,run_id,profile):
        cap=self._cap(profile); row=self.state.get(run_id)
        return int(row.get("frontier_calls") or 0)<int(cap.get("frontier_calls",0))

    def report(self,run_id,profile=None):
        row=self.state.get(run_id); used=self.state.total_usage(run_id)
        profile=profile or row.get("profile") or "M"; cap=self._cap(profile)
        usd=round(float(row.get("est_usd") or 0.0),6)
        verified=row.get("status")=="COMPLETE"
        exposure=self.state.active_budget_reservations(run_id) if hasattr(self.state,"active_budget_reservations") else {}
        unreceipted=self.state.unreceipted_settlements(run_id) if hasattr(self.state,"unreceipted_settlements") else {}
        result={"run_id":run_id,"profile":profile,"settled_unreceipted":unreceipted,"tokens":used["tokens"],"calls":used["calls"],"est_usd":usd,
                "reserved_exposure":exposure,"usage_status":"unknown" if exposure.get("calls") else ("reconciliation_required" if unreceipted.get("calls") else "recorded"),
                "cap":cap,"level":self.level(run_id,profile),
                "cost_per_verified_pass":usd if verified else None,"today":self.state.spend(_today()),
                "rate_limiter":self.rate_limiter.report()}
        if self.subscription_models:
            # Conservative across restart/mixed runs: this constructor enables
            # unknown subscription value; the cash ledger cannot establish it.
            def labeled_cash(value):
                return {**value,"known_api_cash_usd":float(value.get("est_usd") or 0.0),
                        "est_usd":None,"total_cost_usd":None,"total_cost_status":"unknown"}
            result.update({"accounting_mode":"subscription-enabled","known_api_cash_usd":usd,
                           "est_usd":None,"total_cost_usd":None,"total_cost_status":"unknown",
                           "cost_per_verified_pass":None,"today":labeled_cash(result["today"]),
                           "reserved_exposure":labeled_cash(exposure),"settled_unreceipted":labeled_cash(unreceipted)})
        return result
