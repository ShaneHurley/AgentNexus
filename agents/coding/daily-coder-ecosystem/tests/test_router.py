import unittest
from daily_coder.router import size_request, phases_for, workflow_key
from daily_coder.workflow import workflow_for

class TestRouter(unittest.TestCase):
    def test_small(self):
        self.assertEqual(size_request('Fix typo')['profile'], 'S')

    def test_risk(self):
        self.assertIn(size_request('Breaking database migration')['profile'], {'L', 'XL'})

    def test_small_skips_brainstorm(self):
        self.assertNotIn('BRAINSTORM', phases_for('S'))

    def test_trivial_signal_and_workflow_key(self):
        sized = size_request('Fix typo')
        self.assertTrue(sized['trivial_signal'])
        self.assertEqual(workflow_key(sized['profile'], sized['trivial_signal']), 'S_TRIVIAL')

    def test_nontrivial_s_keeps_full_tail(self):
        sized = size_request('Fix off-by-one in parser')
        self.assertEqual(sized['profile'], 'S')
        self.assertFalse(sized['trivial_signal'])
        self.assertEqual(workflow_key(sized['profile'], sized['trivial_signal']), 'S')
        route = phases_for('S')
        self.assertIn('TEST_AUTHOR', route)
        self.assertIn('DOCUMENT', route)
        self.assertIn('ALIGNMENT', route)

    def test_s_trivial_omits_author_and_docs_keeps_alignment(self):
        route = phases_for('S_TRIVIAL')
        self.assertNotIn('TEST_AUTHOR', route)
        self.assertNotIn('DOCUMENT', route)
        self.assertIn('ALIGNMENT', route)
        self.assertIn('TEST_EXECUTE', route)
        self.assertIn('CODE_REVIEW', route)

    def test_s_unchanged_from_trivial_key(self):
        self.assertIn('TEST_AUTHOR', workflow_for('S'))
        self.assertIn('DOCUMENT', workflow_for('S'))

    def test_expanded_trivial_phrases(self):
        for req in (
            'Fix spelling in README',
            'Apply whitespace formatting only',
            'Bump version in pyproject',
        ):
            sized = size_request(req)
            self.assertEqual(sized['profile'], 'S', msg=req)
            self.assertTrue(sized['trivial_signal'], msg=req)
            self.assertEqual(workflow_key(sized['profile'], sized['trivial_signal']), 'S_TRIVIAL')

    def test_trivial_blocked_by_multi_file_or_risk(self):
        multi = size_request('Fix typo across 2 files')
        self.assertFalse(multi['trivial_signal'])
        risky = size_request('Fix typo in production database migration')
        self.assertFalse(risky['trivial_signal'])
        self.assertNotEqual(risky['profile'], 'S')
