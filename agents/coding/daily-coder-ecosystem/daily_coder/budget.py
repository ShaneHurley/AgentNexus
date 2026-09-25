"""Budget enforcement.

Budgets are enforced by the runtime, never by the model. Every provider call must pass
`reserve()` first, so parallel research lanes cannot burst past a profile cap.
"""
from __future__ import annotations
import datetime, threading

class BudgetExceeded(RuntimeError): pass
class DailyCapExceeded(RuntimeError): pass

DEFAULT_THRESHOLDS={"warn_fraction":0.7,"checkpoint_fraction":0.8,"hard_stop_fraction":0.9,"reserve_fraction":0.1}

def _today()->str: return datetime.date.today().isoformat()

class BudgetManager:
    def __init__(self,config,state,pricing=None,limits=None):
        self.config=config; self.state=state; self.pricing=pricing or {}; self.limits=limits or {}
        self._lock=threading.RLock(); self._reserved={}; self._reserved_calls={}; self.events=[]

    def _thresholds(self):
        t=dict(DEFAULT_THRESHOLDS); t.update(self.config.get("thresholds",{})); return t
    def _cap(self,profile):
        p=self.config["profiles"]; return p[profile] if profile in p else p["M"]
    def usable_tokens(self,profile,reserve=True):
        cap=self._cap(profile); t=self._thresholds()
        return int(cap["total_tokens"]*(1-t["reserve_fraction"])) if reserve else int(cap["total_tokens"])
    def price(self,model,input_tokens,output_tokens):
        rate=self.pricing.get(model) or self.pricing.get("default") or {}
        return round(input_tokens/1000.0*float(rate.get("input_per_1k",0.0))+output_tokens/1000.0*float(rate.get("output_per_1k",0.0)),6)
    def _used(self,run_id):
        u=self.state.total_usage(run_id)
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

    def reserve(self,run_id,profile,estimated_tokens):
        """Atomically reserve headroom before a provider call."""
        with self._lock:
            cap=self._cap(profile); used=self._used(run_id); usable=self.usable_tokens(profile)
            if used["calls"]+1>cap["max_calls"]: raise BudgetExceeded({"reason":"call_cap","used":used,"cap":cap})
            if used["tokens"]+estimated_tokens>usable: raise BudgetExceeded({"reason":"token_cap","used":used,"cap":cap,"requested":estimated_tokens})
            self._reserved[run_id]=self._reserved.get(run_id,0)+estimated_tokens
            self._reserved_calls[run_id]=self._reserved_calls.get(run_id,0)+1
            lvl=self.level(run_id,profile)
            if lvl!="ok": self.events.append({"run_id":run_id,"level":lvl,"used":self._used(run_id)})
            return {"reserved":estimated_tokens,"level":lvl}

    def release(self,run_id,estimated_tokens):
        with self._lock:
            tokens=max(0,self._reserved.get(run_id,0)-estimated_tokens)
            calls=max(0,self._reserved_calls.get(run_id,0)-1)
            if tokens: self._reserved[run_id]=tokens
            else: self._reserved.pop(run_id,None)
            if calls: self._reserved_calls[run_id]=calls
            else: self._reserved_calls.pop(run_id,None)

    def settle(self,run_id,estimated_tokens,model,input_tokens,output_tokens):
        usd=self.price(model,input_tokens,output_tokens)
        self.release(run_id,estimated_tokens)
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
        return {"run_id":run_id,"profile":profile,"tokens":used["tokens"],"calls":used["calls"],"est_usd":usd,
                "cap":cap,"level":self.level(run_id,profile),
                "cost_per_verified_pass":usd if verified else None,"today":self.state.spend(_today())}
