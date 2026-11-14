#!/usr/bin/env python3
"""Install simpleIDE into a project (or globally) for Claude, Cursor, Codex and Antigravity.

  python3 install.py --target /path/to/project            # all four tools
  python3 install.py --target . --tools claude,cursor
  python3 install.py --global                             # every project on this machine
  python3 install.py --target . --uninstall
  python3 install.py --target . --dry-run

Standard library only. It writes only files it owns (sx-* agents, the simpleide skill,
.simpleide/) and one marked block in instruction files; everything else is left alone.
"""
import argparse
import hashlib
import os
import shlex
import tempfile
import json
import re
import shutil
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
TOOLS = ("claude", "cursor", "codex", "antigravity")
START = "<!-- simpleIDE:start (managed by simpleIDE/install.py; edit simpleIDE/core/rule.md instead) -->"
END = "<!-- simpleIDE:end -->"
BLOCK_RE = re.compile(r"\n*<!-- simpleIDE:start.*?<!-- simpleIDE:end -->\n*", re.S)


def matching(text, start):
    """Return the close bracket for a JSON object/array, ignoring quoted text."""
    pairs = {"{": "}", "[": "]"}
    stack, quoted, escaped = [], False, False
    for i in range(start, len(text)):
        ch = text[i]
        if quoted:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': quoted = False
            continue
        if ch == '"': quoted = True
        elif ch in pairs: stack.append(pairs[ch])
        elif ch in ("}", "]"):
            if not stack or stack.pop() != ch:
                raise ValueError("malformed JSON")
            if not stack: return i
    raise ValueError("unclosed JSON container")


def event_span(text, event):
    hooks = re.search(r'"hooks"\s*:\s*\{', text)
    if not hooks: return None
    end = matching(text, hooks.end() - 1)
    match = re.search(r'"' + re.escape(event) + r'"\s*:\s*\[', text[hooks.end():end])
    if not match: return None
    key_start = hooks.end() + match.start()
    arr_start = hooks.end() + match.end() - 1
    return key_start, arr_start, matching(text, arr_start)


def legacy_hook(entry):
    command = entry.get("command") if isinstance(entry, dict) else None
    if not command and isinstance(entry, dict) and isinstance(entry.get("hooks"), list) and len(entry["hooks"]) == 1:
        h = entry["hooks"][0]
        if not isinstance(h, dict) or set(h) != {"type", "command"} or h["type"] != "command": return False
        if set(entry) - {"hooks", "matcher"}: return False
        command = h["command"]
    elif not isinstance(entry, dict) or set(entry) - {"command", "failClosed"}:
        return False
    return isinstance(command, str) and bool(re.fullmatch(
        r"python3 (?:\.simpleide/sx\.py|~/\.simpleide/sx\.py) hook (?:capture-request|dispatch-guard|shell-guard|return-log|stop-check|resume) --host (?:cursor|claude|codex)", command))


def sx_command(mem_dir, is_global):
    if is_global:
        return "python3 " + shlex.quote(str(mem_dir / "sx.py"))
    locator = 'from pathlib import Path; p=Path.cwd().resolve(); print(next(d / ".simpleide/sx.py" for d in (p,*p.parents) if (d / ".simpleide/sx.py").is_file()))'
    return 'python3 "$(python3 -c ' + shlex.quote(locator) + ')"'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def remove_owned_from_array(text, event, owned=()):
    """Remove only trailing simpleIDE entries, leaving preexisting entry bytes untouched."""
    span = event_span(text, event)
    if not span: return text
    _, start, end = span
    inner = text[start + 1:end]
    decoder = json.JSONDecoder()
    pos, elements = 0, []
    while pos < len(inner):
        while pos < len(inner) and (inner[pos].isspace() or inner[pos] == ','): pos += 1
        if pos >= len(inner): break
        value, width = decoder.raw_decode(inner[pos:])
        elements.append((pos, pos + width, value))
        pos += width
    if not elements: return text
    kept = [e for e in elements if e[2] not in owned and not legacy_hook(e[2])]
    if len(kept) == len(elements): return text
    # Installer always appends its entries. If a user later appends their own,
    # preserve those elements verbatim while replacing only the separators.
    original = [inner[a:b] for a, b, _ in kept]
    new_inner = ", ".join(original)
    return text[:start + 1] + new_inner + text[end:]


