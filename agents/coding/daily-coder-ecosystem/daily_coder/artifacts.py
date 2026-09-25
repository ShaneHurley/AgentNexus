from __future__ import annotations
import json, os, re, tempfile, time, uuid
from pathlib import Path
from .util import canonical_json, sha256_text

class ArtifactStore:
    def __init__(self,root,state): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True); self.state=state
    def put(self,run_id,kind,producer,payload):
        try: uuid.UUID(run_id)
        except (ValueError, AttributeError): raise ValueError("invalid artifact run_id")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+",kind): raise ValueError("invalid artifact kind")
        envelope={"schema_version":"1.0","run_id":run_id,"kind":kind,"producer_role":producer,"created_at":time.time(),"payload":payload}
        body=canonical_json(envelope); h=sha256_text(body)
        dest=self.root/run_id/kind/f"{h}.json"; dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():
            fd,tmp=tempfile.mkstemp(dir=dest.parent,prefix='.tmp-')
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(json.dumps(envelope,indent=2)+"\n"); f.flush(); os.fsync(f.fileno())
                os.replace(tmp,dest)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        self.state.record_artifact(h,run_id,kind,dest,producer)
        return {"hash":h,"path":str(dest),"kind":kind}

    def load(self,run_id,kind):
        """Return the most recent payload of `kind`, or None. Artifacts are evidence, not state."""
        rows=[r for r in self.state.artifacts(run_id) if r["kind"]==kind]
        if not rows: return None
        path=Path(rows[-1]["path"])
        if not path.exists(): return None
        return json.loads(path.read_text(encoding="utf-8")).get("payload")

    def load_all(self,run_id):
        out={}
        for row in self.state.artifacts(run_id):
            path=Path(row["path"])
            if path.exists():
                out[row["kind"]]=json.loads(path.read_text(encoding="utf-8")).get("payload")
        return out
