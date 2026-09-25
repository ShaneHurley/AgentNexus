import tempfile, unittest
from daily_coder.tool_broker import ToolBroker,ToolDenied
class TestPermissions(unittest.TestCase):
 def cfg(self): return {"role_allowlists":{"researcher":["filesystem.read"],"implementer":["shell.write"]},"disabled_until_adapter_configured":[]}
 def pol(self): return {"path_policy":{"deny":[".git/**","**/.env"],"write_requires_plan_allowlist":True}}
 def test_role_denial(self):
  with tempfile.TemporaryDirectory() as d:
   b=ToolBroker(d,self.cfg(),self.pol())
   with self.assertRaises(ToolDenied): b.authorize('researcher','shell.write')
 def test_escape_denial(self):
  with tempfile.TemporaryDirectory() as d:
   b=ToolBroker(d,self.cfg(),self.pol())
   with self.assertRaises(ToolDenied): b.safe_path('../x')
 def test_allowlist_write(self):
  with tempfile.TemporaryDirectory() as d:
   b=ToolBroker(d,self.cfg(),self.pol())
   with self.assertRaises(ToolDenied): b.safe_path('src/a.py',True,['tests/**'])
