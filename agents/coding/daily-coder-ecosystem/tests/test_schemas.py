import unittest
from pathlib import Path
from daily_coder.schemas import SchemaRegistry,SchemaError
class TestSchema(unittest.TestCase):
 def test_missing_required(self):
  r=SchemaRegistry(Path(__file__).parents[1]/'schemas')
  with self.assertRaises(SchemaError): r.validate('sizing',{'profile':'S'})
