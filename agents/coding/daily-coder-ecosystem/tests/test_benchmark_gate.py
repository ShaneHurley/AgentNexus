import unittest
from daily_coder.benchmark import baseline_gate_failures, exit_code_for_gate

class TestBenchmarkGate(unittest.TestCase):
    def test_passes_clean_summary(self):
        result={
            "summary":{"verified_routes":4,"successful":4},
            "comparison":{"median_tokens":{"percent":5.0}},
        }
        self.assertEqual(baseline_gate_failures(result), [])

    def test_fails_success_regression(self):
        result={
            "summary":{"verified_routes":4,"successful":4},
            "comparison":{"success_regression":True},
        }
        self.assertTrue(baseline_gate_failures(result))
        self.assertEqual(exit_code_for_gate(result), 1)

    def test_fails_token_regression_over_threshold(self):
        result={
            "summary":{"verified_routes":4,"successful":4},
            "comparison":{"p90_tokens":{"percent":10.01}},
        }
        failures=baseline_gate_failures(result)
        self.assertEqual(len(failures), 1)
        self.assertIn("p90_tokens", failures[0])
