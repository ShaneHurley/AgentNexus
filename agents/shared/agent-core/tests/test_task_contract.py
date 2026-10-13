import hashlib,json
from datetime import datetime,timezone
import pytest
from agent_core.contracts import ContractDenied
from agent_core.task_contract import DEFAULT_LIMITS,validate_contract,validate_plan,validate_call,digest
def contract(root,request="Fix clamp"):
    return {"schema_version":1,"request_sha256":hashlib.sha256(request.encode()).hexdigest(),"workspace":str(root.resolve()),
        "acceptance_criteria":["Clamp lower values correctly"],"allowed_paths":["clamp.py"],"operations":["modify"],
        "verification_commands":[["python","-m","unittest","-v"]],"limits":dict(DEFAULT_LIMITS),
        "authorization_source":"user-task","authorized_at":datetime.now(timezone.utc).isoformat()}
def plan():
    return {"change_units":[{"id":"fix","file":"clamp.py","operation":"modify","summary":"Correct boundary","verification":"unit tests"}],
        "file_allowlist":["clamp.py"],"unresolved_questions":[],"verification_commands":[["python","-m","unittest","-v"]]}
def test_contract_is_bound_to_request_workspace_and_parent(tmp_path):
    value=contract(tmp_path)
    assert validate_contract(value,"Fix clamp",tmp_path)==value
    assert digest(value)==digest(dict(reversed(list(value.items()))))
    with pytest.raises(ContractDenied): validate_contract(value,"Different request",tmp_path)
    with pytest.raises(ContractDenied): validate_contract(value,"Fix clamp",tmp_path/"other")
    with pytest.raises(ContractDenied): validate_contract(value,"Fix clamp",tmp_path,parent_tokens=1)
@pytest.mark.parametrize("path",["../escape","/absolute","*.py","folder/../escape",".git/config","folder//file"])
def test_literal_scope_rejects_escapes(tmp_path,path):
    value=contract(tmp_path);value["allowed_paths"]=[path]
    with pytest.raises(ContractDenied): validate_contract(value,"Fix clamp",tmp_path)
def test_symlink_escape_is_rechecked_at_write(tmp_path):
    value=contract(tmp_path);outside=tmp_path.parent/"outside-code.py";outside.write_text("private")
    (tmp_path/"clamp.py").symlink_to(outside)
    with pytest.raises(ContractDenied): validate_call(value,"filesystem.write",{"path":"clamp.py"},tmp_path)
def test_scope_operation_argv_and_timeout_are_checked(tmp_path):
    value=contract(tmp_path);(tmp_path/"clamp.py").write_text("before")
    validate_call(value,"patch.apply",{"path":"clamp.py"},tmp_path)
    for tool,args in [("filesystem.write",{"path":"other.py"}),("tests.run",{"argv":["python","-c","other"]}),("tests.run",{"argv":value["verification_commands"][0],"timeout":121})]:
        with pytest.raises(ContractDenied): validate_call(value,tool,args,tmp_path)
    (tmp_path/"clamp.py").unlink()
    with pytest.raises(ContractDenied): validate_call(value,"filesystem.write",{"path":"clamp.py"},tmp_path)
def test_plan_dag_is_stable_and_rejects_cycles(tmp_path):
    value=contract(tmp_path);p=plan()
    first=dict(p["change_units"][0],id="first")
    second=dict(first,id="second",depends_on=["first"])
    p["change_units"]=[second,first]
    assert [x["id"] for x in validate_plan(value,p)["change_units"]]==["first","second"]
    first["depends_on"]=["second"]
    with pytest.raises(ContractDenied): validate_plan(value,p)
def test_plan_never_broadens_task_authority(tmp_path):
    value=contract(tmp_path);p=plan();p["file_allowlist"]=["other.py"]
    with pytest.raises(ContractDenied): validate_plan(value,p)
    p=plan();p["verification_commands"]=[["python","-c","other"]]
    with pytest.raises(ContractDenied): validate_plan(value,p)
def test_missing_authority_does_not_become_task_permission(tmp_path):
    with pytest.raises(ContractDenied): validate_contract({},"Fix clamp",tmp_path)
    value=contract(tmp_path);value["authorization_source"]="model"
    with pytest.raises(ContractDenied): validate_contract(value,"Fix clamp",tmp_path)
