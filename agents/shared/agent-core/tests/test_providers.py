"""Unit tests for agent_core.providers infrastructure (pure standard library unittest)."""
from __future__ import annotations

import io
import json
import unittest
import urllib.error
import urllib.parse
from unittest.mock import MagicMock, patch

from agent_core.providers.base import (
    Invocation,
    InvocationResult,
    Provider,
    TokenUsage,
    ToolCall,
)
from agent_core.providers.http import (
    ProviderError,
    extract_json,
    get_json,
    get_text,
    json_instruction,
    json_instruction_compact,
    post_json,
    post_stream,
    schema_field_list,
    tool_result_text,
)
from agent_core.providers.mock import MockProvider
from agent_core.providers.openai_compat import OpenAICompatibleProvider
from agent_core.providers.registry import (
    LIVE_PROVIDERS,
    PROVIDERS,
    build_provider,
    is_live,
)


class _MockResponse:
    def __init__(self, data: bytes, status: int = 200) -> None:
        self._fp = io.BytesIO(data)
        self.status = status

    def read(self, *args) -> bytes:
        return self._fp.read(*args)

    def __iter__(self):
        return iter(self._fp)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestAgentCoreProviders(unittest.TestCase):
    def test_token_usage_and_invocation_result(self) -> None:
        usage = TokenUsage.from_counts(prompt_tokens=100, completion_tokens=50, cost_per_1k=0.002)
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
        self.assertEqual(usage.total_tokens, 150)
        self.assertAlmostEqual(usage.cost_usd, 0.0003, places=6)

        res = InvocationResult(output={"key": "val"}, input_tokens=10, output_tokens=5, model="test-model")
        self.assertIsNotNone(res.usage)
        self.assertEqual(res.usage.total_tokens, 15)

        tc = ToolCall(name="calc", arguments={"a": 1}, call_id="c1")
        res_tools = InvocationResult(tool_calls=[tc])
        self.assertEqual(len(res_tools.tool_calls), 1)
        self.assertEqual(res_tools.tool_calls[0].name, "calc")

    def test_http_json_extraction(self) -> None:
        # 1. Plain JSON
        self.assertEqual(extract_json('{"status": "ok"}'), {"status": "ok"})

        # 2. Markdown fence
        fence = "```json\n{\"verdict\": \"pass\"}\n```"
        self.assertEqual(extract_json(fence), {"verdict": "pass"})

        # 3. Leading and trailing prose
        prose = "Here is the result:\n{\"answer\": 42}\nHope this helps!"
        self.assertEqual(extract_json(prose), {"answer": 42})

        # 4. Nested braces
        nested = "Explanation: {\"data\": {\"nested\": true}} end"
        self.assertEqual(extract_json(nested), {"data": {"nested": True}})

        # 5. Non-JSON raises ProviderError
        with self.assertRaises(ProviderError):
            extract_json("not a json object")

    def test_http_instructions_and_tool_results(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }
        instr = json_instruction(schema)
        self.assertIn("Return ONLY a single JSON object", instr)
        self.assertIn("name", instr)

        field_list = schema_field_list(schema)
        self.assertTrue('"required":["name"]' in field_list or '"name"' in field_list)

        compact = json_instruction_compact(schema)
        self.assertIn("Return ONLY a single JSON object", compact)

        # Tool result text truncation
        long_result = {"data": "x" * 20000}
        formatted = tool_result_text(long_result)
        self.assertLessEqual(len(formatted), 12000)

    def test_post_json_retry_and_success(self) -> None:
        calls = []

        def mock_urlopen(req, timeout=None):
            calls.append(req)
            if len(calls) == 1:
                fp = io.BytesIO(b'{"error": "rate limit"}')
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, fp)
            return _MockResponse(json.dumps({"success": True}).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            with patch("time.sleep", return_value=None):
                resp = post_json("https://api.test.com/v1", {"ping": "pong"}, {"Custom": "Header"}, retries=2)
                self.assertEqual(resp, {"success": True})
                self.assertEqual(len(calls), 2)

    def test_post_json_fatal_error(self) -> None:
        def mock_urlopen(req, timeout=None):
            fp = io.BytesIO(b'{"error": "bad request"}')
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, fp)

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            with self.assertRaises(ProviderError) as exc_info:
                post_json("https://api.test.com/v1", {"bad": "data"}, retries=3)
            self.assertIn("HTTP 400", str(exc_info.exception))

    def test_get_json_and_get_text(self) -> None:
        def mock_urlopen_json(req, timeout=None):
            return _MockResponse(b'{"message": "hello"}')

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_json):
            res = get_json("https://api.test.com/data")
            self.assertEqual(res, {"message": "hello"})

        def mock_urlopen_text(req, timeout=None):
            return _MockResponse(b"plain document body")

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_text):
            txt = get_text("https://example.com/doc.txt")
            self.assertEqual(txt, "plain document body")

    def test_post_stream(self) -> None:
        stream_data = (
            b"data: {\"choices\": [{\"delta\": {\"content\": \"Hello \"}}]}\n\n"
            b"data: {\"choices\": [{\"delta\": {\"content\": \"world!\"}}]}\n\n"
            b"data: [DONE]\n\n"
        )

        def mock_urlopen(req, timeout=None):
            return _MockResponse(stream_data)

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            lines = list(post_stream("https://api.test.com/v1/stream", {"model": "test"}))
            self.assertEqual(len(lines), 2)
            self.assertIn("Hello", lines[0])
            self.assertIn("world!", lines[1])

    def test_mock_provider(self) -> None:
        mock = MockProvider()
        req = Invocation(
            run_id="run-1",
            role="planner",
            prompt="Plan the feature",
            input_packet={"task": "Build X"},
            model_tier="mid",
            max_output_tokens=1000,
            idempotency_key="key-1",
        )
        result = mock.invoke(req)
        self.assertEqual(result.model, "mock")
        self.assertIsNotNone(result.output)
        self.assertIn("change_units", result.output)

        custom_mock = MockProvider(canned_responses={"custom_role": {"verdict": "custom_pass"}})
        req_custom = Invocation(
            run_id="run-2",
            role="custom_role",
            prompt="Custom prompt",
            input_packet={},
            model_tier="fast",
            max_output_tokens=500,
            idempotency_key="key-2",
        )
        res_custom = custom_mock.invoke(req_custom)
        self.assertEqual(res_custom.output, {"verdict": "custom_pass"})

    def test_openai_compatible_provider_invocation(self) -> None:
        captured_payload = {}
        captured_headers = {}

        def mock_urlopen(req, timeout=None):
            nonlocal captured_payload, captured_headers
            captured_payload = json.loads(req.data.decode("utf-8"))
            captured_headers = dict(req.headers)
            data = {
                "id": "chatcmpl-123",
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"summary": "Task complete"}',
                        }
                    }
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 15},
            }
            return _MockResponse(json.dumps(data).encode("utf-8"))

        provider = OpenAICompatibleProvider(
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            model_mapping={"fast": "gpt-4o-mini", "strong": "gpt-4o"},
        )

        req = Invocation(
            run_id="r1",
            role="coder",
            prompt="Complete coding task",
            input_packet={"code": "print(1)"},
            model_tier="strong",
            max_output_tokens=2048,
            idempotency_key="idem-123",
            output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
        )

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            res = provider.invoke(req)
            self.assertEqual(res.output, {"summary": "Task complete"})
            self.assertEqual(res.input_tokens, 42)
            self.assertEqual(res.output_tokens, 15)
            self.assertEqual(res.usage.total_tokens, 57)
            self.assertEqual(captured_payload["model"], "gpt-4o")
            self.assertEqual(captured_payload["response_format"], {"type": "json_object"})
            self.assertEqual(captured_headers["Authorization"], "Bearer sk-test-key")
            self.assertEqual(captured_headers["Idempotency-key"], "idem-123")

    def test_openai_compatible_provider_stream_and_complete(self) -> None:
        stream_bytes = (
            b"data: {\"choices\": [{\"delta\": {\"content\": \"chunk1 \"}}]}\n\n"
            b"data: {\"choices\": [{\"delta\": {\"content\": \"chunk2\"}}]}\n\n"
            b"data: [DONE]\n\n"
        )

        def mock_urlopen_stream(req, timeout=None):
            return _MockResponse(stream_bytes)

        provider = OpenAICompatibleProvider(api_key="test-key", base_url="https://api.openai.com/v1")
        req = Invocation("r", "role", "prompt", {}, "mid", 100, "idem")

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_stream):
            tokens = list(provider.stream(req))
            self.assertEqual(tokens, ["chunk1 ", "chunk2"])

        def mock_urlopen_complete(req, timeout=None):
            data = {
                "choices": [{"message": {"content": "direct answer"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
            return _MockResponse(json.dumps(data).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=mock_urlopen_complete):
            ans = provider.complete("What is 2+2?")
            self.assertEqual(ans, "direct answer")

    def test_registry_build_provider(self) -> None:
        mock = build_provider("mock")
        self.assertIsInstance(mock, MockProvider)
        self.assertFalse(is_live("mock"))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-openai"}):
            p_openai = build_provider("openai")
            self.assertIsInstance(p_openai, OpenAICompatibleProvider)
            self.assertEqual(p_openai.api_key, "sk-openai")
            self.assertTrue(is_live("openai"))

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-v1-test"}):
            p_openrouter = build_provider("openrouter")
            self.assertIsInstance(p_openrouter, OpenAICompatibleProvider)
            self.assertEqual(p_openrouter.api_key, "sk-or-v1-test")
            self.assertEqual(p_openrouter.base_url, "https://openrouter.ai/api/v1")
            self.assertTrue(is_live("openrouter"))

        with self.assertRaises(ValueError):
            build_provider("unsupported_provider")


if __name__ == "__main__":
    unittest.main()
