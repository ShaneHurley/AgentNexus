import unittest
from clamp import clamp
class ClampTests(unittest.TestCase):
    def test_below(self): self.assertEqual(clamp(-3,0,10),0)
    def test_lower_boundary(self): self.assertEqual(clamp(0,0,10),0)
    def test_within(self): self.assertEqual(clamp(4,0,10),4)
    def test_above(self): self.assertEqual(clamp(12,0,10),10)
    def test_invalid_bounds(self):
        with self.assertRaises(ValueError): clamp(3,10,0)
if __name__=="__main__": unittest.main()