def remove_empty_event(text, event):
    span = event_span(text, event)
    if not span or text[span[1] + 1:span[2]].strip(): return text
    key_start, _, end = span
    hooks = re.search(r'"hooks"\s*:\s*\{', text)
    before = text[hooks.end():key_start]
    if ',' in before:
        comma = hooks.end() + before.rfind(',')
        return text[:comma] + text[end + 1:]
    after = re.match(r'\s*,', text[end + 1:])
    if after:
        return text[:key_start] + text[end + 1 + after.end():]
    return text[:key_start] + text[end + 1:]


def load_agents():
    agents = []
    for f in sorted((SRC / "agents").glob("sx-*.md")):
        _, fm, body = f.read_text(encoding="utf-8").split("---\n", 2)
        meta = dict(l.split(": ", 1) for l in fm.strip().splitlines())
        meta["readonly"] = meta.get("readonly") == "true"
        meta["body"] = body.strip() + "\n"
        agents.append(meta)
    return agents


def render_md(a, tool, models):
    m = models.get(tool, {}).get(a["role"], {})
    fm = ["name: " + a["name"], "description: " + a["description"]]
    if tool == "claude":
        if a.get("claude_tools"):
            fm.append("tools: " + a["claude_tools"])
        fm.append("model: " + (m.get("model") or "inherit"))
    elif tool == "antigravity":
        fm += ["subagent: true", "mainAgent: false", "model: " + (m.get("model") or "inherit")]
    else:  # cursor
        fm.append("model: " + (m.get("model") or "inherit"))
        if a["readonly"]:
            fm.append("readonly: true")
    return "---\n" + "\n".join(fm) + "\n---\n" + a["body"]


def render_toml(a, models):
    m = models.get("codex", {}).get(a["role"], {})
    out = ["name = " + json.dumps(a["name"]), "description = " + json.dumps(a["description"])]
    if m.get("model"):
        out.append("model = " + json.dumps(m["model"]))
    if m.get("effort"):
        out.append("model_reasoning_effort = " + json.dumps(m["effort"]))
    assert "'''" not in a["body"]
    out.append("developer_instructions = '''\n" + a["body"] + "'''")
    return "\n".join(out) + "\n"


