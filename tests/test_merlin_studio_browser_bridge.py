"""Synthetic but full Studio model/tool/event checks for optional browser bridge.

No Chromium, public website, privileged socket or model process is run here.
The source-citation and tool wire contract is exercised with a fake supervisor;
OCI native browser qualification remains a separate mandatory gate.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
sys.path.insert(0, str(ROOT / "python"))
from browser_bridge import BrowserBridge, BrowserBridgeError, SOCKET, _ref, _listener_registered
from engine import Application
from model import LocalModel
from storage import Store
from tools import ToolSet


SHA = "a" * 64
URL = "https://www.iana.org/domains/reserved"
TEXT = "Synthetic IANA-style source lists example.com and example.org."
BYTES = TEXT.encode("utf-8")
DIGEST = hashlib.sha256(BYTES).hexdigest()


def ref(episode, ending, digest=SHA):
    return {"schema": "merlin-artifact-ref/1", "project_id": "merlin-browser-research",
            "logical_path": "browser/episodes/" + episode + "/" + ending,
            "sha256": digest, "version": 1}


class FakeRootBrowser:
    def __init__(self):
        self.calls = []
        self.read_digest = DIGEST
        self.ref_project = "merlin-browser-research"
        self.response_operation = None
        self.observation_override = None
        self.finished = True
        self.status_override = None
    def request(self, args):
        self.calls.append(args)
        episode = args["episode_id"]
        operation = self.response_operation or args["operation"]
        if args["operation"] == "status":
            state = self.status_override or ("completed" if self.finished else "failed")
            response = {"schema": "merlin-browser-service-result/1",
                        "operation": operation, "episode_id": episode,
                        "model_calls": 0, "status": state}
            if state in ("completed", "completed_with_failures"):
                response.update(publication_ref=ref(episode, "publication.json"),
                                publication={
                                    "schema": "merlin-browser-publication/1",
                                    "episode_id": episode, "status": state,
                                    "qualification": False, "model_calls": 0,
                                    "manifest_ref": ref(episode, "episode.json"),
                                    "handoff_ref": ref(episode, "handoff.json"),
                                    "sources": [
                                        {"observation_id": "o0001", "acquisition_url": URL,
                                         "capture_event_ref": ref(episode, "events/0001.json"),
                                         "context_intake": "source_snapshot"}]})
            elif state == "failed":
                response["failure_ref"] = ref(episode, "execution-failure.json")
            elif state == "reconciliation_needed":
                response.update(request_ref=ref(episode, "request.json"),
                                retained_episode_directory=True, execution_retried=False)
            elif state == "not_found":
                response.update(request_ref=None,
                                retained_episode_directory=False, execution_retried=False)
            return response
        if args["operation"] == "submit":
            return {"schema": "merlin-browser-service-result/1",
                    "operation": operation, "episode_id": episode,
                    "model_calls": 0, "status": "completed" if self.finished else "failed",
                    "publication": {
                        "schema": "merlin-browser-publication/1",
                        "episode_id": episode, "status": "completed",
                        "qualification": False, "model_calls": 0,
                        "manifest_ref": ref(episode, "episode.json"),
                        "handoff_ref": ref(episode, "handoff.json"),
                        "sources": [{"observation_id": "o0001", "acquisition_url": URL,
                                     "capture_event_ref": ref(episode, "events/0001.json"),
                                     "context_intake": "source_snapshot"}],
                    }}
        return {"schema": "merlin-browser-service-result/1",
                "operation": operation, "episode_id": episode, "model_calls": 0,
                "observation_id": self.observation_override or args["observation_id"], "kind": "text",
                "encoding": "utf-8", "acquisition_url": URL,
                "document_status": 200, "start_byte": args["start_byte"],
                "end_byte": args["start_byte"] + len(BYTES),
                "total_bytes": args["start_byte"] + len(BYTES),
                "content": TEXT, "excerpt_sha256": self.read_digest,
                "artifact_ref": {**ref(episode, "observations/o0001/text.txt"),
                                  "project_id": self.ref_project},
                "capture_event_ref": ref(episode, "events/0001.json"),
                "next_start_byte": None}


class BridgeTests(unittest.TestCase):
    def test_host_not_implicitly_enabled(self):
        self.assertEqual(SOCKET, "/run/merlin-public-browser/browser.sock")
        self.assertFalse(BrowserBridge().available())

    def test_orphan_socket_without_proccred_listener_fails_closed(self):
        # Root-owned Unix socket files may survive after service exit. The
        # synthetic /proc/net/unix fixture must not call them a running service.
        header = b"Num RefCount Protocol Flags Type St Inode Path\n"
        stale = (b"00000000: 00000002 00000000 00000000 0001 01 123 "
                 + SOCKET.encode() + b"\n")
        live = (b"00000000: 00000002 00000000 00010000 0001 01 124 "
                + SOCKET.encode() + b"\n")
        self.assertFalse(_listener_registered(header))
        self.assertFalse(_listener_registered(header + stale))
        self.assertTrue(_listener_registered(header + live))
        self.assertFalse(_listener_registered(header + live.replace(b"0001 01", b"0002 01")))
        self.assertFalse(_listener_registered(header + live.replace(b"browser.sock", b"else.sock")))
        self.assertFalse(_listener_registered(header + b"a" * (1024 * 1024)))
        self.assertFalse(_listener_registered(b"garbled contents"))

    def test_source_observation_identity_cannot_be_substituted_by_service(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        episode = bridge.open_public(URL)["episode_id"]
        fake.observation_override = "o0002"
        with self.assertRaisesRegex(BrowserBridgeError, "identity"):
            bridge.read_text(episode, "o0001")

    def test_default_and_invalid_settings_do_not_grant_a_browser(self):
        self.assertIs(Application.validate_settings({})["browser_enabled"], False)
        for bad in ("true", 1, None, [], {}):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Application.validate_settings({"browser_enabled": bad})

    def test_source_url_and_artifact_refs_are_bound_to_exact_episode(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        start = bridge.open_public(URL)
        self.assertTrue(start["browser_completed"])
        self.assertEqual(start["sources"][0]["acquisition_url"], URL)
        self.assertEqual(start["model_calls"], 0)
        episode = start["episode_id"]
        result = bridge.read_text(episode, "o0001")
        self.assertEqual(result["source_text"], TEXT)
        self.assertEqual(result["excerpt_sha256"], DIGEST)
        self.assertEqual(result["artifact_ref"]["project_id"], "merlin-browser-research")
        self.assertTrue(result["source_text_is_untrusted"])
        self.assertEqual([c["operation"] for c in fake.calls], ["submit", "read"])
        self.assertEqual(fake.calls[0]["actions"], [{"action": "open", "url": URL}])
        self.assertEqual(fake.calls[1]["kind"], "text")

    def test_network_denials_reject_before_supervisor_call(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        for url in ("http://127.0.0.1", "http://169.254.169.254/", "file:///etc/passwd",
                    "https://chatgpt.com", "https://user:password@www.iana.org/",
                    "http://localhost/", "https://www.iana.org:8443/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                bridge.open_public(url)
        self.assertEqual(fake.calls, [])

    def test_bad_model_source_digests_and_scopes_fail_closed(self):
        for kind in ("digest", "scope", "operation"):
            with self.subTest(kind=kind):
                fake = FakeRootBrowser()
                bridge = BrowserBridge(requester=fake.request)
                episode = bridge.open_public(URL)["episode_id"]
                if kind == "digest": fake.read_digest = "b" * 64
                if kind == "scope": fake.ref_project = "private-production"
                if kind == "operation": fake.response_operation = "submit"
                with self.assertRaises(BrowserBridgeError):
                    bridge.read_text(episode, "o0001")

    def test_canonical_ref_rejects_wrong_schema_version_or_extra_fields(self):
        episode = "studio-" + "a" * 32
        for key, value in (("schema", "other"), ("version", 0),
                           ("version", True), ("project_id", "other")):
            with self.subTest(key=key, value=value):
                with self.assertRaises(BrowserBridgeError):
                    _ref({**ref(episode, "episode.json"), key: value}, episode)
        with self.assertRaises(BrowserBridgeError):
            _ref({**ref(episode, "episode.json"), "unsafe_extra": "1"}, episode)

    def test_invented_episode_and_observation_rejected(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        for episode in ("arbitrary", "../studio-foo", "studio-", "studio-abc/x"):
            with self.subTest(episode=episode), self.assertRaises(BrowserBridgeError):
                bridge.read_text(episode, "o0001")
        with self.assertRaises(BrowserBridgeError):
            bridge.read_text("studio-abcd", "o99999")
        self.assertEqual(fake.calls, [])

    def test_failed_browser_has_no_successful_source_claim(self):
        fake = FakeRootBrowser()
        fake.finished = False
        result = BrowserBridge(requester=fake.request).open_public(URL)
        self.assertFalse(result["browser_completed"])
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("sources", result)

    def test_status_replays_exact_browser_citations_without_second_navigation(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        episode = bridge.open_public(URL)["episode_id"]
        before = len([call for call in fake.calls if call["operation"] == "submit"])
        replay = bridge.status(episode)
        self.assertEqual(replay["status"], "completed")
        self.assertTrue(replay["replayed_without_launch"])
        self.assertEqual(replay["sources"][0]["acquisition_url"], URL)
        self.assertEqual(replay["publication_ref"],
                         ref(episode, "publication.json"))
        self.assertEqual(len([call for call in fake.calls if call["operation"] == "submit"]), before)

    def test_browser_recovery_never_turns_failure_into_success(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        episode = "studio-" + "c" * 32
        for state in ("failed", "reconciliation_needed", "not_found",
                      "completed_with_failures"):
            with self.subTest(state=state):
                fake.status_override = state
                outcome = bridge.status(episode)
                self.assertEqual(outcome["status"], state)
                self.assertFalse(outcome["browser_completed"])
                self.assertTrue(outcome["replayed_without_launch"])
                self.assertEqual(outcome["reconciliation_required"],
                                 state != "not_found")
        self.assertFalse(any(x["operation"] == "submit" for x in fake.calls))

    def test_forged_status_receipt_or_wrong_identity_is_rejected(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        episode = "studio-" + "d" * 32
        for state in ("unreviewed", "succeeded"):
            with self.subTest(state=state):
                fake.status_override = state
                with self.assertRaises(BrowserBridgeError):
                    bridge.status(episode)
        fake.status_override = "completed"
        fake.response_operation = "read"
        with self.assertRaises(BrowserBridgeError):
            bridge.status(episode)
        self.assertFalse(any(x["operation"] == "submit" for x in fake.calls))

    def test_status_is_restricted_to_same_run_in_studio_tools(self):
        fake = FakeRootBrowser()
        bridge = BrowserBridge(requester=fake.request)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = Store(root / "state")
            settings = {**Application.validate_settings({}),
                        "network_enabled": True, "browser_enabled": True}
            tools = ToolSet(root / "workspace", store, settings,
                            browser_bridge=bridge)
            run_id = "a" * 32
            own = "studio-" + run_id
            other = "studio-" + "b" * 32
            self.assertIn("browser_status", {entry["function"]["name"]
                                            for entry in tools.schemas()})
            with self.assertRaises(PermissionError):
                tools.execute("browser_status", {"episode_id": other}, run_id)
            res = tools.execute("browser_status", {"episode_id": own}, run_id)
            self.assertTrue(res["replayed_without_launch"])
            self.assertEqual(res["episode_id"], own)
            self.assertEqual([x["operation"] for x in fake.calls], ["status"])

    def test_native_mode_is_explicit_and_read_only_compat_excludes_browser(self):
        fake = FakeRootBrowser()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = Store(root / "state")
            settings = {**Application.validate_settings({}),
                        "network_enabled": True, "browser_enabled": True,
                        "python_enabled": False, "desktop_enabled": False}
            bridge = BrowserBridge(requester=fake.request)
            tools = ToolSet(root / "workspace", store, settings, browser_bridge=bridge)
            self.assertTrue(tools.capabilities()["browser"])
            names = {t["function"]["name"] for t in tools.schemas()}
            self.assertIn("browser_open", names)
            self.assertIn("browser_read", names)
            self.assertIn("browser_status", names)
            owner = "a" * 32
            other = "b" * 32
            opened = tools.execute("browser_open", {"url": URL}, owner)
            self.assertEqual(opened["status"], "completed")
            self.assertEqual(opened["episode_id"], "studio-" + owner)
            with self.assertRaisesRegex(PermissionError, "outside this Studio run"):
                tools.execute("browser_read", {
                    "episode_id": opened["episode_id"], "observation_id": "o0001"}, other)
            read = tools.execute("browser_read", {
                "episode_id": opened["episode_id"], "observation_id": "o0001"}, owner)
            self.assertEqual(read["excerpt_sha256"], DIGEST)
            for change in ({"browser_enabled": False}, {"network_enabled": False},
                           {"tool_compatibility": "read_only_json"}):
                with self.subTest(change=change):
                    unavailable = ToolSet(root / "workspace", store, {**settings, **change},
                                          browser_bridge=bridge)
                    self.assertFalse(unavailable.capabilities()["browser"])
                    self.assertNotIn("browser_open", {x["function"]["name"] for x in unavailable.schemas()})
                    with self.assertRaises(ValueError):
                        unavailable.execute("browser_open", {"url": URL}, "run")

    def test_synthetic_model_tools_read_actual_capture_then_answer_with_source(self):
        fake = FakeRootBrowser()
        responses = []
        def complete(method, path, payload, timeout):
            responses.append(payload)
            tool_results = [m for m in payload["messages"] if m.get("role") == "tool"]
            if not tool_results:
                name, args = "browser_open", {"url": URL}
            elif len(tool_results) == 1:
                first = json.loads(tool_results[0]["content"])
                self.assertEqual(first["sources"][0]["acquisition_url"], URL)
                name, args = "browser_read", {
                    "episode_id": first["episode_id"], "observation_id": "o0001"}
            else:
                latest = json.loads(tool_results[-1]["content"])
                self.assertEqual(latest["excerpt_sha256"], DIGEST)
                self.assertEqual(latest["source_text"], TEXT)
                return {"choices": [{"message": {
                    "content": "The source lists example.com and example.org. Source: " + URL}}]}
            return {"choices": [{"message": {"tool_calls": [{
                "id": "browser-step-" + str(len(responses)), "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}
            }]}}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Application(root, root / "state",
                              start_bundled=False,
                              model_factory=lambda settings: LocalModel(settings, transport=complete),
                              browser_bridge_factory=lambda: BrowserBridge(requester=fake.request))
            try:
                app.save_settings({"model_url": "http://127.0.0.1:18772/v1",
                                   "model_id": "synthetic", "network_enabled": True,
                                   "python_enabled": False, "desktop_enabled": False,
                                   "browser_enabled": True, "max_steps": 3})
                cid = app.store.create_conversation()["id"]
                rid = app.start_run(cid, "Check IANA's official reserved domains page")
                with app.threads_lock:
                    thread = app.threads.get(rid)
                if thread is not None:
                    thread.join(timeout=10)
                run = app.store.run(rid)
                self.assertEqual(run["status"], "completed", run)
                types = [x["type"] for x in run["events"]]
                self.assertEqual(types.count("tool_started"), 2)
                self.assertEqual(types.count("tool_result"), 2)
                self.assertEqual(types.count("model_request"), 3)
                self.assertEqual(len(fake.calls), 2)
                self.assertIn(URL, app.store.conversation(cid)["messages"][-1]["content"])
            finally:
                app.close()

    def test_midrun_browser_setting_enable_does_not_grant_existing_model(self):
        fake = FakeRootBrowser()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = Application(root, root / "state", start_bundled=False,
                              browser_bridge_factory=lambda: BrowserBridge(requester=fake.request))
            try:
                app.save_settings({"network_enabled": True, "browser_enabled": False,
                                   "python_enabled": False, "desktop_enabled": False})
                cid = app.store.create_conversation()["id"]
                run_id = app.store.start_run(cid, "Browser was disabled at startup")
                app.save_settings({"browser_enabled": True})
                self.assertTrue(app.tools().capabilities()["browser"])
                with self.assertRaisesRegex(ValueError, "not active when this model run started"):
                    app._tool(run_id, "browser_open", {"url": URL}, model_selected=True,
                              browser_allowed_run=False)
                self.assertEqual(fake.calls, [])
                self.assertFalse(any(
                    event["type"] == "tool_started" for event in app.store.run(run_id)["events"]))
            finally:
                app.close()

    def test_browser_client_has_explicit_bounded_timeout(self):
        import inspect
        from merlin.browser_client import request_browser
        self.assertEqual(inspect.signature(request_browser).parameters["timeout_seconds"].default, 85)


if __name__ == "__main__":
    unittest.main(verbosity=2)
