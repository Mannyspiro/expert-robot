import json
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from pathlib import Path

from python.merlin.app import EventStore, make_handler


class MerlinApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = EventStore(Path(cls.temp.name) / "events.sqlite3")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.store))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def post(self, path, payload):
        request = Request(self.base + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_health_and_capabilities(self):
        with urlopen(self.base + "/health", timeout=5) as response:
            self.assertTrue(json.loads(response.read())["ok"])
        with urlopen(self.base + "/api/capabilities", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertIn("engineering.geometry.validate", {row["id"] for row in payload["capabilities"]})

    def test_council_roles_and_prepare_endpoint(self):
        with urlopen(self.base + "/api/council/roles", timeout=5) as response:
            roles = json.loads(response.read())["roles"]
        self.assertGreaterEqual(len(roles), 5)
        self.assertIn("skeptic", {role["id"] for role in roles})

        payload = self.post("/api/council/prepare", {
            "question": "Should Merlin use hybrid routing?",
            "verbosity": "lively",
        })
        self.assertEqual(payload["schema"], "merlin-council-packets/1")
        self.assertGreaterEqual(len(payload["packets"]), 5)
        self.assertFalse(payload["promotion_authorized"])

    def test_ideonomy_rank_endpoint(self):
        payload = self.post("/api/ideonomy/rank", {"ideas": [{
            "title": "Mesh reduction", "mechanism": "Collapse degree-two nodes.",
            "assumptions": ["2-manifold"], "constraints": ["fix boundary"],
            "observable": "Euler characteristic", "falsifier": "topology changes",
            "feasibility": 0.9, "testability": 0.9
        }]})
        self.assertEqual(len(payload["accepted"]), 1)

    def test_rsi_fails_closed(self):
        payload = self.post("/api/rsi/qualify", {
            "tests_passed": True, "independent_review": True,
            "held_out_qualification": False, "rollback_ready": True,
            "authority_unchanged": True, "human_approval": False,
            "compute_budget_respected": True
        })
        self.assertEqual(payload["status"], "BLOCKED")

    def test_council_run_fails_closed_until_local_model_qualified(self):
        request = Request(self.base + "/api/council/run",
                          data=json.dumps({"question": "Should we proceed?"}).encode(),
                          headers={"Content-Type": "application/json"})
        try:
            urlopen(request, timeout=5)
        except HTTPError as error:
            self.assertEqual(error.code, 503)
            self.assertEqual(json.loads(error.read())["error"], "council_model_unavailable")
        else:
            self.fail("council execution must fail closed until local model qualification")

    def test_simulation_hud_and_control_api(self):
        with urlopen(self.base + "/hud", timeout=5) as response:
            self.assertIn("text/html", response.headers.get("Content-Type", ""))
            hud = response.read().decode("utf-8")
            self.assertIn("MERLIN", hud)
            self.assertIn('data-feedback="success"', hud)
            self.assertIn("recordUiInteraction", hud)
            self.assertIn("task_submitted", hud)
            self.assertIn("feedback_submitted", hud)
            self.assertIn("telemetryOpt", hud)
            self.assertIn("feedbackOpt", hud)
            self.assertIn("deleteSessionFeedback", hud)
            self.assertIn("loadLearningPreferences", hud)
            self.assertIn("/api/chat", hud)
            self.assertIn("/api/speech", hud)
            self.assertIn("providerMode", hud)
            self.assertIn("councilPrepare", hud)
            self.assertIn("chatTranscript", hud)
        with urlopen(self.base + "/api/sim/state", timeout=5) as response:
            initial = json.loads(response.read())
        self.assertTrue(initial["simulation_only"])
        result = self.post("/api/sim/step", {"action": "advance"})
        self.assertEqual(result["state"]["tick"], 1)
        self.assertGreater(result["state"]["progress"], 0)
        with urlopen(self.base + "/api/sim/events", timeout=5) as response:
            events = json.loads(response.read())
        self.assertGreaterEqual(len(events["events"]), 2)

    def test_telemetry_ingest_and_source_separation(self):
        # Fresh store prevents unrelated HTTP boundary events from polluting counts.
        with tempfile.TemporaryDirectory() as tmp:
            isolated_store = EventStore(Path(tmp) / "isolated.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(isolated_store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                def post(path, payload):
                    request = Request(base + path, data=json.dumps(payload).encode(),
                                      headers={"Content-Type": "application/json"})
                    with urlopen(request, timeout=5) as response:
                        return json.loads(response.read())
                accepted = post("/api/telemetry/ingest", {
                    "source": "runtime", "kind": "task.progress", "run_id": "api-test",
                    "task_id": "task-1", "payload": {"step": 1}, "cpu_percent": 8.5
                })
                self.assertTrue(accepted["accepted"])
                self.assertEqual(accepted["event"]["source"], "runtime")
                post("/api/telemetry/ingest", {
                    "source": "simulation", "kind": "task.progress", "run_id": "sim-test"
                })
                with urlopen(base + "/api/telemetry", timeout=5) as response:
                    view = json.loads(response.read())
                # Two POSTs and the GET each emit an HTTP-boundary runtime event.
                self.assertEqual(view["source_counts"]["runtime"], 3)
                self.assertEqual(view["source_counts"]["simulation"], 1)
                self.assertTrue(view["simulation_is_not_runtime"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_http_boundaries_emit_measured_runtime_telemetry(self):
        with urlopen(self.base + "/health", timeout=5) as response:
            self.assertEqual(response.status, 200)
        rows = self.store.by_kind("/api/telemetry/ingest", 10000)
        events = [row["summary"]["event"] for row in rows
                  if row.get("summary", {}).get("event", {}).get("task_id") == "/health"]
        self.assertTrue(events)
        event = events[-1]
        self.assertEqual(event["source"], "runtime")
        self.assertEqual(event["payload"]["component"], "http_api")
        self.assertEqual(event["payload"]["method"], "GET")
        self.assertEqual(event["payload"]["status_code"], 200)
        self.assertGreaterEqual(event["duration_ms"], 0)
        self.assertGreater(event["payload"]["response_bytes"], 0)

    def test_simulation_operator_events_remain_source_separated(self):
        self.post("/api/sim/step", {"action": "advance"})
        rows = self.store.by_kind("/api/telemetry/ingest", 10000)
        events = [row["summary"]["event"] for row in rows
                  if row.get("summary", {}).get("event", {}).get("source") == "simulation"]
        self.assertTrue(any(e["kind"] == "operator.action" and
                            e["payload"].get("simulation_only") is True for e in events))

    def test_simulation_replay_survives_server_restart(self):
        from http.server import ThreadingHTTPServer
        import threading
        db = Path(self.temp.name) / "replay.sqlite3"
        store = EventStore(db)
        first = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
        thread = threading.Thread(target=first.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{first.server_port}"
        try:
            for action in ("advance", "verify", "advance"):
                request = Request(base + "/api/sim/step", data=json.dumps({"action": action}).encode(),
                                  headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
        finally:
            first.shutdown()
            first.server_close()
            thread.join(timeout=2)
        second = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(EventStore(db)))
        thread2 = threading.Thread(target=second.serve_forever, daemon=True)
        thread2.start()
        try:
            with urlopen(f"http://127.0.0.1:{second.server_port}/api/sim/replay", timeout=5) as response:
                replay = json.loads(response.read())
            self.assertEqual(replay["replayed_actions"], 3)
            self.assertEqual(replay["actions"], ["advance", "verify", "advance"])
            self.assertEqual(replay["state"]["state"]["tick"], 3)
        finally:
            second.shutdown()
            second.server_close()
            thread2.join(timeout=2)

    def test_telemetry_graph_endpoint(self):
        self.post("/api/telemetry/ingest", {
            "source": "verifier", "kind": "verification.completed", "run_id": "graph-run",
            "task_id": "proof-task", "evidence_refs": ["sha256:proof"]
        })
        with urlopen(self.base + "/api/telemetry/graph", timeout=5) as response:
            graph = json.loads(response.read())
        kinds = {node["kind"] for node in graph["nodes"]}
        self.assertTrue({"run", "task", "event", "evidence"}.issubset(kinds))

    def test_model_route_fails_closed_until_qualified(self):
        request = Request(self.base + "/api/chat", data=json.dumps({"messages": []}).encode(), headers={"Content-Type": "application/json"})
        try:
            urlopen(request, timeout=5)
        except HTTPError as error:
            self.assertEqual(error.code, 503)
            self.assertEqual(json.loads(error.read())["error"], "model_not_qualified")
        else:
            self.fail("unqualified model route must return 503")

    def test_speech_route_requires_local_sidecar(self):
        import os
        previous = os.environ.get("MERLIN_TTS_URL")
        os.environ["MERLIN_TTS_URL"] = "http://127.0.0.1:1/v1/audio/speech"
        try:
            request = Request(self.base + "/api/speech", data=json.dumps({"input": "test"}).encode(), headers={"Content-Type": "application/json"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 503)
        finally:
            if previous is None:
                os.environ.pop("MERLIN_TTS_URL", None)
            else:
                os.environ["MERLIN_TTS_URL"] = previous

    def test_events_store_metadata_not_request_text(self):
        self.post("/api/ideonomy/rank", {"ideas": []})
        with urlopen(self.base + "/api/events", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertGreaterEqual(len(payload["events"]), 1)
        self.assertNotIn("Mesh reduction", json.dumps(payload["events"]))


    def test_remote_model_requires_https_and_explicit_host_allowlist(self):
        import os
        from unittest.mock import patch
        from python.merlin.app import _remote_model_endpoint

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            self.assertEqual(_remote_model_endpoint(), (
                "https://api.example.test/v1/chat/completions", "test-secret"
            ))

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "http://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            with self.assertRaises(ValueError):
                _remote_model_endpoint()

        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://unapproved.example/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "test-secret",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
        }, clear=False):
            with self.assertRaises(ValueError):
                _remote_model_endpoint()


    def test_remote_sse_stream_is_forwarded_and_secret_is_not_returned(self):
        import os
        from unittest.mock import patch
        from urllib.request import Request as UpstreamRequest
        import python.merlin.app as merlin_app

        chunks = [
            b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]
        captured = {}

        class FakeResponse:
            headers = {"Content-Type": "text/event-stream"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size=-1):
                return chunks.pop(0) if chunks else b""

        def fake_urlopen(request, timeout=0):
            captured["authorization"] = request.get_header("Authorization")
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        payload = {"provider": "cloud", "model": "test-model", "messages": [{"role": "user", "content": "say hello"}], "stream": True}
        request = Request(self.base + "/api/chat", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with patch.dict(os.environ, {
            "MERLIN_REMOTE_MODEL_URL": "https://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "private-test-key",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
            "MERLIN_REMOTE_MODEL_QUALIFIED": "1",
        }, clear=False), patch.object(merlin_app, "urlopen", side_effect=fake_urlopen):
            with urlopen(request, timeout=5) as response:
                streamed = response.read()
                self.assertIn("text/event-stream", response.headers.get("Content-Type", ""))

        self.assertIn(b'"hello"', streamed)
        self.assertIn(b'" world"', streamed)
        self.assertIn(b"[DONE]", streamed)
        self.assertEqual(captured["authorization"], "Bearer private-test-key")
        self.assertNotIn(b"private-test-key", streamed)
        self.assertEqual(captured["url"], "https://api.example.test/v1/chat/completions")
        self.assertNotIn("provider", captured["payload"])
        rows = self.store.by_kind("/api/telemetry/ingest", 10000)
        model_events = [row["summary"]["event"] for row in rows
                        if row.get("summary", {}).get("event", {}).get("payload", {}).get("component") == "chat_adapter"]
        self.assertTrue(model_events)
        self.assertEqual(model_events[-1]["source"], "model_output")
        self.assertTrue(model_events[-1]["payload"]["streamed"])
        self.assertEqual(model_events[-1]["payload"]["response_bytes"], len(streamed))
        self.assertGreaterEqual(model_events[-1]["duration_ms"], 0)


    def test_learning_attempt_storage_and_hermes_recommendation_api(self):
        learner = "api-learner-rotation-test"
        base = {
            "learner_id": learner, "idea_id": "MATH-REP-001",
            "problem_id": "rotation-coordinate-90", "problem_version": "1",
            "dimension": "conceptual_explanation", "score": 1.0, "rubric_version": "rotation-r1",
            "response": {"x": 0, "y": 1}, "transfer": False, "delayed": False,
        }
        for attempt_id, session in (("rotation-attempt-1", "session-a"),
                                    ("rotation-attempt-2", "session-b")):
            self.post("/api/learning/attempt", {
                **base, "attempt_id": attempt_id, "session_id": session,
            })
        with urlopen(self.base + "/api/learning/learner?learner_id=" + learner, timeout=5) as response:
            state = json.loads(response.read())
        self.assertEqual(state["attempts"], 2)
        self.assertEqual(state["skills"]["MATH-REP-001"]["procedure"]["state"],
                         "provisionally_mastered")
        with urlopen(self.base + "/api/learning/recommendation?learner_id=" + learner + "&curriculum_id=mathematics", timeout=5) as response:
            recommendation = json.loads(response.read())
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["authority"], "recommendation_only")
        self.assertIn("reason", recommendation)


    def test_b2b_curriculum_starts_with_ml_foundations(self):
        learner = "api-learner-b2b-test"
        with urlopen(self.base + "/api/learning/recommendation?learner_id=" + learner +
                     "&curriculum_id=b2b-ml-agentic-ai", timeout=5) as response:
            recommendation = json.loads(response.read())
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["idea_id"], "B2B-ML-001")
        self.assertEqual(recommendation["lesson_id"], "b2b-ml-foundations-v0.1")
        self.assertEqual(recommendation["authority"], "recommendation_only")


    def test_art_math_curriculum_routes_from_linked_math_and_art_graphs(self):
        learner = "api-learner-art-math-test"
        with urlopen(self.base + "/api/learning/recommendation?learner_id=" + learner +
                     "&curriculum_id=art-math-studio", timeout=5) as response:
            recommendation = json.loads(response.read())
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["lesson_id"], "art-math-symmetry-studio-v0.1")
        self.assertIn(recommendation["idea_id"], {"MATH-ART-001", "ART-PAT-001"})
        self.assertEqual(recommendation["authority"], "recommendation_only")

        event = {
            "learner_id": learner, "attempt_id": "art-math-composition-1",
            "session_id": "art-session-1", "idea_id": "ART-PAT-001",
            "problem_id": "radial-pattern-composition", "problem_version": "1",
            "dimension": "self_reflection", "score": 1.0,
            "rubric_version": "art-math-studio-r1",
            "response": {"reflection": "Repeated forms create visual rhythm."},
        }
        self.post("/api/learning/attempt", event)
        with urlopen(self.base + "/api/learning/learner?learner_id=" + learner, timeout=5) as response:
            state = json.loads(response.read())
        self.assertIn("ART-PAT-001", state["skills"])
        self.assertIn("self_reflection", state["skills"]["ART-PAT-001"])



    def test_runtime_provider_status_is_explicit_and_never_exposes_credentials(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "0",
            "MERLIN_REMOTE_MODEL_QUALIFIED": "0",
            "MERLIN_TTS_QUALIFIED": "0",
            "MERLIN_REMOTE_API_KEY": "must-not-leak",
            "MERLIN_REMOTE_MODEL_URL": "https://private.example.test/v1/chat/completions",
        }, clear=False):
            with urlopen(self.base + "/api/runtime/providers", timeout=5) as response:
                payload = json.loads(response.read())
        self.assertEqual(payload["schema"], "merlin-runtime-providers/1")
        self.assertEqual(payload["providers"]["local"]["status"], "UNAVAILABLE")
        self.assertEqual(payload["providers"]["cloud"]["status"], "UNAVAILABLE")
        self.assertEqual(payload["providers"]["speech_output"]["status"], "UNAVAILABLE")
        self.assertEqual(payload["providers"]["speech_input"]["status"], "BROWSER_DEPENDENT")
        self.assertFalse(payload["raw_conversation_retention"])
        self.assertNotIn("must-not-leak", json.dumps(payload))
        self.assertNotIn("private.example.test", json.dumps(payload))

    def test_local_model_provider_can_be_selected_only_when_qualified(self):
        import os
        from unittest.mock import patch
        import python.merlin.app as merlin_app
        captured = {}
        class FakeResponse:
            headers = {"Content-Type": "application/json"}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size=-1):
                return b'{"model":"qwen2.5:3b","choices":[{"message":{"content":"Local response"}}]}'
        def fake_urlopen(request, timeout=0):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()
        request = Request(self.base + "/api/chat",
            data=json.dumps({"provider":"local","messages":[{"role":"user","content":"hello"}],"stream":False}).encode(),
            headers={"Content-Type":"application/json"})
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED":"1",
            "MERLIN_LOCAL_MODEL":"qwen2.5:3b",
            "MERLIN_REMOTE_MODEL_URL":"",
            "MERLIN_REMOTE_MODEL_QUALIFIED":"0",
        }, clear=False), patch.object(merlin_app,"urlopen",side_effect=fake_urlopen):
            with urlopen(request,timeout=5) as response:
                payload=json.loads(response.read())
        self.assertEqual(payload["choices"][0]["message"]["content"],"Local response")
        self.assertEqual(captured["url"],"http://127.0.0.1:8080/v1/chat/completions")
        self.assertEqual(captured["payload"]["model"],"qwen2.5:3b")
        self.assertNotIn("provider",captured["payload"])

    def test_speech_output_fails_closed_before_contacting_unqualified_sidecar(self):
        import os
        from unittest.mock import patch
        import python.merlin.app as merlin_app
        request = Request(self.base + "/api/speech",
            data=json.dumps({"input":"hello"}).encode(),
            headers={"Content-Type":"application/json"})
        with patch.dict(os.environ, {"MERLIN_TTS_QUALIFIED":"0"}, clear=False), \
             patch.object(merlin_app,"urlopen",side_effect=AssertionError("must not contact sidecar")):
            with self.assertRaises(HTTPError) as caught:
                urlopen(request,timeout=5)
        self.assertEqual(caught.exception.code,503)
        self.assertEqual(json.loads(caught.exception.read())["error"],"tts_not_qualified")

    def test_provider_qualification_is_not_reported_as_live_health(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {
            "MERLIN_MODEL_QUALIFIED": "1",
            "MERLIN_LOCAL_MODEL": "qwen3.5-4b",
            "MERLIN_MODEL_URL": "http://127.0.0.1:8080/v1/chat/completions",
            "MERLIN_REMOTE_MODEL_QUALIFIED": "1",
            "MERLIN_REMOTE_MODEL_NAME": "cloud-test-model",
            "MERLIN_REMOTE_MODEL_URL": "https://api.example.test/v1/chat/completions",
            "MERLIN_REMOTE_API_KEY": "private-test-key",
            "MERLIN_REMOTE_ALLOWED_HOSTS": "api.example.test",
            "MERLIN_TTS_QUALIFIED": "1",
            "MERLIN_TTS_MODEL": "kokoro-test",
            "MERLIN_TTS_URL": "http://127.0.0.1:8880/v1/audio/speech",
        }, clear=False):
            with urlopen(self.base + "/api/runtime/providers", timeout=5) as response:
                payload = json.loads(response.read())
        for key in ("local", "cloud", "speech_output"):
            self.assertEqual(payload["providers"][key]["status"], "QUALIFIED_CONFIGURED")
            self.assertEqual(payload["providers"][key]["health"], "not_probed")
        self.assertNotIn("private-test-key", json.dumps(payload))
        self.assertNotIn("api.example.test", json.dumps(payload))

    def test_memory_vault_requires_approval_and_keeps_values_out_of_event_ledger(self):
        request = Request(self.base + "/api/memory/preferences",
            data=json.dumps({"key": "preferred_language", "value": "Japanese"}).encode(),
            headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as denied:
            urlopen(request, timeout=5)
        self.assertEqual(denied.exception.code, 403)
        self.assertEqual(json.loads(denied.exception.read())["error"],
                         "explicit_approval_required")

        saved = self.post("/api/memory/preferences", {
            "key": "preferred_language", "value": "Japanese", "approved": True,
        })
        self.assertEqual(saved["kind"], "preference")
        self.assertEqual(saved["version"], 1)
        project = self.post("/api/memory/projects", {
            "name": "Merlin", "status": "Build the hybrid voice and research runtime.",
            "approved": True,
        })
        self.assertEqual(project["kind"], "project")

        with urlopen(self.base + "/api/memory", timeout=5) as response:
            vault = json.loads(response.read())
        self.assertTrue(vault["policy"]["user_approved_only"])
        self.assertTrue(vault["policy"]["memory_context_opt_in_required"])
        self.assertEqual(vault["preferences"][0]["value"], "Japanese")
        self.assertEqual(vault["projects"][0]["name"], "Merlin")

        with urlopen(self.base + "/api/events", timeout=5) as response:
            events = json.loads(response.read())["events"]
        encoded_events = json.dumps(events)
        self.assertNotIn("Japanese", encoded_events)
        self.assertNotIn("Build the hybrid voice", encoded_events)

        delete_pref = Request(self.base + "/api/memory/preferences?key=preferred_language",
                              method="DELETE")
        with urlopen(delete_pref, timeout=5) as response:
            self.assertTrue(json.loads(response.read())["deleted"])
        delete_project = Request(self.base + "/api/memory/projects?name=Merlin",
                                 method="DELETE")
        with urlopen(delete_project, timeout=5) as response:
            self.assertTrue(json.loads(response.read())["deleted"])
        with urlopen(self.base + "/api/memory", timeout=5) as response:
            empty = json.loads(response.read())
        self.assertEqual(empty["preferences"], [])
        self.assertEqual(empty["projects"], [])

    def test_memory_vault_rejects_secret_like_preference_keys(self):
        request = Request(self.base + "/api/memory/preferences",
            data=json.dumps({"key": "api_key", "value": "not-a-real-secret",
                             "approved": True}).encode(),
            headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(json.loads(caught.exception.read())["error"], "invalid_request")

if __name__ == "__main__":
    unittest.main()