class Installer:
    def __init__(self, dry, command="", hook_entries=None):
        self.dry, self.command = dry, command
        self.log, self.changes = [], {}
        self.hook_entries = hook_entries or {}

    def read(self, path):
        return self.changes[path] if path in self.changes else path.read_text(encoding="utf-8") if path.exists() else ""

    def write(self, path, text):
        self.log.append("write   %s" % path)
        self.changes[path] = text

    def remove(self, path):
        if path.exists():
            if path.is_dir(): raise ValueError("refusing directory deletion: " + str(path))
            self.log.append("remove  %s" % path)
            self.changes[path] = None

    def apply(self):
        if self.dry: return
        staged, originals, created_dirs, applied = {}, {}, [], []
        try:
            # Stage every replacement before changing any destination. Manifest is inserted last.
            for path, text in self.changes.items():
                if path.is_symlink() or path.exists() and not path.is_file():
                    raise ValueError("expected an ordinary file: " + str(path))
                originals[path] = (path.read_bytes(), path.stat().st_mode) if path.exists() else None
                missing = []
                parent = path.parent
                while not parent.exists(): missing.append(parent); parent = parent.parent
                for d in reversed(missing): d.mkdir(); created_dirs.append(d)
                if text is not None:
                    fd, name = tempfile.mkstemp(prefix=".sx-stage-", dir=path.parent)
                    with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(text)
                    staged[path] = Path(name)
            for path, text in self.changes.items():
                if text is None:
                    if path.exists(): path.unlink()
                else:
                    os.replace(staged[path], path)
                    del staged[path]
                    if originals[path]: os.chmod(path, originals[path][1])
                applied.append(path)
        except Exception:
            for path in reversed(applied):
                original = originals[path]
                if original is None:
                    if path.exists(): path.unlink()
                else:
                    fd, name = tempfile.mkstemp(prefix=".sx-rollback-", dir=path.parent)
                    with os.fdopen(fd, "wb") as f: f.write(original[0])
                    os.replace(name, path); os.chmod(path, original[1])
            raise
        finally:
            for stage in staged.values():
                if stage.exists(): stage.unlink()
            for d in reversed(created_dirs):
                try: d.rmdir()
                except OSError: pass

    def block(self, path, text):
        """Insert or replace the marked block in an instruction file. text=None removes it."""
        old = self.read(path)
        rest = BLOCK_RE.sub("\n\n", old).strip()
        if text is None:
            if old == "" or START[:21] not in old:
                return
            new = rest + "\n" if rest else ""
            self.log.append("unblock %s" % path)
        else:
            new = (rest + "\n\n" if rest else "") + START + "\n" + text.strip() + "\n" + END + "\n"
            self.log.append("block   %s" % path)
        if new: self.write(path, new)
        elif path.exists(): self.remove(path)

    def hooks(self, path, tool, uninstall=False):
        old_text = self.read(path) or "{}\n"
        old_data = json.loads(old_text)
        text = old_text
        if tool == "cursor" and not uninstall and "version" not in old_data:
            # Add the required top-level field without rewriting user hook entries.
            start = text.index("{") + 1
            text = text[:start] + '"version":1' + ("," if old_data else "") + text[start:]
        events = {
            "claude": {"UserPromptSubmit": "capture-request", "PreToolUse": "shell-guard", "SubagentStart": "dispatch-guard", "SubagentStop": "return-log", "Stop": "stop-check", "SessionStart": "resume", "PreCompact": "resume"},
            "cursor": {"beforeSubmitPrompt": "capture-request", "subagentStart": "dispatch-guard", "beforeShellExecution": "shell-guard", "subagentStop": "return-log", "stop": "stop-check", "sessionStart": "resume"},
            "codex": {"UserPromptSubmit": "capture-request", "SubagentStart": "dispatch-guard", "PreToolUse": "dispatch-guard,shell-guard", "SubagentStop": "return-log", "Stop": "stop-check", "SessionStart": "resume"},
        }[tool]
        if tool == "claude":
            events["PreToolUse"] = "dispatch-guard,shell-guard"
        state_file = path.parent.parent / ".simpleide" / ("hook-created-" + tool + ".json")
        created = json.loads(state_file.read_text()) if state_file.exists() else []
        if not uninstall:
            created = sorted(set(created) | {e for e in events if event_span(old_text, e) is None})
        prefix = "~/.simpleide/sx.py" if path.parent.parent == Path.home() else ".simpleide/sx.py"
        for event, handlers in events.items():
            text = remove_owned_from_array(text, event, self.hook_entries.get(tool, {}).get(event, []))
            if uninstall:
                continue
            for handler in handlers.split(","):
                cmd = self.command + " hook " + handler + " --host " + tool
                if tool == "cursor":
                    entry = {"command": cmd}
                    if handler == "shell-guard": entry["failClosed"] = True
                else:
                    entry = {"hooks": [{"type": "command", "command": cmd}]}
                    if tool == "claude" and handler == "dispatch-guard" and event == "PreToolUse": entry["matcher"] = "Task|Agent"
                    if tool == "claude" and handler == "shell-guard": entry["matcher"] = "Bash"
                    if tool == "codex" and handler == "shell-guard": entry["matcher"] = "Bash|exec_command"
                    if tool == "codex" and handler == "dispatch-guard" and event == "PreToolUse": entry["matcher"] = "spawn_agent|Task"
                span = event_span(text, event)
                item = json.dumps(entry, separators=(",", ":"))
                if span:
                    _, start, end = span
                    comma = "," if text[start + 1:end].strip() else ""
                    text = text[:end] + comma + item + text[end:]
                else:
                    hooks = re.search(r'"hooks"\s*:\s*\{', text)
                    if hooks:
                        end = matching(text, hooks.end() - 1)
                        comma = "," if text[hooks.end():end].strip() else ""
                        text = text[:end] + comma + json.dumps(event) + ":[" + item + "]" + text[end:]
                    else:
                        # No preexisting hook entries to preserve.
                        data = json.loads(text)
                        data["hooks"] = {event: [entry]}
                        text = json.dumps(data, indent=2) + "\n"
        if uninstall:
            for event in created:
                text = remove_empty_event(text, event)
            self.remove(state_file)
        else:
            self.write(state_file, json.dumps(created) + "\n")
        if text == old_text:
            return
        json.loads(text)  # refuse to write malformed merged configuration
        self.write(path, text)


