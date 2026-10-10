"""Deterministic bounded context helpers; no imports of inspected code or network."""
from __future__ import annotations
import ast
import hashlib
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import tempfile
from .contracts import ContractDenied

PROTECTED = frozenset(('intent','constraints','permissions','approval_hash','plan_hash','budget','pending_calls'))

def token_estimate(text):
    return max(1,math.ceil(len(text.encode('utf-8'))/3)) if text else 0

def repo_outline(path, grant, *, max_bytes=1024*1024, max_symbols=200):
    path=Path(path)
    grant.authorize('tools','filesystem.read',path)
    if not 1 <= max_bytes <= 1024*1024 or not 1 <= max_symbols <= 200: raise ValueError('outline bounds exceeded')
    # Refuse any symlink component, including within an otherwise authorized root.
    if any(p.is_symlink() for p in (path,*path.parents)): raise ContractDenied('outline symlink denied')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream: data=stream.read(max_bytes+1)
    if len(data)>max_bytes: raise ValueError('source exceeds bounded inspection size')
    tree=ast.parse(data,filename=path.name)
    symbols=[]
    imports=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            signature=ast.unparse(node.args) if hasattr(node,'args') else ', '.join(ast.unparse(b) for b in node.bases)
            symbols.append({'name':node.name,'kind':type(node).__name__,'signature':signature[:1000],
                            'start':node.lineno,'end':node.end_lineno})
        elif isinstance(node,(ast.Import,ast.ImportFrom)):
            imports.append({'text':ast.unparse(node)[:1000],'start':node.lineno,'end':node.end_lineno})
    return {'source_hash':hashlib.sha256(data).hexdigest(),'symbols':symbols[:max_symbols],
            'imports':imports[:max_symbols],'truncated':len(symbols)>max_symbols or len(imports)>max_symbols,
            'expansion':{'path':str(path),'source_hash':hashlib.sha256(data).hexdigest()}}

def context_pack(protected,evidence,*,evidence_tokens=4000,max_context_tokens=32000):
    if set(protected) != PROTECTED: raise ValueError('all protected fields required; authority is never inferred')
    if not 0 <= evidence_tokens <= 4000: raise ValueError('evidence allocation outside bounds')
    protected=json.loads(json.dumps(protected,allow_nan=False))
    used=token_estimate(json.dumps(protected,sort_keys=True))
    if used>max_context_tokens: raise ValueError('protected context cannot fit; stop or split task')
    included=[]; deferred=[]; seen=set(); consumed=0
    for record in evidence:
        if not isinstance(record,dict) or not isinstance(record.get('id'),str) or not record['id'] or record['id'] in seen: raise ValueError('unique evidence references required')
        seen.add(record['id'])
        cost=token_estimate(json.dumps(record,allow_nan=False,sort_keys=True))
        if len(included)>=8 or consumed+cost>min(evidence_tokens,max_context_tokens-used): deferred.append(record['id']); continue
        included.append(record);consumed+=cost
    return {'version':1,'protected':protected,'evidence':included,'expansion_refs':deferred,
            'evidence_tokens':consumed,'protected_tokens':used,'token_count_status':'estimated'}

def _redact(value,secrets):
    if isinstance(value,str):
        for secret in sorted(set(secrets),key=len,reverse=True):
            if secret: value=value.replace(secret,'[REDACTED]')
        return value
    if isinstance(value,dict):
        return {k:('[REDACTED]' if k.lower() in {'api_key','password','authorization','access_token','client_secret'} else _redact(v,secrets)) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_redact(v,secrets) for v in value]
    return value

def tool_result_reduce(result,artifact_dir,*,known_secrets=(),max_chars=12000):
    if not isinstance(result,dict) or not 1<=max_chars<=12000: raise ValueError('invalid result reduction')
    clean=_redact(result,known_secrets); raw=json.dumps(clean,sort_keys=True,allow_nan=False,ensure_ascii=False)
    if len(raw.encode())>8*1024*1024: raise ValueError('tool evidence exceeds artifact limit')
    key=hashlib.sha256(raw.encode()).hexdigest(); directory=Path(artifact_dir)
    if any(p.is_symlink() for p in (directory,*directory.parents)): raise ContractDenied('artifact symlink denied')
    directory.mkdir(parents=True,exist_ok=True)
    target=directory/(key+'.json')
    if target.is_symlink(): raise ContractDenied('artifact symlink denied')
    fd,name=tempfile.mkstemp(prefix='.evidence-',dir=directory)
    try:
        with os.fdopen(fd,'w') as stream: stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
    return {'artifact_id':key,'returncode':result.get('returncode'),'timeout':bool(result.get('timeout',False)),
            'cancelled':bool(result.get('cancelled',False)),'summary':raw[:max_chars],
            'truncated':len(raw)>max_chars,'original_chars':len(raw),'token_count_status':'estimated',
            'estimated_tokens':token_estimate(raw[:max_chars])}

class _Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.hidden+=1
        if not self.hidden and tag in ('p','div','br','tr','td','th','li','h1','h2','h3'):self.parts.append('\n' if tag!='td' else '\t')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','tr','li'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

def evidence_extract(html,provenance):
    if not isinstance(html,str) or len(html.encode())>4*1024*1024:raise ValueError('retrieved HTML exceeds extraction bounds')
    if not provenance.get('id') or provenance.get('retrieval_status') not in ('retrieved','partial'):raise ValueError('retrieval provenance required')
    parser=_Text();parser.feed(html)
    text='\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
    return {'text':text,'original_hash':hashlib.sha256(html.encode()).hexdigest(),'text_hash':hashlib.sha256(text.encode()).hexdigest(),
            'provenance':dict(provenance),'extraction':'stdlib-htmlparser/v1','verification_state':'unverified'}

def usage_report(records):
    groups={}; cost=0.0;unknown=0;input_tokens=0;output_tokens=0;unknown_input=0;unknown_output=0
    for row in records:
        key=(row.get('role','unknown'),row.get('phase','unknown'))
        group=groups.setdefault(key,{'role':key[0],'phase':key[1],'calls':0,'known_cost_usd':0.0,'unknown_calls':0,'input_tokens':0,'output_tokens':0,'evidence_statuses':[]})
        group['calls']+=1
        for field in ('input_tokens','output_tokens'):
            value=row.get(field)
            if value is not None and (type(value) is not int or value<0):raise ValueError('invalid token count')
            if value is not None:group[field]+=value
        value=row.get('cost_usd')
        if value is None:unknown+=1;group['unknown_calls']+=1
        else:
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0:raise ValueError('invalid cost')
            cost+=value;group['known_cost_usd']+=value
        status=row.get('evidence_status','unknown')
        if status not in ('unknown','estimated','reported','reconciled'):raise ValueError('invalid usage evidence')
        if status not in group['evidence_statuses']:group['evidence_statuses'].append(status)
        unknown_input+=row.get('input_tokens') is None
        unknown_output+=row.get('output_tokens') is None
        input_tokens+=row.get('input_tokens') or 0;output_tokens+=row.get('output_tokens') or 0
    return {'cost_usd':None if unknown else cost,'known_cost_usd':cost,'unknown_calls':unknown,
            'input_tokens':None if unknown_input else input_tokens,'output_tokens':None if unknown_output else output_tokens,
            'known_input_tokens':input_tokens,'known_output_tokens':output_tokens,'unknown_input_calls':unknown_input,'unknown_output_calls':unknown_output,'groups':list(groups.values())}
