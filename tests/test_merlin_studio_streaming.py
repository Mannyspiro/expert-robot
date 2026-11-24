"""Real loopback stream/cancellation tests; model output is a synthetic fixture.

These tests exercise transport and lifecycle, not model intelligence or quality.
"""
from __future__ import annotations

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable" / "merlin_studio"))
import server as studio_server
from model import LocalModel, ModelError, _ChatStream, MAX_STREAM_FRAME_BYTES
from storage import Store


def frame(delta=None, finish=None):
    return ("data: " + json.dumps({"choices": [{"index": 0, "delta": delta or {},
                                               "finish_reason": finish}]}, ensure_ascii=False)
            + "\n\n").encode("utf-8")


def ending(reason="stop"):
    return frame(finish=reason) + b"data: [DONE]\n\n"


class Upstream:
    def __init__(self, script, *, headers=None):
        self.release = threading.Event()
        self.started = threading.Event()
        self.requests = []
        self.errors = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *_):
                pass
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                owner.requests.append(json.loads(body))
                self.send_response(200)
                for name, value in (headers if headers is not None else [
                        ("Content-Type", "text/event-stream"), ("Connection", "close")]):
                    self.send_header(name, value)
                self.end_headers()
                self.close_connection = True
                owner.started.set()
                def send(raw):
                    self.wfile.write(raw)
                    self.wfile.flush()
                try:
                    script(owner, send)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except BaseException as exc:
                    owner.errors.append(exc)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port) + "/v1"

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class StreamTests(unittest.TestCase):
    def upstream(self, script, **kwargs):
        fixture = Upstream(script, **kwargs)
        self.addCleanup(fixture.close)
        return fixture

    def model(self, fixture):
        return LocalModel({"model_url": fixture.url, "model_id": "synthetic-stream", "max_output_tokens": 64})

    def async_stream(self, model, *, cancelled=lambda: False, timeout=5):
        result = {"deltas": []}
        arrived = threading.Event()
        def receive(text):
            result["deltas"].append(text)
            arrived.set()
        def work():
            try:
                result["reply"] = model.stream([], [], on_delta=receive, cancelled=cancelled, timeout=timeout)
            except BaseException as exc:
                result["error"] = exc
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        return thread, arrived, result

    def test_actual_text_arrives_while_upstream_is_still_blocked(self):
        def script(owner, send):
            send(frame({"role": "assistant", "content": "First "}))
            owner.release.wait(5)
            raw = frame({"content": "café 🧠"}) + ending()
            for offset in range(0, len(raw), 3):
                send(raw[offset:offset + 3])
        fixture = self.upstream(script)
        thread, arrived, result = self.async_stream(self.model(fixture))
        self.assertTrue(arrived.wait(2))
        self.assertEqual(result["deltas"], ["First "])
        self.assertTrue(thread.is_alive())
        self.assertNotIn("reply", result)
        fixture.release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", result)
        self.assertEqual(result["reply"]["content"], "First café 🧠")
        self.assertEqual("".join(result["deltas"]), result["reply"]["content"])
        self.assertTrue(fixture.requests[0]["stream"])
        self.assertEqual(fixture.requests[0]["temperature"], 0.3)
        self.assertEqual(fixture.requests[0]["max_tokens"], 64)
        self.assertNotIn("seed", fixture.requests[0])

    def test_byte_fragmented_utf8_crlf_comments_and_multiline_data(self):
        seen = []
        decoder = _ChatStream(seen.append)
        raw = (b": keep-alive\r\nevent: message\r\n"
               b'data: {"choices":\r\ndata: [{"index":0,"delta":{"content":"'
               + "🧠".encode() + b'"},"finish_reason":null}]}\r\n\r\n' + ending())
        for byte in raw:
            decoder.feed(bytes([byte]))
        self.assertEqual(decoder.finish()["content"], "🧠")
        self.assertEqual(seen, ["🧠"])

    def test_fragmented_tool_is_assembled_and_only_returned_when_complete(self):
        raw = (frame({"tool_calls": [{"index": 0, "id": "call-a", "type": "function",
                "function": {"name": "read_", "arguments": '{"pa'}}]})
               + frame({"tool_calls": [{"index": 0, "function": {"name": "file", "arguments": 'th":"a.txt"}'}}]})
               + ending("tool_calls"))
        fixture = self.upstream(lambda owner, send: send(raw))
        seen = []
        answer = self.model(fixture).stream([], [], on_delta=seen.append, cancelled=lambda: False)
        self.assertEqual(seen, [])
        self.assertEqual(answer["tool_calls"], [{"id": "call-a", "type": "function", "function": {
            "name": "read_file", "arguments": '{"path":"a.txt"}'}}])

    def test_malformed_or_incomplete_streams_are_not_final_answers(self):
        bad = [
            frame({"content": "partial"}),
            frame({"content": "partial"}) + b"data: [DONE]\n\n",
            ending() + frame({"content": "late"}),
            b'data: {"choices":[],"choices":[]}\n\n',
            b'data: {"choices":[{"delta":{"content":"\xff"}}]}\n\n',
            b"unknown: field\n\n",
            frame({"content": 42}) + ending(),
            frame({"role": "user", "content": "wrong role"}) + ending(),
            frame({"function_call": {"name": "legacy"}}) + ending(),
            frame({"tool_calls": [{"index": True}]}) + ending("tool_calls"),
            frame({"tool_calls": [{"index": 4}]}) + ending("tool_calls"),
            frame({"tool_calls": [{"index": 1, "id": "sparse", "function": {"name": "read_file", "arguments": "{}"}}]}) + ending("tool_calls"),
            frame({"tool_calls": [{"index": 0, "id": "unfinished", "function": {"name": "read_file", "arguments": "{}"}}]}) + ending(),
            ending("tool_calls"),
            frame({"content": "text"}, finish="content_filter") + b"data: [DONE]\n\n",
        ]
        for raw in bad:
            with self.subTest(raw=raw[:100]), self.assertRaises(ModelError):
                decoder = _ChatStream(lambda _: None)
                decoder.feed(raw)
                decoder.finish()

    def test_partial_or_duplicate_tool_arguments_fail_normalization(self):
        cases = [
            [{"index": 0, "id": "one", "function": {"name": "read_file", "arguments": '{"path":'}}],
            [{"index": 0, "id": "one", "function": {"name": "read_file", "arguments": "[]"}}],
            [{"index": n, "id": "duplicate", "function": {"name": "read_file", "arguments": "{}"}} for n in range(2)],
        ]
        for calls in cases:
            fixture = self.upstream(lambda owner, send, c=calls: send(frame({"tool_calls": c}) + ending("tool_calls")))
            with self.subTest(calls=calls), self.assertRaises(ModelError):
                self.model(fixture).stream([], [], on_delta=lambda _: None, cancelled=lambda: False)

    def test_frame_text_and_event_budgets_reject_before_acceptance(self):
        for raw in (b"data: " + b"x" * MAX_STREAM_FRAME_BYTES,
                    frame({"content": "x" * 65537}),
                    frame({"content": "x"}) * 4097,
                    b'data: {"choices":[],"usage":{}}\n\n' * 8193):
            with self.subTest(length=len(raw)), self.assertRaises(ModelError):
                _ChatStream(lambda _: None).feed(raw)

    def test_legacy_json_response_never_manufactures_text_deltas(self):
        raw = json.dumps({"choices": [{"message": {"content": "whole JSON answer"}}]}).encode()
        fixture = self.upstream(lambda owner, send: send(raw), headers=[("Content-Type", "application/json")])
        seen = []
        reply = self.model(fixture).stream([], [], on_delta=seen.append, cancelled=lambda: False)
        self.assertEqual(reply["content"], "whole JSON answer")
        self.assertEqual(seen, [])

    def test_stream_http_framing_and_content_type_limits(self):
        for headers in ([('Content-Type', 'text/html')],
                        [('Content-Type', 'text/event-stream'), ('Content-Encoding', 'gzip')],
                        [('Content-Length', '2097153'), ('Content-Type', 'text/event-stream')],
                        [('Content-Type', 'text/event-stream'), ('Content-Length', '2'), ('Content-Length', '2')]):
            fixture = self.upstream(lambda owner, send: send(b"{}"), headers=headers)
            with self.subTest(headers=headers), self.assertRaises(ModelError):
                self.model(fixture).stream([], [], on_delta=lambda _: None, cancelled=lambda: False)

    def test_total_byte_budget_applies_to_stream_comments_too(self):
        raw = (b": " + b"x" * 30000 + b"\n\n") * 71
        fixture = self.upstream(lambda owner, send: send(raw))
        with self.assertRaisesRegex(ModelError, "2 MiB"):
            self.model(fixture).stream([], [], on_delta=lambda _: None, cancelled=lambda: False)

    def test_deadline_interrupts_stalled_stream_after_partial_text(self):
        def script(owner, send):
            send(frame({"content": "partial"}))
            owner.release.wait(5)
        fixture = self.upstream(script)
        started = time.monotonic()
        thread, arrived, result = self.async_stream(self.model(fixture), timeout=0.2)
        self.assertTrue(arrived.wait(1))
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(result.get("error"), ModelError)
        self.assertIn("deadline", str(result["error"]))
        self.assertLess(time.monotonic() - started, 1)

    def test_cancellation_interrupts_the_actual_blocked_model_read(self):
        def script(owner, send):
            send(frame({"content": "partial"}))
            owner.release.wait(5)
        fixture = self.upstream(script)
        cancelled = threading.Event()
        thread, arrived, result = self.async_stream(self.model(fixture), cancelled=cancelled.is_set)
        self.assertTrue(arrived.wait(2))
        cancelled.set()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertIsInstance(result.get("error"), InterruptedError)
        self.assertNotIn("reply", result)
        self.assertEqual(len(fixture.requests), 1)

    def test_done_does_not_wait_for_peer_to_close_tcp(self):
        def script(owner, send):
            send(frame({"content": "complete"}) + ending())
            owner.release.wait(5)
        fixture = self.upstream(script)
        thread, _, result = self.async_stream(self.model(fixture))
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result.get("reply", {}).get("content"), "complete")
        self.assertFalse(fixture.release.is_set())

    def test_pre_cancelled_request_never_reaches_upstream(self):
        fixture = self.upstream(lambda owner, send: send(ending()))
        with self.assertRaises(InterruptedError):
            self.model(fixture).stream([], [], on_delta=lambda _: None, cancelled=lambda: True)
        self.assertEqual(fixture.requests, [])


class StudioEventHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.server = studio_server.create_server(data_dir=Path(self.temp.name) / "state", start_bundled=False)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.token = self.request("GET", "/api/status")[1]["session_token"]

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def connection(self):
        return http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)

    def request(self, method, path, value=None, *, headers=None):
        connection = self.connection()
        supplied = dict(headers or {})
        body = None
        if method == "POST":
            supplied.update({"Content-Type": "application/json", "X-Merlin-Token": self.token})
            body = json.dumps(value or {}).encode()
        try:
            connection.request(method, path, body=body, headers=supplied)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def stream(self, run_id, *, query="?after=0", headers=None):
        connection = self.connection()
        supplied = {"X-Merlin-Token": self.token, **(headers or {})}
        connection.request("GET", "/api/runs/" + run_id + "/events" + query, headers=supplied)
        response = connection.getresponse()
        self.addCleanup(response.close)
        self.addCleanup(connection.close)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream; charset=utf-8")
        return connection, response

    def read_event(self, response):
        event = {}
        while True:
            line = response.readline(262145)
            self.assertLess(len(line), 262145)
            if not line:
                return None
            text = line.decode("utf-8").rstrip("\r\n")
            if not text:
                if "data" in event:
                    event["data"] = json.loads(event["data"])
                    return event
                event = {}
            elif ":" in text:
                key, value = text.split(":", 1)
                event[key] = value.removeprefix(" ")

    def until_delta(self, response):
        seen = []
        while True:
            event = self.read_event(response)
            self.assertIsNotNone(event)
            seen.append(event)
            if event["event"] == "merlin" and event["data"]["type"] == "text_delta":
                return seen

    def remaining(self, response):
        seen = []
        while True:
            event = self.read_event(response)
            if event is None:
                return seen
            seen.append(event)

    def fixture_run(self, script, message="Synthetic stream test"):
        fixture = Upstream(script)
        self.addCleanup(fixture.close)
        self.assertEqual(self.request("POST", "/api/settings", {"model_url": fixture.url,
                         "network_enabled": False, "python_enabled": False})[0], 200)
        status, value = self.request("POST", "/api/conversations")
        self.assertEqual(status, 201)
        cid = value["conversation"]["id"]
        status, value = self.request("POST", "/api/chat", {"conversation_id": cid, "message": message})
        self.assertEqual(status, 202)
        return fixture, value["run_id"]

    @staticmethod
    def delayed(owner, send):
        send(frame({"content": "Live "}))
        owner.release.wait(5)
        send(frame({"content": "answer"}) + ending())

    def test_live_sse_precedes_final_message_and_preserves_persisted_answer(self):
        fixture, rid = self.fixture_run(self.delayed)
        _, response = self.stream(rid)
        events = self.until_delta(response)
        snapshot = self.request("GET", "/api/runs/" + rid)[1]
        self.assertEqual(snapshot["run"]["status"], "running")
        self.assertEqual([m["role"] for m in snapshot["conversation"]["messages"]], ["user"])
        fixture.release.set()
        events += self.remaining(response)
        merlin = [e["data"] for e in events if e["event"] == "merlin"]
        self.assertEqual([e["type"] for e in merlin], ["started", "model_request", "text_delta", "text_delta", "model_response", "completed"])
        self.assertEqual([e["ordinal"] for e in merlin], sorted({e["ordinal"] for e in merlin}))
        self.assertTrue(all(str(e["data"]["ordinal"]) == e["id"] for e in events if e["event"] == "merlin"))
        self.assertTrue(all(isinstance(e["id"], str) and len(e["id"]) == 32 for e in merlin))
        self.assertEqual(merlin[-2]["step"], 1)
        self.assertTrue(merlin[-2]["streamed"])
        self.assertEqual(events[-1]["event"], "snapshot")
        self.assertTrue(events[-1]["data"]["refresh_required"])
        self.assertNotIn("events", events[-1]["data"]["run"])
        done = self.request("GET", "/api/runs/" + rid)[1]
        text = "".join(e["content"] for e in merlin if e["type"] == "text_delta")
        self.assertEqual(done["conversation"]["messages"][-1]["content"], text)
        self.assertEqual(text, "Live answer")
        self.assertEqual(done["run"]["events"], merlin)
        self.assertEqual(len(fixture.requests), 1)

    def test_disconnect_and_cursor_reconnect_neither_repeat_nor_cancel_model(self):
        fixture, rid = self.fixture_run(self.delayed)
        first_connection, first_response = self.stream(rid)
        before = self.until_delta(first_response)
        cursor = before[-1]["data"]["ordinal"]
        first_response.close()
        first_connection.close()
        _, resumed = self.stream(rid, query="", headers={"Last-Event-ID": str(cursor)})
        self.assertEqual(self.request("GET", "/api/runs/" + rid)[1]["run"]["status"], "running")
        fixture.release.set()
        after = [e["data"] for e in self.remaining(resumed) if e["event"] == "merlin"]
        self.assertTrue(all(e["ordinal"] > cursor for e in after))
        self.assertEqual([e["content"] for e in after if e["type"] == "text_delta"], ["answer"])
        self.assertEqual(after[-1]["type"], "completed")
        self.assertEqual(len(fixture.requests), 1)

    def test_cancel_api_stops_blocked_upstream_and_prevents_late_final_message(self):
        fixture, rid = self.fixture_run(self.delayed)
        _, response = self.stream(rid)
        before = self.until_delta(response)
        self.assertEqual(self.request("POST", "/api/runs/" + rid + "/cancel")[0], 200)
        remaining = self.remaining(response)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with self.server.app.threads_lock:
                active = rid in self.server.app.threads
            if not active:
                break
            time.sleep(0.01)
        self.assertFalse(active, "Cancelled network read retained an agent worker")
        fixture.release.set()
        done = self.request("GET", "/api/runs/" + rid)[1]
        self.assertEqual(done["run"]["status"], "cancelled")
        self.assertEqual([m["role"] for m in done["conversation"]["messages"]], ["user"])
        self.assertEqual([e["type"] for e in done["run"]["events"]], ["started", "model_request", "text_delta", "cancelled"])
        self.assertEqual([e["data"]["type"] for e in remaining if e["event"] == "merlin"], ["cancelled"])
        self.assertEqual(len(fixture.requests), 1)

    def completed(self):
        store = self.server.app.store
        cid = store.create_conversation()["id"]
        rid = store.start_run(cid, "recorded")
        store.event(rid, "text_delta", content="recorded text", step=1, require_active=True)
        store.finish(rid, "recorded text")
        return rid

    def test_completed_replay_has_stable_ordinals_across_reopened_store(self):
        rid = self.completed()
        stored = self.server.app.store.events(rid)
        self.assertEqual(Store(self.server.app.store.root).events(rid), stored)
        _, response = self.stream(rid, query="?after=" + str(stored[0]["ordinal"]))
        replay = self.remaining(response)
        self.assertEqual([e["data"] for e in replay if e["event"] == "merlin"], stored[1:])
        _, response = self.stream(rid, query="?after=" + str(stored[-1]["ordinal"]))
        self.assertEqual([e["event"] for e in self.remaining(response)], ["snapshot"])
        with self.assertRaises(InterruptedError):
            self.server.app.store.event(rid, "text_delta", content="late", require_active=True)

    def test_stream_requires_token_and_retains_host_origin_and_cross_site_checks(self):
        rid = self.completed()
        path = "/api/runs/" + rid + "/events?after=0"
        cases = ({}, {"X-Merlin-Token": "wrong"},
                 {"X-Merlin-Token": self.token, "Origin": "http://example.org"},
                 {"X-Merlin-Token": self.token, "Host": "example.org"},
                 {"X-Merlin-Token": self.token, "Sec-Fetch-Site": "cross-site"})
        for headers in cases:
            with self.subTest(headers=list(headers)):
                self.assertEqual(self.request("GET", path, headers=headers)[0], 403)
        self.assertEqual(self.request("GET", path + "&token=" + self.token)[0], 403)

    def test_bad_cursors_and_query_credentials_are_rejected_before_sse(self):
        rid = self.completed()
        for query in ("?after=-1", "?after=", "?after=true", "?after=1.0", "?after=9223372036854775808",
                      "?after=1&after=2", "?other=1", "?token=hidden", "?after=0&token=hidden"):
            with self.subTest(query=query):
                self.assertEqual(self.request("GET", "/api/runs/" + rid + "/events" + query,
                    headers={"X-Merlin-Token": self.token})[0], 400)
        self.assertEqual(self.request("GET", "/api/runs/" + rid + "/events?after=1",
            headers={"X-Merlin-Token": self.token, "Last-Event-ID": "2"})[0], 400)

    def test_subscription_limit_and_unknown_run_have_bounded_json_failures(self):
        rid = self.completed()
        headers = {"X-Merlin-Token": self.token}
        self.assertEqual(self.request("GET", "/api/runs/unknown/events", headers=headers)[0], 404)
        acquired = 0
        try:
            while self.server.stream_slots.acquire(blocking=False):
                acquired += 1
            self.assertEqual(acquired, 16)
            self.assertEqual(self.request("GET", "/api/runs/" + rid + "/events", headers=headers)[0], 429)
        finally:
            for _ in range(acquired):
                self.server.stream_slots.release()

    def test_connection_window_can_end_without_cancelling_active_generation(self):
        fixture, rid = self.fixture_run(self.delayed)
        ready = time.monotonic() + 2
        while time.monotonic() < ready and not any(
                e["type"] == "text_delta" for e in self.server.app.store.events(rid)):
            time.sleep(0.01)
        with patch.object(studio_server, "STREAM_WINDOW_SECONDS", 0.15):
            _, response = self.stream(rid)
            before = self.remaining(response)
        self.assertTrue(any(e["data"].get("type") == "text_delta" for e in before))
        self.assertEqual(self.request("GET", "/api/runs/" + rid)[1]["run"]["status"], "running")
        cursor = max(e["data"]["ordinal"] for e in before if e["event"] == "merlin")
        _, response = self.stream(rid, query="?after=" + str(cursor))
        fixture.release.set()
        self.assertEqual(self.remaining(response)[-1]["data"]["run"]["status"], "completed")
        self.assertEqual(len(fixture.requests), 1)

    def test_byte_windows_resume_without_dropping_or_repeating_events(self):
        rid = self.completed()
        seen = []
        cursor = 0
        terminal_snapshot = False
        with patch.object(studio_server, "STREAM_WINDOW_BYTES", 500):
            for _ in range(5):
                _, response = self.stream(rid, query="?after=" + str(cursor))
                raw = response.read()
                self.assertLessEqual(len(raw), 500)
                for block in raw.split(b"\n\n"):
                    fields = dict(line.split(b": ", 1) for line in block.splitlines() if b": " in line)
                    if fields.get(b"event") == b"merlin":
                        event = json.loads(fields[b"data"])
                        self.assertGreater(event["ordinal"], cursor)
                        cursor = event["ordinal"]
                        seen.append(event)
                    elif fields.get(b"event") == b"snapshot":
                        terminal_snapshot = True
                if terminal_snapshot:
                    break
        self.assertTrue(terminal_snapshot)
        self.assertEqual(seen, self.server.app.store.events(rid))

    def test_invalid_streamed_tool_never_executes_or_persists_an_answer(self):
        def script(owner, send):
            send(frame({"tool_calls": [{"index": 0, "id": "bad", "function": {
                "name": "write_file", "arguments": '{"path":"should-not-exist","content":'}}]})
                + ending("tool_calls"))
        _, rid = self.fixture_run(script)
        _, response = self.stream(rid)
        self.remaining(response)
        done = self.request("GET", "/api/runs/" + rid)[1]
        self.assertEqual(done["run"]["status"], "failed")
        self.assertNotIn("tool_started", [e["type"] for e in done["run"]["events"]])
        self.assertFalse((self.server.app.workspace / "should-not-exist").exists())
        self.assertEqual(len(done["conversation"]["messages"]), 1)

    def test_streamed_tool_cycle_separates_stage_text_from_authoritative_answer(self):
        def script(owner, send):
            if len(owner.requests) == 1:
                send(frame({"content": "Inspecting workspace."}))
                send(frame({"tool_calls": [{"index": 0, "id": "list-once", "function": {
                    "name": "list_files", "arguments": '{"path":"."}'}}]}) + ending("tool_calls"))
            else:
                send(frame({"content": "Inspected "}) + frame({"content": "the workspace."}) + ending())
        fixture, rid = self.fixture_run(script)
        _, response = self.stream(rid)
        self.remaining(response)
        done = self.request("GET", "/api/runs/" + rid)[1]
        self.assertEqual(done["run"]["status"], "completed")
        self.assertEqual(done["conversation"]["messages"][-1]["content"], "Inspected the workspace.")
        responses = [e for e in done["run"]["events"] if e["type"] == "model_response"]
        self.assertEqual([(e["step"], e["tool_call_count"]) for e in responses], [(1, 1), (2, 0)])
        self.assertEqual(len(fixture.requests), 2)
        self.assertTrue(any(m["role"] == "tool" for m in fixture.requests[-1]["messages"]))
        self.assertEqual(len([e for e in done["run"]["events"] if e["type"] == "tool_started"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
