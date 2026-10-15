"""Review context reduction preserves complete, tested candidate evidence."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from daily_coder.candidate_evidence import review_sources


def fixture(body="a=1\n"):
    sha=hashlib.sha256(body.encode()).hexdigest()
    patch="".join(difflib.unified_diff([],body.splitlines(True),fromfile="/dev/null",tofile="b/new.py"))
    source={"path":"new.py","status":"available","sha256":sha,"content":"excerpt","complete":False}
    row={"path":"new.py","change":"create","before_sha256":None,"after_sha256":sha,"diff":patch,"complete":True}
    return [source],{"files":[row]}


@pytest.mark.parametrize("body",["a=1\n","a=1","a=1\r\nb=2\r\n",'a="x\u2028y"\n'])
def test_complete_addition_supplies_exact_bytes_once(body):
    sources,manifest=fixture(body)
    before=json.dumps([sources,manifest],sort_keys=True)
    assert review_sources(sources,manifest)==[]
    assert json.dumps([sources,manifest],sort_keys=True)==before


@pytest.mark.parametrize("case",["incomplete","modify","prior_hash","missing_prior_hash","bad_hash","stale_source","header","hunk","extra_hunk","removed_line","truncated","count","no_file","unavailable","duplicate","non_string","missing_complete"])
def test_uncertain_evidence_retains_source(case):
    sources,manifest=fixture(); row=manifest["files"][0]
    if case=="incomplete": manifest["incomplete"]=True
    elif case=="modify": row["change"]="modify"
    elif case=="prior_hash": row["before_sha256"]="b"*64
    elif case=="missing_prior_hash": row.pop("before_sha256")
    elif case=="bad_hash": row["after_sha256"]="b"*64
    elif case=="stale_source": sources[0]["sha256"]="b"*64
    elif case=="header": row["diff"]=row["diff"].replace("b/new.py","b/other.py")
    elif case=="hunk": row["diff"]=row["diff"].replace("-0,0","-1,0")
    elif case=="extra_hunk": row["diff"]+="@@ -0,0 +1 @@\n+x\n"
    elif case=="removed_line": row["diff"]=row["diff"].replace("+a=1","-a=1")
    elif case=="truncated": row["diff"]=row["diff"][:-2]
    elif case=="count": row["diff"]=row["diff"].replace("+1 @@","+1,2 @@")
    elif case=="no_file": manifest["files"]=[]
    elif case=="unavailable": sources[0]["status"]="absent"
    elif case=="duplicate": manifest["files"].append(dict(row))
    elif case=="non_string": row["diff"]=None
    elif case=="missing_complete": row.pop("complete")
    assert review_sources(sources,manifest)==sources


def test_default_packet_is_unchanged_and_opt_in_keeps_full_manifest(tmp_path):
    spec=importlib.util.spec_from_file_location("candidate_helpers",Path(__file__).with_name("test_candidate_evidence.py"))
    helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    engine,run,packet,gateway,broker=helpers.reviewed_fixture(tmp_path)
    default=engine._role_extra(run,"code_reviewer",packet,broker)
    assert [row["path"] for row in default["SOURCE_SNAPSHOTS"]]==["clamp.py","new.py"]
    engine.config["coder_v1"]["review_source_projection"]="verified-additions-v1"
    reduced=engine._role_extra(run,"code_reviewer",packet,broker)
    assert [row["path"] for row in reduced["SOURCE_SNAPSHOTS"]]==["clamp.py"]
    assert reduced["CANDIDATE_MANIFEST"]==default["CANDIDATE_MANIFEST"]
    assert "+new_value=3" in reduced["CANDIDATE_MANIFEST"]["files"][1]["diff"]
    assert engine._review_manifest_valid(run)
    (broker.repo/"new.py").write_text("changed\n")
    assert not engine._review_manifest_valid(run)


def test_projection_is_validated_and_bound_to_execution_configuration(tmp_path):
    spec=importlib.util.spec_from_file_location("coder_helpers",Path(__file__).with_name("test_coder_v1.py"))
    helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    before=engine._execution_hash()
    config_path=engine.root/"config/default.json"
    config=json.loads(config_path.read_text()); config["coder_v1_review_source_projection"]="verified-additions-v1"
    config_path.write_text(json.dumps(config))
    configured=helpers.CoderV1(engine.root,engine.state,helpers.MockProvider(),task_contract=engine.task_contract)
    assert configured.config["coder_v1"]["review_source_projection"]=="verified-additions-v1"
    assert configured._execution_hash()!=before
    from agent_core.contracts import ContractDenied
    config["coder_v1_review_source_projection"]="unknown"
    config_path.write_text(json.dumps(config))
    with pytest.raises(ContractDenied,match="unsupported coder-v1 review source projection"):
        helpers.CoderV1(engine.root,engine.state,helpers.MockProvider(),task_contract=engine.task_contract)
    assert engine.state.total_usage(run)["calls"]==0


@pytest.mark.parametrize("manifest",[None,[],{"files":None},{"files":[None]},{"files":["invalid"]}])
def test_malformed_manifest_containers_retain_source(manifest):
    sources,_=fixture()
    assert review_sources(sources,manifest)==sources


def test_malformed_source_or_unencodable_patch_retains_source():
    sources,manifest=fixture()
    assert review_sources([None],manifest)==[None]
    assert review_sources(None,manifest) is None
    row=manifest["files"][0]
    row["diff"]=row["diff"].replace("+1 @@","+1,"+"9"*5000+" @@")
    assert review_sources(sources,manifest)==sources
    sources,manifest=fixture()
    manifest["files"][0]["diff"]=manifest["files"][0]["diff"].replace("a=1",chr(0xd800))
    assert review_sources(sources,manifest)==sources


@pytest.mark.parametrize("path",[[],{},None,1])
def test_invalid_source_path_is_retained(path):
    sources,manifest=fixture()
    sources[0]["path"]=path
    assert review_sources(sources,manifest)==sources