def plan(target, tools, is_global):
    """Where things go. Returns (skill_dirs, md_agent_dirs{tool:dir}, toml_dir, rule_files, claude_import, mem_dir)."""
    home = Path.home()
    skills, md, toml, rules, claude_import, ag = [], {}, None, [], None, None
    if is_global:
        mem_dir = home / ".simpleide"
        if "claude" in tools:
            skills.append(home / ".claude/skills"); md["claude"] = home / ".claude/agents"
            rules.append(home / ".claude/CLAUDE.md")
        if "cursor" in tools:
            md["cursor"] = home / ".cursor/agents"
        if "codex" in tools:
            toml = home / ".codex/agents"
            rules.append(home / ".codex/AGENTS.md")
        if "antigravity" in tools:
            ag = home / ".gemini/config/agents"; rules.append(home / ".gemini/GEMINI.md")
        if set(tools) & {"cursor", "codex", "antigravity"}:
            skills.append(home / ".agents/skills")
    else:
        mem_dir = target / ".simpleide"
        rules.append(target / "AGENTS.md")
        if "claude" in tools:
            skills.append(target / ".claude/skills"); md["claude"] = target / ".claude/agents"
            claude_import = target / "CLAUDE.md"
        if "cursor" in tools:
            md["cursor"] = target / ".cursor/agents"
        if set(tools) & {"cursor", "codex", "antigravity"}:
            skills.append(target / ".agents/skills")
        if "codex" in tools:
            toml = target / ".codex/agents"
        if "antigravity" in tools:
            ag = target / ".agents/agents"
    return skills, md, toml, rules, claude_import, mem_dir, ag


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", default=".", help="project folder (default: current folder)")
    ap.add_argument("--tools", default="all", help="comma list of %s, or all" % ",".join(TOOLS))
    ap.add_argument("--global", dest="is_global", action="store_true", help="install for every project of this user")
    ap.add_argument("--models", default=str(SRC / "core/models.json"), help="model map to use")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hooks", action="store_true", help="merge simpleIDE hooks into tool configs")
    args = ap.parse_args(argv)

    try:
        return install_plan(args)
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as err:
        print("install: " + str(err), file=sys.stderr)
        return 2


def validate_hooks(path, tool):
    if not path.exists(): return
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        raise ValueError("invalid hooks object: " + str(path))
    if tool == "cursor" and data.get("version", 1) != 1:
        raise ValueError("unsupported Cursor hooks version")
    for event, entries in data.get("hooks", {}).items():
        if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
            raise ValueError("hook events must contain arrays of objects: " + str(path))
        for entry in entries:
            if tool == "cursor":
                if not isinstance(entry.get("command"), str): raise ValueError("hook command must be text")
            elif not isinstance(entry.get("hooks"), list) or any(not isinstance(h,dict) or not isinstance(h.get("command"),str) for h in entry["hooks"]):
                raise ValueError("invalid nested hook commands")


