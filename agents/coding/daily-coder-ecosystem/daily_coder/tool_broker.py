from __future__ import annotations
import fnmatch, hashlib, os, re, shlex, subprocess, time
from pathlib import Path

class ToolDenied(PermissionError): pass

DEFAULT_COMMAND_ALLOW=["python","python3","py","pytest","npm","npx","node","go","cargo","dotnet","git","make","ruff","mypy"]
SECRET_PATTERNS=[re.compile(r"(?i)\b(api[-_ ]?key|secret|password|passwd|token|bearer|authorization)\b\s*[:=]\s*\S+"),
                 re.compile(r"\b(sk-|ghp_|gho_|xox[baprs]-)[A-Za-z0-9_\-]{10,}"),
                 re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----")]
MAX_OUTPUT_CHARS=20000

def redact(text):
    if not isinstance(text,str): return text
    for p in SECRET_PATTERNS: text=p.sub("[REDACTED]",text)
    return text

def bounded_output(text,limit=MAX_OUTPUT_CHARS):
    text=redact(text or "")
    if len(text)<=limit: return text
    half=limit//2
    return text[:half]+f"\n...[{len(text)-limit} chars omitted]...\n"+text[-half:]

def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(65536),b""): h.update(block)
    return h.hexdigest()

class ToolBroker:
    def __init__(self,repo,tool_config,policy_config,extra_tools=None):
        self.repo=Path(repo).resolve(); self.tools=tool_config; self.policy=policy_config; self._extra=dict(extra_tools or {})

    def authorize(self,role,tool):
        if tool not in self.tools["role_allowlists"].get(role,[]): raise ToolDenied(f"{role} is not allowed to use {tool}")
        if tool in self.tools.get("disabled_until_adapter_configured",[]) and tool not in self._extra:
            raise ToolDenied(f"{tool} has no configured adapter")

    def register(self,name,fn):
        """Register a configured adapter (for example web.fetch) at runtime."""
        self._extra[name]=fn

    def safe_path(self,path,write=False,plan_allowlist=None):
        candidate=Path(path)
        p=(self.repo/candidate) if not candidate.is_absolute() else candidate
        # resolve() collapses symlinks, so a symlinked escape cannot survive the jail check.
        p=p.resolve()
        if self.repo!=p and self.repo not in p.parents: raise ToolDenied("path escapes repository root")
        rel=p.relative_to(self.repo).as_posix() if p!=self.repo else "."
        deny=self.policy.get("path_policy",{}).get("deny",[])
        if any(fnmatch.fnmatch(rel,g) for g in deny): raise ToolDenied("path denied by policy")
        if write and self.policy.get("path_policy",{}).get("write_requires_plan_allowlist",True):
            if not plan_allowlist or not any(fnmatch.fnmatch(rel,g) for g in plan_allowlist):
                raise ToolDenied("write path not in approved plan allowlist")
        return p

    def execute(self,role,tool,arguments,plan_allowlist=None):
        self.authorize(role,tool)
        args=dict(arguments or {})
        if tool in self._extra: return self._extra[tool](args)
        handlers={
            "filesystem.read":self._t_filesystem_read,"filesystem.list":self._t_filesystem_list,
            "filesystem.search":self._t_filesystem_search,"filesystem.write":self._t_filesystem_write,
            "patch.apply":self._t_patch_apply,"repository.status":self._t_repository_status,
            "repository.diff":self._t_repository_diff,"repository.history":self._t_repository_history,
            "shell.readonly":self._t_shell_readonly,"tests.run":self._t_tests_run,
        }
        handler=handlers.get(tool)
        if handler is None: raise ToolDenied(f"{tool} has no implementation")
        return handler(args,plan_allowlist)

    # --- read ---------------------------------------------------------
    def _t_filesystem_read(self,a,_allow=None):
        p=self.safe_path(a["path"]); text=p.read_text(encoding="utf-8",errors="replace"); lines=text.splitlines()
        start=max(1,int(a.get("start",1))); end=min(len(lines),int(a.get("end",start+399)))
        body="\n".join(f"{i}\t{lines[i-1]}" for i in range(start,end+1)) if lines else ""
        return {"path":a["path"],"start":start,"end":end,"total_lines":len(lines),"sha256":file_sha(p),
                "content":redact(body)[:MAX_OUTPUT_CHARS]}
    def _t_filesystem_list(self,a,_allow=None):
        p=self.safe_path(a.get("path","."))
        return {"path":a.get("path","."),"entries":[{"name":c.name,"dir":c.is_dir()} for c in sorted(p.iterdir())[:500]]}
    def _t_filesystem_search(self,a,_allow=None):
        needle=a["query"].lower(); limit=min(int(a.get("max_results",50)),200)
        deny=self.policy.get("path_policy",{}).get("deny",[]); hits=[]
        for path in self.repo.glob(a.get("glob","**/*")):
            if len(hits)>=limit: break
            if not path.is_file(): continue
            rel=path.relative_to(self.repo).as_posix()
            if any(fnmatch.fnmatch(rel,g) for g in deny): continue
            try:
                safe=self.safe_path(rel)
                for n,line in enumerate(safe.read_text(encoding="utf-8",errors="ignore").splitlines(),1):
                    if needle in line.lower(): hits.append({"path":rel,"line":n,"text":redact(line.strip())[:300]}); break
            except OSError: continue
        return {"query":a["query"],"hits":hits}
    def _t_repository_status(self,a,_allow=None): return self._git(["status","--porcelain=v1","--branch"])
    def _t_repository_diff(self,a,_allow=None):
        argv=["diff","--unified=3"]
        if a.get("staged"): argv.append("--cached")
        if a.get("path"): self.safe_path(a["path"]); argv+=["--",a["path"]]
        return self._git(argv)
    def _t_repository_history(self,a,_allow=None):
        return self._git(["log",f"-{min(int(a.get('limit',10)),50)}","--oneline","--no-color"])

    # --- write --------------------------------------------------------
    def _t_filesystem_write(self,a,plan_allowlist=None):
        p=self.safe_path(a["path"],True,plan_allowlist); expected=a.get("expected_sha256")
        if p.exists():
            if not expected: raise ToolDenied("expected_sha256 is required when overwriting an existing file")
            if expected!=file_sha(p): raise ToolDenied("file changed since it was read; re-read before writing")
        p.parent.mkdir(parents=True,exist_ok=True); p.write_text(a["content"],encoding="utf-8")
        return {"path":a["path"],"bytes":len(a["content"]),"sha256":file_sha(p)}
    def _t_patch_apply(self,a,plan_allowlist=None):
        p=self.safe_path(a["path"],True,plan_allowlist); original=p.read_text(encoding="utf-8")
        if a.get("expected_sha256") and a["expected_sha256"]!=file_sha(p):
            raise ToolDenied("file changed since it was read; re-read before patching")
        found=original.count(a["find"])
        if found!=1: raise ToolDenied(f"find text matched {found} times; it must match exactly once")
        p.write_text(original.replace(a["find"],a["replace"],1),encoding="utf-8")
        return {"path":a["path"],"applied":True,"sha256":file_sha(p)}

    # --- execution ----------------------------------------------------
    def _t_shell_readonly(self,a,_allow=None): return self._run(a.get("argv") or shlex.split(a["command"]),int(a.get("timeout",120)))
    def _t_tests_run(self,a,_allow=None): return self._run(a.get("argv") or shlex.split(a["command"]),int(a.get("timeout",900)))
    def _git(self,argv): return self._run(["git"]+argv,60)
    def _run(self,argv,timeout):
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) for x in argv):
            raise ValueError("argv must be a non-empty string list")
        allow=self.policy.get("command_policy",{}).get("allow",DEFAULT_COMMAND_ALLOW)
        if Path(argv[0]).name != argv[0]:
            raise ToolDenied("command must be an allowlisted name, not an executable path")
        base=Path(argv[0]).name.lower()
        if base.endswith(".exe"): base=base[:-4]
        if base not in allow: raise ToolDenied(f"command {base} is not in the allowlist")
        env={k:v for k,v in {"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT",""),
             "HOME":os.environ.get("HOME",""),"PYTHONIOENCODING":"utf-8"}.items() if v}
        started=time.time()
        try:
            cp=subprocess.run(argv,cwd=self.repo,capture_output=True,text=True,timeout=timeout,env=env)
        except subprocess.TimeoutExpired:
            return {"argv":argv,"returncode":None,"timeout":True,"duration_s":timeout,"stdout":"","stderr":f"timed out after {timeout}s"}
        return {"argv":argv,"returncode":cp.returncode,"timeout":False,"duration_s":round(time.time()-started,3),
            "stdout":bounded_output(cp.stdout),"stderr":bounded_output(cp.stderr)}

    # --- compatibility helpers ----------------------------------------
    def read(self,role,path):
        self.authorize(role,"filesystem.read"); return self.safe_path(path).read_text(encoding="utf-8")
    def write(self,role,path,content,plan_allowlist):
        self.authorize(role,"filesystem.write"); p=self.safe_path(path,True,plan_allowlist)
        p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding="utf-8")
    def run_tests(self,role,argv,timeout=300):
        self.authorize(role,"tests.run"); return self._run(argv,timeout)
