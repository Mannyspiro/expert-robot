"""Real HTTP boundaries and durable canonical integration, using explicit fixtures.

Gateway assertions below are synthetic syntax fixtures. These tests do not
claim to verify Cloudflare identity or an externally reachable deployment.
"""
from __future__ import annotations

from hashlib import sha256
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import server
from gateway import load_gateway_contract
from merlin.knowledge_graph import GraphNode


def gateway_data():
    return {"schema": "merlin-studio-trusted-gateway/1", "contract_version": 1,
            "public_origin": "https://merlin.example.com", "team_name": "example-team",
            "audiences": ["12345678abcdef"], "identity_verifier": "cloudflared-access-required"}


class IntegratedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "studio"
        self.research = self.root / "research"
        self.server = None
        self.addCleanup(self.stop)

    def start(self, *, enabled=True, gateway=False):
        config = None
        if gateway:
            config = self.root / "gateway.json"
            config.write_text(json.dumps(gateway_data()))
        with patch.dict("os.environ", {"MERLIN_MODEL_URL": "", "MERLIN_MODEL_ID": ""}):
            self.server = server.create_server(data_dir=self.data, start_bundled=False,
                research_state_dir=self.research if enabled else None, gateway_config=config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.token = body["session_token"]
        return body

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None

    def request(self, method, path, value=None, *, headers=None, token=True):
        headers = dict(headers or {})
        body = None
        if method == "POST":
            body = json.dumps(value or {}).encode()
            headers.setdefault("Content-Type", "application/json")
            if token:
                headers.setdefault("X-Merlin-Token", self.token)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            result = json.loads(data) if "application/json" in response.getheader("Content-Type", "") else data
            return response.status, dict(response.getheaders()), result
        finally:
            connection.close()

    def run_state(self, run_id):
        self.server.research.sync()
        return self.request("GET", "/api/hud/activity?run_id=studio:" + run_id)[2]

    def direct_run(self):
        store = self.server.app.store
        conversation = store.create_conversation("Fixture conversation")
        return store.start_run(conversation["id"], "PRIVATE_INPUT_FIXTURE_DO_NOT_PUBLISH")

    def test_disabled_research_is_explicit_and_offline_chat_still_works(self):
        status = self.start(enabled=False)
        self.assertFalse(status["research"]["enabled"])
        self.assertFalse(status["updates"]["model_token_streaming"])
        self.assertEqual(self.request("GET", "/research/dashboard")[0], 503)
        _, _, created = self.request("POST", "/api/conversations", {"title": "Offline fixture"})
        _, _, started = self.request("POST", "/api/chat", {"conversation_id": created["conversation"]["id"], "message": "/help"})
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            _, _, record = self.request("GET", "/api/runs/" + started["run_id"])
            if record["run"]["status"] == "completed":
                break
            time.sleep(0.02)
        self.assertEqual(record["run"]["status"], "completed")
        self.assertIn("/files", record["conversation"]["messages"][-1]["content"])

    def test_real_canonical_artifacts_and_narrow_iframe_headers(self):
        self.start()
        proof = self.root / "proof.lean"
        proof.write_text("-- explicit test fixture\nexample : 1 = 1 := rfl\n")
        registered = self.server.research.window.register_artifact(proof, allowed_roots=[self.root],
            run_id="fixture-scientific-run", title="Fixture proof", display_kind="source")
        code, headers, body = self.request("GET", registered["url"])
        self.assertEqual(code, 200)
        self.assertEqual(body, proof.read_bytes())
        self.assertEqual(headers["X-Artifact-SHA256"], sha256(body).hexdigest())
        self.assertIn("sandbox; default-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        code, headers, body = self.request("GET", "/research/dashboard?run_id=fixture-scientific-run")
        self.assertEqual(code, 200)
        self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
        self.assertIn(b"run_id", body)
        _, main_headers, _ = self.request("GET", "/studio/")
        self.assertIn("frame-src 'self'", main_headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", main_headers["Content-Security-Policy"])
        _, _, node = self.request("GET", "/api/hud/node?node_id=" + registered["node_id"])
        self.assertTrue(node["linked_artifacts"][0]["verified"])

    def test_research_allowlist_query_and_write_boundaries(self):
        self.start()
        for route in ("/api/hud/graph?url=http://127.0.0.1:8080", "/api/hud/node?node_id=a&node_id=b",
                      "/api/hud/artifact?path=/etc/passwd", "/research/dashboard?run_id=one&run_id=two"):
            with self.subTest(route=route):
                self.assertEqual(self.request("GET", route)[0], 400)
        self.assertEqual(self.request("GET", "http://127.0.0.1:8080/private")[0], 400)
        self.assertEqual(self.request("GET", "/api/hud/arbitrary")[0], 404)
        for route in ("/api/hud/activity", "/api/hud/artifact", "/research/dashboard"):
            self.assertEqual(self.request("POST", route)[0], 405)

    def test_corrupt_and_oversize_graph_references_fail_before_unbounded_resolution(self):
        self.start()
        window = self.server.research.window
        ref_path = self.root / "fixture.txt"
        ref_path.write_text("fixture")
        registered = window.register_artifact(ref_path, allowed_roots=[self.root],
            run_id="fixture", title="Fixture", display_kind="data")
        digest = registered["artifact_ref"]["sha256"]
        (window.registry.blobs / digest[:2] / digest[2:]).write_bytes(b"changed")
        self.assertEqual(self.request("GET", registered["url"])[0], 503)
        content = b"x" * (8 * 1024 * 1024 + 1)
        window.registry.put_artifact(window.project_id, "large.txt", content, "text/plain")
        reference = window.registry.artifact_ref(window.project_id, "large.txt")
        window.graph.add_node(GraphNode("artifact:large-fixture", "artifact", "Oversize fixture", {
            "project_id": window.project_id, "logical_path": "large.txt", "artifact_ref": reference, "display_kind": "data"}, "unreviewed"))
        with patch.object(window.registry, "resolve_artifact_ref", side_effect=AssertionError("unbounded reader called")):
            self.assertEqual(self.request("GET", "/api/hud/node?node_id=artifact:large-fixture")[0], 503)
            self.assertEqual(self.request("GET", "/api/hud/artifact?node_id=artifact:large-fixture")[0], 503)

    def test_actual_event_mapping_preserves_approval_and_terminal_states(self):
        self.start()
        store = self.server.app.store
        run = self.direct_run()
        self.assertEqual(self.run_state(run)["run_status"], "active")
        approval = store.request_approval(run, "run_python", {"path": "private.py"})
        self.assertEqual(self.run_state(run)["run_status"], "waiting")
        store.approve(run, approval, True)
        self.assertEqual(self.run_state(run)["run_status"], "active")
        store.event(run, "tool_started", tool="run_python", arguments={"private": "DO_NOT_PUBLISH_ARGUMENT"})
        store.event(run, "tool_result", tool="run_python", result={"private": "DO_NOT_PUBLISH_RESULT"})
        store.finish(run, "DO_NOT_PUBLISH_ANSWER", status="cancelled")
        state = self.run_state(run)
        self.assertEqual(state["run_status"], "cancelled")
        self.assertEqual(state["completed_stages"], [])
        self.assertNotIn("verified", state["research"].get("proof_status", "").lower())
        records = self.server.research.window.outbox.recent(topics=self.server.research.window.topics, limit=1000)
        encoded = json.dumps(records)
        for marker in ("PRIVATE_INPUT_FIXTURE", "DO_NOT_PUBLISH_ARGUMENT", "DO_NOT_PUBLISH_RESULT", "DO_NOT_PUBLISH_ANSWER", "private.py"):
            self.assertNotIn(marker, encoded)
        self.assertTrue(all(row["payload"]["payload"]["component"] == "merlin_studio" for row in records))

    def test_replay_is_idempotent_and_restart_interrupts_without_reexecution(self):
        self.start()
        run = self.direct_run()
        self.run_state(run)
        old = self.server.research.window.outbox.counts()
        self.server.research.sync()
        self.assertEqual(old, self.server.research.window.outbox.counts())
        self.stop()
        self.start()
        state = self.run_state(run)
        self.assertEqual(state["run_status"], "interrupted")
        records = self.server.research.window.outbox.recent(topics=self.server.research.window.topics, limit=1000)
        self.assertEqual(len(records), 2)
        self.assertEqual(len({r["payload"]["event_id"] for r in records}), 2)
        self.assertEqual(self.server.app.store.run(run)["status"], "interrupted")

    def test_external_gateway_contract_preserves_identity_delegation_and_csrf(self):
        self.start(gateway=True)
        public = {"Host": "merlin.example.com", "Origin": "https://merlin.example.com",
                  "Cf-Access-Jwt-Assertion": "synthetic.payload.signature"}
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "merlin.example.com"})[0], 403)
        code, _, body = self.request("GET", "/api/status", headers=public)
        self.assertEqual(code, 200)
        self.assertFalse(body["access"]["application_verifies_access_jwt"])
        self.assertEqual(body["access"]["scope"], "single_owner_shared_workspace")
        self.assertEqual(self.request("POST", "/api/conversations", {"title": "Fixture"}, headers=public, token=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/conversations", {"title": "Fixture"}, headers=public)[0], 201)
        for extra in ({"Origin": "https://evil.example.com"}, {"Origin": "http://127.0.0.1:8771"},
                      {"Host": "evil.example.com"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.request("GET", "/api/status", headers={**public, **extra})[0], 403)
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "evil.example.com",
            "X-Forwarded-Host": "merlin.example.com", "X-Forwarded-Proto": "https", "Cf-Access-Jwt-Assertion": "synthetic.payload.signature"})[0], 403)

    def test_external_hostname_cannot_enable_itself_without_contract(self):
        self.start(enabled=False)
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "merlin.example.com",
            "Cf-Access-Jwt-Assertion": "synthetic.payload.signature", "X-Forwarded-Proto": "https"})[0], 403)

    def test_duplicate_boundary_headers_are_rejected(self):
        self.start(gateway=True)
        for name, value in (("Host", "merlin.example.com"), ("Origin", "https://merlin.example.com"),
                            ("Cf-Access-Jwt-Assertion", "synthetic.payload.signature")):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            try:
                connection.putrequest("GET", "/api/status", skip_host=True)
                connection.putheader("Host", "merlin.example.com")
                connection.putheader("Origin", "https://merlin.example.com")
                connection.putheader("Cf-Access-Jwt-Assertion", "synthetic.payload.signature")
                connection.putheader(name, value)
                connection.endheaders()
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            finally:
                connection.close()

    def test_sse_uses_saved_event_ids_scoped_to_one_run_and_ends_terminally(self):
        self.start()
        store = self.server.app.store
        run = self.direct_run()
        cursor = store.stream_update(run, 0)["cursor"]
        other = self.direct_run()
        store.event(other, "tool_started", tool="OTHER_RUN_TOOL")
        store.event(run, "tool_started", tool="list_files", arguments={"secret": "NOT_IN_SSE"})
        store.finish(run, "COMPLETE_ANSWER_NOT_TOKEN_STREAMED")
        code, headers, body = self.request("GET", "/api/runs/" + run + "/events", headers={"Last-Event-ID": str(cursor)})
        self.assertEqual(code, 200)
        self.assertIn("text/event-stream", headers["Content-Type"])
        self.assertIn(b"event: run", body)
        self.assertNotIn(b"OTHER_RUN_TOOL", body)
        self.assertNotIn(b"NOT_IN_SSE", body)
        self.assertNotIn(b"COMPLETE_ANSWER_NOT_TOKEN_STREAMED", body)
        data = json.loads(next(line[6:] for line in body.splitlines() if line.startswith(b"data: ")))
        self.assertTrue(data["terminal"])
        self.assertEqual([e["type"] for e in data["events"]], ["tool_started", "completed"])
        self.assertTrue(all(e["ordinal"] > cursor for e in data["events"]))
        self.assertEqual(self.request("GET", "/api/runs/" + run + "/events?run_id=" + other)[0], 400)
        self.assertEqual(self.request("GET", "/api/runs/" + run + "/events", headers={"Last-Event-ID": "-1"})[0], 400)
        self.assertEqual(self.request("GET", "/api/runs/" + run + "/events", headers={"Origin": "https://evil.example"})[0], 403)

    def test_sse_concurrency_and_duration_are_bounded(self):
        self.start()
        run = self.direct_run()
        for _ in range(12):
            self.assertTrue(self.server.stream_slots.acquire(blocking=False))
        try:
            self.assertEqual(self.request("GET", "/api/runs/" + run + "/events")[0], 503)
        finally:
            for _ in range(12):
                self.server.stream_slots.release()
        self.server.stream_seconds = 0.1
        started = time.monotonic()
        self.assertEqual(self.request("GET", "/api/runs/" + run + "/events")[0], 200)
        self.assertLess(time.monotonic() - started, 2)
        acquired = 0
        try:
            for _ in range(12):
                self.assertTrue(self.server.stream_slots.acquire(blocking=False))
                acquired += 1
        finally:
            for _ in range(acquired):
                self.server.stream_slots.release()


class GatewayConfigTests(unittest.TestCase):
    def test_contract_rejects_ambiguous_origins_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gateway.json"
            for origin in ("http://merlin.example.com", "https://merlin.example.com/", "https://u:p@merlin.example.com",
                           "https://*.example.com", "https://merlin.example.com?x=1", "https://merlin.example.com#x",
                           "https://merlin.example.com:443", "https://MERLIN.example.com"):
                path.write_text(json.dumps({**gateway_data(), "public_origin": origin}))
                with self.subTest(origin=origin), self.assertRaises(ValueError):
                    load_gateway_contract(path)
            path.write_text(json.dumps({**gateway_data(), "trust_x_forwarded_headers": True}))
            with self.assertRaises(ValueError):
                load_gateway_contract(path)
            path.write_text('{"schema":"one","schema":"two"}')
            with self.assertRaises(ValueError):
                load_gateway_contract(path)


if __name__ == "__main__":
    unittest.main()
