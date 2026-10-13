import importlib.util
import shlex
import sys
from pathlib import Path
import pytest

@pytest.fixture
def hook(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[3]
    hooks=root/".codex/hooks"
    monkeypatch.syspath_prepend(str(hooks))
    sys.modules.pop("_ide_pack_policy",None)
    spec=importlib.util.spec_from_file_location("tested_codex_hook",hooks/"deny-mutating-for-readonly.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake=tmp_path/"project"
    executable=fake/".venv/bin/ide-bridge"
    executable.parent.mkdir(parents=True)
    executable.write_text("test bridge identity only")
    monkeypatch.setattr(module,"__file__",str(fake/".codex/hooks/deny-mutating-for-readonly.py"))
    return module,str(executable)

def test_quoted_python_is_data_inside_trusted_bridge(hook):
    module,exe=hook
    source="python -c 'def f() -> int: pass; path.mkdir()'"
    command=shlex.quote(exe)+" daily-coder run --provider command --provider-command "+shlex.quote(source)
    assert module.is_mutating_shell(command) is False

@pytest.mark.parametrize("suffix",["; echo done"," | cat"," && echo done"," > out","\necho done"," $(echo bad)"," `echo bad`"])
def test_bridge_chaining_and_expansion_remain_blocked(hook,suffix):
    module,exe=hook
    assert module.is_mutating_shell(shlex.quote(exe)+" daily-coder run"+suffix) is True

def test_native_and_forged_bridge_remain_blocked(hook):
    module,exe=hook
    assert module.is_mutating_shell("python -c 'path.mkdir()'") is True
    assert module.is_mutating_shell("/tmp/ide-bridge daily-coder run --provider-command 'mkdir bad'") is True
    assert module.is_mutating_shell("git commit -m bad") is True
