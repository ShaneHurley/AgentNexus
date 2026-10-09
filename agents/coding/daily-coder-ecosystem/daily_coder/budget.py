"""Budget enforcement.

Budgets are enforced by the runtime, never by the model. Every provider call must pass
`reserve()` first, so parallel research lanes cannot burst past a profile cap.
"""
from __future__ import annotations
import datetime, math, threading, time, uuid
from agent_core.rate_limiter import RateLimiter, RateLimiterConfig, RateLimitExceeded

class BudgetExceeded(RuntimeError): pass
class DailyCapExceeded(RuntimeError): pass

DEFAULT_THRESHOLDS={"warn_fraction":0.7,"checkpoint_fraction":0.8,"hard_stop_fraction":0.9,"reserve_fraction":0.1}

def _today()->str: return datetime.date.today().isoformat()

class BudgetManager:
    def __init__(self,config,state,pricing=None,limits=None):
        self.config=config; self.state=state; self.pricing=pricing or {}; self.limits=limits or {}
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
        if mu is not None and spent["est_usd"]>=mu: raise DailyCapExceeded({"day":day,"spent":spent,"max_spend_usd":mu})
        return spent

    def reserve(self,run_id,profile,estimated_tokens,*,model=None,estimated_usd=None,reservation_id=None):
        """Atomically reserve headroom before a provider call."""
        self.rate_limiter.acquire()  # Rate-limit gate (cheap mode)
        deadline=self.limits.get("deadline")
        if deadline is not None and time.time()>=deadline:
            from agent_core.lifecycle import ReconciliationRequired
            self.state.request_cancel(run_id)
            raise ReconciliationRequired("supervised deadline reached before provider reservation")
        reservation_id=reservation_id or str(uuid.uuid4())
        if model is not None:
            input_rate,output_rate=self.validate_model_pricing(model)
            if estimated_usd is None:
                estimated_usd=max(input_rate,output_rate)*estimated_tokens/1000.0
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
                raise BudgetExceeded({"reason":"persistent_budget_cap","detail":str(exc)}) from exc
            with self._lock:
                self._reserved[run_id]=self._reserved.get(run_id,0)+estimated_tokens
                self._reserved_calls[run_id]=self._reserved_calls.get(run_id,0)+1
                self._reservation_ids.setdefault((run_id,estimated_tokens),[]).append(reservation_id)
            lvl=self.level(run_id,profile)
            if lvl!="ok": self.events.append({"run_id":run_id,"level":lvl,"used":self._used(run_id)})
            return {"reserved":estimated_tokens,"estimated_usd":estimated_usd,"level":lvl,
                    "reservation_id":reservation_id,**reservation}
        with self._lock:
            cap=self._cap(profile); used=self._used(run_id); usable=self.usable_tokens(profile)
            if used["calls"]+1>cap["max_calls"]: raise BudgetExceeded({"reason":"call_cap","used":used,"cap":cap})
            if used["tokens"]+estimated_tokens>usable: raise BudgetExceeded({"reason":"token_cap","used":used,"cap":cap,"requested":estimated_tokens})
            self._reserved[run_id]=self._reserved.get(run_id,0)+estimated_tokens
            self._reserved_calls[run_id]=self._reserved_calls.get(run_id,0)+1
            self._reservation_ids.setdefault((run_id,estimated_tokens),[]).append(reservation_id)
            lvl=self.level(run_id,profile)
            if lvl!="ok": self.events.append({"run_id":run_id,"level":lvl,"used":self._used(run_id)})
            return {"reserved":estimated_tokens,"level":lvl,"reservation_id":reservation_id}

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

    def settle(self,run_id,estimated_tokens,model,input_tokens,output_tokens,reservation_id=None):
        usd=self.price(model,input_tokens,output_tokens)
        if reservation_id is None:
            ids=self._reservation_ids.get((run_id,estimated_tokens),[])
            reservation_id=ids[0] if ids else None
        if reservation_id and hasattr(self.state,"settle_budget_reservation"):
            self.state.settle_budget_reservation(reservation_id,input_tokens+output_tokens,usd)
            self.release(run_id,estimated_tokens,reservation_id)
        else:
            self.release(run_id,estimated_tokens,reservation_id)
            self.state.add_spend(_today(),input_tokens+output_tokens,usd)
        return usd

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
        return {"run_id":run_id,"profile":profile,"settled_unreceipted":unreceipted,"tokens":used["tokens"],"calls":used["calls"],"est_usd":usd,
                "reserved_exposure":exposure,"usage_status":"unknown" if exposure.get("calls") else ("reconciliation_required" if unreceipted.get("calls") else "recorded"),
                "cap":cap,"level":self.level(run_id,profile),
                "cost_per_verified_pass":usd if verified else None,"today":self.state.spend(_today()),
                "rate_limiter":self.rate_limiter.report()}
