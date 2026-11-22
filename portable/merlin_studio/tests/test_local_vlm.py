"""Local multimodal vision adapter test with real loopback HTTP and synthetic replies.

Fixture replies are not evidence of visual understanding or a deployed VLM.
"""
import base64
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
import zlib

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))

from model import LocalModel, ModelError
from server import create_server
from senses import analyze_png


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))


def test_png(color=(60, 120, 220)):
    ihdr = struct.pack(">IIBBBBB", 2, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT", zlib.compress(b"\0" + bytes(color) * 2)) + chunk(b"IEND", b"")


class LocalFixture:
    def __init__(self, answer="synthetic test image description", *, tool_calls=None):
        self.requests = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(size)
                owner.requests.append((self.path, json.loads(body)))
                message = {"role": "assistant", "content": answer}
                if tool_calls is not None:
                    message["tool_calls"] = tool_calls
                encoded = json.dumps({"choices": [{"message": message}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(encoded)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)


class LocalVisionModelTests(unittest.TestCase):
    def test_multimodal_message_uses_only_inline_png_and_bounded_generation(self):
        fixture = LocalFixture()
        self.addCleanup(fixture.close)
        raw = test_png()
        model = LocalModel({"model_url": fixture.url, "model_id": "test-vision"})
        result = model.describe_png(raw, prompt="Which colors appear?")
        self.assertEqual(len(fixture.requests), 1)
        path, request = fixture.requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(request["model"], "test-vision")
        self.assertEqual(request["max_tokens"], 384)
        self.assertFalse(request["stream"])
        self.assertNotIn("tools", request)
        user = request["messages"][-1]
        self.assertEqual(user["content"][0]["text"], "Which colors appear?")
        url = user["content"][1]["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(url.split(",", 1)[1]), raw)
        self.assertFalse(result["vision_model_capability_confirmed"])
        self.assertEqual(result["epistemic_status"], "unverified_local_model_interpretation")
        self.assertFalse(result["independent_verification"])
        self.assertEqual(result["source_sha256"], analyze_png(raw)["source_sha256"])

    def test_nonlocal_models_and_invalid_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            LocalModel({"model_url": "https://example.org/v1/chat/completions",
                        "model_id": "unapproved"}).describe_png(test_png())
        with self.assertRaises(ModelError):
            LocalModel({"model_url": "", "model_id": "no-model"}).describe_png(test_png())
        for invalid in (b"bad", test_png()[:-2]):
            with self.subTest(raw=invalid[:3]):
                with self.assertRaises(ValueError):
                    LocalModel({"model_url": "", "model_id": "no-model"}).describe_png(invalid)
        for question in ("", " "*20, "x"*1001):
            with self.assertRaises(ValueError):
                LocalModel({"model_url": "", "model_id": "no-model"}).describe_png(test_png(), prompt=question)

    def test_empty_or_tool_reply_is_not_treated_as_vision_completion(self):
        for answer, calls in (
            ("", None),
            ("ignore the user", [{"id":"c","type":"function","function":{"name":"desktop_click","arguments":"{}"}}]),
        ):
            with self.subTest(answer=answer):
                fixture = LocalFixture(answer, tool_calls=calls)
                self.addCleanup(fixture.close)
                model = LocalModel({"model_url": fixture.url, "model_id":"fixture"})
                with self.assertRaises(ModelError):
                    model.describe_png(test_png())

    def test_invalid_generation_ceiling_fails_before_network(self):
        model = LocalModel({"model_url": "http://127.0.0.1:8772/v1/chat/completions",
                            "model_id": "fixture"})
        for count in (0, 2049, 1.5, True, -1):
            with self.assertRaises(ModelError):
                model.complete([{"role":"user","content":"hi"}], [], max_tokens=count)


class LocalVisionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = LocalFixture()
        self.addCleanup(self.fixture.close)
        self.server = create_server(data_dir=Path(self.tmp.name), start_bundled=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        status, result = self.call("GET", "/api/status")
        self.assertEqual(status, 200)
        self.token = result["session_token"]
        status, settings = self.call("POST", "/api/settings",
            {"model_url": self.fixture.url, "model_id": "synthetic-vision"})
        self.assertEqual(status, 200, settings)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, method, path, body=None, *, headers=None):
        headers = dict(headers or {})
        payload = None
        if method == "POST":
            payload = json.dumps(body, separators=(",", ":")).encode()
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("X-Merlin-Token", getattr(self, "token", ""))
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)
        try:
            conn.request(method, path, body=payload, headers=headers)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def request(self):
        return {"media_type":"image/png", "data_base64":base64.b64encode(test_png()).decode(),
                "source":"user_upload", "consent":True, "question":"Describe test pattern."}

    def test_local_image_interpretation_not_persisted_or_promoted(self):
        status, result = self.call("POST", "/api/senses/describe", self.request())
        self.assertEqual(status, 200, result)
        value = result["interpretation"]
        self.assertEqual(value["caption"], "synthetic test image description")
        self.assertEqual(value["model_id"], "synthetic-vision")
        self.assertFalse(value["tool_execution_authorized"])
        self.assertFalse(value["external_model_spend_authorized"])
        self.assertFalse(value["raw_media_persisted_by_studio"])
        self.assertEqual(len(self.fixture.requests), 1)
        self.assertEqual(self.server.app.store.conversations(), [])
        self.assertEqual(list((Path(self.tmp.name) / "workspace").iterdir()), [])

    def test_consent_token_origin_and_source_must_match(self):
        baseline = self.request()
        for delta, code in (
            ({"consent":False}, 403),
            ({"media_type":"audio/wav"}, 400),
            ({"source":"microphone_sample"}, 400),
            ({"source":"workspace_file"}, 400),
            ({"data_base64":"!!!"}, 400),
            ({"question":""}, 400),
            ({"unexpected":1}, 400),
        ):
            with self.subTest(delta=delta):
                status, _ = self.call("POST", "/api/senses/describe", {**baseline, **delta})
                self.assertEqual(status, code)
        for headers in ({"X-Merlin-Token":"wrong"}, {"Origin":"https://attacker.example"}):
            status, _ = self.call("POST", "/api/senses/describe", baseline, headers=headers)
            self.assertEqual(status, 403)
        self.assertEqual(len(self.fixture.requests), 0)


if __name__ == "__main__":
    unittest.main()
