import argparse
import builtins
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from agent_core.efficiency_commands import register, execute
from agent_core.contracts import ContractDenied, LAYERS

REPOSITORY=Path(__file__).resolve().parents[4]


class EfficiencyCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name).resolve()
        self.parser=argparse.ArgumentParser()
        register(self.parser.add_subparsers(dest="command",required=True))

    def file(self,name,data):
        path=self.workspace/name
        path.write_text(json.dumps(data));return str(path)

    def grant(self,role="researcher",deny=None):
        entry={"tools":["filesystem.read","filesystem.write"],"workspace_roots":[str(self.workspace)],"write_roots":[str(self.workspace)]}
        layers={name:dict(entry) for name in LAYERS}
        if deny: layers[deny]={**entry,"tools":[]}
        return self.file("grant.json",{"role":"dc:"+role,"layers":layers})

    def access(self,role="researcher",deny=None):
        return ["--namespace","dc","--role",role,"--workspace",str(self.workspace),"--grant-file",self.grant(role,deny)]

    def call(self,*argv):
        return execute(self.parser.parse_args(argv),REPOSITORY)

    def test_outline_uses_actual_registry_and_never_executes_source(self):
        source=self.workspace/"code.py"
        source.write_text("raise RuntimeError('must never execute')\ndef answer(a: int): return a + 1\n")
        original=builtins.__import__
        def guard(name,*args,**kwargs):
            if name.startswith("agent_core.providers") or name in {"supervisor","agent_core.supervisor"}:
                raise AssertionError("offline tools loaded execution machinery")
            return original(name,*args,**kwargs)
        with patch("builtins.__import__",side_effect=guard),patch("socket.socket",side_effect=AssertionError("offline tool network")):
            result=self.call("tools","outline","--path",str(source),*self.access())
        self.assertEqual(result["symbols"][0]["name"],"answer")
        self.assertFalse((self.workspace/".agentnexus").exists())

    def test_outline_denies_missing_layer_unknown_role_escape_and_symlink(self):
        source=self.workspace/"code.py";source.write_text("pass")
        with self.assertRaises(ContractDenied):self.call("tools","outline","--path",str(source),*self.access(deny="approval"))
        with self.assertRaises(ContractDenied):self.call("tools","outline","--path",str(source),*self.access(role="invented"))
        with tempfile.TemporaryDirectory() as outside:
            external=Path(outside)/"code.py"; external.write_text("pass")
            with self.assertRaises(ContractDenied):self.call("tools","outline","--path",str(external),*self.access())
            link=self.workspace/"link.py";link.symlink_to(external)
            with self.assertRaises(ContractDenied):self.call("tools","outline","--path",str(link),*self.access())
        access=self.access(); payload=json.loads(Path(access[-1]).read_text());payload["layers"].pop("approval")
        Path(access[-1]).write_text(json.dumps(payload))
        with self.assertRaises(ContractDenied):self.call("tools","outline","--path",str(source),*access)

    def test_supplied_role_contract_cannot_manufacture_write_authority(self):
        result=self.file("result.json",{"stdout":"hello"})
        destination=self.workspace/"artifacts"
        access=self.access(role="researcher")
        with self.assertRaises(ContractDenied):self.call("tools","reduce","--input",result,"--artifact-dir",str(destination),*access)
        self.assertFalse(destination.exists())
        payload=json.loads(Path(access[-1]).read_text());payload["contract"]={"active":True,"write_authority":"gateway"}
        Path(access[-1]).write_text(json.dumps(payload))
        with self.assertRaises((ContractDenied,ValueError)):self.call("tools","reduce","--input",result,"--artifact-dir",str(destination),*access)

    def test_reduce_requires_approval_write_scope_and_keeps_original(self):
        result=self.file("result.json",{"stdout":"x"*20000,"returncode":2,"api_key":"fixture"})
        directory=self.workspace/"artifacts"
        with self.assertRaises(ContractDenied):self.call("tools","reduce","--input",result,"--artifact-dir",str(directory),*self.access(role="implementer",deny="approval"))
        self.assertFalse(directory.exists())
        reduced=self.call("tools","reduce","--input",result,"--artifact-dir",str(directory),"--max-chars","100",*self.access(role="implementer"))
        self.assertEqual(reduced["returncode"],2);self.assertTrue(reduced["truncated"])
        original=json.loads((directory/(reduced["artifact_id"]+".json")).read_text())
        self.assertEqual(original["api_key"],"[REDACTED]")
        self.assertEqual(len(original["stdout"]),20000)
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(ContractDenied):self.call("tools","reduce","--input",result,"--artifact-dir",outside,*self.access(role="implementer"))

    def test_context_and_extract_are_pure_bounded_local_transforms(self):
        protected={key:key for key in ("intent","constraints","permissions","approval_hash","plan_hash","budget","pending_calls")}
        source=self.file("context.json",{"protected":protected,"evidence":[{"id":"large","text":"x"*20000}]})
        before=set(self.workspace.iterdir())
        packed=self.call("tools","context-pack","--input",source,"--evidence-tokens","10")
        self.assertEqual(packed["protected"],protected);self.assertEqual(packed["expansion_refs"],["large"])
        self.assertEqual(before,set(self.workspace.iterdir()))
        with self.assertRaises(ValueError):self.call("tools","context-pack","--input",source,"--evidence-tokens","4001")
        html=self.workspace/"source.html";html.write_text("<script>danger()</script><table><tr><td>Only if X</td><td>5</td></tr></table>")
        provenance=self.file("provenance.json",{"id":"source1","retrieval_status":"retrieved"})
        before=set(self.workspace.iterdir())
        extracted=self.call("tools","extract","--html",str(html),"--provenance",provenance)
        self.assertIn("Only if X",extracted["text"]);self.assertNotIn("danger()",extracted["text"])
        self.assertEqual(extracted["verification_state"],"unverified")
        self.assertEqual(before,set(self.workspace.iterdir()))

if __name__=="__main__":unittest.main()
