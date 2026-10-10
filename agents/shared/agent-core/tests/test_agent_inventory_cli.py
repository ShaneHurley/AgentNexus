import json
from agent_core import nexus_cli
from agent_core.agent_inventory import build_inventory


def test_public_audit_never_creates_execution_state(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("audit constructed the execution supervisor")
    monkeypatch.setattr(nexus_cli, "Supervisor", forbidden)
    code=nexus_cli.main(["--repository", str(tmp_path), "--state-dir", str(tmp_path/"state"), "agents", "audit", "--check"])
    report=json.loads(capsys.readouterr().out)
    assert code==3 and report["findings"]
    assert not (tmp_path/"state").exists()


def test_oversized_prompt_is_reported_without_truncation(tmp_path):
    folder=tmp_path/"agents/ide/canonical"
    folder.mkdir(parents=True)
    (folder.parent/"MANIFEST.yml").write_text("agents:\n- name: researcher\n  user_invocable: true\n")
    (folder/"researcher.md").write_text("---\nname: researcher\nuser_invocable: true\ncontract_version: '1.0'\n---\n# Prompt\n")
    path=tmp_path/"agents/ide/canonical/researcher.md"
    original=path.read_text()
    path.write_text(original+"x"*40000)
    report=build_inventory(tmp_path)
    assert any(row["code"]=="oversized-prompt" and row["path"]=="agents/ide/canonical/researcher.md" for row in report["findings"])
    assert path.read_text()==original+"x"*40000

def test_runtime_compiler_does_not_read_escaped_prompt(tmp_path, monkeypatch):
    root=tmp_path/"repo"
    source=__import__("pathlib").Path(__file__).resolve().parents[4]
    files=["agents/coding/daily-coder-ecosystem/config/tools.json", "agents/coding/daily-coder-ecosystem/agents/researcher/agent.json"]
    for relative in files:
        path=root/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes((source/relative).read_bytes())
    registry=root/"agents/shared/agent-core/registry.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text("roles: []")
    target=tmp_path/"outside.md"
    target.write_text("outside synthetic content")
    prompt=root/"agents/coding/daily-coder-ecosystem/agents/researcher/prompt.md"
    prompt.symlink_to(target)
    path_type=type(target)
    original=path_type.read_bytes
    reads=[]
    def monitored(path):
        if path.resolve()==target:reads.append(path)
        return original(path)
    monkeypatch.setattr(path_type,"read_bytes",monitored)
    report=build_inventory(root)
    assert reads==[]
    assert any(f["code"] in {"runtime-contract-unavailable","escaped-path"} for f in report["findings"])
