import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
from agent_core.model_commands import register, execute
from agent_core.model_catalog import digest, routing_policy_digest


def catalog():
    return {"schema_version":1,"models":{"reviewed-mock":{"provider":"mock","model":"mock",
        "context_tokens":10000,"output_tokens":2000,"risks":["low"],"privacy":["local"],
        "features":[],"credential_ref":None,"pricing":{"input_per_million":0,"output_per_million":0},"latency_ms":1}}}


def policy():
    return {"schema_version":1,"roles":{"fixture:worker":{"allowed_models":["reviewed-mock"],
        "default":"reviewed-mock","fallback":None,"reviewed_baseline":True,"evaluation_class":"code","qualifications":{}}}}


class ModelCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        config=self.root/"agents/shared/agent-core/config"; config.mkdir(parents=True)
        (config/"catalog.yaml").write_text(yaml.safe_dump(catalog()))
        (config/"agents.yaml").write_text(yaml.safe_dump(policy()))
        self.parser=argparse.ArgumentParser()
        register(self.parser.add_subparsers(dest="command",required=True))

    def call(self,*argv):
        return execute(self.parser.parse_args(argv),self.root)

    def file(self,name,value):
        path=self.root/name; path.write_text(json.dumps(value)); return str(path)

    def test_inspect_explain_are_offline_and_do_not_initialize_state(self):
        import sys
        before=set(sys.modules)
        import builtins
        original_import=builtins.__import__
        def offline_import(name,*args,**kwargs):
            if name.startswith("agent_core.providers") or name in {"supervisor","agent_core.supervisor"}:
                raise AssertionError("offline command loaded execution machinery")
            return original_import(name,*args,**kwargs)
        with patch("builtins.__import__",side_effect=offline_import), patch("socket.socket",side_effect=AssertionError("offline command attempted network")):
            inspected=self.call("models","inspect")
            explained=self.call("models","explain","--role","fixture:worker","--requirements",'{}')
        self.assertEqual(inspected["model_catalog_hash"],digest(catalog()))
        self.assertEqual(explained["selected_alias"],"reviewed-mock")
        self.assertEqual(explained["routing_policy_hash"],routing_policy_digest(policy()))
        self.assertFalse((self.root/".agentnexus").exists())
        self.assertNotIn("agent_core.supervisor",set(sys.modules)-before)
        self.assertNotIn("agent_core.providers.registry",set(sys.modules)-before)

    def test_environment_and_override_cannot_broaden_eligibility(self):
        r=self.call("models","explain","--role","fixture:worker","--requirements",'{"features":["tools"]}',
                    "--environment",'{"available_providers":["mock"],"available_credentials":[]}',"--override","reviewed-mock")
        self.assertIsNone(r["selected_alias"])
        self.assertIn("unsupported_feature:tools",r["excluded"]["reviewed-mock"])
        with self.assertRaises(ValueError):
            self.call("models","explain","--role","fixture:worker","--requirements",'{"features":NaN}')

    def test_publish_diff_never_activate_and_activation_checks_pair_confirmation(self):
        first=self.call("models","publish","--catalog",self.file("first.json",catalog()))
        c=copy.deepcopy(catalog());c["models"]["reviewed-mock"]["context_tokens"]=12000
        second=self.call("models","publish","--catalog",self.file("second.json",c))
        directory=self.root/".agentnexus/models"
        self.assertFalse((directory/"routing-active.json").exists())
        difference=self.call("models","diff",first["catalog_hash"],second["catalog_hash"])
        self.assertIn("reviewed-mock",difference["changed"])
        policy_path=self.file("policy.json",policy())
        args=("models","activate","--catalog-hash",first["catalog_hash"],"--policy",policy_path,"--policy-hash",digest(policy()))
        with self.assertRaises(ValueError):self.call(*args)
        self.assertFalse((directory/"routing-active.json").exists())
        with self.assertRaises(ValueError):self.call(*(args[:-1]+("0"*64,"--confirm")))
        result=self.call(*args,"--confirm")
        self.assertEqual(result["catalog_hash"],first["catalog_hash"])
        self.assertEqual(self.call("models","inspect")["model_catalog_hash"],first["catalog_hash"])
        self.assertEqual(self.call("models","inspect","--catalog-hash",second["catalog_hash"])["catalog_hash"],second["catalog_hash"])
        self.assertEqual(json.loads((directory/"routing-active.json").read_text()),result)

    def test_missing_store_reads_do_not_create_state(self):
        with self.assertRaises(ValueError):self.call("models","diff","a"*64,"b"*64)
        with self.assertRaises(ValueError):self.call("models","inspect","--catalog-hash","a"*64)
        self.assertFalse((self.root/".agentnexus").exists())

    def test_eval_and_usage_are_offline_with_mock_default_and_unknown_cost(self):
        rows=[dict(task_id="task",run_id="run",model=m,success=True,critical_policy_violation=False,
                   input_tokens=10,output_tokens=5,tool_calls=0,repairs=0,escalations=0,latency_ms=1,
                   cost_usd=None) for m in ("candidate","baseline")]
        with patch("socket.socket",side_effect=AssertionError("offline command attempted network")):
            report=self.call("eval","--records",self.file("eval.json",rows),"--role","fixture:worker",
                 "--evaluation-class","code","--candidate","candidate","--baseline","baseline",
                 "--corpus-hash","a"*64,"--catalog-hash",digest(catalog()),"--routing-policy-hash",routing_policy_digest(policy()))
            usage=self.call("usage-report","--records",self.file("usage.json",[{"role":"fixture:worker","input_tokens":10,"cost_usd":None}]))
        self.assertFalse(report["qualified"])
        self.assertIn("mock_evidence",report["exclusion_reasons"])
        self.assertEqual(report["policy_hash"],routing_policy_digest(policy()))
        self.assertIsNone(usage["cost_usd"])
        self.assertEqual(usage["unknown_calls"],1)
        self.assertFalse((self.root/".agentnexus").exists())

    def test_json_records_validation_and_required_evaluation_pins(self):
        for payload in ({"records":[]},[None]):
            with self.assertRaises(ValueError):self.call("usage-report","--records",self.file("bad.json",payload))
        from contextlib import redirect_stderr
        from io import StringIO
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            self.parser.parse_args(["eval","--records","unused.json"])

if __name__=="__main__":unittest.main()
