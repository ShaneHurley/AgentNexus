"""Opaque SQLite metadata with authorized, adapter-scoped Keychain use."""
from __future__ import annotations
import dataclasses
import json
import sqlite3
import time
import uuid
from pathlib import Path

class SecretBrokerError(RuntimeError):
    pass

@dataclasses.dataclass(frozen=True)
class SecretUseGrant:
    caller: str
    task_id: str
    ref: str
    purpose: str
    expires_at: float
    effective_grant: object = dataclasses.field(repr=False,compare=False)
    generation: int = 0
    token: str = dataclasses.field(default="",repr=False)

class SecretBroker:
    def __init__(self,path,backend=None,*,allow_test_backend=False):
        if backend is None:
            try:
                import keyring
                backend=keyring.get_keyring()
            except Exception:
                raise SecretBrokerError("approved vault backend unavailable") from None
        if not allow_test_backend and (type(backend).__module__ != "keyring.backends.macOS" or type(backend).__name__ != "Keyring"):
            raise SecretBrokerError("approved macOS Keychain backend required")
        self._backend=backend
        self._grants={}
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self._db=sqlite3.connect(path)
        self._db.execute("CREATE TABLE IF NOT EXISTS refs (ref TEXT PRIMARY KEY, service TEXT, owner TEXT, scope TEXT, vault_service TEXT, vault_account TEXT, generation INTEGER, revoked INTEGER)")
        self._db.commit()

    def register(self,service,owner,scope,*,vault_ref=None,ref=None):
        ref=ref or "secret/"+uuid.uuid4().hex
        if not service or not owner or not ref or not scope:
            raise SecretBrokerError("invalid secret metadata")
        vault_ref=vault_ref or {"service":service,"account":owner}
        self._db.execute("INSERT INTO refs VALUES (?,?,?,?,?,?,1,0)",(ref,service,owner,json.dumps(list(scope)),vault_ref["service"],vault_ref["account"]))
        self._db.commit()
        return ref

    def _row(self,ref):
        row=self._db.execute("SELECT * FROM refs WHERE ref=?",(ref,)).fetchone()
        if row is None or row[7]: raise SecretBrokerError("secret reference unavailable")
        return row

    @staticmethod
    def _authorize_capability(effective_grant,ref):
        try:
            if effective_grant.authorize("secret_use",ref) is False:
                raise SecretBrokerError("secret capability denied")
        except Exception:
            raise SecretBrokerError("secret capability denied") from None

    def authorize(self,caller,task_id,ref,purpose,expires_at,effective_grant):
        row=self._row(ref)
        if getattr(effective_grant,"role_id",None)!=caller:
            raise SecretBrokerError("secret caller identity denied")
        if caller not in json.loads(row[3]) or not task_id or purpose!="invoke" or not time.time()<expires_at<=time.time()+300:
            raise SecretBrokerError("secret use denied")
        self._authorize_capability(effective_grant,ref)
        token=uuid.uuid4().hex
        grant=SecretUseGrant(caller,task_id,ref,purpose,expires_at,effective_grant,row[6],token)
        self._grants[token]=grant
        return grant

    def available(self,ref):
        try: self._row(ref)
        except SecretBrokerError: return False
        return True

    def probe(self,grant):
        """Authorized presence check; never returns the vault value."""
        try:
            return self.use(grant,lambda value:True)
        except SecretBrokerError:
            return False

    def _validate(self,grant):
        row=self._row(grant.ref)
        if self._grants.get(grant.token) is not grant or grant.generation!=row[6] or grant.expires_at<=time.time():
            raise SecretBrokerError("secret use grant invalid")
        self._authorize_capability(grant.effective_grant,grant.ref)
        return row

    def _value(self,grant):
        row=self._validate(grant)
        try: value=self._backend.get_password(row[4],row[5])
        except Exception: raise SecretBrokerError("vault missing or locked") from None
        if not isinstance(value,str) or not value: raise SecretBrokerError("vault secret missing")
        return value

    def _redact(self,item,value):
        if isinstance(item,str): return item.replace(value,"[REDACTED]")
        if isinstance(item,bytes): return item.replace(value.encode(),b"[REDACTED]")
        if isinstance(item,dict): return {self._redact(k,value):self._redact(v,value) for k,v in item.items()}
        if isinstance(item,list): return [self._redact(v,value) for v in item]
        if isinstance(item,tuple): return tuple(self._redact(v,value) for v in item)
        if dataclasses.is_dataclass(item):
            return dataclasses.replace(item,**{f.name:self._redact(getattr(item,f.name),value) for f in dataclasses.fields(item)})
        if item is None or isinstance(item,(bool,int,float)): return item
        raise SecretBrokerError("unsupported secret operation output")

    @staticmethod
    def _raise_sanitized(exc):
        from agent_core.providers.http import ProviderError
        if isinstance(exc,ProviderError):
            raise ProviderError("provider operation failed",category=exc.category,remote_acceptance=exc.remote_acceptance,retryable=exc.retryable) from None
        raise SecretBrokerError("authorized secret operation failed") from None

    def use(self,grant,callback):
        value=self._value(grant)
        try:
            result=callback(value)
            self._validate(grant)
            return self._redact(result,value)
        except Exception as exc: self._raise_sanitized(exc)

    def stream_use(self,grant,callback):
        """Redact across text deltas, retaining at most one credential prefix."""
        value=self._value(grant)
        iterator=None
        pending=""
        template=None
        terminal=None
        def text_event(item):
            return isinstance(item,str) or (dataclasses.is_dataclass(item) and getattr(item,"type",None)=="text" and isinstance(getattr(item,"text",None),str))
        def event_text(item):
            return item if isinstance(item,str) else item.text
        def emit(item,text):
            return text if isinstance(item,str) else self._redact(dataclasses.replace(item,text=text),value)
        try:
            iterator=iter(callback(value))
            while True:
                self._validate(grant)
                try: item=next(iterator)
                except StopIteration:
                    if pending:
                        self._validate(grant)
                        yield emit(template,pending)
                    if terminal is not None:
                        yield self._redact(terminal,value)
                    return
                self._validate(grant)
                if text_event(item):
                    text=pending+event_text(item)
                    # Full matches are consumed before retaining any trailing
                    # prefix; overlapping matches cannot resurrect redacted text.
                    end=0
                    while True:
                        match=text.find(value,end)
                        if match<0: break
                        end=match+len(value)
                    tail=0
                    for length in range(1,min(len(value),len(text)-end+1)):
                        if text.endswith(value[:length]): tail=length
                    cut=len(text)-tail
                    safe=text[:cut].replace(value,"[REDACTED]")
                    pending=text[cut:]
                    template=item
                    # An empty text event preserves an immediate event boundary
                    # even if its entire text is an incomplete secret prefix.
                    yield emit(item,safe)
                else:
                    # Retain an intervening finish until the producer ends,
                    # so even malformed streams cannot flush a secret prefix
                    # and subsequently expose its remaining characters.
                    if getattr(item,"type",None)=="finish" and pending:
                        if terminal is not None:
                            raise SecretBrokerError("duplicate pending terminal event")
                        terminal=item
                    else:
                        yield self._redact(item,value)
        except Exception as exc: self._raise_sanitized(exc)
        finally:
            if iterator is not None:
                close=getattr(iterator,"close",None)
                if close is not None:
                    try: close()
                    except Exception: pass
            value=None
            pending=""

    def revoke(self,ref):
        self._row(ref)
        self._db.execute("UPDATE refs SET revoked=1,generation=generation+1 WHERE ref=?",(ref,));self._db.commit()

    def rotate(self,ref,value):
        row=self._row(ref)
        try: self._backend.set_password(row[4],row[5],value)
        except Exception: raise SecretBrokerError("vault rotation failed") from None
        self._db.execute("UPDATE refs SET generation=generation+1 WHERE ref=?",(ref,));self._db.commit()

    def delete(self,ref):
        row=self._row(ref)
        try: self._backend.delete_password(row[4],row[5])
        except Exception: raise SecretBrokerError("vault deletion failed") from None
        self.revoke(ref)
