"""Explicitly scoped SQLite knowledge, with human-reviewed acceptance."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from urllib.parse import quote
from .contracts import EffectiveGrant, ContractDenied

SCHEMA_VERSION = 1
SCHEMA_SQL = '''
CREATE TABLE store_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,checksum TEXT NOT NULL);
CREATE TABLE records(id TEXT PRIMARY KEY,namespace TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,created_at REAL NOT NULL,updated_at REAL NOT NULL,author_identity TEXT NOT NULL,run_id TEXT NOT NULL,verification_state TEXT NOT NULL,sensitivity TEXT NOT NULL,content_hash TEXT NOT NULL,revision INTEGER NOT NULL,expires_at REAL,deleted_at REAL,stale INTEGER NOT NULL DEFAULT 0,conflicted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE sources(id TEXT PRIMARY KEY,locator TEXT NOT NULL,retrieved_at REAL NOT NULL,content_hash TEXT NOT NULL,retrieval_status TEXT NOT NULL,synthetic INTEGER NOT NULL);
CREATE TABLE record_sources(record_id TEXT REFERENCES records(id),source_id TEXT REFERENCES sources(id),span TEXT NOT NULL DEFAULT '',PRIMARY KEY(record_id,source_id,span));
CREATE TABLE relationships(src_id TEXT REFERENCES records(id),dst_store_id TEXT NOT NULL,dst_id TEXT NOT NULL,kind TEXT NOT NULL,PRIMARY KEY(src_id,dst_store_id,dst_id,kind));
CREATE TABLE dependencies(record_id TEXT REFERENCES records(id),key TEXT NOT NULL,fingerprint TEXT NOT NULL,PRIMARY KEY(record_id,key));
CREATE TABLE promotions(source_store TEXT,source_id TEXT,destination_id TEXT REFERENCES records(id),source_hash TEXT,transformation TEXT,approved_by TEXT,at REAL);
CREATE TABLE record_revisions(id TEXT PRIMARY KEY,record_id TEXT REFERENCES records(id),event TEXT,previous_hash TEXT,new_hash TEXT,actor_identity TEXT,run_id TEXT,at REAL);
CREATE TABLE memory_tombstones(record_id TEXT PRIMARY KEY REFERENCES records(id),deleted_at REAL,purge_after REAL);
CREATE TABLE import_lineage(record_id TEXT REFERENCES records(id),source_store TEXT,source_id TEXT,source_hash TEXT,PRIMARY KEY(record_id,source_store,source_id));
CREATE VIRTUAL TABLE records_fts USING fts5(title,body,record_id UNINDEXED,namespace UNINDEXED);
'''
SCHEMA_CHECKSUM = hashlib.sha256(SCHEMA_SQL.encode()).hexdigest()
_LOCKS: dict[str,threading.RLock] = {}
_LOCK_GUARD = threading.Lock()
MAX_TEXT = 200_000

def safe_path(path):
    p=Path(path).expanduser().absolute()
    for part in (p,*p.parents):
        if part.is_symlink(): raise ValueError('symlink paths are forbidden')
    return p.resolve()

def record_hash(record):
    data={k:record[k] for k in ('namespace','kind','title','body','sensitivity')}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def _text(value,name,limit=MAX_TEXT,empty=False):
    if not isinstance(value,str) or (not empty and not value.strip()) or len(value)>limit or '\x00' in value: raise ValueError('invalid '+name)
    return value

def _timestamp(value):
    if isinstance(value,str):
        try: value=datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
        except ValueError: raise ValueError('invalid timestamp') from None
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError('invalid timestamp')
    return float(value)

def _uuid(value):
    try: return str(uuid.UUID(str(value)))
    except (ValueError,TypeError): raise ValueError('invalid UUID') from None

def _secret_check(value, _depth=0):
    if _depth>16: raise ValueError('credential validation nesting exceeded')
    forbidden={'password','secret','api_key','access_token','private_key','credentials'}
    if isinstance(value,dict):
        for key,item in value.items():
            if str(key).lower() in forbidden: raise ValueError('structured credential field forbidden')
            _secret_check(item,_depth+1)
    elif isinstance(value,(list,tuple)):
        for item in value: _secret_check(item,_depth+1)
    elif isinstance(value,str):
        # Match recognizable provider formats, not arbitrary high-entropy prose.
        token_pattern=r"(?:sk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{20,}|ant-api\d{2}-[A-Za-z0-9_-]{20,}|[A-Za-z0-9]{20,})|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
        assignment=r"(?i)(?:password|api[_-]?key|access[_-]?token|secret)\s*[=:]\s*[^\s,}\"']+"
        structured=r'(?i)["\'](?:password|secret|api_key|access_token|private_key|credentials)["\']\s*:'
        if re.search(token_pattern,value) or re.search(assignment,value) or re.search(structured,value): raise ValueError('credential material forbidden')
        text=value.strip()
        if text[:1] in ('{','[','"'):
            try: decoded=json.loads(text)
            except (ValueError,RecursionError): return
            if isinstance(decoded,(dict,list,str)) and decoded!=value: _secret_check(decoded,_depth+1)

@dataclass(frozen=True)
class MemoryAccess:
    identity: str
    run_id: str
    effective_grant: EffectiveGrant
    def __post_init__(self):
        _text(self.identity,'identity',256); _text(self.run_id,'run_id',256)
        if not isinstance(self.effective_grant,EffectiveGrant): raise ValueError('effective grant required')

class KnowledgeStore:
    def __init__(self,path):
        self.path=safe_path(path)
        if not self.path.is_file(): raise FileNotFoundError(self.path)
        with _LOCK_GUARD: self._lock=_LOCKS.setdefault(str(self.path),threading.RLock())
        with self.connect() as db:
            try:
                meta=dict(db.execute('SELECT key,value FROM store_meta'))
                version=int(meta['schema_version'])
                if version!=SCHEMA_VERSION: raise ValueError('unsupported schema version')
                row=db.execute('SELECT checksum FROM schema_migrations WHERE version=?',(version,)).fetchone()
                if row is None or row[0]!=SCHEMA_CHECKSUM: raise ValueError('schema migration checksum mismatch')
                reference=sqlite3.connect(':memory:')
                try:
                    reference.executescript(SCHEMA_SQL)
                    expected=dict(reference.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
                finally: reference.close()
                actual=dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
                if actual!=expected: raise ValueError('schema structure mismatch')
                self.store_id=_uuid(meta['store_id']); self.kind=meta['kind']
                if self.kind not in ('project','research','daily','shared'): raise ValueError('invalid store kind')
            except (sqlite3.Error,KeyError,TypeError): raise ValueError('invalid knowledge schema') from None

    @classmethod
    def create(cls,path,*,store_id,kind,access,raw_run_retention_days,confirmed=False):
        if confirmed is not True: raise ValueError('confirmation required')
        sid=_uuid(store_id)
        if kind not in ('project','research','daily','shared'): raise ValueError('invalid store kind')
        retention=raw_run_retention_days
        if retention!='none' and (isinstance(retention,bool) or not isinstance(retention,int) or retention<0): raise ValueError('explicit raw retention required')
        p=safe_path(path)
        access.effective_grant.authorize('memory_write',f'store:{sid}:meta',p)
        if not p.parent.is_dir(): raise FileNotFoundError(p.parent)
        # Exclusive creation prevents overwriting another store.
        with p.open('xb'): pass
        try:
            db=sqlite3.connect(p)
            db.executescript(SCHEMA_SQL)
            db.executemany('INSERT INTO store_meta VALUES (?,?)',[('store_id',sid),('kind',kind),('schema_version',str(SCHEMA_VERSION)),('generation','0'),('raw_run_retention_days',str(retention))])
            db.execute('INSERT INTO schema_migrations VALUES (?,?)',(SCHEMA_VERSION,SCHEMA_CHECKSUM)); db.commit(); db.close()
            return cls(p)
        except BaseException:
            p.unlink(missing_ok=True)
            raise

    @contextmanager
    def connect(self,write=False):
        safe_path(self.path)
        acquired=False
        if write:
            acquired=self._lock.acquire(timeout=2)
            if not acquired: raise sqlite3.OperationalError('writer busy')
        db=None
        try:
            db=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=rw',uri=True,timeout=2,isolation_level=None)
            db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA busy_timeout=2000')
            if write:
                db.execute('PRAGMA journal_mode=WAL'); db.execute('BEGIN IMMEDIATE')
            if not write: db.execute('PRAGMA query_only=ON')
            yield db
            if write: db.commit()
        except BaseException:
            if db is not None and write: db.rollback()
            raise
        finally:
            if db is not None: db.close()
            if acquired: self._lock.release()

    @property
    def metadata(self):
        with self.connect() as db: result=dict(db.execute('SELECT key,value FROM store_meta'))
        for k in ('schema_version','generation'): result[k]=int(result[k])
        if result['raw_run_retention_days']!='none': result['raw_run_retention_days']=int(result['raw_run_retention_days'])
        return result

    def close(self): pass
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
    def _authorize(self,access,namespace,write=False):
        _text(namespace,'namespace',128)
        access.effective_grant.authorize('memory_write' if write else 'memory_read',f'store:{self.store_id}:{namespace}',self.path)
    @staticmethod
    def _row_dict(row): return dict(row)
    @staticmethod
    def _bump(db): db.execute("UPDATE store_meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
    def _class(self,access,sensitivity): access.effective_grant.authorize('data_classes',sensitivity)
    def _audit(self,db,record,access,event,previous=None):
        db.execute('INSERT INTO record_revisions VALUES (?,?,?,?,?,?,?,?)',(str(uuid.uuid4()),record['id'],event,previous,record['content_hash'],access.identity,access.run_id,time.time()))
    def _expanded(self,db,row):
        result=dict(row)
        result['sources']=[dict(x) for x in db.execute('SELECT s.*,rs.span FROM sources s JOIN record_sources rs ON s.id=rs.source_id WHERE rs.record_id=? ORDER BY s.id',(result['id'],))]
        result['dependencies']=dict(db.execute('SELECT key,fingerprint FROM dependencies WHERE record_id=?',(result['id'],)))
        result['relationships']=[dict(x) for x in db.execute('SELECT * FROM relationships WHERE src_id=?',(result['id'],))]
        return result
    def _get(self,db,record_id,access,write=False,include_deleted=False):
        row=db.execute('SELECT * FROM records WHERE id=?',(_uuid(record_id),)).fetchone()
        if row is None: raise KeyError(record_id)
        self._authorize(access,row['namespace'],write); self._class(access,row['sensitivity'])
        if row['deleted_at'] is not None and not include_deleted: raise KeyError(record_id)
        return row
    def inspect(self,record_id,access,*,include_deleted=False):
        with self.connect() as db: return self._expanded(db,self._get(db,record_id,access,include_deleted=include_deleted))
    def _validated(self,payload):
        p=dict(payload); _secret_check(p)
        p.setdefault('namespace','default'); p.setdefault('kind','note'); p.setdefault('sensitivity','private')
        for key in ('namespace','kind'): _text(p[key],key,128)
        for key in ('title','body'): _text(p[key],key,empty=key=='body')
        if p['sensitivity'] not in ('public','private','restricted'): raise ValueError('invalid sensitivity')
        sources=p.get('sources')
        if not isinstance(sources,list) or not sources or len(sources)>128: raise ValueError('source provenance required')
        normalized=[]
        for source in sources:
            if not isinstance(source,dict): raise ValueError('invalid provenance')
            if set(source)-{'id','locator','retrieved_at','content_hash','retrieval_status','synthetic','span'}: raise ValueError('unknown source fields')
            s=dict(source); s.setdefault('id',str(uuid.uuid4())); s.setdefault('span','')
            for key in ('id','locator','content_hash'): _text(s.get(key),key,4096)
            if not re.fullmatch('[a-fA-F0-9]{64}',s['content_hash']): raise ValueError('source hash required')
            s['retrieved_at']=_timestamp(s.get('retrieved_at'))
            if s.get('retrieval_status') not in ('provided','retrieved','partial','failed','unavailable'): raise ValueError('invalid retrieval status')
            if not isinstance(s.get('synthetic'),(bool,int)) or s['synthetic'] not in (True,False): raise ValueError('synthetic flag required')
            s['synthetic']=int(s['synthetic']); _text(s['span'],'span',4096,empty=True); normalized.append(s)
        p['sources']=normalized
        deps=p.get('dependencies') or {}
        if not isinstance(deps,dict) or len(deps)>256: raise ValueError('invalid dependencies')
        for key,value in deps.items(): _text(key,'dependency key',4096); _text(value,'fingerprint',4096)
        p['dependencies']=deps
        p['id']=_uuid(p.get('record_id') or p.get('id') or str(uuid.uuid4()))
        expires=p.get('expires_at')
        p['expires_at']=_timestamp(expires) if expires is not None else time.time()+30*86400 if p['kind']=='cache' else None
        p['content_hash']=record_hash(p)
        return p
    def _insert_draft(self,db,access,payload):
        p=self._validated(payload); self._authorize(access,p['namespace'],True); self._class(access,p['sensitivity'])
        old=db.execute('SELECT * FROM records WHERE id=?',(p['id'],)).fetchone()
        if old is not None:
            self._authorize(access,old['namespace'],True); self._class(access,old['sensitivity'])
            if old['content_hash']!=p['content_hash'] or old['deleted_at'] is not None: raise ValueError('record ID conflict')
            if old['verification_state']!='draft': raise ValueError('accepted records require reviewed revision')
        else:
            now=time.time()
            db.execute('INSERT INTO records(id,namespace,kind,title,body,created_at,updated_at,author_identity,run_id,verification_state,sensitivity,content_hash,revision,expires_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(p['id'],p['namespace'],p['kind'],p['title'],p['body'],now,now,access.identity,access.run_id,'draft',p['sensitivity'],p['content_hash'],1,p['expires_at']))
            db.execute('INSERT INTO records_fts VALUES (?,?,?,?)',(p['title'],p['body'],p['id'],p['namespace']))
        for s in p['sources']:
            keys=('id','locator','retrieved_at','content_hash','retrieval_status','synthetic'); values=tuple(s[k] for k in keys)
            exists=db.execute('SELECT * FROM sources WHERE id=?',(s['id'],)).fetchone()
            if exists is not None and tuple(exists[k] for k in keys)!=values: raise ValueError('source ID conflict')
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?)',values)
            db.execute('INSERT OR IGNORE INTO record_sources VALUES (?,?,?)',(p['id'],s['id'],s['span']))
        for key,value in p['dependencies'].items():
            exists=db.execute('SELECT fingerprint FROM dependencies WHERE record_id=? AND key=?',(p['id'],key)).fetchone()
            if exists and exists[0]!=value: raise ValueError('dependency conflict')
            db.execute('INSERT OR IGNORE INTO dependencies VALUES (?,?,?)',(p['id'],key,value))
        self._audit(db,p,access,'draft'); self._bump(db)
        return self._expanded(db,db.execute('SELECT * FROM records WHERE id=?',(p['id'],)).fetchone())
    def add_draft(self,access,*,namespace='default',kind='note',title,body,sources,dependencies=None,sensitivity='private',record_id=None,expires_at=None):
        payload=dict(namespace=namespace,kind=kind,title=title,body=body,sources=sources,dependencies=dependencies,sensitivity=sensitivity,record_id=record_id,expires_at=expires_at)
        with self.connect(write=True) as db: return self._insert_draft(db,access,payload)
    def accept(self,record_id,access,*,expected_hash,confirmed=False):
        if confirmed is not True: raise ValueError('confirmation required')
        with self.connect(write=True) as db:
            row=self._get(db,record_id,access,True)
            if row['content_hash']!=expected_hash: raise ValueError('stale content hash')
            sources=db.execute('SELECT s.* FROM sources s JOIN record_sources rs ON s.id=rs.source_id WHERE rs.record_id=?',(row['id'],)).fetchall()
            if not sources or any(s['synthetic'] or s['retrieval_status'] in ('failed','unavailable') for s in sources): raise ValueError('unverified source cannot be accepted')
            if row['conflicted']: raise ValueError('conflicted record')
            db.execute("UPDATE records SET verification_state='accepted',updated_at=? WHERE id=?",(time.time(),row['id']))
            self._audit(db,row,access,'accept',expected_hash); self._bump(db)
            return self._expanded(db,db.execute('SELECT * FROM records WHERE id=?',(row['id'],)).fetchone())
    def search(self,query,access,*,namespace='default',include_drafts=False,limit=8,token_budget=4000,fingerprints=None):
        self._authorize(access,namespace)
        _text(query,'query',4096)
        if not isinstance(include_drafts,bool): raise ValueError('include_drafts requires boolean')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=8: raise ValueError('invalid limit')
        if isinstance(token_budget,bool) or not isinstance(token_budget,int) or not 1<=token_budget<=4000: raise ValueError('invalid token budget')
        if fingerprints is not None and not isinstance(fingerprints,dict): raise ValueError('invalid fingerprints')
        out=[]; used=0
        with self.connect() as db:
            try: rows=db.execute("SELECT r.* FROM records_fts f JOIN records r ON r.id=f.record_id WHERE records_fts MATCH ? AND r.namespace=? AND r.deleted_at IS NULL AND r.stale=0 AND r.conflicted=0 AND (r.expires_at IS NULL OR r.expires_at>?) AND (r.verification_state='accepted' OR ?) ORDER BY bm25(records_fts) LIMIT 1000",(query,namespace,time.time(),int(bool(include_drafts)))).fetchall()
            except sqlite3.OperationalError: raise ValueError('malformed FTS query') from None
            for row in rows:
                try: self._class(access,row['sensitivity'])
                except ContractDenied: continue
                expanded=self._expanded(db,row)
                if any((fingerprints or {}).get(key)!=fp for key,fp in expanded['dependencies'].items()): continue
                # UTF-8 bytes conservatively bound token count without an external tokenizer.
                cost=len(json.dumps(expanded,ensure_ascii=False).encode())
                if used+cost>token_budget: continue
                out.append(expanded); used+=cost
                if len(out)>=limit: break
        return out
    def refresh_dependencies(self,access,fingerprints,*,namespace='default'):
        self._authorize(access,namespace,True)
        if not isinstance(fingerprints,dict): raise ValueError('invalid fingerprints')
        checked=stale=0
        with self.connect(write=True) as db:
            rows=db.execute('SELECT * FROM records WHERE namespace=? AND deleted_at IS NULL',(namespace,)).fetchall()
            for row in rows:
                self._class(access,row['sensitivity']); deps=dict(db.execute('SELECT key,fingerprint FROM dependencies WHERE record_id=?',(row['id'],)))
                if not deps: continue
                checked+=1
                if any(fingerprints.get(k)!=v for k,v in deps.items()) and not row['stale']:
                    db.execute('UPDATE records SET stale=1,updated_at=? WHERE id=?',(time.time(),row['id'])); stale+=1
            if stale: self._bump(db)
        return dict(checked=checked,stale=stale)
    def revise(self,record_id,access,*,expected_hash,title,body,sources,confirmed=False):
        if confirmed is not True: raise ValueError('confirmation required')
        with self.connect(write=True) as db:
            old=self._get(db,record_id,access,True)
            if old['content_hash']!=expected_hash: raise ValueError('stale content hash')
            new=self._insert_draft(db,access,dict(namespace=old['namespace'],kind=old['kind'],title=title,body=body,sources=sources,sensitivity=old['sensitivity'],dependencies=dict(db.execute('SELECT key,fingerprint FROM dependencies WHERE record_id=?',(old['id'],)))))
            db.execute('UPDATE records SET revision=? WHERE id=?',(old['revision']+1,new['id']))
            db.execute('UPDATE records SET stale=1 WHERE id=?',(old['id'],))
            db.execute('INSERT INTO relationships VALUES (?,?,?,?)',(new['id'],self.store_id,old['id'],'supersedes'))
            self._audit(db,new,access,'revise',expected_hash)
            return self._expanded(db,db.execute('SELECT * FROM records WHERE id=?',(new['id'],)).fetchone())
    def namespaces(self,access,*,write=False):
        action='memory_write' if write else 'memory_read'
        prefix=f'store:{self.store_id}:'
        result=[]
        for capability in sorted(access.effective_grant.capabilities(action)):
            if capability.startswith(prefix):
                namespace=capability[len(prefix):]; self._authorize(access,namespace,write); result.append(namespace)
        return result
