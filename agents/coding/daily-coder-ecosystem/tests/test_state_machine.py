import unittest
from daily_coder.models import Phase
from daily_coder.state_machine import allowed_transition
class TestStateMachine(unittest.TestCase):
 def test_linear(self): self.assertTrue(allowed_transition(Phase.NEW,Phase.INTAKE))
 def test_skip_denied(self): self.assertFalse(allowed_transition(Phase.NEW,Phase.IMPLEMENT))
 def test_terminal_denied(self): self.assertFalse(allowed_transition(Phase.COMPLETE,Phase.NEW))
