"""Studio integration tests; local model fixtures are not inference qualification."""
from __future__ import annotations

import concurrent.futures
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))
from storage import Store
from model import LocalModel, ModelError, endpoint_parts
from tools import ToolSet, MAX_FILE


SETTINGS = {
    "model_url": "", "model_id": "fixture", "network_enabled": False,
    "python_enabled": True, "desktop_enabled": False,
}


class FixtureHTTP:
    """A real TCP server whose content is deliberately synthetic."""
    def __init__(self, responder):
        self.requests = []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                self.respond()
            def do_POST(self):
                self.respond()
            def respond(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                owner.requests.append((self.command, self.path, dict(self.headers), body))
                status, headers, payload = responder(self.command, self.path, body)
                if not isinstance(payload, bytes):
                    payload = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                try:
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.server.server_port)
    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.store = Store(self.root)

    def test_completed_conversation_and_settings_survive_restart(self):
        conversation = self.store.create_conversation()
        run_id = self.store.start_run(conversation["id"], "Remember the test result")
        self.store.finish(run_id, "The fixture result is 42")
        self.store.save_settings(SETTINGS)
        reopened = Store(self.root)
        self.assertEqual(reopened.recover_interrupted(), [])
        self.assertEqual([m["content"] for m in reopened.conversation(conversation["id"])["messages"]],
                         ["Remember the test result", "The fixture result is 42"])
        self.assertEqual(reopened.settings(), SETTINGS)

    def test_restart_interrupts_pending_action_without_replaying_it(self):
        conversation = self.store.create_conversation()
        run_id = self.store.start_run(conversation["id"], "Run the script")
        approval_id = self.store.request_approval(run_id, "run_python", {"path": "job.py"})
        reopened = Store(self.root)
        self.assertEqual(reopened.recover_interrupted(), [run_id])
        run = reopened.run(run_id)
        self.assertEqual(run["status"], "interrupted")
        self.assertIsNone(run["pending_approval"])
        self.assertEqual(reopened.recover_interrupted(), [])
        with self.assertRaises(ValueError):
            reopened.approve(run_id, approval_id, True)
        self.assertEqual(len(reopened.conversation(conversation["id"])["messages"]), 1)

    def test_one_active_run_is_enforced_across_store_instances(self):
        cid = self.store.create_conversation()["id"]
        another = Store(self.root)
        barrier = threading.Barrier(2)
        def start(store):
            barrier.wait(timeout=2)
            try:
                return ("started", store.start_run(cid, "concurrent request"))
            except ValueError:
                return ("rejected", None)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(start, [self.store, another]))
        self.assertEqual(sorted(kind for kind, _ in outcomes), ["rejected", "started"])
        self.assertEqual(len(self.store.conversation(cid)["messages"]), 1)

    def test_exact_approval_identity_and_no_duplicate_decision(self):
        cid = self.store.create_conversation()["id"]
        run_id = self.store.start_run(cid, "Approve exactly one action")
        aid = self.store.request_approval(run_id, "run_python", {"path": "a.py"})
        for wrong in ("wrong", "", run_id):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                self.store.approve(run_id, wrong, True)
        with self.assertRaises(ValueError):
            self.store.approve(run_id, aid, "true")
        self.store.approve(run_id, aid, True)
        self.assertTrue(self.store.approval_answer(run_id, aid))
        self.assertIsNone(self.store.approval_answer(run_id, aid))
        with self.assertRaises(ValueError):
            self.store.approve(run_id, aid, True)

    def test_terminal_state_prevents_late_answer_and_duplicate_finish(self):
        cid = self.store.create_conversation()["id"]
        run_id = self.store.start_run(cid, "Cancel this request")
        aid = self.store.request_approval(run_id, "run_python", {"path": "a.py"})
        self.assertTrue(self.store.finish(run_id, status="cancelled"))
        self.assertFalse(self.store.finish(run_id, "Late model reply"))
        with self.assertRaises(ValueError):
            self.store.approve(run_id, aid, True)
        self.assertEqual(len(self.store.conversation(cid)["messages"]), 1)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.store = Store(self.root / "data")
        self.tools = ToolSet(self.root / "workspace", self.store, dict(SETTINGS))

    def run_script(self, cancelled=lambda: False):
        arguments = {"path": "job.py"}
        return self.tools.execute("run_python", arguments, "run1", cancelled=cancelled, approved=True,
                                  approval_binding=self.tools.approval_details("run_python", arguments))

    def test_write_read_and_immutable_backup_survive_later_edits(self):
        one = self.tools.execute("write_file", {"path": "notes/a.txt", "content": "first"}, "run1")
        two = self.tools.execute("write_file", {"path": "notes/a.txt", "content": "second"}, "run1")
        three = self.tools.execute("write_file", {"path": "notes/a.txt", "content": "third"}, "run1")
        self.assertEqual(self.tools.execute("read_file", {"path": "notes/a.txt"}, "run1")["content"], "third")
        registry = Store(self.root / "data").registry
        for ref, expected in ((one["artifact_ref"], b"first"), (two["previous_artifact_ref"], b"first"),
                              (three["previous_artifact_ref"], b"second")):
            self.assertEqual(registry.read_artifact_ref(ref)["content"], expected)
        self.assertEqual(list((self.tools.workspace / "notes").glob(".merlin-*")), [])

    def test_traversal_absolute_and_symlinks_rejected(self):
        outside = self.root / "private.txt"
        outside.write_text("private")
        for name in ("../private.txt", str(outside), "a/../../private.txt", "bad\0path"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.tools.execute("read_file", {"path": name}, "run1")
        if hasattr(os, "symlink"):
            try:
                (self.tools.workspace / "link").symlink_to(outside)
                (self.tools.workspace / "dirlink").symlink_to(self.root, target_is_directory=True)
            except OSError:
                self.skipTest("This host does not permit symlinks")
            for name in ("link", "dirlink/private.txt"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    self.tools.execute("read_file", {"path": name}, "run1")
            self.assertEqual(outside.read_text(), "private")

    def test_oversized_write_preserves_existing_content(self):
        p = self.tools.workspace / "keep.txt"
        p.write_text("keep")
        with self.assertRaises(ValueError):
            self.tools.execute("write_file", {"path": "keep.txt", "content": "x" * (MAX_FILE + 1)}, "run1")
        self.assertEqual(p.read_text(), "keep")

    def test_failed_atomic_replace_preserves_file_and_cleans_temporary(self):
        p = self.tools.workspace / "keep.txt"
        p.write_text("keep")
        with patch("tools.os.replace", side_effect=OSError("injected replace failure")):
            with self.assertRaises(OSError):
                self.tools.execute("write_file", {"path": "keep.txt", "content": "new"}, "run1")
        self.assertEqual(p.read_text(), "keep")
        self.assertEqual(list(self.tools.workspace.glob(".merlin-*")), [])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO control")
    def test_fifo_read_and_backup_reject_with_external_deadline(self):
        os.mkfifo(self.tools.workspace / "pipe")
        code = '''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from storage import Store
from tools import ToolSet
root=Path(sys.argv[2])
tools=ToolSet(root/'workspace',Store(root/'data'),{'python_enabled':False,'network_enabled':False,'desktop_enabled':False})
for name in ('read_file','write_file'):
    arguments={'path':'pipe'}
    if name=='write_file': arguments['content']='must not replace a pipe'
    try:
        tools.execute(name,arguments,'fifo-regression')
    except ValueError:
        print(name+' rejected')
    else:
        raise SystemExit('FIFO unexpectedly accepted')
'''
        result = subprocess.run([sys.executable, "-I", "-c", code, str(STUDIO), str(self.root)],
                                capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["read_file rejected", "write_file rejected"])

    def test_disabled_and_unapproved_tools_do_not_execute(self):
        (self.tools.workspace / "job.py").write_text("from pathlib import Path\nPath('should-not-exist').write_text('bad')\n")
        with self.assertRaises(PermissionError):
            self.tools.execute("run_python", {"path": "job.py"}, "run1")
        with self.assertRaises(ValueError):
            self.tools.execute("fetch_url", {"url": "https://example.org"}, "run1")
        self.assertFalse((self.tools.workspace / "should-not-exist").exists())

    def test_approved_worker_does_not_write_bytecode_in_writable_workspace(self):
        # Regression for tight RLIMIT_FSIZE and shared cache poisoning. The
        # workspace is writable: a parent-only read-only CI mount is not enough.
        module = self.tools.workspace / "cache_probe.py"
        module.write_text("VALUE = 42\\n")
        (self.tools.workspace / "job.py").write_text(
            "import os,sys\\nsys.path.insert(0, os.getcwd())\\n"
            "import cache_probe\\nprint(cache_probe.VALUE)\\n")
        result = self.run_script()
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertEqual(result["stdout"].strip(), "42")
        self.assertEqual(list(self.tools.workspace.rglob("*.pyc")), [])

    def test_approved_python_runs_and_does_not_inherit_credential_variables(self):
        (self.tools.workspace / "job.py").write_text("import os\nprint(6*7)\nprint(os.environ.get('MERLIN_TEST_SECRET','absent'))\n")
        with patch.dict(os.environ, {"MERLIN_TEST_SECRET": "credential-must-not-pass"}):
            result = self.run_script()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["stdout"].splitlines(), ["42", "absent"])
        self.assertEqual(result["termination"], "completed")
        self.assertFalse(result["os_sandbox"])

    def test_cancel_stops_actual_running_python(self):
        marker = self.tools.workspace / "started.txt"
        (self.tools.workspace / "job.py").write_text("from pathlib import Path\nimport time\nPath('started.txt').write_text('started')\ntime.sleep(60)\nPath('completed.txt').write_text('bad')\n")
        began = time.monotonic()
        result = self.run_script(cancelled=marker.exists)
        self.assertEqual(result["termination"], "cancelled")
        self.assertLess(time.monotonic() - began, 3)
        self.assertFalse((self.tools.workspace / "completed.txt").exists())

    def test_python_output_is_bounded(self):
        (self.tools.workspace / "job.py").write_text("print('x'*70000)\n")
        result = self.run_script()
        self.assertEqual(len(result["stdout"].encode()), 65536)
        self.assertTrue(result["truncated"])

    def test_python_real_deadline_stops_sleeping_worker(self):
        (self.tools.workspace / "job.py").write_text("import time\ntime.sleep(60)\n")
        began = time.monotonic()
        result = self.run_script()
        elapsed = time.monotonic() - began
        self.assertEqual(result["termination"], "timeout")
        self.assertGreaterEqual(elapsed, 14)
        self.assertLess(elapsed, 20)

    def test_script_approval_rejects_changed_source_before_execution(self):
        script = self.tools.workspace / "job.py"
        script.write_text("print('approved source')\n")
        arguments = {"path": "job.py"}
        binding = self.tools.approval_details("run_python", arguments)
        script.write_text("from pathlib import Path\nPath('unapproved-action').write_text('bad')\n")
        with self.assertRaises(PermissionError):
            self.tools.execute("run_python", arguments, "run1", approved=True, approval_binding=binding)
        self.assertFalse((self.tools.workspace / "unapproved-action").exists())


class LocalModelTests(unittest.TestCase):
    def fixture(self, responder):
        fixture = FixtureHTTP(responder)
        self.addCleanup(fixture.close)
        return fixture

    def test_endpoint_rejects_external_credentials_and_wrong_paths(self):
        bad = ("https://127.0.0.1:1234/v1", "http://example.org/v1", "http://user:pass@127.0.0.1/v1",
               "http://127.0.0.1:1234/v1?secret=x", "http://127.0.0.1:1234/internal", "http://127.0.0.1:0/v1")
        for endpoint in bad:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                endpoint_parts(endpoint)
        self.assertEqual(endpoint_parts("http://localhost:1234/v1"), ("127.0.0.1", 1234, "/v1/chat/completions"))

    def test_live_model_protocol_ignores_environment_proxy(self):
        trap = self.fixture(lambda *args: (500, {}, {}))
        upstream = self.fixture(lambda method, path, body: (200, {}, {"data": [{"id": "fixture-model"}]}
            if method == "GET" else {"choices": [{"message": {"content": "fixture reply"}}]}))
        model = LocalModel({**SETTINGS, "model_url": upstream.base + "/v1"})
        with patch.dict(os.environ, {"HTTP_PROXY": trap.base, "http_proxy": trap.base, "ALL_PROXY": trap.base, "NO_PROXY": "", "no_proxy": ""}):
            self.assertTrue(model.probe()["reachable"])
            self.assertEqual(model.complete([{"role": "user", "content": "test"}], [])["content"], "fixture reply")
        self.assertEqual(trap.requests, [])
        self.assertEqual([r[1] for r in upstream.requests], ["/v1/models", "/v1/chat/completions"])

    def test_live_model_redirect_is_never_followed(self):
        trap = self.fixture(lambda *args: (200, {}, {"secret": "not requested"}))
        upstream = self.fixture(lambda *args: (302, {"Location": trap.base + "/capture"}, b""))
        model = LocalModel({**SETTINGS, "model_url": upstream.base + "/v1"})
        with self.assertRaises(ModelError):
            model.complete([{"role": "user", "content": "test"}], [])
        self.assertEqual(trap.requests, [])

    def test_malformed_model_messages_and_duplicate_calls_rejected(self):
        call = {"id": "same", "function": {"name": "read_file", "arguments": '{"path":"a"}'}}
        messages = (None, [], {"content": 5}, {"tool_calls": {}}, {"tool_calls": [call, call]},
                    {"tool_calls": [{"id": "one", "function": {"name": "read_file", "arguments": "[]"}}]})
        for message in messages:
            model = LocalModel({**SETTINGS, "model_url": "http://127.0.0.1:1234/v1"},
                               transport=lambda *args: {"choices": [{"message": message}]})
            with self.subTest(message=message), self.assertRaises(ModelError):
                model.complete([], [])

    def test_model_total_deadline_stops_slow_response_body(self):
        class Slow(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                payload = b'{"data":[]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                for byte in payload:
                    try:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        break
                    time.sleep(0.04)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        model = LocalModel({**SETTINGS, "model_url": "http://127.0.0.1:" + str(server.server_port) + "/v1"})
        try:
            started = time.monotonic()
            with self.assertRaises(ModelError):
                model._request("GET", "/v1/models", timeout=0.1)
            self.assertLess(time.monotonic() - started, 0.35)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class StudioHTTPTests(unittest.TestCase):
    """Exercise the real local HTTP boundary and durable agent/tool state."""
    def setUp(self):
        import server
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.data = Path(self.folder.name) / "data"
        self.factory = None
        self.server_module = server
        self.start_server()
        self.addCleanup(self.stop_server)

    def start_server(self):
        self.server = self.server_module.create_server(data_dir=self.data, model_factory=self.factory, start_bundled=False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        status, result = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.token = result["session_token"]

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None

    def request(self, method, path, value=None, *, headers=None, authenticated=True, raw=None):
        supplied = dict(headers or {})
        if method == "POST":
            supplied.setdefault("Content-Type", "application/json")
            if authenticated:
                supplied.setdefault("X-Merlin-Token", self.token)
            payload = raw if raw is not None else json.dumps({} if value is None else value, ensure_ascii=False).encode()
        else:
            payload = raw
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=payload, headers=supplied)
            response = connection.getresponse()
            data = response.read()
            return response.status, json.loads(data) if "application/json" in response.getheader("Content-Type", "") else data.decode()
        finally:
            connection.close()

    def conversation(self):
        status, value = self.request("POST", "/api/conversations")
        self.assertEqual(status, 201, value)
        return value["conversation"]["id"]

    def start_run(self, cid, message):
        status, value = self.request("POST", "/api/chat", {"conversation_id": cid, "message": message})
        self.assertEqual(status, 202, value)
        return value["run_id"]

    def wait_run(self, rid, statuses=("completed", "failed", "cancelled", "waiting_approval"), timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status, value = self.request("GET", "/api/runs/" + rid)
            self.assertEqual(status, 200, value)
            if value["run"]["status"] in statuses:
                return value
            time.sleep(0.02)
        self.fail("Request did not reach a terminal or approval state within the test budget")

    def write(self, name, content):
        status, result = self.request("POST", "/api/tool", {"tool": "write_file", "args": {"path": name, "content": content}})
        self.assertEqual(status, 200, result)
        return result["result"]

    def test_offline_command_and_artifact_restore_after_server_restart(self):
        cid = self.conversation()
        rid = self.start_run(cid, "/write notes/a.txt\nretained offline content")
        result = self.wait_run(rid)
        self.assertEqual(result["run"]["status"], "completed", result)
        artifacts = [e["result"]["artifact_ref"] for e in result["run"]["events"] if e["type"] == "tool_result"]
        self.assertEqual(len(artifacts), 1)
        old_token = self.token
        self.stop_server()
        self.start_server()
        self.assertNotEqual(self.token, old_token)
        status, conversation = self.request("GET", "/api/conversations/" + cid)
        self.assertEqual(status, 200)
        self.assertEqual(len(conversation["conversation"]["messages"]), 2)
        self.assertEqual((self.server.app.workspace / "notes/a.txt").read_text(), "retained offline content")
        self.assertEqual(self.server.app.store.registry.read_artifact_ref(artifacts[0])["content"], b"retained offline content")
        status, _ = self.request("POST", "/api/conversations", headers={"X-Merlin-Token": old_token})
        self.assertEqual(status, 403)

    def test_large_utf8_read_retains_full_result_with_bounded_event_preview(self):
        content = "\u732b" * 70000
        self.assertEqual(len(content.encode()), 210000)
        self.write("large.txt", content)
        done = self.wait_run(self.start_run(self.conversation(), "/read large.txt"))
        self.assertEqual(done["run"]["status"], "completed", done["run"].get("error"))
        events = [event for event in done["run"]["events"] if event["type"] == "tool_result"]
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertTrue(event["truncated"])
        self.assertLess(len(json.dumps(event, ensure_ascii=False).encode()), 160000)
        complete = json.loads(self.server.app.store.registry.read_artifact_ref(event["full_event_artifact_ref"])["content"])
        self.assertEqual(complete["result"]["content"], content)
        self.assertEqual(done["conversation"]["messages"][-1]["content"], content)
        self.assertNotIn("tool_error", [item["type"] for item in done["run"]["events"]])

    def test_live_host_origin_token_contenttype_and_body_guards(self):
        cases = [
            ({"Host": "attacker.example"}, 403),
            ({"Origin": "https://attacker.example"}, 403),
            ({"Sec-Fetch-Site": "cross-site"}, 403),
            ({"X-Merlin-Token": "wrong"}, 403),
            ({"Content-Type": "text/plain"}, 400),
            ({"Content-Length": str(self.server_module.MAX_BODY + 1)}, 400),
        ]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                status, _ = self.request("POST", "/api/conversations", headers=headers)
                self.assertEqual(status, expected)
        status, _ = self.request("POST", "/api/conversations", authenticated=False)
        self.assertEqual(status, 403)
        for payload in (b"[]", b'{"title":NaN}', b"{broken"):
            with self.subTest(payload=payload):
                status, _ = self.request("POST", "/api/conversations", raw=payload)
                self.assertEqual(status, 400)
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"}):
            status, _ = self.request("GET", "/api/status", headers=headers)
            self.assertEqual(status, 403)
        self.assertEqual(self.server.app.store.conversations(), [])

    def test_duplicate_content_length_rejected_without_mutation(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.putrequest("POST", "/api/conversations")
            connection.putheader("X-Merlin-Token", self.token)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", "2")
            connection.putheader("Content-Length", "2")
            connection.endheaders(b"{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            connection.close()
        self.assertEqual(self.server.app.store.conversations(), [])

    def test_manual_endpoint_cannot_execute_python(self):
        status, _ = self.request("POST", "/api/tool", {"tool": "run_python", "args": {"path": "a.py"}})
        self.assertEqual(status, 403)

    def test_approved_python_runs_once_and_is_not_replayed_after_restart(self):
        self.write("job.py", "from pathlib import Path\np=Path('count.txt')\np.write_text((p.read_text() if p.exists() else '')+'x')\nprint(6*7)\n")
        cid = self.conversation()
        rid = self.start_run(cid, "/python job.py")
        waiting = self.wait_run(rid)
        self.assertEqual(waiting["run"]["status"], "waiting_approval")
        approval = waiting["run"]["pending_approval"]
        self.assertIn("script_sha256", approval["arguments"])
        status, _ = self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": approval["id"], "approved": True})
        self.assertEqual(status, 200)
        status, _ = self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": approval["id"], "approved": True})
        self.assertEqual(status, 400)
        completed = self.wait_run(rid, statuses=("completed", "failed"))
        self.assertEqual(completed["run"]["status"], "completed", completed)
        results = [e["result"] for e in completed["run"]["events"] if e["type"] == "tool_result"]
        self.assertEqual(results[0]["stdout"].strip(), "42")
        self.assertEqual((self.server.app.workspace / "count.txt").read_text(), "x")
        self.stop_server()
        self.start_server()
        self.assertEqual((self.server.app.workspace / "count.txt").read_text(), "x")

    def test_modifying_script_while_waiting_invalidates_exact_approval(self):
        self.write("job.py", "print('original')\n")
        rid = self.start_run(self.conversation(), "/python job.py")
        waiting = self.wait_run(rid)
        approval = waiting["run"]["pending_approval"]
        self.write("job.py", "from pathlib import Path\nPath('unapproved.txt').write_text('bad')\n")
        status, _ = self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": approval["id"], "approved": True})
        self.assertEqual(status, 200)
        done = self.wait_run(rid, statuses=("completed", "failed"))
        self.assertFalse((self.server.app.workspace / "unapproved.txt").exists())
        errors = [e for e in done["run"]["events"] if e["type"] == "tool_error"]
        self.assertEqual(len(errors), 1, done)
        self.assertEqual(errors[0]["result"]["error_type"], "PermissionError")

    def test_cancelled_approval_cannot_run_later(self):
        self.write("job.py", "from pathlib import Path\nPath('unapproved.txt').write_text('bad')\n")
        rid = self.start_run(self.conversation(), "/python job.py")
        waiting = self.wait_run(rid)
        aid = waiting["run"]["pending_approval"]["id"]
        self.assertEqual(self.request("POST", "/api/runs/" + rid + "/cancel")[0], 200)
        self.assertEqual(self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": aid, "approved": True})[0], 400)
        self.assertEqual(self.wait_run(rid)["run"]["status"], "cancelled")
        self.assertFalse((self.server.app.workspace / "unapproved.txt").exists())

    def test_declined_approval_finishes_without_execution(self):
        self.write("job.py", "from pathlib import Path\nPath('unapproved.txt').write_text('bad')\n")
        rid = self.start_run(self.conversation(), "/python job.py")
        aid = self.wait_run(rid)["run"]["pending_approval"]["id"]
        self.assertEqual(self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": aid, "approved": False})[0], 200)
        done = self.wait_run(rid, statuses=("completed", "failed"))
        self.assertEqual(done["run"]["status"], "completed")
        self.assertIn("tool_denied", [e["type"] for e in done["run"]["events"]])
        self.assertFalse((self.server.app.workspace / "unapproved.txt").exists())

    def test_conversation_and_global_worker_limits_hold_during_approval(self):
        self.write("job.py", "print('approved only')\n")
        conversations = [self.conversation() for _ in range(5)]
        active = []
        try:
            first = self.start_run(conversations[0], "/python job.py")
            active.append(first)
            self.assertEqual(self.wait_run(first)["run"]["status"], "waiting_approval")
            status, _ = self.request("POST", "/api/chat", {"conversation_id": conversations[0], "message": "second request"})
            self.assertEqual(status, 400)
            for cid in conversations[1:4]:
                rid = self.start_run(cid, "/python job.py")
                active.append(rid)
                self.assertEqual(self.wait_run(rid)["run"]["status"], "waiting_approval")
            status, _ = self.request("POST", "/api/chat", {"conversation_id": conversations[4], "message": "fifth request"})
            self.assertEqual(status, 400)
            self.assertEqual(len(self.server.app.store.conversation(conversations[0])["messages"]), 1)
            self.assertEqual(self.server.app.store.conversation(conversations[4])["messages"], [])
        finally:
            for rid in active:
                self.request("POST", "/api/runs/" + rid + "/cancel")

    def test_disabled_python_is_rechecked_after_approval_wait(self):
        self.write("job.py", "from pathlib import Path\nPath('unapproved.txt').write_text('bad')\n")
        rid = self.start_run(self.conversation(), "/python job.py")
        aid = self.wait_run(rid)["run"]["pending_approval"]["id"]
        self.assertEqual(self.request("POST", "/api/settings", {"python_enabled": False})[0], 200)
        self.assertEqual(self.request("POST", "/api/runs/" + rid + "/approve", {"approval_id": aid, "approved": True})[0], 200)
        done = self.wait_run(rid, statuses=("completed", "failed"))
        self.assertFalse((self.server.app.workspace / "unapproved.txt").exists())
        self.assertIn("tool_error", [e["type"] for e in done["run"]["events"]])

    def test_local_model_fixture_selects_tool_then_observes_result(self):
        def respond(method, path, body):
            payload = json.loads(body)
            if any(m["role"] == "tool" for m in payload["messages"]):
                message = {"content": "Fixture inspected the saved artifact result."}
            else:
                message = {"content": "Fixture is saving the requested file.", "tool_calls": [{
                    "id": "write-once", "type": "function", "function": {"name": "write_file", "arguments": json.dumps({"path": "fixture.txt", "content": "synthetic model tool loop"})}}]}
            return 200, {}, {"choices": [{"message": message}]}
        fixture = FixtureHTTP(respond)
        self.addCleanup(fixture.close)
        self.assertEqual(self.request("POST", "/api/settings", {"model_url": fixture.base + "/v1", "model_id": "synthetic-fixture"})[0], 200)
        rid = self.start_run(self.conversation(), "Save a file and inspect the result")
        done = self.wait_run(rid)
        self.assertEqual(done["run"]["status"], "completed", done)
        self.assertEqual(len(fixture.requests), 2)
        self.assertEqual((self.server.app.workspace / "fixture.txt").read_text(), "synthetic model tool loop")
        self.assertEqual(done["conversation"]["messages"][-1]["content"], "Fixture inspected the saved artifact result.")
        result_events = [e for e in done["run"]["events"] if e["type"] == "tool_result"]
        self.assertEqual(len(result_events), 1)
        self.assertEqual(self.server.app.store.registry.read_artifact_ref(result_events[0]["result"]["artifact_ref"])["content"], b"synthetic model tool loop")

    def test_model_cannot_reuse_tool_identity_to_repeat_write(self):
        reply = {"choices": [{"message": {"tool_calls": [{"id": "same", "type": "function", "function": {
            "name": "write_file", "arguments": json.dumps({"path": "once.txt", "content": "first"})}}]}}]}
        fixture = FixtureHTTP(lambda *args: (200, {}, reply))
        self.addCleanup(fixture.close)
        self.assertEqual(self.request("POST", "/api/settings", {"model_url": fixture.base + "/v1"})[0], 200)
        done = self.wait_run(self.start_run(self.conversation(), "Use a tool"))
        self.assertEqual(done["run"]["status"], "failed")
        self.assertIn("reused", done["run"]["error"])
        self.assertEqual(len([e for e in done["run"]["events"] if e["type"] == "tool_started"]), 1)

    def test_non_loopback_server_binding_is_rejected(self):
        with self.assertRaises(ValueError):
            self.server_module.create_server(host="0.0.0.0", data_dir=self.data)


if __name__ == "__main__":
    unittest.main()
