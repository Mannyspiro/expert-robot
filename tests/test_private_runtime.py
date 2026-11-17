import ast
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge, canonical, digest
from dot_ai_os.private_runtime import (MAX_CALL_BYTES, PrivateDispatcher,
    PrivateHostConfigurationError, PrivateReadOnlyRegistry, PrivateUnixServer,
    RegisteredTool, call_socket, load_configuration, _receive)


class PrivateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "demo-state"
        self.registry = MerlinRegistry(self.state)
        self.bridge = DotContextBridge(self.registry)
        self.bridge.initialize()
        self.source_ref = self.source("merlin", "Engineering demo: box width 2 and height 3; scale by 2.")
        self.other_ref = self.source("morgana-cace", "Excluded synthetic namespace fixture.")
        self.bridge.save_handoff("demo-current", summary="Continue the bounded box simulation",
                                 next_action="Compare transform invariants", source_refs=[self.source_ref])
        self.reader = PrivateReadOnlyRegistry(self.state)
        self.scoped = DotContextBridge(self.reader, namespaces=("merlin",))
        self.uid = os.getuid()
        self.tools = ["health", "context_status", "context_search", "context_fetch", "session_handoff", "rsi_status", "box_simulation"]
        def simulation(args, principal):
            for key in ("width", "height", "scale"):
                value = args[key]
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 10:
                    raise ValueError("invalid bounded geometry parameter")
            return {"area": args["width"] * args["height"] * args["scale"] ** 2,
                    "principal_sha256": digest(principal.encode()), "qualification": False}
        self.plugin = RegisteredTool(simulation, frozenset({"width", "height", "scale"}))
        self.dispatcher = PrivateDispatcher(self.scoped,
            grants={self.uid: {"principal": "unix:reviewed-demo-reader", "tools": self.tools}},
            plugin_tools={"box_simulation": self.plugin})
        self.socket_path = self.root / "private.sock"
        self.server = None
        self.thread = None

    def source(self, namespace, text):
        return self.bridge.ingest(namespace=namespace, source_id="demo-source", title="Engineering fixture",
                                  content=text.encode(), source_url="https://example.org/engineering-demo",
                                  source_version="fixture-v1", epistemic="source_snapshot",
                                  captured_at="2026-11-17T15:00:00Z")["source_ref"]

    def start(self, dispatcher=None):
        try:
            self.server = PrivateUnixServer(self.socket_path, dispatcher or self.dispatcher)
        except PermissionError as exc:
            if exc.errno != 1:
                raise
            self.skipTest("AF_UNIX socket creation blocked by local EPERM; run on the OCI Linux host")
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None

    def request(self, tool="health", arguments=None):
        return {"schema": "merlin-private-call/1", "request_id": "fixture-call-1",
                "tool": tool, "arguments": arguments or {}}

    def call(self, tool="health", arguments=None):
        return call_socket(self.socket_path, self.request(tool, arguments), expected_server_uid=self.uid)

    def raw_call(self, raw, prefix=None):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.socket_path))
            client.sendall(struct.pack("!I", prefix if prefix is not None else len(raw)) + raw)
            client.shutdown(socket.SHUT_WR)
            return json.loads(_receive(client, 65536))

    def test_actual_socket_peer_credentials_and_simulation_roundtrip(self):
        self.start()
        self.assertEqual(stat.S_IMODE(self.socket_path.stat().st_mode), 0o660)
        health = self.call()
        self.assertTrue(health["ok"])
        self.assertEqual(health["result"]["transport"], "unix")
        self.assertFalse(health["result"]["public_listener"])
        simulation = self.call("box_simulation", {"width": 2, "height": 3, "scale": 2})
        self.assertEqual(simulation["result"]["area"], 24)
        self.assertEqual(simulation["result"]["principal_sha256"], digest(b"unix:reviewed-demo-reader"))
        self.assertFalse(simulation["qualification"])

    def test_cli_roundtrip_uses_local_socket_without_mcp_http_dependency(self):
        self.start()
        request = self.request("box_simulation", {"width": 2, "height": 3, "scale": 2})
        result = subprocess.run([sys.executable, "-m", "dot_ai_os.private_runtime", "call",
                                 "--socket", str(self.socket_path), "--server-uid", str(self.uid)],
                                input=canonical(request), capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["area"], 24)
        imports = subprocess.run([sys.executable, "-c",
            "import sys; import dot_ai_os.private_runtime; assert 'mcp' not in sys.modules; assert 'httpx' not in sys.modules"],
            capture_output=True, timeout=5)
        self.assertEqual(imports.returncode, 0, imports.stderr)

    def test_unallowed_uid_is_rejected_before_reading_request(self):
        dispatcher = PrivateDispatcher(self.scoped, grants={self.uid + 1: {"principal": "different-uid", "tools": ["health"]}})
        self.start(dispatcher)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(str(self.socket_path))
            reply = json.loads(_receive(client, 65536))
        self.assertEqual(reply["error"]["code"], "unauthorized_peer")

    def test_request_cannot_spoof_principal_or_invoke_ungranted_tool(self):
        self.start()
        request = self.request()
        request["principal"] = "admin"
        reply = self.raw_call(canonical(request))
        self.assertFalse(reply["ok"])
        self.assertEqual(self.call("job_submit", {"idempotency_key": "one", "request": {}})["error"]["code"], "tool_not_allowed")
        self.assertEqual(self.call("shell", {"command": "anything"})["error"]["code"], "tool_not_allowed")

    def test_context_fetch_respects_namespace_and_exact_source_digest(self):
        self.start()
        result = self.call("context_search", {"query": "Engineering", "namespace": "merlin"})
        self.assertTrue(result["ok"])
        page = self.call("context_fetch", {"source_ref": self.source_ref})
        self.assertIn("Engineering demo", page["result"]["text"])
        denied = self.call("context_fetch", {"source_ref": self.other_ref})
        self.assertFalse(denied["ok"])
        self.assertNotIn("Excluded synthetic", json.dumps(denied))
        tampered = deepcopy(self.source_ref)
        tampered["sha256"] = "f" * 64
        self.assertFalse(self.call("context_fetch", {"source_ref": tampered})["ok"])

    def test_saved_handoff_and_nonexistent_workflow_status_are_read_only(self):
        before = self.reader.db_path.read_bytes()
        self.start()
        handoff = self.call("session_handoff", {"session_id": "demo-current"})
        self.assertEqual(handoff["result"]["handoff"]["next_action"], "Compare transform invariants")
        workflow = self.call("rsi_status", {"session_id": "not-started"})
        self.assertEqual(workflow["result"]["status"], "not_started")
        self.assertEqual(self.reader.db_path.read_bytes(), before)
        with self.assertRaises(PermissionError):
            self.reader.put_artifact("dot-ai-os", "bad", b"bad")

    def test_transport_rejects_oversized_duplicate_nonfinite_and_deep_json(self):
        self.start()
        cases = [
            (b"", MAX_CALL_BYTES + 1),
            (b'{"schema":"merlin-private-call/1","schema":"duplicate"}', None),
            (b'{"value":NaN}', None),
            (b'{"value":' + b'[' * 20 + b'0' + b']' * 20 + b'}', None),
        ]
        for raw, prefix in cases:
            with self.subTest(raw=raw[:40]):
                reply = self.raw_call(raw, prefix)
                self.assertEqual(reply["error"]["code"], "invalid_private_frame")

    def test_argument_and_result_caps_do_not_pass_through_hidden_fields(self):
        self.start()
        self.assertFalse(self.call("box_simulation", {"width": True, "height": 3, "scale": 2})["ok"])
        self.assertFalse(self.call("box_simulation", {"width": 2, "height": 3, "scale": 2, "path": "/etc/shadow"})["ok"])
        self.assertFalse(self.call("context_search", {"query": "Engineering", "budget_bytes": 64000})["ok"])
        big = PrivateDispatcher(self.scoped, grants={self.uid: {"principal": "reader", "tools": ["huge_result"]}},
            plugin_tools={"huge_result": RegisteredTool(lambda args, principal: {"text": "x" * 100},
                                                       frozenset(), max_result_bytes=50)})
        self.assertEqual(big.call(self.uid, self.request("huge_result"))["error"]["code"], "result_exceeds_limit")

    def test_configuration_cannot_import_plugins_or_grant_missing_write_tools(self):
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateDispatcher(self.scoped, grants={self.uid: {"principal": "reader", "tools": ["job_submit"]}})
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateDispatcher(self.scoped, grants={self.uid: {"principal": "reader", "tools": ["*"]}})
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateDispatcher(self.scoped, grants={self.uid: {"principal": "reader", "tools": ["health"]}},
                plugin_tools={"health": self.plugin})
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateDispatcher(self.scoped, grants={self.uid: {"principal": "reader", "tools": ["health"]}},
                plugin_tools={"dangerous": RegisteredTool(lambda args, principal: {}, frozenset(), read_only=False)})

    def test_socket_client_checks_server_uid_and_private_parent(self):
        self.start()
        with self.assertRaises(PrivateHostConfigurationError):
            call_socket(self.socket_path, self.request(), expected_server_uid=self.uid + 1)
        self.root.chmod(0o770)
        try:
            with self.assertRaises(PrivateHostConfigurationError):
                self.call()
        finally:
            self.root.chmod(0o700)

    def test_server_does_not_replace_live_or_non_socket_paths(self):
        self.socket_path.write_text("unrelated")
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateUnixServer(self.socket_path, self.dispatcher)
        self.assertEqual(self.socket_path.read_text(), "unrelated")
        self.socket_path.unlink()
        self.start()
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateUnixServer(self.socket_path, self.dispatcher)

    def test_readonly_registry_rejects_wal_and_operator_config_permissions(self):
        config = self.root / "config.json"
        payload = {"schema": "merlin-private-host/1", "project_id": "dot-ai-os", "namespaces": ["merlin"],
                   "grants": [{"uid": self.uid, "principal": "reader", "tools": ["health"]}]}
        config.write_bytes(canonical(payload))
        config.chmod(0o600)
        self.assertIn(self.uid, load_configuration(config)["grants"])
        config.chmod(0o660)
        with self.assertRaises(PrivateHostConfigurationError):
            load_configuration(config)
        with sqlite3.connect(self.registry.db_path) as db:
            db.execute("PRAGMA journal_mode=WAL")
        with self.assertRaises(PrivateHostConfigurationError):
            PrivateReadOnlyRegistry(self.state)

    def test_new_runtime_parses_under_python_39_grammar(self):
        path = Path(__file__).parents[1] / "python/dot_ai_os/private_runtime.py"
        ast.parse(path.read_text(), feature_version=(3, 9))

    def test_direct_dispatch_real_canonical_reads_and_simulation_without_socket(self):
        before = self.reader.db_path.read_bytes()
        health = self.dispatcher.call(self.uid, self.request())
        self.assertTrue(health["ok"])
        result = self.dispatcher.call(self.uid, self.request("box_simulation", {"width": 2, "height": 3, "scale": 2}))
        self.assertEqual(result["result"]["area"], 24)
        source = self.dispatcher.call(self.uid, self.request("context_fetch", {"source_ref": self.source_ref}))
        self.assertIn("Engineering demo", source["result"]["text"])
        denied = self.dispatcher.call(self.uid, self.request("context_fetch", {"source_ref": self.other_ref}))
        self.assertFalse(denied["ok"])
        self.assertEqual(self.reader.db_path.read_bytes(), before)

    def test_direct_dispatch_uid_scope_schema_and_default_write_denial(self):
        self.assertEqual(self.dispatcher.call(self.uid + 1, self.request())["error"]["code"], "unauthorized_peer")
        request = self.request()
        request["principal"] = "spoofed"
        self.assertFalse(self.dispatcher.call(self.uid, request)["ok"])
        self.assertEqual(self.dispatcher.call(self.uid, self.request("job_submit"))["error"]["code"], "tool_not_allowed")
        result = self.dispatcher.call(self.uid, self.request("box_simulation", {"width": True, "height": 3, "scale": 2}))
        self.assertFalse(result["ok"])

    def test_direct_resume_handoff_and_status_without_writes(self):
        before = self.reader.db_path.read_bytes()
        handoff = self.dispatcher.call(self.uid, self.request("session_handoff", {"session_id": "demo-current"}))
        self.assertEqual(handoff["result"]["handoff"]["session_id"], "demo-current")
        status = self.dispatcher.call(self.uid, self.request("rsi_status", {"session_id": "not-started"}))
        self.assertEqual(status["result"]["status"], "not_started")
        self.assertEqual(self.reader.db_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
