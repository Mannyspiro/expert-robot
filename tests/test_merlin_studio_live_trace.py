"""Bounded trace protocol tests; fixtures do not qualify a real model."""
import contextlib
import http.server
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/merlin"))
import studio_live_stream_trace as trace

TOKEN = "synthetic-local-session-secret-" + "q" * 32
PRIVATE = "synthetic-private-field-sentinel"
STAMP = "2026-11-24T12:00:00+00:00"
IDENTITY = {"model_sha256": "1" * 64, "engine_sha256": "2" * 64,
            "python_sha256": "3" * 64, "profile_manifest_sha256": "4" * 64}


def frame(ordinal, kind, **details):
    return {"event": "merlin", "id": str(ordinal),
            "data": {"ordinal": ordinal, "type": kind, "created_at": STAMP, **details}}


class Scenario:
    cid, rid = "a" * 32, "b" * 32

    def __init__(self, *, live=True, answer="A workspace helps locally.", deltas=None):
        self.live, self.answer = live, answer
        self.deltas = ["A workspace ", "helps locally."] if deltas is None else deltas
        self.finished = False
        self.calls = []
        self.windows = []

    def request(self, path, method="GET", value=None, token=None, **kwargs):
        self.calls.append((path, method, value, token))
        if path == "/api/status":
            return 200, {"session_token": TOKEN, "private_inventory": PRIVATE}
        if path == "/api/settings":
            return 200, {"settings": {"private": PRIVATE}}
        if path == "/api/conversations":
            return 201, {"conversation": {"id": self.cid}}
        if path == "/api/chat":
            return 202, {"run_id": self.rid}
        if path == "/api/runs/" + self.rid:
            return 200, {"run": {"status": "running" if self.live and not self.finished else "completed",
                                  "error": PRIVATE, "session_token": TOKEN}}
        if path == "/api/conversations/" + self.cid:
            return 200, {"conversation": {"messages": [
                {"role": "user", "content": trace.PROMPT},
                {"role": "assistant", "content": self.answer}], "private": PRIVATE}}
        raise AssertionError("unexpected endpoint")

    def stream(self, run_id, token, after, seconds):
        self.windows.append((run_id, token, after, seconds))
        yield frame(1, "started", content=PRIVATE, arguments={"token": TOKEN})
        yield frame(2, "model_request", step=1, content=PRIVATE)
        for index, content in enumerate(self.deltas, 3):
            yield frame(index, "text_delta", step=1, content=content)
        yield frame(len(self.deltas) + 3, "model_response", step=1, content="".join(self.deltas),
                    streamed=True, tool_call_count=0, reasoning=PRIVATE)
        self.finished = True
        yield frame(len(self.deltas) + 4, "completed", content=PRIVATE)


class LiveTraceTests(unittest.TestCase):
    def execute(self, scenario, stream=None):
        with mock.patch.object(trace, "request", scenario.request), \
                mock.patch.object(trace, "stream_events", stream or scenario.stream):
            result = trace.run_trace(IDENTITY, "a" * 40, "b" * 40)
        raw = json.dumps(result)
        self.assertLessEqual(len(raw.encode()), trace.MAX_REPORT)
        self.assertNotIn(TOKEN, raw)
        self.assertNotIn(PRIVATE, raw)
        return result

    def test_live_trace_matches_actual_deltas_final_state_and_public_prompt(self):
        scenario = Scenario()
        result = self.execute(scenario)
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["answer"]["text"], scenario.answer)
        self.assertEqual(result["answer"]["sha256"], trace.digest_text(scenario.answer))
        self.assertTrue(result["verification"]["live_running_state_observed_after_delta"])
        self.assertEqual(result["verification"]["nonempty_delta_count"], 2)
        self.assertEqual(result["run_id"], scenario.rid)
        self.assertEqual([c[2]["message"] for c in scenario.calls if c[0] == "/api/chat"], [trace.PROMPT])
        self.assertEqual(result["sampling"]["temperature"], 0.3)
        self.assertIsNone(result["sampling"]["seed"])
        self.assertFalse(result["production_qualified"])
        self.assertEqual([e["type"] for e in result["events"]],
                         ["model_request", "text_delta", "text_delta", "model_response", "completed"])
        self.assertTrue(all(c[3] == TOKEN for c in scenario.calls if c[0] != "/api/status"))

    def test_replayed_completed_response_and_mismatched_final_answer_fail(self):
        for scenario, code in ((Scenario(live=False), "no_observed_live_stream"),
                               (Scenario(answer="Different text"), "deltas_differ_from_persisted_answer"),
                               (Scenario(deltas=["A workspace helps locally."]), "no_observed_live_stream")):
            with self.subTest(code=code):
                result = self.execute(scenario)
                self.assertEqual(result["result"], "fail")
                self.assertEqual(result["failure"]["code"], code)
                self.assertNotIn("answer", result)

    def test_generated_token_split_between_deltas_is_removed(self):
        scenario = Scenario(answer=TOKEN, deltas=[TOKEN[:17], TOKEN[17:]])
        result = self.execute(scenario)
        self.assertEqual(result["result"], "fail")
        self.assertEqual(result["events"], [])
        self.assertEqual(result["failure"]["code"], "token_in_generated_text")

    def test_cursor_reconnect_keeps_real_event_order_and_ignores_snapshot_payload(self):
        scenario = Scenario()

        def reconnect(run_id, token, after, seconds):
            scenario.windows.append(after)
            if after == 0:
                yield frame(10, "model_request", step=1)
                yield frame(11, "text_delta", step=1, content=scenario.deltas[0])
                yield {"event": "snapshot", "id": None, "data": {"private": PRIVATE, "token": TOKEN}}
            elif after == 11:
                yield frame(12, "text_delta", step=1, content=scenario.deltas[1])
                yield frame(13, "model_response", step=1, content=scenario.answer, streamed=True, tool_call_count=0)
                scenario.finished = True
                yield frame(14, "completed")
            else:
                raise AssertionError("unexpected reconnect")

        result = self.execute(scenario, reconnect)
        self.assertEqual(result["result"], "pass")
        self.assertEqual(scenario.windows, [0, 11])
        self.assertEqual(result["stream_windows"], 2)

    def test_false_step_duplicate_cursor_and_oversized_content_fail(self):
        variants = [(frame(1, "model_request", step=True), "unexpected_model_step"),
                    (frame(0, "model_request", step=1), "event_order_or_identity")]
        for item, code in variants:
            def stream(*_):
                yield item
            with self.subTest(code=code):
                result = self.execute(Scenario(), stream)
                self.assertEqual(result["failure"]["code"], code)
        result = self.execute(Scenario(deltas=["x" * (trace.MAX_TEXT + 1)]))
        self.assertEqual(result["failure"]["code"], "text_limit")

    def test_profile_identity_reads_only_pinned_allowlisted_fields(self):
        profile = {"schema": "merlin-linux-offline-profile/1", "model_id": "local",
                   "model_expected_sha256": "1" * 64, "llama_expected_sha256": "2" * 64,
                   "python_expected_sha256": "3" * 64, "private": PRIVATE}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            path.write_text(json.dumps(profile))
            identity = trace.profile_identity(path, "1" * 64)
            self.assertEqual(set(identity), set(IDENTITY))
            self.assertNotIn(PRIVATE, json.dumps(identity))
            with self.assertRaisesRegex(trace.SmokeFailure, "profile_model_pin_mismatch"):
                trace.profile_identity(path, "9" * 64)
            path.write_bytes(b"x" * (1024 * 1024 + 1))
            with self.assertRaisesRegex(trace.SmokeFailure, "profile_manifest_limit"):
                trace.profile_identity(path, "1" * 64)

    def test_import_does_not_start_network(self):
        with mock.patch("http.client.HTTPConnection", side_effect=AssertionError("network on import")):
            spec = importlib.util.spec_from_file_location("live_trace_import_test", Path(trace.__file__))
            loaded = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loaded)
        self.assertTrue(callable(loaded.main))


