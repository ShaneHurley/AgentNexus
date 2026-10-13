import hashlib
import pytest
from daily_coder.verification_evidence import execution_evidence
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("coder_v1_test_helpers",Path(__file__).with_name("test_coder_v1.py"))
helpers=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
make,plan=helpers.make,helpers.plan

@pytest.mark.parametrize("argv,stdout,stderr,positive,count",[
    (["python","-m","unittest","discover"],"","Ran 0 tests in 0.000s\n\nOK\n",False,0),
    (["python","-m","unittest","-v"],"","Ran 5 tests in 0.001s\n\nOK\n",True,5),
    (["/usr/bin/python3.12","-m","unittest"],"","Ran 1 test in 0.001s\n\nOK\n",True,1),
    (["python","-m","unittest"],"","Ran 5 tests in 0.001s\n\nOK (skipped=5)\n",False,0),
    (["python","-m","unittest"],"","Ran 5 tests in 0.001s\n\nOK (skipped=2)\n",True,3),
    (["python","-m","unittest"],"success","",False,None),
    (["python","-m","unittest"],"","Ran 5 tests in 0.1s\nFAILED (failures=1)\n",False,None),
    (["pytest","-q"],"5 passed in 0.01s","",True,5),
    (["python","-m","pytest"],"=== 2 passed, 3 skipped in 0.01s ===","",True,2),
    (["pytest"],"5 skipped in 0.01s","",False,0),
    (["pytest"],"no tests ran in 0.01s","",False,0),
    (["pytest"],"no tests collected in 0.01s","",False,0),
    (["pytest"],"success","",False,None),
    (["pytest"],"1 failed, 4 passed in 0.01s","",False,None),
    (["pytest"],"5 passed in 0.01s\n5 passed in 0.01s","",False,None),
    (["python","assertions.py"],"","",True,None),
    (["python","-c","assert 1"],"","",True,None),
])
def test_execution_summary(argv,stdout,stderr,positive,count):
    evidence=execution_evidence(argv,{"stdout":stdout,"stderr":stderr})
    assert evidence["positive"] is positive
    assert evidence["executed_tests"]==count

@pytest.mark.parametrize("stderr,expected",[
    ("Ran 0 tests in 0.001s\n\nOK\n","repair"),
    ("Ran 5 tests in 0.001s\n\nOK\n","ok"),
    ("Ran 5 tests in 0.001s\n\nOK (skipped=5)\n","repair"),
    ("unrecognized success","repair"),
])
def test_runtime_gate_requires_executed_tests_with_matching_source(tmp_path,stderr,expected):
    engine,run,packet,gateway,broker=make(tmp_path)
    packet["plan"]=plan();packet["plan_hash"]="reviewed"
    result={"argv":plan()["verification_commands"][0],"returncode":0,"timeout":False,"cancelled":False,
        "image":"sha256:"+"a"*64,"source_snapshot_sha256":"b"*64,
        "source_hashes":{"clamp.py":hashlib.sha256((broker.repo/"clamp.py").read_bytes()).hexdigest()},
        "stdout":"","stderr":stderr}
    gateway.safe_execute=lambda *args,**kwargs: {"ok":True,"result":result}
    engine._record=lambda run_id,phase,payload,value: payload.update({phase.lower():value}) or "ok"
    outcome=engine._run_phase(run,"TEST_EXECUTE","S",packet,gateway,broker)
    assert (outcome if isinstance(outcome,str) else outcome[0])==expected
    receipt=engine.artifacts.load(run,"test_receipts")
    assert receipt["commands"][0]["test_execution"]["positive"] is (expected=="ok")
    reviewer=engine._role_extra(run,"code_reviewer",packet,broker)["VERIFICATION_EVIDENCE"]
    assert reviewer["commands"][0]["stderr"]==stderr
    assert reviewer["commands"][0]["test_execution"]["positive"] is (expected=="ok")
