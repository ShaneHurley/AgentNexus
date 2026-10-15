from __future__ import annotations
import ast, fnmatch, hashlib, os, re, shlex, subprocess, time
from pathlib import Path
from agent_core.contracts import ContractDenied
from agent_core.runtime_authority import RuntimeAuthority
from agent_core.isolation import DockerRunner, IsolationUnavailable

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

def _source_read_text(text,path,start,end):
    """Preserve proven Python references and control syntax; retain credential filters."""
    safe={}
    if path.suffix==".py" and len(text)<=1000000:
        try:
            tree=ast.parse(text)
            starts=[0]+[match.end() for match in re.finditer(r"\r\n|\r|\n",text)]
            def position(line,column):
                offset=starts[line-1]
                last=starts[line] if line<len(starts) else len(text)
                return offset+len(text[offset:last].encode("utf-8")[:column].decode("utf-8"))
            def reference(value):
                if isinstance(value,ast.Name): return True
                if isinstance(value,ast.Attribute): return reference(value.value)
                if isinstance(value,ast.Subscript):
                    index=value.slice
                    return reference(value.value) and (reference(index) or (isinstance(index,ast.Constant) and type(index.value) is int))
                return False
            for node in ast.walk(tree):
                if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and reference(node.value):
                    target=node.targets[0]; value=node.value
                    if target.id.casefold() not in {"api_key","apikey","secret","password","passwd","token","bearer","authorization"}: continue
                    if len(safe)==512: break
                    safe[position(target.lineno,target.col_offset)]=(position(value.lineno,value.col_offset),position(value.end_lineno,value.end_col_offset))
            sensitive={"api_key","apikey","secret","password","passwd","token","bearer","authorization"}
            controls=[node for node in ast.walk(tree) if isinstance(node,(ast.If,ast.While)) and node.body]
            control_ends={(node.test.end_lineno,node.test.end_col_offset) for node in controls}
            for node in controls:
                if len(safe)==512: break
                keyword={ast.Return:"return",ast.Raise:"raise",ast.Pass:"pass",ast.Break:"break",ast.Continue:"continue"}.get(type(node.body[0]))
                if keyword is None: continue
                first=node.body[0]; body=position(first.lineno,first.col_offset)
                for name in ast.walk(node.test):
                    if len(safe)==512: break
                    if not isinstance(name,ast.Name) or name.id.casefold() not in sensitive: continue
                    if (name.end_lineno,name.end_col_offset)!=(node.test.end_lineno,node.test.end_col_offset): continue
                    finish=position(name.end_lineno,name.end_col_offset)
                    if re.fullmatch(r"\s*:\s*",text[finish:body]) is None: continue
                    if len(safe)<512: safe[position(name.lineno,name.col_offset)]=(body+len(keyword),body+len(keyword))
            for node in ast.walk(tree):
                if len(safe)==512: break
                if (not isinstance(node,ast.Compare) or not isinstance(node.left,ast.Name) or node.left.id.casefold()!="token"
                    or len(node.ops)!=1 or not isinstance(node.ops[0],ast.Eq) or len(node.comparators)!=1
                    or not isinstance(node.comparators[0],ast.Constant) or node.comparators[0].value!="--"): continue
                name=node.left; first=position(name.end_lineno,name.end_col_offset)+1
                finish=position(node.end_lineno,node.end_col_offset)
                if (node.end_lineno,node.end_col_offset) in control_ends:
                    delimiter=re.match(r"\s*:",text[finish:])
                    if delimiter: finish+=delimiter.end()
                if len(safe)<512: safe[position(name.lineno,name.col_offset)]=(first,finish)
        except (SyntaxError,ValueError,RecursionError,IndexError): safe={}
    spans=[]
    for index,pattern in enumerate(SECRET_PATTERNS):
        for match in pattern.finditer(text):
            bounds=safe.get(match.start())
            if index==0 and bounds and bounds[0]<=match.end()<=bounds[1]: continue
            left,right=max(start,match.start()),min(end,match.end())
            if left<right: spans.append((left,right))
    merged=[]
    for left,right in sorted(spans):
        if merged and left<=merged[-1][1]: merged[-1]=(merged[-1][0],max(right,merged[-1][1]))
        else: merged.append((left,right))
    pieces=[]; cursor=start
    for left,right in merged:
        pieces.extend((text[cursor:left],"[REDACTED]")); cursor=right
    pieces.append(text[cursor:end])
    return "".join(pieces)

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
    def __init__(self,repo,tool_config,policy_config,extra_tools=None, *, authority=None, isolated_runner=None):
        self.repo=Path(repo).resolve(); self.tools=tool_config; self.policy=policy_config; self._extra=dict(extra_tools or {})
        self.authority=authority or RuntimeAuthority("dc",self.repo)
        configured=self.policy.get("execution_policy",{}).get("image")
        self.isolated_runner=isolated_runner or (DockerRunner(configured,self.repo,deny_paths=self.policy.get("path_policy",{}).get("deny",[])) if configured else None)
        if self.isolated_runner is not None and (type(self.isolated_runner) is not DockerRunner or self.isolated_runner.workspace != self.repo):
            raise ToolDenied("runner must be the workspace-bound Docker backend")

    def authorize(self,role,tool):
        try: self.authority.tool(role,tool)
        except ContractDenied as exc: raise ToolDenied(str(exc)) from exc
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

    def execute(self,role,tool,arguments,plan_allowlist=None,cancel_check=None):
        self.authorize(role,tool)
        args=dict(arguments or {})
        if tool in ("shell.readonly", "tests.run"):
            if self.isolated_runner is None:
                raise ToolDenied(f"{tool} requires a configured isolated execution runner")
            argv=args.get("argv") or shlex.split(args.get("command", ""))
            try:
                return self.isolated_runner.run(argv,timeout=int(args.get("timeout",900)),cancel_check=cancel_check) if cancel_check is not None else self.isolated_runner.run(argv,timeout=int(args.get("timeout",900)))
            except (IsolationUnavailable,ValueError) as exc:
                raise ToolDenied(str(exc)) from exc
        if tool.startswith(("filesystem.","patch.","repository.")):
            target=self.safe_path(args.get("path","."),tool in {"filesystem.write","patch.apply"},plan_allowlist)
            try: self.authority.tool(role,tool,target=target,write=tool in {"filesystem.write","patch.apply"})
            except ContractDenied as exc: raise ToolDenied(str(exc)) from exc
        if tool=="filesystem.read" and args.get("view")=="outline":
            from agent_core.efficiency_tools import repo_outline
            return repo_outline(target,self.authority.effective(role))
        if tool in self._extra:
            if tool.startswith(("filesystem.","patch.","repository.")):
                raise ToolDenied("typed built-in operations cannot be replaced by plugin callbacks")
            return self._extra[tool](args)
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
        p=self.safe_path(a["path"]); raw=p.read_bytes(); digest=hashlib.sha256(raw).hexdigest(); text=raw.decode("utf-8",errors="replace"); lines=text.splitlines()
        start=max(1,int(a.get("start",1))); end=min(len(lines),int(a.get("end",start+399)))
        chunks=text.splitlines(keepends=True); left=sum(len(line) for line in chunks[:start-1]); right=left+sum(len(line) for line in chunks[start-1:end])
        source=text[left:right]; source_clean=_source_read_text(text,p,left,right)
        clean="\n".join(f"{start+index}\t{line}" for index,line in enumerate(source_clean.splitlines()))
        return {"path":a["path"],"start":start,"end":end,"total_lines":len(lines),"sha256":digest,
                "content":clean[:MAX_OUTPUT_CHARS],"truncated":len(clean)>MAX_OUTPUT_CHARS,
                "ends_with_newline":raw.endswith(b"\n"),"source_text":source_clean[:MAX_OUTPUT_CHARS],"redacted":source_clean!=source,
                "expansion":{"path":a["path"],"start":start,"end":end,"sha256":digest,"instruction":"Request smaller line ranges when truncated; each read is reauthorized."} if len(clean)>MAX_OUTPUT_CHARS else None}
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
        argv=["diff","--no-ext-diff","--no-textconv","--unified=3"]
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
        expected=a.get("expected_sha256")
        if not expected:
            raise ToolDenied("expected_sha256 is required when patching a file")
        if expected!=file_sha(p):
            raise ToolDenied("file changed since it was read; re-read before patching")
        found=original.count(a["find"])
        if found!=1: raise ToolDenied(f"find text matched {found} times; it must match exactly once")
        p.write_text(original.replace(a["find"],a["replace"],1),encoding="utf-8")
        return {"path":a["path"],"applied":True,"sha256":file_sha(p)}

    # --- execution ----------------------------------------------------
    def _t_shell_readonly(self,a,_allow=None): return self._run(a.get("argv") or shlex.split(a["command"]),int(a.get("timeout",120)))
    def _t_tests_run(self,a,_allow=None): return self._run(a.get("argv") or shlex.split(a["command"]),int(a.get("timeout",900)))
    def _git(self,argv): return self._run(["git","-c","core.fsmonitor=false","-c","core.hooksPath=/dev/null"]+argv,60)
    def validate_command(self,argv):
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) for x in argv):
            raise ValueError("argv must be a non-empty string list")
        allow=self.policy.get("command_policy",{}).get("allow",DEFAULT_COMMAND_ALLOW)
        if Path(argv[0]).name != argv[0]:
            raise ToolDenied("command must be an allowlisted name, not an executable path")
        base=Path(argv[0]).name.lower()
        if base.endswith(".exe"): base=base[:-4]
        if base not in allow: raise ToolDenied(f"command {base} is not in the allowlist")
        return argv
    def _run(self,argv,timeout):
        argv=self.validate_command(argv)
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
        self.authorize(role,"filesystem.read")
        target=self.safe_path(path)
        try: self.authority.tool(role,"filesystem.read",target=target)
        except ContractDenied as exc: raise ToolDenied(str(exc)) from exc
        return redact(target.read_text(encoding="utf-8"))
    def write(self,role,path,content,plan_allowlist):
        raise ToolDenied("legacy write helper has no approval context; use PolicyGateway.execute")
    def run_tests(self,role,argv,timeout=300):
        return self.execute(role,"tests.run",{"argv":argv,"timeout":timeout})
