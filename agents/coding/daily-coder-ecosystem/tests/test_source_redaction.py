"""Source references remain exact; literals and uncertain secrets stay hidden."""
import hashlib
import importlib.util
from pathlib import Path
import pytest
from daily_coder.candidate_evidence import collect_source
from daily_coder.tool_broker import ToolDenied,redact
spec=importlib.util.spec_from_file_location("source_helpers",Path(__file__).with_name("test_coder_v1.py"))
helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)


@pytest.mark.parametrize("body",["token=args[index]\n","token = args[index]\n","password = data.value\n","secret = values[0]\n","name='é'; token=args[index]\r\n",'name="a\u2028b"; token=args[index]\n'])
def test_python_reference_assignments_reconstruct_exactly(tmp_path,body):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_bytes(body.encode())
    result=collect_source(engine.state,gateway,run,"planner","PLAN","clamp.py",run+":reference")
    assert result["content"]==body
    assert result["sha256"]==hashlib.sha256(body.encode()).hexdigest()
    assert redact(body)!=body


@pytest.mark.parametrize("body",["token='private-value'\n","token=args['private-value']\n","# token=private-value\n",'text="token=args[index]"\n',"token=(\n args[index]\n)\n","token=ghp_"+"x"*36+"\n"])
def test_literal_or_ambiguous_source_is_still_redacted(tmp_path,body):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_bytes(body.encode())
    receipt=gateway.execute(run,"planner","PLAN","filesystem.read",{"path":"clamp.py","start":1,"end":80},operation_id=run+":literal")
    assert receipt["redacted"] is True
    assert "private-value" not in receipt["source_text"]
    with pytest.raises(ToolDenied,match="required_source_redacted"):
        collect_source(engine.state,gateway,run,"planner","PLAN","clamp.py",run+":blocked")


def test_non_python_reference_text_keeps_original_credential_filter(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"settings.txt").write_text("token=args[index]\n")
    receipt=broker._t_filesystem_read({"path":"settings.txt","start":1,"end":1})
    assert receipt["redacted"] is True and "args[index]" not in receipt["source_text"]


def test_paged_source_uses_original_offsets_and_does_not_expose_other_lines(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    body="token=args[index]\npassword='private-value'\n"
    (broker.repo/"clamp.py").write_text(body)
    first=broker._t_filesystem_read({"path":"clamp.py","start":1,"end":1})
    second=broker._t_filesystem_read({"path":"clamp.py","start":2,"end":2})
    assert first["source_text"]=="token=args[index]\n" and first["redacted"] is False
    assert "password" not in first["source_text"]
    assert second["redacted"] is True and "private-value" not in second["source_text"]


@pytest.mark.parametrize("path",["clamp.py","settings.txt"])
def test_secret_assignment_crossing_page_boundary_stays_hidden(tmp_path,path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/path).write_text("token=\n 'private-value'\n")
    for line in (1,2):
        receipt=broker._t_filesystem_read({"path":path,"start":line,"end":line})
        assert receipt["redacted"] is True
        assert "private-value" not in receipt["source_text"]


def test_exemption_ceiling_is_conservative(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_text("token=args[index]\n"*513)
    first=broker._t_filesystem_read({"path":"clamp.py","start":1,"end":1})
    last=broker._t_filesystem_read({"path":"clamp.py","start":513,"end":513})
    assert first["redacted"] is False
    assert last["redacted"] is True