class SSETransportTests(unittest.TestCase):
    @contextlib.contextmanager
    def server(self, mode):
        release, sent = threading.Event(), threading.Event()
        observed = []

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *_):
                pass

            def do_GET(self):
                observed.append((self.path, self.headers.get("X-Merlin-Token")))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Connection", "close")
                self.end_headers()
                try:
                    if mode == "slow":
                        release.wait(1)
                    elif mode == "oversized":
                        self.wfile.write(b"data: " + b"x" * trace.MAX_FRAME + b"\n\n")
                    elif mode == "duplicate":
                        self.wfile.write(b'event: merlin\nid: 1\nid: 1\ndata: {}\n\n')
                    elif mode == "json-duplicate":
                        self.wfile.write(b'event: merlin\nid: 1\ndata: {"x":1,"x":2}\n\n')
                    else:
                        self.wfile.write(b': connected\nretry: 1000\n\nevent: merlin\nid: 1\n'
                                         b'data: {"ordinal":1,"type":"text_delta","content":"hello"}\n\n')
                        self.wfile.flush()
                        sent.set()
                        release.wait(2)
                        self.wfile.write(b'event: snapshot\ndata: {"refresh_required":true}\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.object(trace, "STUDIO_PORT", server.server_port):
                yield release, sent, observed
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)

    def test_actual_http10_delta_arrives_while_upstream_still_open(self):
        with self.server("live") as (release, sent, observed):
            iterator = trace.stream_events("a" * 32, TOKEN, 0, 1.5)
            try:
                first = next(iterator)
                # The client can receive flushed bytes before the server thread
                # sets its notification. Await that notification, while keeping
                # completion blocked by the independent release event below.
                self.assertTrue(sent.wait(0.5))
                self.assertFalse(release.is_set())
                self.assertEqual(first["data"]["content"], "hello")
                self.assertEqual(first["id"], "1")
                self.assertEqual(observed, [("/api/runs/" + "a" * 32 + "/events?after=0", TOKEN)])
                release.set()
                self.assertEqual(next(iterator)["event"], "snapshot")
                self.assertEqual(list(iterator), [])
            finally:
                iterator.close()

    def test_actual_transport_deadline_and_malformed_frame_bounds(self):
        for mode, code in (("oversized", "stream_byte_limit"), ("duplicate", "duplicate_sse_field"),
                           ("json-duplicate", "duplicate_json_key")):
            with self.subTest(mode=mode), self.server(mode):
                with self.assertRaisesRegex(trace.SmokeFailure, code):
                    list(trace.stream_events("a" * 32, TOKEN, 0, 1))
        with self.server("slow"):
            started = time.monotonic()
            with self.assertRaises((trace.SmokeFailure, OSError, trace.http.client.HTTPException)):
                list(trace.stream_events("a" * 32, TOKEN, 0, 0.08))
            self.assertLess(time.monotonic() - started, 0.8)


if __name__ == "__main__":
    unittest.main()
