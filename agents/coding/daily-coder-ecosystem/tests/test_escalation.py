import unittest
from daily_coder.escalation import authorize_frontier
class TestEscalation(unittest.TestCase):
 def test_requires_lower_tier(self): self.assertFalse(authorize_frontier("unresolved_architecture_choice",0,0)[0])
 def test_routine_denied(self): self.assertFalse(authorize_frontier("formatting",2,0)[0])
 def test_qualified(self): self.assertTrue(authorize_frontier("contradictory_verified_evidence",1,0)[0])
