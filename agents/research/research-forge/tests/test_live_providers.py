"""Unit and integration tests for Research Forge Live Providers (LiveModel, LiveSearchAdapter, LiveReaderAdapter)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_core.providers.base import Invocation, InvocationResult, Provider, TokenUsage
from agent_core.providers.http import ProviderError
from research_forge.providers.live_model import LiveModel
from research_forge.providers.live_reader import LiveReaderAdapter
from research_forge.providers.live_search import LiveSearchAdapter
from research_forge.wave1.orchestrator import Wave1Orchestrator


class MockTestProvider(Provider):
    """Simple mock Provider for testing LiveModel."""
    name = "mock_test_provider"

    def __init__(self, canned_text: str = '{"status": "ok"}', input_tokens: int = 10, output_tokens: int = 20) -> None:
        self.canned_text = canned_text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.last_invocation: Invocation | None = None

    def invoke(self, request: Invocation) -> InvocationResult:
        self.last_invocation = request
        usage = TokenUsage(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=self.input_tokens + self.output_tokens,
        )
        return InvocationResult(
            raw_text=self.canned_text,
            output={"raw_text": self.canned_text} if not request.output_schema else {"status": "ok"},
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            model=request.model or "test-model",
            usage=usage,
        )


class TestLiveModel(unittest.TestCase):
    def test_complete_with_mocked_provider(self) -> None:
        provider = MockTestProvider(canned_text="Live model response text", input_tokens=12, output_tokens=34)
        model = LiveModel(provider=provider, model="openai/gpt-4o-mini")

        res = model.complete("Analyze multi-agent coordination", task_id="task-001")
        self.assertEqual(res["text"], "Live model response text")
        self.assertEqual(res["usage"]["prompt_tokens"], 12)
        self.assertEqual(res["usage"]["completion_tokens"], 34)
        self.assertEqual(res["model_tier"], "openai/gpt-4o-mini")
        self.assertEqual(model.call_count, 1)
        self.assertIsNotNone(provider.last_invocation)
        self.assertEqual(provider.last_invocation.prompt, "Analyze multi-agent coordination")

    def test_generate_returns_plain_text(self) -> None:
        provider = MockTestProvider(canned_text="Simple text output")
        model = LiveModel(provider=provider)
        output = model.generate("Hello world")
        self.assertEqual(output, "Simple text output")

    def test_generate_structured(self) -> None:
        provider = MockTestProvider(canned_text='{"result": "success", "count": 42}')
        model = LiveModel(provider=provider)
        schema = {"type": "object", "properties": {"result": {"type": "string"}}}
        structured = model.generate_structured("Produce structured data", schema=schema)
        self.assertIsInstance(structured, dict)
        self.assertEqual(structured.get("status"), "ok")

    def test_env_api_key_loading(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-env-key-123"}):
            model = LiveModel()
            self.assertEqual(model.api_key, "test-env-key-123")


class TestLiveSearchAdapter(unittest.TestCase):
    @patch("research_forge.providers.live_search.get_json")
    def test_brave_search_api_mock(self, mock_get_json: MagicMock) -> None:
        mock_get_json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Brave SOTA Multi-Agent Paper",
                        "url": "https://example.com/brave-paper",
                        "description": "Empirical comparison of multi-agent architectures.",
                        "page_age": "2025-02-15",
                    },
                    {
                        "title": "Brave Framework Benchmark",
                        "url": "https://example.com/brave-bench",
                        "description": "Benchmark throughput across agent frameworks.",
                        "page_age": "2025-02-20",
                    },
                ]
            }
        }

        adapter = LiveSearchAdapter(api_key="mock-brave-token", adapter_id="public_search_v1")
        res = adapter.search("multi-agent benchmarks", page_size=2)

        self.assertEqual(res["query"], "multi-agent benchmarks")
        self.assertEqual(res["adapter_id"], "public_search_v1")
        self.assertEqual(len(res["results"]), 2)
        first = res["results"][0]
        self.assertEqual(first["title"], "Brave SOTA Multi-Agent Paper")
        self.assertEqual(first["canonical_title"], "Brave SOTA Multi-Agent Paper")
        self.assertEqual(first["url"], "https://example.com/brave-paper")
        self.assertEqual(first["canonical_url"], "https://example.com/brave-paper")
        self.assertEqual(first["snippet"], "Empirical comparison of multi-agent architectures.")
        self.assertEqual(first["source_type"], "web")
        mock_get_json.assert_called_once()

    def test_search_does_not_invent_results_when_provider_is_missing(self) -> None:
        mock_model = MagicMock(spec=LiveModel)
        mock_model.generate_structured.return_value = {
            "results": [
                {
                    "title": "Synthetic Multi-Agent Framework Study",
                    "url": "https://arxiv.org/abs/2503.11111",
                    "snippet": "Synthetic evaluation demonstrating reliable coordination.",
                    "source_type": "paper",
                }
            ]
        }

        adapter = LiveSearchAdapter(api_key="", model=mock_model)
        res = adapter.search("multi-agent coordination", page_size=1)

        self.assertEqual(res["results"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "unavailable")
        mock_model.generate_structured.assert_not_called()

    def test_search_failure_does_not_invent_results(self) -> None:
        mock_model = MagicMock(spec=LiveModel)
        adapter = LiveSearchAdapter(api_key="brave-token", model=mock_model)
        with patch("research_forge.providers.live_search.get_json", side_effect=ProviderError("offline")):
            res = adapter.search("multi-agent orchestration frameworks 2025", page_size=2)
        self.assertEqual(res["results"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "failed")
        mock_model.generate_structured.assert_not_called()


class TestLiveReaderAdapter(unittest.TestCase):
    @patch("research_forge.providers.live_reader.get_text")
    def test_read_http_success(self, mock_get_text: MagicMock) -> None:
        mock_get_text.return_value = (
            "<html><body><h1>Framework Comparison</h1>"
            "<p>Multi-agent coordination achieved 99.8% verification reliability.</p></body></html>"
        )
        adapter = LiveReaderAdapter(adapter_id="web_reader_v1")
        res = adapter.read("https://standards.org/agents-spec")

        self.assertEqual(res["canonical_url"], "https://standards.org/agents-spec")
        self.assertEqual(res["access_level"], "full")
        self.assertEqual(res["adapter_id"], "web_reader_v1")
        self.assertIn("Framework Comparison", res["content"])
        self.assertIn("99.8%", res["content"])
        self.assertTrue(len(res["chunks"]) >= 1)
        mock_get_text.assert_called_once()

    def test_read_example_url_reports_unavailable_without_fixture(self) -> None:
        adapter = LiveReaderAdapter()
        res = adapter.read("https://example.org/multi-agent-spec")
        self.assertEqual(res["canonical_url"], "https://example.org/multi-agent-spec")
        self.assertEqual(res["content"], "")
        self.assertEqual(res["chunks"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "unavailable")

    def test_explicit_reader_fixture_is_marked_synthetic(self) -> None:
        adapter = LiveReaderAdapter(custom_fixtures={"https://example.org/spec": "fixture text"})
        res = adapter.read("https://example.org/spec")
        self.assertEqual(res["content"], "fixture text")
        self.assertTrue(res["metadata"]["synthetic"])
        self.assertEqual(res["metadata"]["retrieval_status"], "fixture")

    @patch("research_forge.providers.live_reader.get_text")
    def test_read_network_error_returns_no_content(self, mock_get_text: MagicMock) -> None:
        mock_get_text.side_effect = ProviderError("HTTP 500: Internal Server Error")
        adapter = LiveReaderAdapter()
        res = adapter.read("https://unstable-source.com/doc")
        self.assertEqual(res["canonical_url"], "https://unstable-source.com/doc")
        self.assertEqual(res["content"], "")
        self.assertEqual(res["chunks"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "failed")

    def test_read_with_dict_source_ref_and_abstract(self) -> None:
        adapter = LiveReaderAdapter()
        ref = {"url": "https://example.org/abstract-only", "abstract_only": True}
        res = adapter.read(ref)
        self.assertEqual(res["canonical_url"], "https://example.org/abstract-only")
        self.assertEqual(res["access_level"], "abstract")


class TestWave1LiveIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_orchestrator_initializes_live_adapters_when_live_true(self) -> None:
        orch = Wave1Orchestrator(
            self.repo_root,
            live=True,
            model_name="anthropic/claude-3.5-sonnet",
            api_key="test-orch-key",
        )
        self.assertTrue(orch.live)
        self.assertIsInstance(orch.search, LiveSearchAdapter)
        self.assertIsInstance(orch.reader, LiveReaderAdapter)
        self.assertIsInstance(orch.model, LiveModel)
        self.assertEqual(orch.model.model, "anthropic/claude-3.5-sonnet")
        self.assertEqual(orch.model.api_key, "test-orch-key")
        self.assertIs(orch.search._model, orch.model)

    def test_orchestrator_initializes_mock_adapters_when_live_false(self) -> None:
        orch = Wave1Orchestrator(self.repo_root, live=False)
        self.assertFalse(orch.live)
        self.assertEqual(orch.search.adapter_id, "mock_search_v1")
        self.assertEqual(orch.reader.adapter_id, "web_reader_v1")
        self.assertIsNone(orch.model)

    def test_orchestrator_end_to_end_with_live_adapters(self) -> None:
        # Test full sequential pipeline (clarify -> charter -> search -> select -> read -> extract -> verify -> compose -> done)
        # using LiveSearchAdapter and LiveReaderAdapter
        search_adapter = LiveSearchAdapter(
            adapter_id="live_search_v1",
        )
        reader_adapter = LiveReaderAdapter(
            adapter_id="web_reader_v1",
            custom_fixtures={
                "https://example.org/a": (
                    "Alpha Paper body. Alpha claims 42% improvement (n=100). Methods described."
                ),
                "https://example.org/b": (
                    "Beta Paper body. Beta contradicts alpha at 38% in a separate cohort."
                ),
            },
        )
        orch = Wave1Orchestrator(
            self.repo_root,
            live=False,
            search_adapter=search_adapter,
            reader_adapter=reader_adapter,
        )

        request = {
            "topic": "Alpha vs Beta multi-agent performance",
            "objective": "Compare reported improvements across cohorts",
            "intended_decision_or_use": "internal planning",
            "required_output": "brief",
            "desired_depth": "standard",
        }

        res = orch.run(request)
        self.assertTrue(res["ok"])
        self.assertIn("report", res)
        self.assertIn("report_hash", res)
        self.assertIn("packet", res)
        self.assertEqual(res["state"]["phase"], "done")
        self.assertEqual(res["state"]["evidence"], [])


if __name__ == "__main__":
    unittest.main()
