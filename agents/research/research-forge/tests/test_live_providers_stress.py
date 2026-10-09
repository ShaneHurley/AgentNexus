"""Empirical stress test suite for Research Forge Live Providers and Wave 1 Orchestrator.

Adversarial testing targeting:
- LiveModel: model tiers, prompt formats, structured schemas, error simulations, malformed data
- LiveSearchAdapter: 3-tier fallback matrix, API failures, malformed JSON, network timeouts
- LiveReaderAdapter: massive docs, malformed HTML, binary contents, network failures, edge URLs
- Wave1Orchestrator: live integration, failure resilience, schema validation under stress
"""

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


class MockStressProvider(Provider):
    """Configurable mock Provider for stress-testing LiveModel."""
    name = "mock_stress_provider"

    def __init__(
        self,
        canned_text: str = '{"status": "ok"}',
        canned_output: Any = None,
        input_tokens: int = 15,
        output_tokens: int = 25,
        fail_with: Exception | None = None,
        token_usage_obj: TokenUsage | None = None,
    ) -> None:
        self.canned_text = canned_text
        self.canned_output = canned_output
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.fail_with = fail_with
        self.token_usage_obj = token_usage_obj
        self.invocations: list[Invocation] = []

    def invoke(self, request: Invocation) -> InvocationResult:
        self.invocations.append(request)
        if self.fail_with:
            raise self.fail_with

        output = self.canned_output
        if output is None:
            if not request.output_schema:
                output = {"raw_text": self.canned_text}
            else:
                output = {"status": "ok"}

        usage = self.token_usage_obj
        if usage is None and (self.input_tokens or self.output_tokens):
            usage = TokenUsage(
                input_tokens=self.input_tokens,
                output_tokens=self.output_tokens,
                total_tokens=self.input_tokens + self.output_tokens,
            )

        return InvocationResult(
            raw_text=self.canned_text,
            output=output,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            model=request.model or "stress-test-model",
            usage=usage,
        )


class TestLiveModelStress(unittest.TestCase):
    """Stress tests for LiveModel."""

    def test_massive_prompt_and_unicode_handling(self) -> None:
        provider = MockStressProvider(canned_text="Processed massive prompt")
        model = LiveModel(provider=provider, model="anthropic/claude-3.5-sonnet")

        # 100k character prompt with multilingual unicode and control characters
        huge_prompt = (
            "Complex test: \u200b\u200c\u200d\U0001F600\U0001F916\n"
            + ("AgentNexus Orchestration Stress Test \u4e2d\u6587 \u0627\u0644\u0639\u0631\u0628\u064a\u0629 " * 2000)
        )
        res = model.complete(huge_prompt, task_id="task-stress-01")
        self.assertEqual(res["text"], "Processed massive prompt")
        self.assertEqual(model.call_count, 1)
        self.assertEqual(len(provider.invocations), 1)
        self.assertEqual(provider.invocations[0].prompt, huge_prompt)
        self.assertEqual(provider.invocations[0].model, "anthropic/claude-3.5-sonnet")

    def test_structured_generation_fenced_markdown_json(self) -> None:
        # Model returns markdown-fenced JSON inside raw_text
        canned_fenced = "```json\n{\n  \"findings\": [\"Alpha\", \"Beta\"],\n  \"confidence\": 0.98\n}\n```"
        provider = MockStressProvider(canned_text=canned_fenced, canned_output={"raw_text": canned_fenced})
        model = LiveModel(provider=provider)

        schema = {
            "type": "object",
            "properties": {
                "findings": {"type": "array"},
                "confidence": {"type": "number"},
            },
            "required": ["findings", "confidence"],
        }
        res = model.generate_structured("Extract findings", schema=schema)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("findings"), ["Alpha", "Beta"])
        self.assertEqual(res.get("confidence"), 0.98)

    def test_structured_generation_malformed_json_raises_provider_error(self) -> None:
        # Model returns invalid non-JSON prose when schema is requested
        canned_bad = "I am sorry, but as an AI I cannot produce valid JSON for this request: {unclosed bracket"
        provider = MockStressProvider(canned_text=canned_bad, canned_output={"raw_text": canned_bad})
        model = LiveModel(provider=provider)

        schema = {"type": "object", "properties": {"status": {"type": "string"}}}
        with self.assertRaises(ProviderError) as ctx:
            model.generate_structured("Request schema", schema=schema)
        self.assertIn("model did not return JSON", str(ctx.exception))

    def test_provider_invocation_failure_propagation(self) -> None:
        # Simulate network error / 500 error raised by underlying provider
        provider = MockStressProvider(fail_with=ProviderError("HTTP 500: Gateway Timeout"))
        model = LiveModel(provider=provider)

        with self.assertRaises(ProviderError) as ctx:
            model.complete("Hello world")
        self.assertIn("HTTP 500", str(ctx.exception))

    def test_usage_calculation_with_none_usage(self) -> None:
        # Provider returns None for usage
        provider = MockStressProvider(input_tokens=0, output_tokens=0, token_usage_obj=None)
        model = LiveModel(provider=provider)
        res = model.complete("No usage test")
        self.assertIn("usage", res)
        self.assertEqual(res["usage"]["prompt_tokens"], 0)
        self.assertEqual(res["usage"]["completion_tokens"], 0)

    def test_idempotency_key_hashing_consistency(self) -> None:
        provider = MockStressProvider()
        model = LiveModel(provider=provider)
        model.complete("Sample prompt", task_id="test-run-1")
        model.complete("Sample prompt", task_id="test-run-1")

        self.assertEqual(len(provider.invocations), 2)
        # Idempotency key must be identical for same task_id and prompt
        self.assertEqual(
            provider.invocations[0].idempotency_key,
            provider.invocations[1].idempotency_key,
        )


