"""Receipt authority regressions with real SQLite and source files."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'agents/shared/agent-core'),str(ROOT/'agents/coding/daily-coder-ecosystem')]
from daily_coder.state_store import StateStore
from daily_coder.coder_v1 import CoderV1
from agent_core.task_contract import digest
from agent_core.lifecycle import ReconciliationRequired

class DurableWritesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve(); self.state=StateStore(self.root/'state.sqlite')
        self.state.create('r','request',str(self.root),'cfg','create')
        self.contract={'allowed_paths':['a.py']}
        self.engine=SimpleNamespace(state=self.state,task_contract=self.contract)
        self.broker=SimpleNamespace(safe_path=lambda p,*a:(self.root/p).resolve())
        self.n=0; self.approve('p')
    def approve(self,plan,actor=None):
        self.state.prepare_plan_approval('r',plan)
        self.state.decide_approval('r','plan',plan,'approved',actor or 'task-contract:'+digest(self.contract))
    def write(self,body='hello',plan='p',state='completed',role='implementer'):
        self.n+=1; op='op'+str(self.n)
        args={'path':'a.py','content':body}; sha=hashlib.sha256(body.encode()).hexdigest()
        self.state.begin_tool_operation(op,'r',role,'IMPLEMENT','filesystem.write',args,plan,str(self.root/'a.py'),sha)
        if state!='pending': self.state.finish_tool_operation(op,{'path':'a.py','sha256':sha},state)
        (self.root/'a.py').write_text(body)
        self.state.record_tool_call('r',role,'IMPLEMENT','filesystem.write',args,'allow')
        return op
    def paths(self):
        return CoderV1._accepted_write_paths(self.engine,'r',self.broker,['a.py'])
    def corrupt(self,op,**values):
        with self.state._connect() as c:
            for key,value in values.items(): c.execute('UPDATE tool_operations SET '+key+'=? WHERE operation_id=?',(value,op))
    def test_display_boundary_never_drives_acceptance(self):
        overhead=len(json.dumps({'path':'a.py','content':''},sort_keys=True))
        for size in (3999,4000,4001,9000):
            with self.subTest(size=size):
                self.write('x'*(size-overhead))
                display=self.state.tool_calls('r')[0]['arguments']
                self.assertEqual(len(display),min(size,4000))
                if size in (4001,9000):
                    with self.assertRaises(ValueError): json.loads(display)
                self.assertEqual(self.paths(),['a.py'])
    def test_latest_hash_and_prior_approved_attempt_survive(self):
        self.write('one'); self.approve('new'); self.write('two',plan='new')
        self.assertEqual(self.paths(),['a.py']); self.assertEqual(len(self.state.write_operations('r')),2)
    def test_display_row_limit_cannot_hide_write(self):
        self.write()
        for i in range(1001): self.state.record_tool_call('r','planner','PLAN','filesystem.read',{},'allow')
        self.assertEqual(self.paths(),['a.py'])
    def test_denied_receipt_not_counted(self):
        self.write(state='denied'); self.assertEqual(self.paths(),[])
    def test_pending_blocks(self):
        self.write(state='pending')
        with self.assertRaises(ReconciliationRequired): self.paths()
    def test_other_run_excluded(self):
        self.write(); self.assertEqual(self.state.write_operations('other'),[])
    def test_unapproved_or_wrong_contract(self):
        for plan in ('missing','foreign'):
            with self.subTest(plan=plan):
                if plan=='foreign': self.approve(plan,'task-contract:other')
                op=self.write(plan=plan)
                with self.assertRaises(ReconciliationRequired): self.paths()
                with self.state._connect() as c: c.execute('DELETE FROM tool_operations WHERE operation_id=?',(op,))
                self.state.set_status('r','ACTIVE')
    def test_malformed_and_inconsistent_receipts(self):
        cases=[{'arguments':'{'},{'result':'[]'},{'result':'{}'},
               {'result':json.dumps({'path':'other.py','sha256':'a'*64})},
               {'path':str(self.root/'elsewhere')},{'expected_output_hash':'bad'},
               {'arguments':json.dumps({'path':'other.py'})}, {'role':'planner'},{'state':'unknown'}]
        for change in cases:
            with self.subTest(change=change):
                op=self.write(); self.corrupt(op,**change)
                with self.assertRaises(ReconciliationRequired): self.paths()
                with self.state._connect() as c: c.execute('DELETE FROM tool_operations WHERE operation_id=?',(op,))
                self.state.set_status('r','ACTIVE')
    def test_stale_or_missing_final_source(self):
        self.write(); (self.root/'a.py').write_text('changed')
        with self.assertRaises(ReconciliationRequired): self.paths()
        (self.root/'a.py').unlink()
        with self.assertRaises(ReconciliationRequired): self.paths()

if __name__=='__main__': unittest.main()