def install_plan(args):
    tools = set(TOOLS if args.tools == "all" else (t.strip() for t in args.tools.split(",") if t.strip()))
    if not tools or tools - set(TOOLS): raise ValueError("select at least one supported tool")
    target = Path(args.target).expanduser().resolve()
    base = Path.home().resolve() if args.is_global else target
    if not base.is_dir():
        if not args.is_global: raise ValueError("target folder does not exist")
        # No mkdir here: dry run and preflight have no destination mutations.
    models = json.loads(Path(args.models).read_text())
    roles = {"planner", "worker", "tester", "reviewer"}
    if not isinstance(models, dict) or not any(k in TOOLS for k in models):
        raise ValueError("model map must be a nonempty host mapping")
    for tool, mapping in models.items():
        if tool.startswith("_"): continue
        if tool not in TOOLS or not isinstance(mapping,dict) or not mapping:
            raise ValueError("invalid/empty model mapping: " + tool)
        if set(mapping) - (roles | {"scout"}): raise ValueError("unknown model role in " + tool)
        if any(not isinstance(v,dict) or not isinstance(v.get("model"),str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}",v["model"]) or ("effort" in v and v["effort"] not in ("low","medium","high","xhigh","max","ultra")) for v in mapping.values()):
            raise ValueError("invalid/empty model role in " + tool)
    # A partial custom map deliberately inherits unspecified roles; persisted map is complete.
    for tool in TOOLS:
        mapping = models.setdefault(tool,{})
        for role in roles: mapping.setdefault(role,{"model":"inherit"})
    agents = load_agents()
    mem_dir = base / ".simpleide"
    manifest_path = mem_dir / "install-manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"version": 1,"hosts": [],"assets": {},"hooks": {},"hook_entries": {}}
    if previous.get("version") != 1 or not isinstance(previous.get("assets"),dict) or not isinstance(previous.get("hosts"),list):
        raise ValueError("unsupported installation manifest")
    if set(previous["hosts"]) - set(TOOLS) or not isinstance(previous.get("hooks",{}),dict) or not isinstance(previous.get("hook_entries",{}),dict):
        raise ValueError("invalid installation manifest hosts/hooks")
    for key, asset in previous["assets"].items():
        if not isinstance(key,str) or Path(key).is_absolute() or ".." in Path(key).parts or not isinstance(asset,dict) or asset.get("kind") not in ("file","block") or not isinstance(asset.get("hash"),str):
            raise ValueError("invalid installation manifest asset")
    known = set(json.loads((SRC / "core/legacy-owned-hashes.json").read_text()))
    existing_hosts = set(previous["hosts"])
    # Conservative legacy discovery requires exact recognized generated bytes.
    if not manifest_path.exists():
        for tool in TOOLS:
            _, md, toml, _, _, _, ag = plan(base, [tool], args.is_global)
            directory = toml if tool == "codex" else ag if tool == "antigravity" else md.get(tool)
            ext = ".toml" if tool == "codex" else ".md"
            worker = directory / ("sx-worker" + ext)
            if worker.is_file() and digest(worker.read_text()) in known:
                existing_hosts.add(tool)
    hosts = existing_hosts - tools if args.uninstall else existing_hosts | tools
    command = sx_command(mem_dir, args.is_global)
    ins = Installer(args.dry_run, command, previous.get("hook_entries"))
    hook_paths = {"claude": ".claude/settings.json", "cursor": ".cursor/hooks.json", "codex": ".codex/hooks.json"}
    for tool in existing_hosts | tools:
        if tool in hook_paths: validate_hooks(base / hook_paths[tool], tool)
    assets = {}

    def owned(path, text, consumers, kind="file"):
        key = str(path.relative_to(base))
        old = previous["assets"].get(key)
        current = path.read_text() if path.exists() else ""
        if kind == "block":
            found = BLOCK_RE.search(current)
            current_part = found.group().strip() if found else ""
            wanted = START + "\n" + text.strip() + "\n" + END
        else:
            current_part, wanted = current, text
        if path.exists() and current_part and current_part != wanted:
            trusted = old and digest(current_part) == old["hash"] or digest(current_part) in known
            if not trusted: raise ValueError("edited/unowned collision preserved: " + str(path))
        assets[key] = {"hash": digest(wanted), "kind": kind, "consumers": sorted(consumers)}
        if kind == "block": ins.block(path,text)
        else: ins.write(path,text)

    # Runtime stays available on last-host uninstall; memory is never an owned asset.
    for name in ("sx.py", "mem.py", "legacy-owned-hashes.json"):
        owned(mem_dir / name, (SRC / "core" / name).read_text(), hosts)
    owned(mem_dir / "models.json",json.dumps(models,indent=2)+"\n",hosts)
    if not args.is_global:
        owned(mem_dir / ".gitignore", "project.db*\nartifacts/\ncontext.json\nworktrees.json*\nhook-created-*.json\n",hosts)
    destinations = {}
    for tool in sorted(hosts):
        skills, md, toml, rules, claude_import, _, ag = plan(base,[tool],args.is_global)
        for directory in skills:
            for skill in ("simpleide", "sx-writeup"):
                for source in (SRC / "skill" / skill).rglob("*"):
                    if not source.is_file(): continue
                    dst = directory / skill / source.relative_to(SRC / "skill" / skill)
                    text = source.read_text().replace("{SX}",command).replace("python3 .simpleide/sx.py",command)
                    destinations.setdefault(dst,[text,set()])[1].add(tool)
        for a in agents:
            if toml:
                dst,text = toml/(a["name"]+".toml"),render_toml(a,models)
                try:
                    import tomllib
                    tomllib.loads(text)
                except ImportError: pass
                destinations.setdefault(dst,[text,set()])[1].add(tool)
            elif a["name"] != "sx-scout" or ag:
                directory = ag or md[tool]
                text = render_md(a,tool,models)
                if not text.startswith("---\n") or "\n---\n" not in text: raise ValueError("invalid generated agent")
                destinations.setdefault(directory/(a["name"]+".md"),[text,set()])[1].add(tool)
        rule = (SRC/"core/rule.md").read_text().replace("python3 {MEM}",command+" mem").replace("{SX}",command)
        for f in rules:
            destinations.setdefault(f,[rule,set(),"block"])[1].add(tool)
        if claude_import:
            existing = claude_import.read_text() if claude_import.exists() else ""
            if "@AGENTS.md" not in BLOCK_RE.sub("",existing):
                destinations.setdefault(claude_import,["@AGENTS.md",set(),"block"])[1].add(tool)
    for dst, entry in destinations.items():
        owned(dst,entry[0],entry[1],entry[2] if len(entry)>2 else "file")
    # Remove only exact formerly owned assets, never their containing directories.
    for key, old in previous["assets"].items():
        if key in assets: continue
        path = base / key
        if not path.exists(): continue
        text = path.read_text()
        part = BLOCK_RE.search(text) if old["kind"] == "block" else None
        current = part.group().strip() if part else text
        if digest(current) != old["hash"]:
            ins.log.append("preserve edited " + str(path)); continue
        if old["kind"] == "block": ins.block(path,None)
        else: ins.remove(path)
    # Bootstrap legacy removals only from exact known agent/skill bytes.
    if args.uninstall and not manifest_path.exists():
        remain_paths = set(destinations)
        skills,md,toml,rules,claude_import,_,ag = plan(base,tools,args.is_global)
        candidates=[]
        for d in skills:
            for name in ("simpleide","sx-writeup"):
                if (d/name).exists(): candidates += list((d/name).rglob("*"))
        for d in [*md.values(), *([toml] if toml else []), *([ag] if ag else [])]:
            candidates += [d/(a["name"]+(".toml" if d==toml else ".md")) for a in agents]
        for path in candidates:
            if path not in remain_paths and path.is_file() and digest(path.read_text()) in known: ins.remove(path)
        for path in rules + ([claude_import] if claude_import else []):
            if path in remain_paths or not path.exists(): continue
            found=BLOCK_RE.search(path.read_text())
            if found and digest(found.group().strip()) in known: ins.block(path,None)
    enabled, signatures = {}, {}
    for tool in existing_hosts | tools:
        if tool not in hook_paths: continue
        path = base / hook_paths[tool]
        old_text = path.read_text() if path.exists() else ""
        was_enabled = previous.get("hooks",{}).get(tool,False) or any(legacy_hook(e) for entries in json.loads(old_text or "{}").get("hooks",{}).values() for e in entries)
        enable = tool in hosts and (args.hooks or was_enabled)
        if enable or tool not in hosts and path.exists(): ins.hooks(path,tool,not enable)
        enabled[tool] = enable
        if enable:
            data=json.loads(ins.read(path))
            # Inspect commands structurally; JSON escapes shell quoting.
            signatures[tool]={event:[e for e in entries if (e.get("command","").startswith(command+" hook ") or any(h.get("command","").startswith(command+" hook ") for h in e.get("hooks",[])))] for event,entries in data.get("hooks",{}).items()}
    manifest={"version":1,"hosts":sorted(hosts),"assets":assets,"hooks":enabled,"hook_entries":signatures}
    ins.write(manifest_path,json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    # Validate every expected path before creating even a staging directory.
    for path in ins.changes:
        if path.is_symlink() or path.exists() and not path.is_file(): raise ValueError("expected ordinary file: " + str(path))
        for parent in path.parents:
            if parent.exists() and not parent.is_dir(): raise ValueError("expected directory: " + str(parent))
    ins.apply()
    print("\n".join(ins.log))
    print(("DRY RUN, nothing written. " if args.dry_run else "") + "Runtime: " + command + " (stats: " + command + " stats). Memory databases retained.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
