"""Synthetic contract + real Studio orchestration for optional read-only JSON tool bridge.

Model responses here are fixtures; only the separate OCI run qualifies a
model's actual behavior. No network, system process, or external model used.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from engine import Application
from model import LocalModel, _read_only_json_tool_call

DECLARED = [
    {"type": "function", "function": {"name": "read_file"}},
    {"type": "function", "function": {"name": "list_files"}},
    {"type": "function", "function": {"name": "write_file"}},
    {"type": "function", "function": {"name": "fetch_url"}},
    {"type": "function", "function": {"name": "run_python"}},
    {"type": "function", "function": {"name": "desktop_click"}}
]
JSON_CALL = json.dumps({"name": "read_file", "arguments": {"path": "receipt.txt"}})
FENCED_CALL = "```json\n" + json.dumps(
    {"name": "read_file", "arguments": {"path": "receipt.txt"}}, indent=2) + "\n```"


def model_reply(text, *, mode="native", tools=DECLARED):
    responses = {"choices": [{"message": {"content": text}}]}
    model = LocalModel({
        "model_url": "http://127.0.0.1:18772/v1",
        "model_id": "synthetic",
        "tool_compatibility": mode,
    }, transport=lambda *_: responses)
    return model.complete([{"role": "user", "content": "fixture request"}], tools)


class ReadOnlyCompatibilityTests(unittest.TestCase):
    def test_default_mode_keeps_generated_json_as_text(self):
        reply = model_reply(FENCED_CALL)
        self.assertEqual(reply["content"], FENCED_CALL)
        self.assertNotIn("tool_calls", reply)
        self.assertNotIn("_compatibility_adapter", reply)

    def test_opt_in_converts_exact_raw_or_fenced_read_only_calls(self):
        for body in (JSON_CALL, FENCED_CALL):
            with self.subTest(body=body[:16]):
                reply = model_reply(body, mode="read_only_json")
                self.assertEqual(reply["content"], "")
                self.assertEqual(reply["_compatibility_adapter"], "read_only_json")
                self.assertEqual(len(reply["tool_calls"]), 1)
                call = reply["tool_calls"][0]
                self.assertTrue(call["id"].startswith("merlin-readonly-"))
                self.assertEqual(call["function"]["name"], "read_file")
                self.assertEqual(json.loads(call["function"]["arguments"]), {"path": "receipt.txt"})

    def test_read_only_list_files_may_omit_path(self):
        body = '{"name":"list_files","arguments":{}}'
        reply = model_reply(body, mode="read_only_json")
        self.assertEqual(reply["tool_calls"][0]["function"]["name"], "list_files")
        self.assertEqual(json.loads(reply["tool_calls"][0]["function"]["arguments"]), {})

    def test_mutating_and_network_actions_remain_literal_text(self):
        for name, args in (
            ("write_file", {"path": "x", "content": "bad"}),
            ("run_python", {"path": "x.py"}),
            ("fetch_url", {"url": "https://example.org"}),
            ("desktop_click", {"x": 1, "y": 2})
        ):
            with self.subTest(tool=name):
                body = json.dumps({"name": name, "arguments": args})
                reply = model_reply(body, mode="read_only_json")
                self.assertEqual(reply["content"], body)
                self.assertNotIn("tool_calls", reply)

    def test_disallowed_paths_rejected_before_tool_policy(self):
        for bad in ("/etc/passwd", "../secret", "folder/../a", "./receipt.txt",
                    "a//b", "a\\\\b", "", ".", "x "):
            with self.subTest(path=bad):
                body = json.dumps({"name": "read_file", "arguments": {"path": bad}})
                self.assertIsNone(_read_only_json_tool_call(body, DECLARED))

    def test_unambiguous_json_envelope_only(self):
        bad_values = (
            "read the file instead", "Before this call:\n" + JSON_CALL,
            JSON_CALL + "\nmore", "```python\n" + JSON_CALL + "\n```",
            '{"name":"read_file","name":"read_file","arguments":{"path":"receipt.txt"}}',
            '{"name":"read_file","arguments":{"path":"receipt.txt","path":"receipt.txt"}}',
            '{"name":"read_file","arguments":{"path":"receipt.txt"},"extra":true}',
            '{"name":"read_file","arguments":"{\"path\":\"receipt.txt\"}"}',
            '{"name":"read_file","arguments":{"path":42}}',
            '{"name":"read_file","arguments":{"path":"receipt.txt","content":"x"}}',
            JSON_CALL * 1000
        )
        for text in bad_values:
            with self.subTest(body=text[:30]):
                self.assertIsNone(_read_only_json_tool_call(text, DECLARED))

    def test_declared_tool_policy_still_gates_compatibility(self):
        self.assertIsNone(_read_only_json_tool_call(JSON_CALL, []))
        self.assertIsNone(_read_only_json_tool_call(JSON_CALL, [DECLARED[1]]))
        self.assertIsNotNone(_read_only_json_tool_call(JSON_CALL, [DECLARED[0]]))

    def test_native_tool_calls_take_precedence(self):
        native = {"id": "existing", "type": "function",
                  "function": {"name": "read_file",
                               "arguments": '{"path":"native.txt"}'}}
        model = LocalModel({"model_url": "http://127.0.0.1:18772/v1",
                            "tool_compatibility": "read_only_json"},
                           transport=lambda *_: {"choices": [{"message": {
                               "content": JSON_CALL, "tool_calls": [native]}}]})
        reply = model.complete([], DECLARED)
        self.assertEqual(reply["tool_calls"], [native])
        self.assertEqual(reply["content"], JSON_CALL)
        self.assertNotIn("_compatibility_adapter", reply)

    def test_settings_explicit_default_and_invalid_values(self):
        self.assertEqual(Application.validate_settings({})["tool_compatibility"], "native")
        self.assertEqual(Application.validate_settings({
            "tool_compatibility": "read_only_json"})["tool_compatibility"], "read_only_json")
        for invalid in (None, False, True, "", "auto", "write_json", 1, [], {}):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    Application.validate_settings({"tool_compatibility": invalid})

    def test_real_studio_synthetic_file_tool_run_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = "MERLIN_TOOL_" + "f" * 32
            source = ("Fixture verification marker: " + marker + "\n").encode()
            requests = []

            def synthetic_transport(method, path, payload, timeout):
                requests.append(payload)
                if any(msg.get("role") == "tool" for msg in payload["messages"]):
                    tool_message = next(msg for msg in payload["messages"]
                                        if msg.get("role") == "tool")
                    receipt = json.loads(tool_message["content"])
                    self.assertEqual(receipt["sha256"], hashlib.sha256(source).hexdigest())
                    self.assertEqual(receipt["content"], source.decode())
                    return {"choices": [{"message": {"content": marker}}]}
                return {"choices": [{"message": {"content": FENCED_CALL}}]}

            root = Path(tmp)
            app = Application(root, root / "data",
                              model_factory=lambda settings: LocalModel(
                                  settings, transport=synthetic_transport),
                              start_bundled=False)
            try:
                app.save_settings({
                    "model_url": "http://127.0.0.1:18772/v1",
                    "model_id": "synthetic",
                    "max_steps": 2,
                    "network_enabled": False,
                    "python_enabled": False,
                    "desktop_enabled": False,
                    "tool_compatibility": "read_only_json",
                })
                app.tools()
                fixture = app.workspace / "receipt.txt"
                fixture.write_bytes(source)
                conversation = app.store.create_conversation()
                run_id = app.start_run(conversation["id"], "Read receipt.txt")
                with app.threads_lock:
                    thread = app.threads.get(run_id)
                if thread is not None:
                    thread.join(timeout=8)
                finished = app.store.run(run_id)
                self.assertEqual(finished["status"], "completed", finished)
                events = finished["events"]
                adapter = [e for e in events if e["type"] == "model_tool_adapter"]
                self.assertEqual(len(adapter), 1)
                self.assertEqual(adapter[0]["mode"], "read_only_json")
                self.assertEqual(adapter[0]["tool"], "read_file")
                self.assertEqual(len([e for e in events if e["type"] == "tool_started"]), 1)
                self.assertEqual(len([e for e in events if e["type"] == "tool_result"]), 1)
                self.assertEqual(len(requests), 2)
                self.assertIn("tools", requests[0])
                self.assertEqual(
                    {tool["function"]["name"] for tool in requests[0]["tools"]},
                    {"read_file", "list_files"},
                )
                self.assertNotIn("tools", requests[1])
                self.assertTrue(any(
                    message.get("role") == "user" and "has finished" in message.get("content", "")
                    for message in requests[1]["messages"]
                ))
                fixed_handoffs = [
                    message["content"] for message in requests[1]["messages"]
                    if message.get("role") == "user" and "has finished" in message.get("content", "")
                ]
                self.assertEqual(len(fixed_handoffs), 1)
                self.assertNotIn("MERLIN_TOOL_", fixed_handoffs[0])
                self.assertIn("no prefix", fixed_handoffs[0])
                self.assertIn("no suffix", fixed_handoffs[0])
                self.assertIn("untrusted data", fixed_handoffs[0])
                self.assertEqual(fixture.read_bytes(), source)
                history = app.store.conversation(conversation["id"])["messages"]
                self.assertEqual(history[-1]["content"], marker)
                self.assertEqual(len(history), 2)
            finally:
                app.close()

    def test_repeated_json_tool_envelope_does_not_execute_twice(self):
        # A weak model may repeat the same call; the fallback must never
        # replay a read because the first response did not satisfy it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payloads = []
            def synthetic_transport(method, path, payload, timeout):
                payloads.append(payload)
                return {"choices": [{"message": {"content": FENCED_CALL}}]}
            app = Application(root, root / "data",
                              model_factory=lambda settings: LocalModel(
                                  settings, transport=synthetic_transport),
                              start_bundled=False)
            try:
                app.save_settings({
                    "model_url": "http://127.0.0.1:18772/v1",
                    "model_id": "synthetic", "max_steps": 3,
                    "network_enabled": False, "python_enabled": False,
                    "desktop_enabled": False, "tool_compatibility": "read_only_json",
                })
                app.tools()  # Creates the workspace, as the real service does.
                (app.workspace / "receipt.txt").write_text("fixture read once", encoding="utf-8")
                cid = app.store.create_conversation()["id"]
                rid = app.start_run(cid, "Read receipt.txt")
                with app.threads_lock:
                    thread = app.threads.get(rid)
                if thread is not None:
                    thread.join(timeout=8)
                state = app.store.run(rid)
                self.assertEqual(state["status"], "completed", state)
                self.assertEqual(len([e for e in state["events"] if e["type"] == "model_tool_adapter"]), 1)
                self.assertEqual(len([e for e in state["events"] if e["type"] == "tool_started"]), 1)
                self.assertEqual(len([e for e in state["events"] if e["type"] == "tool_result"]), 1)
                self.assertEqual(len(payloads), 2)
                self.assertIn("tools", payloads[0])
                self.assertNotIn("tools", payloads[1])
                self.assertEqual(app.store.conversation(cid)["messages"][-1]["content"], FENCED_CALL)
                self.assertEqual((app.workspace / "receipt.txt").read_text(), "fixture read once")
            finally:
                app.close()

    def test_native_write_call_is_denied_in_read_only_compat_mode(self):
        # A model must not bypass the fallback's read-only authority by using
        # a real provider tool_calls object instead of textual JSON.
        with tempfile.TemporaryDirectory() as tmp:
            observed = []
            result = {"choices": [{"message": {"tool_calls": [{
                "id": "malicious-native-write",
                "type": "function",
                "function": {"name": "write_file",
                             "arguments": '{"path":"should-not-exist.txt","content":"bad"}'}
            }]}}]}
            def transport(method, path, payload, timeout):
                observed.append(payload)
                return result
            root = Path(tmp)
            app = Application(root, root / "data",
                              model_factory=lambda settings: LocalModel(
                                  settings, transport=transport),
                              start_bundled=False)
            try:
                app.save_settings({
                    "model_url": "http://127.0.0.1:18772/v1",
                    "model_id": "synthetic", "max_steps": 2,
                    "network_enabled": False, "python_enabled": False,
                    "desktop_enabled": False, "tool_compatibility": "read_only_json",
                })
                cid = app.store.create_conversation()["id"]
                rid = app.start_run(cid, "Read a file only")
                with app.threads_lock:
                    thread = app.threads.get(rid)
                if thread is not None:
                    thread.join(timeout=8)
                run = app.store.run(rid)
                self.assertEqual(run["status"], "failed", run)
                self.assertIn("forbids this model-selected tool", run["error"])
                self.assertFalse((app.workspace / "should-not-exist.txt").exists())
                self.assertEqual(len([e for e in run["events"] if e["type"] == "tool_started"]), 0)
                self.assertEqual({x["function"]["name"] for x in observed[0]["tools"]},
                                 {"read_file", "list_files"})
            finally:
                app.close()

    def test_explicit_user_write_still_works_with_model_compat_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = Application(root, root / "data", start_bundled=False)
            try:
                app.save_settings({
                    "tool_compatibility": "read_only_json",
                    "network_enabled": False, "python_enabled": False,
                    "desktop_enabled": False
                })
                cid = app.store.create_conversation()["id"]
                rid = app.start_run(cid, "/write operator-owned.txt\nexplicit user action")
                with app.threads_lock:
                    thread = app.threads.get(rid)
                if thread is not None:
                    thread.join(timeout=8)
                self.assertEqual(app.store.run(rid)["status"], "completed", app.store.run(rid))
                self.assertEqual((app.workspace / "operator-owned.txt").read_text(),
                                 "explicit user action")
            finally:
                app.close()

    def test_read_only_authority_not_expanded_by_mid_run_setting_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = Application(root, root / "data", start_bundled=False)
            try:
                app.save_settings({"tool_compatibility": "read_only_json"})
                cid = app.store.create_conversation()["id"]
                rid = app.store.start_run(cid, "Only read workspace")
                # The user may change global settings while the original model
                # turn is still running; that cannot grant new authority to it.
                app.save_settings({"tool_compatibility": "native"})
                with self.assertRaisesRegex(ValueError, "forbids this model-selected tool"):
                    app._tool(rid, "write_file",
                              {"path": "would-be-unsafe.txt", "content": "bad"},
                              model_selected=True, read_only_run=True)
                self.assertFalse((app.workspace / "would-be-unsafe.txt").exists())
            finally:
                app.close()

    def test_ui_mode_present_with_unmodified_default(self):
        html = (STUDIO / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="tool-compatibility"', html)
        self.assertIn('value="native"', html)
        self.assertIn('value="read_only_json"', html)
        self.assertIn("settings.tool_compatibility||'native'", html)
        self.assertIn("tool_compatibility:$('tool-compatibility').value", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