class TestLiveSearchAdapterStress(unittest.TestCase):
    """Stress tests ensuring retrieval failures remain explicit and empty."""

    @patch("research_forge.providers.live_search.get_json")
    def test_brave_api_malformed_payload_does_not_trigger_synthetic_fallback(self, mock_get_json: MagicMock) -> None:
        # Brave returns unexpected payload structure (e.g. web is a string instead of dict)
        mock_get_json.return_value = {"web": "malformed_string_payload"}

        mock_model = MagicMock(spec=LiveModel)
        mock_model.generate_structured.return_value = {
            "results": [
                {
                    "title": "LLM Recovered Benchmark",
                    "url": "https://example.org/llm-rec",
                    "snippet": "Successfully recovered via synthetic LLM fallback.",
                    "source_type": "web",
                }
            ]
        }

        adapter = LiveSearchAdapter(api_key="mock-key", model=mock_model)
        res = adapter.search("multi-agent benchmark", page_size=1)

        self.assertEqual(res["results"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "failed")
        mock_model.generate_structured.assert_not_called()

    @patch("research_forge.providers.live_search.get_json")
    def test_brave_api_empty_results_remain_empty(self, mock_get_json: MagicMock) -> None:
        # Brave returns valid JSON but zero results
        mock_get_json.return_value = {"web": {"results": []}}

        mock_model = MagicMock(spec=LiveModel)
        mock_model.generate_structured.return_value = {
            "results": [
                {
                    "title": "LLM Fallback Result",
                    "url": "https://example.org/fallback",
                    "snippet": "Synthetic snippet.",
                    "source_type": "paper",
                }
            ]
        }

        adapter = LiveSearchAdapter(api_key="mock-key", model=mock_model)
        res = adapter.search("empty search query", page_size=1)

        self.assertEqual(res["results"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "empty")
        mock_model.generate_structured.assert_not_called()

    @patch("research_forge.providers.live_search.get_json")
    def test_brave_api_network_timeout_returns_typed_failure(self, mock_get_json: MagicMock) -> None:
        # A provider failure must remain a failure, not be dressed up as results.
        mock_get_json.side_effect = ProviderError("Connection timed out after 10.0s")

        mock_model = MagicMock(spec=LiveModel)
        mock_model.generate_structured.side_effect = ProviderError("HTTP 429: Rate limit exceeded")

        adapter = LiveSearchAdapter(api_key="mock-key", model=mock_model)
        res = adapter.search("agent resilience patterns", page_size=2)

        self.assertEqual(res["results"], [])
        self.assertEqual(res["metadata"]["retrieval_status"], "failed")
        mock_model.generate_structured.assert_not_called()

    def test_deterministic_fallback_with_hostile_queries(self) -> None:
        # Extreme queries: regex chars, punctuation, empty, very long
        adapter = LiveSearchAdapter(api_key="")

        test_queries = [
            "",  # Empty query
            "   ",  # Whitespace only
            "***???+++[[[(((///\\\\)))]]]",  # Punctuation and regex specials
            "A" * 5000,  # Extremely long query
            "Multi-agent \U0001F916 \u4e2d\u6587 \u0627\u0644\u0639\u0631\u0628\u064a\u0629",  # Unicode
        ]

        for q in test_queries:
            res = adapter.search(q, page_size=2)
            self.assertEqual(res["query"], q)
            self.assertIsInstance(res["results"], list)
            self.assertTrue(len(res["results"]) <= 2)
            for item in res["results"]:
                self.assertIn("result_id", item)
                self.assertIn("title", item)
                self.assertIn("url", item)
                self.assertIn("source_type", item)

    def test_unavailable_search_has_no_fabricated_pages(self) -> None:
        adapter = LiveSearchAdapter(api_key="")
        page1 = adapter.search("framework comparison", page_size=1, cursor=0)
        page2 = adapter.search("framework comparison", page_size=1, cursor=1)
        page_empty = adapter.search("framework comparison", page_size=1, cursor=100)
        self.assertEqual(page1["results"], [])
        self.assertEqual(page2["results"], [])
        self.assertEqual(page_empty["results"], [])
        self.assertEqual(page1["metadata"]["retrieval_status"], "unavailable")


class TestLiveReaderAdapterStress(unittest.TestCase):
    """Stress tests for LiveReaderAdapter HTML cleaning, massive documents, and failures."""

    @patch("research_forge.providers.live_reader.get_text")
    def test_massive_document_truncation(self, mock_get_text: MagicMock) -> None:
        # 1MB HTML content with repetitive tags
        large_body = "<p>" + ("Nexus multi-agent verification benchmark analysis. " * 20000) + "</p>"
        mock_get_text.return_value = f"<html><body><h1>Title</h1>{large_body}</body></html>"

        adapter = LiveReaderAdapter()
        res = adapter.read("https://large-doc-site.com/report")

        self.assertEqual(res["canonical_url"], "https://large-doc-site.com/report")
        self.assertLessEqual(len(res["content"]), 32000)
        self.assertIn("Nexus multi-agent verification", res["content"])
        self.assertNotIn("<p>", res["content"])

    @patch("research_forge.providers.live_reader.get_text")
    def test_malformed_html_and_script_tag_sanitization(self, mock_get_text: MagicMock) -> None:
        # Script tags with complex attributes and unclosed tags
        dirty_html = (
            "<html><head>"
            "<script type=\"text/javascript\" async src=\"evil.js\">"
            "alert('malicious code'); window.location = 'http://bad.org';"
            "</script>"
            "<style>body { display: none; }</style>"
            "</head>"
            "<body>"
            "<div>Clean content line 1</div>"
            "<div><<<malformed unclosed tags <p>Clean line 2"
            "<SCRIPT>console.log('case insensitive script');</SCRIPT>"
            "</div></body></html>"
        )
        mock_get_text.return_value = dirty_html

        adapter = LiveReaderAdapter()
        res = adapter.read("https://dirty-site.org/post")

        content = res["content"]
        self.assertNotIn("alert('malicious code')", content)
        self.assertNotIn("display: none", content)
        self.assertNotIn("console.log", content)
        self.assertIn("Clean content line 1", content)
        self.assertIn("Clean line 2", content)

    @patch("research_forge.providers.live_reader.get_text")
    def test_unclosed_script_tag_safety(self, mock_get_text: MagicMock) -> None:
        # Ensure regex does not suffer catastrophic backtracking or crash on unclosed script tags
        unclosed_html = "<script>var x = 1;\n" + ("some text line\n" * 5000)
        mock_get_text.return_value = unclosed_html

        adapter = LiveReaderAdapter()
        res = adapter.read("https://unclosed-script.com/page")
        self.assertIsInstance(res["content"], str)
        self.assertLessEqual(len(res["content"]), 32000)

    @patch("research_forge.providers.live_reader.get_text")
    def test_binary_or_corrupt_content_fallback(self, mock_get_text: MagicMock) -> None:
        # get_text returns decoded replacement chars and null bytes
        mock_get_text.return_value = "\x00\x00\xff\xfe\x01\x02PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        adapter = LiveReaderAdapter()
        res = adapter.read("https://image-binary.com/file.png")
        self.assertIsInstance(res["content"], str)

    def test_mock_and_example_hosts_routing(self) -> None:
        adapter = LiveReaderAdapter()
        mock_urls = [
            "http://example.com/spec",
            "https://example.org/study-1",
            "http://example.net/architecture",
            "http://localhost:8080/data",
            "http://127.0.0.1:3000/api",
        ]
        for url in mock_urls:
            res = adapter.read(url)
            self.assertEqual(res["canonical_url"], url)
            self.assertEqual(res["access_level"], "full")
            self.assertEqual(res["content"], "")
            self.assertEqual(res["metadata"]["retrieval_status"], "unavailable")

    def test_access_levels_abstract_and_snippet(self) -> None:
        adapter = LiveReaderAdapter(
            custom_fixtures={"https://fixture.com/doc": "A" * 2000}
        )
        full_res = adapter.read("https://fixture.com/doc", level="full")
        self.assertEqual(len(full_res["content"]), 2000)

        abs_res = adapter.read("https://fixture.com/doc", level="abstract")
        self.assertEqual(len(abs_res["content"]), 800)

        snip_res = adapter.read("https://fixture.com/doc", level="snippet")
        self.assertEqual(len(snip_res["content"]), 300)

    def test_source_ref_dict_with_abstract_flag_and_locator(self) -> None:
        adapter = LiveReaderAdapter(
            custom_fixtures={"https://fixture.com/paper": "B" * 1500}
        )
        ref = {
            "url": "https://fixture.com/paper",
            "abstract_only": True,
            "locator": "section:abstract",
        }
        res = adapter.read(ref)
        self.assertEqual(res["canonical_url"], "https://fixture.com/paper")
        self.assertEqual(res["access_level"], "abstract")
        self.assertEqual(res["locator"], "section:abstract")
        self.assertEqual(len(res["content"]), 800)
        self.assertEqual(res["chunks"][0]["locator"], "section:abstract")


class TestWave1OrchestratorStress(unittest.TestCase):
    """Stress tests for Wave1Orchestrator live adapter integration and edge cases."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_mock_pipeline_completes_with_fixture_evidence(self) -> None:
        orch = Wave1Orchestrator(self.repo_root, live=False)

        request = {
            "topic": "Adversarial Stress Test on Distributed Multi-Agent Consensus",
            "objective": "Verify consensus resilience under Byzantine node behavior",
            "intended_decision_or_use": "architecture review",
            "required_output": "research_packet",
            "desired_depth": "deep",
        }

        res = orch.run(request)
        self.assertTrue(res["ok"])
        self.assertEqual(res["state"]["phase"], "done")
        self.assertIn("report", res)
        self.assertIn("packet", res)
        self.assertIn("report_hash", res)
        self.assertTrue(res["state"]["evidence"])
        self.assertTrue(all(s["source_authenticity"] == "synthetic_fixture" for s in res["state"]["sources"].values()))
        self.assertTrue(all(s["content_availability"] == "available" for s in res["state"]["sources"].values()))

        # Validate that the produced packet satisfies the schema registry
        orch.registry.validate("research_packet", res["packet"])

    def test_mock_pipeline_selects_its_fixture_sources(self) -> None:
        request = {
            "topic": "Partial Read Resilience",
            "objective": "Assess behavior when remote source documents are inaccessible",
            "intended_decision_or_use": "robustness analysis",
            "required_output": "brief",
            "desired_depth": "standard",
        }

        res = Wave1Orchestrator(self.repo_root, live=False).run(request)
        self.assertTrue(res["ok"])
        self.assertEqual(res["state"]["phase"], "done")
        self.assertTrue(res["state"]["selected_urls"])


if __name__ == "__main__":
    unittest.main()
