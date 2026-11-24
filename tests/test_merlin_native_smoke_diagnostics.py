"""Synthetic control-flow/privacy tests; these do not qualify a native model."""
import contextlib
import email.message
import hashlib
import http.server
import importlib.util
import io
import json
from pathlib import Path
import threading
import time
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/merlin/native_self_contained_smoke.py"


def load_smoke():
    spec = importlib.util.spec_from_file_location("native_smoke_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smoke = load_smoke()
TOKEN = "synthetic-session-secret-" + "q" * 32
PRIVATE = "synthetic-private-inventory-sentinel"
REASONING = "synthetic-hidden-reasoning-sentinel"


class Scenario:
    cid, fresh_cid = "a" * 32, "b" * 32
    help_id, answer_id, fresh_id = "c" * 32, "d" * 32, "e" * 32

    def __init__(self, answer):
        self.answer = answer
        self.primary_sent = False
        self.calls = []

    def ready(self, path, **kwargs):
        if path == "/api/status":
            return {"ready": True, "session_token": TOKEN, "private_inventory": PRIVATE}
        if path == "/v1/models":
            return {"data": [{"id": "local"}]}
        raise AssertionError("unexpected readiness endpoint")

    def history(self, fresh=False):
        items = [] if fresh else [{"role": "user", "content": "/help"},
                                  {"role": "assistant", "content": "Offline help"}]
        if fresh or self.primary_sent:
            items += [{"role": "user", "content": smoke.PROMPT},
                      {"role": "assistant", "content": "4" if fresh else self.answer}]
        return {"conversation": {"messages": items, "private_inventory": PRIVATE}}

    def request(self, path, method="GET", value=None, token=None, **kwargs):
        self.calls.append((path, method, value, token, kwargs))
        if path == "/api/conversations" and method == "POST":
            cid = self.cid if value["title"] == "Native ZIP test" else self.fresh_cid
            return 201, {"conversation": {"id": cid}}
        if path == "/api/chat":
            if value["message"] == "/help":
                return 202, {"run_id": self.help_id}
            if value["conversation_id"] == self.cid:
                self.primary_sent = True
                return 202, {"run_id": self.answer_id}
            return 202, {"run_id": self.fresh_id}
        if path == "/api/conversations/" + self.cid:
            return 200, self.history()
        if path == "/api/conversations/" + self.fresh_cid:
            return 200, self.history(fresh=True)
        if path in ("/api/settings", "/api/model/probe"):
            return 200, {"settings": {"private_inventory": PRIVATE, "session_token": TOKEN}}
        if path == "/v1/chat/completions":
            return 200, {"choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "4", "reasoning_content": REASONING,
                "tool_calls": []}}], "usage": {"completion_tokens": 1},
                "private_inventory": PRIVATE, "session_token": TOKEN}
        raise AssertionError("unexpected request endpoint")

    def finished(self, run_id, seconds=160):
        events = [{"type": "started", "arguments": {"secret": TOKEN}},
                  {"type": "model_request", "content": REASONING},
                  {"type": PRIVATE, "result": {"private_inventory": PRIVATE}}] * 100
        return "completed", {"run": {"events": events, "error": PRIVATE}}


