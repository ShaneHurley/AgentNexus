import tempfile, unittest
from daily_coder.state_store import StateStore
class TestStore(unittest.TestCase):
 def test_idempotent_transition(self):
  with tempfile.TemporaryDirectory() as d:
   s=StateStore(d+'/s.db'); s.create('r','q','.', 'c','create'); self.assertTrue(s.transition('r','INTAKE',{},'k')); self.assertFalse(s.transition('r','INTAKE',{},'k'))
