import json
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from pathlib import Path

from python.merlin.app import EventStore, make_handler


class MerlinApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = EventStore(Path(cls.temp.name) / "events.sqlite3")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.store))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def post(self, path, payload):
        request = Request(self.base + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_health_and_capabilities(self):
        with urlopen(self.base + "/health", timeout=5) as response:
            self.assertTrue(json.loads(response.read())["ok"])
        with urlopen(self.base + "/api/capabilities", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertIn("engineering.geometry.validate", {row["id"] for row in payload["capabilities"]})

    def test_ideonomy_rank_endpoint(self):
        payload = self.post("/api/ideonomy/rank", {"ideas": [{
            "title": "Mesh reduction", "mechanism": "Collapse degree-two nodes.",
            "assumptions": ["2-manifold"], "constraints": ["fix boundary"],
            "observable": "Euler characteristic", "falsifier": "topology changes",
            "feasibility": 0.9, "testability": 0.9
        }]})
        self.assertEqual(len(payload["accepted"]), 1)

    def test_rsi_fails_closed(self):
        payload = self.post("/api/rsi/qualify", {
            "tests_passed": True, "independent_review": True,
            "held_out_qualification": False, "rollback_ready": True,
            "authority_unchanged": True, "human_approval": False,
            "compute_budget_respected": True
        })
        self.assertEqual(payload["status"], "BLOCKED")

    def test_model_route_fails_closed_until_qualified(self):
        request = Request(self.base + "/api/chat", data=json.dumps({"messages": []}).encode(), headers={"Content-Type": "application/json"})
        try:
            urlopen(request, timeout=5)
        except HTTPError as error:
            self.assertEqual(error.code, 503)
            self.assertEqual(json.loads(error.read())["error"], "model_not_qualified")
        else:
            self.fail("unqualified model route must return 503")

    def test_speech_route_requires_local_sidecar(self):
        import os
        previous = os.environ.get("MERLIN_TTS_URL")
        os.environ["MERLIN_TTS_URL"] = "http://127.0.0.1:1/v1/audio/speech"
        try:
            request = Request(self.base + "/api/speech", data=json.dumps({"input": "test"}).encode(), headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 503)
        finally:
            if previous is None:
                os.environ.pop("MERLIN_TTS_URL", None)
            else:
                os.environ["MERLIN_TTS_URL"] = previous

    def test_events_store_metadata_not_request_text(self):
        self.post("/api/ideonomy/rank", {"ideas": []})
        with urlopen(self.base + "/api/events", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertGreaterEqual(len(payload["events"]), 1)
        self.assertNotIn("Mesh reduction", json.dumps(payload["events"]))


    def test_remote_model_requires_https_and_explicit_host_allowlist(self):
        import os
        from unittest.mock import patch
        from python.merlin.app import _remote_model_endpoint

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            self.assertEqual(_remote_model_endpoint(), (
                "https://api.example.test/v1/chat/completions", "test-secret"
            ))

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "http://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            with self.assertRaises(ValueError):
                _remote_model_endpoint()

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://unapproved.example/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            with self.assertRaises(ValueError):
                _remote_model_endpoint()


    def test_remote_sse_stream_is_forwarded_and_secret_is_not_returned(self):
        import os
        from unittest.mock import patch
        from urllib.request import Request as UpstreamRequest
        import python.merlin.app as merlin_app

        chunks = [
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        captured = {}

        class FakeResponse:
            headers = {"Content-Type": "text/event-stream"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size=-1):
                return chunks.pop(0) if chunks else b""

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.get_header("Authorization")
            captured["url"] = request.full_url
            return FakeResponse()

        payload = {"model": "test-model", "messages": [{"role": "user", "content": "say hello"}], "stream": True}
        request = Request(self.base + "/api/chat", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "private-test-key",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
            "MERLIN_REMOTE_MODEL_QUALIFIED": "1",
        }, clear=False), patch.object(merlin_app, "urlopen", side_effect=fake_urlopen):
            with urlopen(request, timeout=5) as response:
                streamed = response.read()
                self.assertIn("text/event-stream", response.headers.get("Content-Type", ""))

        self.assertIn(b'"hello"', streamed)
        self.assertIn(b'" world"', streamed)
        self.assertIn(b"[DONE]", streamed)
        self.assertEqual(captured["authorization"], "Bearer private-test-key")
        self.assertNotIn(b"private-test-key", streamed)
        self.assertEqual(captured["url"], "https://api.example.test/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
