import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from daily_coder.models import Invocation
from daily_coder.providers.anthropic import AnthropicProvider
from daily_coder.providers.gemini import GeminiProvider
from daily_coder.providers.openai_compat import OpenAICompatibleProvider


class _FakeHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, fmt, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        self.__class__.requests.append((self.path, body, dict(self.headers)))
        if self.path.endswith("/chat/completions"):
            payload = {"model": body["model"], "choices": [{"message": {"content": '{"verdict":"pass"}'}}],
                       "usage": {"prompt_tokens": 11, "completion_tokens": 3}}
        elif self.path.endswith("/messages"):
            payload = {"model": body["model"], "content": [{"type": "text", "text": '{"verdict":"pass"}'}],
                       "usage": {"input_tokens": 12, "output_tokens": 4}}
        else:
            payload = {"candidates": [{"content": {"parts": [{"text": '{"verdict":"pass"}'}]}}],
                       "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 5}}
        data = json.dumps(payload).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


class TestProviderContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def request(self, model="test-model"):
        return Invocation("run", "reviewer", "Return JSON", {"x": 1}, "mid", 123, "idem",
                          model=model, output_schema={"type": "object"})

    def test_openai_compatible_contract(self):
        provider = OpenAICompatibleProvider("key", self.base + "/v1")
        result = provider.invoke(self.request())
        self.assertEqual(result.output, {"verdict": "pass"})
        self.assertEqual((result.input_tokens, result.output_tokens), (11, 3))
        _, body, _ = _FakeHandler.requests[-1]
        self.assertEqual(body["max_tokens"], 123)

    def test_anthropic_contract(self):
        provider = AnthropicProvider("key", self.base + "/v1")
        result = provider.invoke(self.request())
        self.assertEqual(result.output, {"verdict": "pass"})
        self.assertEqual((result.input_tokens, result.output_tokens), (12, 4))

    def test_gemini_contract(self):
        provider = GeminiProvider("key", self.base + "/v1beta")
        result = provider.invoke(self.request())
        self.assertEqual(result.output, {"verdict": "pass"})
        self.assertEqual((result.input_tokens, result.output_tokens), (13, 5))


if __name__ == "__main__":
    unittest.main()
