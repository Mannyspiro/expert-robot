"""Focused integration tests: no GPU, model weights or third-party imports."""
from __future__ import annotations

import importlib.util
import http.client
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bridge = load("airllm_sidecar", ROOT / "portable/merlin_studio/airllm_sidecar.py")
companion = load("openbot_companion", ROOT / "scripts/merlin/run_openbot_companion.py")
verifier = load("upstream_verifier", ROOT / "scripts/merlin/verify_third_party_sources.py")


class TokenIds(list):
    @property
    def shape(self):
        return (1, len(self))

    def to(self, device):
        return self


class FakeTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        return "|".join(message["content"] for message in messages)

    def __call__(self, *args, **kwargs):
        return {"input_ids": TokenIds([10, 20])}

    def decode(self, output, **kwargs):
        return "reply" if output == [30, 40] else "bad slice"


class FakeModel:
    device = "cpu"
    tokenizer = FakeTokenizer()

    def generate(self, input_ids, **kwargs):
        if kwargs["max_new_tokens"] <= 0:
            raise ValueError("bad budget")
        return type("Generated", (), {"sequences": [[10, 20, 30, 40]]})()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "config.json").write_text("{}")
        self.backend = bridge.AirLLMBackend(self.root, loader=lambda _: FakeModel())

    def test_mock_generation_excludes_input_tokens(self):
        messages, count = bridge.prepare_request({"messages": [{"role": "user", "content": "Hi"}]})
        self.assertEqual(count, 128)
        self.assertEqual(self.backend.generate(messages, count), "reply")

    def test_remote_model_paths_and_unsupported_inputs_rejected(self):
        with self.assertRaises(FileNotFoundError):
            bridge.AirLLMBackend("Qwen/Qwen3-32B", loader=lambda _: FakeModel())
        bad = [
            {"messages": []},
            {"messages": [{"role": "system", "content": [{"type": "image_url"}]}]},
            {"messages": [{"role": "user", "content": "test"}], "stream": True},
            {"messages": [{"role": "user", "content": "test"}], "max_tokens": 999999},
            {"messages": [{"role": "user", "content": "test"}], "max_tokens": True},
            {"messages": [{"role": "user", "content": "test"}], "response_format": {"type": "json_schema"}},
            {"messages": [{"role": "user", "content": "test"}], "model": "bad-model"},
            {"messages": [{"role": "user", "content": "x" * (bridge.MAX_PROMPT_CHARS + 1)}]},
        ]
        for item in bad:
            with self.subTest(item=item.get("model", str(item.keys()))), self.assertRaises(bridge.BridgeError):
                bridge.prepare_request(item)

    def test_native_tool_calls_never_synthesized(self):
        messages, _ = bridge.prepare_request({"messages": [{"role": "user", "content": "read a.txt"}],
            "tools": [{"type": "function", "function": {"name": "read_file"}}]})
        self.assertIn("host enforces", messages[0]["content"])
        self.assertEqual(self.backend.generate(messages, 30), "reply")

    def test_http_local_only_bad_request_and_busy(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.make_handler(self.backend))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def request(method, path, payload=None, host="127.0.0.1"):
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            body = None if payload is None else json.dumps(payload)
            conn.request(method, path, body, {"Host": host + ":" + str(server.server_port),
                                               "Content-Type": "application/json"})
            response = conn.getresponse()
            data = response.status, json.loads(response.read())
            conn.close()
            return data

        self.assertEqual(request("GET", "/v1/models")[1]["data"][0]["id"], bridge.MODEL_ID)
        status, result = request("POST", "/v1/chat/completions", {"messages": [{"role":"user","content":"hello"}]})
        self.assertEqual((status, result["choices"][0]["message"]["content"]), (200, "reply"))
        self.assertEqual(request("GET", "/v1/models", host="attacker.test")[0], 403)
        self.assertEqual(request("POST", "/v1/chat/completions", {"messages": [], "stream": True})[0], 400)
        self.backend.lock.acquire()
        try:
            self.assertEqual(request("POST", "/v1/chat/completions", {"messages":[{"role":"user","content":"hey"}]})[0], 503)
        finally:
            self.backend.lock.release()

    def test_companion_explicit_local_only_and_separate_state(self):
        source = self.root / "third_party/openbot"
        source.mkdir(parents=True)
        (source / "server.mjs").write_text("// fixture")
        (source / "LICENSE").write_text("MIT License")
        with patch.dict("os.environ", {"OPENBOT_REMOTE_BASE_URL": "https://external.invalid",
                                     "OPENBOT_BROWSER_ALLOW_HOSTS": "example.com"}):
            command, cwd, env = companion.plan(self.root)
        self.assertEqual(command[0], "node")
        self.assertEqual(cwd, str(source))
        self.assertEqual(env["OPENBOT_REMOTE_BASE_URL"], "")
        self.assertEqual(env["OPENBOT_LOCAL_ONLY"], "1")
        self.assertEqual(env["OPENBOT_BROWSER_ALLOW_HOSTS"], "127.0.0.1,localhost")
        self.assertIn(".local-merlin/openbot", env["OPENBOT_DATA_DIR"])
        with self.assertRaises(ValueError):
            companion.plan(self.root, model_port=8772, bot_port=8772)

    def test_source_verifier_rejects_missing_and_mismatched_sources(self):
        config = self.root / "config/merlin"
        config.mkdir(parents=True)
        manifest = {"components":[{"name":"OpenBot fixture", "path":"third_party/openbot",
            "source_commit":"a"*40, "repository":"https://github.com/example/OpenBot",
            "license":"MIT", "license_file":"LICENSE"},
            {"name":"AirLLM fixture", "path":"third_party/airllm",
            "source_commit":"b"*40, "repository":"https://github.com/example/airllm",
            "license":"Apache-2.0", "license_file":"LICENSE"}]}
        (config / "third-party-sources.json").write_text(json.dumps(manifest))
        (self.root / ".gitmodules").write_text(
            '[submodule "third_party/openbot"]\n path = third_party/openbot\n url = https://github.com/example/OpenBot.git\n'
            '[submodule "third_party/airllm"]\n path = third_party/airllm\n url = https://github.com/example/airllm.git\n')
        self.assertEqual(len(verifier.verify(self.root)), 2)
        for component in manifest["components"]:
            path = self.root / component["path"]
            path.mkdir(parents=True)
            (path / component["license_file"]).write_text(
                "MIT License" if component["license"] == "MIT" else "Apache License")
        def fake_git(*argv):
            if argv[0] == "config":
                return "https://github.com/example/" + ("OpenBot.git" if "openbot" in argv[-1] else "airllm.git")
            if argv[-1] == "HEAD":
                return "a"*40 if "openbot" in str(argv[1]) else "b"*40
            return ""
        with patch.object(verifier, "git", side_effect=fake_git):
            self.assertEqual(verifier.verify(self.root), [])
            (self.root / "third_party/airllm/LICENSE").write_text("wrong")
            self.assertIn("AirLLM fixture: expected license notice missing", verifier.verify(self.root))
            (self.root / "third_party/airllm/LICENSE").write_text("Apache License")
            with patch.object(verifier, "git", return_value="wrong"):
                self.assertTrue(verifier.verify(self.root))


if __name__ == "__main__":
    unittest.main()