class NativeSmokeDiagnosticsTests(unittest.TestCase):
    def execute(self, scenario):
        output = io.StringIO()
        with mock.patch.object(smoke, "ready", scenario.ready), \
                mock.patch.object(smoke, "request", scenario.request), \
                mock.patch.object(smoke, "finished", scenario.finished), \
                contextlib.redirect_stdout(output):
            code = smoke.main()
        raw = output.getvalue()
        self.assertEqual(len(raw.splitlines()), 1)
        self.assertLessEqual(len(raw.encode()), smoke.MAX_REPORT + 1)
        return code, json.loads(raw), raw

    def test_import_is_safe_and_does_not_start_network_or_smoke(self):
        with mock.patch("http.client.HTTPConnection", side_effect=AssertionError("network on import")), \
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network on import")), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            imported = load_smoke()
        self.assertTrue(callable(imported.main))
        self.assertEqual(output.getvalue(), "")

    def test_primary_pass_preserves_original_conversation_settings_and_oracle(self):
        scenario = Scenario("The answer is 4.")
        with mock.patch.object(smoke, "failure_diagnostics", side_effect=AssertionError("diagnostic on pass")):
            code, evidence, _ = self.execute(scenario)
        self.assertEqual(code, 0)
        self.assertEqual(evidence["result"], "pass")
        self.assertEqual(evidence["primary"]["assistant"]["text"], "The answer is 4.")
        self.assertEqual(evidence["diagnostics"], {"status": "not_run"})
        chats = [c[2] for c in scenario.calls if c[0] == "/api/chat"]
        self.assertEqual(chats, [{"conversation_id": scenario.cid, "message": "/help"},
                                {"conversation_id": scenario.cid, "message": smoke.PROMPT}])
        settings = [c[2] for c in scenario.calls if c[0] == "/api/settings"]
        self.assertEqual(settings, [{"model_url": "http://127.0.0.1:8772/v1/chat/completions",
            "model_id": "local", "network_enabled": False, "python_enabled": False,
            "desktop_enabled": False, "max_steps": 1, "max_output_tokens": 64,
            "model_timeout_seconds": 120, "tool_compatibility": "native"}])

    def test_bounded_failure_evidence_and_successful_diagnostics_cannot_rescue_primary(self):
        answer = "5 " + TOKEN + " " + "wrong " * 10000
        scenario = Scenario(answer)
        code, evidence, raw = self.execute(scenario)
        self.assertEqual(code, 1)
        self.assertEqual(evidence["result"], "fail")
        self.assertFalse(evidence["primary"]["standalone_4_oracle_passed"])
        summary = evidence["primary"]["assistant"]
        self.assertLessEqual(len(summary["text"]), 512)
        self.assertEqual(summary["length_chars"], len(answer))
        self.assertEqual(summary["sha256"], hashlib.sha256(answer.encode()).hexdigest())
        self.assertEqual(evidence["primary"]["events"]["counted"], 256)
        self.assertTrue(evidence["primary"]["events"]["truncated"])
        for secret in (TOKEN, PRIVATE, REASONING):
            self.assertNotIn(secret, raw)
        for name in ("direct_no_tools", "fresh_studio"):
            self.assertTrue(evidence["diagnostics"][name]["standalone_4_oracle_passed"])
        direct = [c for c in scenario.calls if c[0] == "/v1/chat/completions"]
        self.assertEqual(len(direct), 1)
        self.assertIsNone(direct[0][3])
        self.assertEqual(direct[0][2], {"model": "local", "messages": [
            {"role": "user", "content": smoke.PROMPT}], "stream": False,
            "max_tokens": 64, "temperature": 0.3})
        self.assertEqual(direct[0][4], {"base": smoke.MODEL, "timeout": 120})
        self.assertEqual(len([c for c in scenario.calls if c[0] == "/api/settings"]), 1)
        self.assertEqual([c[2]["message"] for c in scenario.calls if c[0] == "/api/chat"],
                         ["/help", smoke.PROMPT, smoke.PROMPT])

    def test_empty_malformed_and_nonstandalone_answers_remain_failures(self):
        for answer, state in (("", "empty"), (None, "missing"), (["4"], "malformed"),
                              ("14", "text")):
            with self.subTest(answer=answer):
                code, evidence, _ = self.execute(Scenario(answer))
                self.assertEqual(code, 1)
                self.assertEqual(evidence["primary"]["assistant"]["content_state"], state)
                self.assertFalse(evidence["primary"]["standalone_4_oracle_passed"])

    def test_reasoning_markup_and_malformed_direct_response_do_not_leak(self):
        text = "<think>" + REASONING + "</think>4"
        summary = smoke.answer_summary(text, TOKEN)
        self.assertEqual(summary["text"], "")
        self.assertTrue(summary["preview_omitted_reasoning_markup"])
        self.assertEqual(summary["length_chars"], len(text))
        for value in ({}, {"choices": []}, {"choices": [{"message": None}]}):
            with self.subTest(value=value), mock.patch.object(smoke, "request", return_value=(200, value)):
                with self.assertRaises(smoke.SmokeFailure):
                    smoke.direct_diagnostic(TOKEN)

    def test_early_failure_still_emits_json_without_raw_exception_or_status(self):
        output = io.StringIO()
        with mock.patch.object(smoke, "ready", side_effect=OSError(TOKEN + PRIVATE)), \
                contextlib.redirect_stdout(output):
            code = smoke.main()
        self.assertEqual(code, 1)
        evidence = json.loads(output.getvalue())
        self.assertEqual(evidence["failure"]["error_type"], "OSError")
        self.assertEqual(evidence["diagnostics"], {"status": "not_run"})
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(PRIVATE, output.getvalue())

    def test_http_body_redirect_and_total_deadline_bounds(self):
        class Response:
            def __init__(self, raw=b"{}", status=200, declared=None, after_read=None):
                self.status, self.body, self.after_read = status, io.BytesIO(raw), after_read
                self.headers = email.message.Message()
                if declared is not None:
                    self.headers["Content-Length"] = str(declared)
                self.reads, self.closed = [], False

            def read1(self, size):
                self.reads.append(size)
                value = self.body.read(size)
                if self.after_read:
                    self.after_read()
                if not value:
                    self.closed = True
                return value

            def isclosed(self):
                return self.closed

            def close(self):
                self.closed = True

        for response, error in ((Response(declared=smoke.MAX_BODY + 1), "response_body_limit"),
                                (Response(raw=b"x" * (smoke.MAX_BODY + 1)), "response_body_limit"),
                                (Response(status=302), "http_status_rejected")):
            with self.subTest(error=error):
                connection = mock.Mock()
                connection.getresponse.return_value = response
                with mock.patch.object(smoke.http.client, "HTTPConnection", return_value=connection) as factory:
                    with self.assertRaisesRegex(smoke.SmokeFailure, error):
                        smoke.request("/v1/models", base=smoke.MODEL)
                factory.assert_called_once_with("127.0.0.1", 8772, timeout=5)
                self.assertTrue(response.closed)
                if response.reads:
                    self.assertLessEqual(max(response.reads), 65536)
        clock = [0.0]
        response = Response(after_read=lambda: clock.__setitem__(0, 2.0))
        connection = mock.Mock()
        connection.getresponse.return_value = response
        with mock.patch.object(smoke.http.client, "HTTPConnection", return_value=connection), \
                mock.patch.object(smoke.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(smoke.SmokeFailure, "http_deadline"):
                smoke.request("/api/status", timeout=1)
        self.assertTrue(response.closed)
        with mock.patch.object(smoke.http.client, "HTTPConnection") as factory:
            with self.assertRaisesRegex(smoke.SmokeFailure, "invalid_loopback_request"):
                smoke.request("/", base="https://example.invalid")
            factory.assert_not_called()

    def test_actual_loopback_http10_close_truncation_and_deadline(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_):
                pass

            def do_GET(self):
                body = b'{"ready":true}'
                self.send_response(200)
                self.send_header("Connection", "close")
                self.send_header("Content-Length", str(len(body) + (10 if self.path == "/truncated" else 0)))
                self.end_headers()
                if self.path == "/slow":
                    time.sleep(0.2)
                try:
                    self.wfile.write(body)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original_connection = smoke.http.client.HTTPConnection

        def local_connection(host, port, timeout):
            self.assertEqual((host, port), ("127.0.0.1", 18771))
            # Only substitute the fixture's ephemeral port. The actual stdlib
            # HTTP connection, socket, framing, body reads and deadline execute.
            return original_connection(host, server.server_port, timeout=timeout)

        try:
            with mock.patch.object(smoke.http.client, "HTTPConnection", side_effect=local_connection):
                self.assertEqual(smoke.request("/ok"), (200, {"ready": True}))
                with self.assertRaisesRegex(smoke.SmokeFailure, "short_response_body"):
                    smoke.request("/truncated")
                started = time.monotonic()
                with self.assertRaises((smoke.SmokeFailure, OSError, smoke.http.client.HTTPException)):
                    smoke.request("/slow", timeout=0.06)
                self.assertLess(time.monotonic() - started, 0.8)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


if __name__ == "__main__":
    unittest.main()
