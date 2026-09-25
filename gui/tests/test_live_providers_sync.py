"""Guard against drift between dashboard adapter and daily-coder registry."""
from __future__ import annotations

import unittest

from agent_dashboard.adapters.daily_coder import LIVE_PROVIDERS as DASHBOARD_LIVE_PROVIDERS
from daily_coder.providers.registry import LIVE_PROVIDERS as REGISTRY_LIVE_PROVIDERS


class LiveProvidersSyncTests(unittest.TestCase):
    def test_live_providers_match_registry(self):
        self.assertEqual(DASHBOARD_LIVE_PROVIDERS, REGISTRY_LIVE_PROVIDERS)


if __name__ == "__main__":
    unittest.main()
