import unittest
from pathlib import Path
from daily_coder.validation import validate_tree
class TestTree(unittest.TestCase):
 def test_complete(self): self.assertEqual(validate_tree(Path(__file__).parents[1]),[])
