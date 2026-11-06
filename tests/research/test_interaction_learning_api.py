"""HTTP integration tests for Merlin's interaction learning loop."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

from python.merlin.app import EventStore, make_handler


class InteractionLearningApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.temp.name) / "events.sqlite3")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        request = Request(self.base + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_preferences_expose_metadata_only_defaults(self):
        _, result = self.request("GET", "/api/learning/preferences")
        prefs = result["preferences"]
        self.assertTrue(prefs["aggregate_telemetry"])
        self.assertTrue(prefs["explicit_feedback_learning"])
        self.assertFalse(prefs["personalization"])
        self.assertFalse(prefs["raw_conversation_retention"])
        self.assertFalse(prefs["automatic_self_modification"])

    def test_explicit_feedback_produces_aggregate_quality_proposal(self):
        for i in range(5):
            self.request("POST", "/api/interaction/feedback", {
                "event_id": f"fb-{i}", "session_id": "opaque-session-1",
                "domain": "research", "task_type": "literature_review",
                "outcome": "failure" if i < 3 else "success",
                "friction_code": "incomplete_answer" if i < 3 else None,
                "correction_type": "scope" if i < 3 else None,
                "satisfaction": 2 if i < 3 else 4,
                "free_text": "this raw text must not be stored",
            })
        _, result = self.request("GET", "/api/learning/improvements")
        self.assertEqual(result["feedback"]["sample_count"], 5)
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["type"], "task_quality")
        self.assertFalse(result["automatic_code_or_policy_changes"])
        self.assertFalse(result["raw_conversation_content_stored"])
        rows = self.store.by_kind("/api/interaction/feedback", 20)
        self.assertNotIn("this raw text must not be stored", json.dumps(rows))

    def test_feedback_learning_can_be_disabled(self):
        self.request("POST", "/api/learning/preferences", {
            "explicit_feedback_learning": False,
        })
        request = Request(
            self.base + "/api/interaction/feedback",
            data=json.dumps({
                "session_id": "session-2", "task_type": "chat", "outcome": "success",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(json.loads(caught.exception.read())["error"], "learning_disabled")

    def test_operational_telemetry_can_be_disabled(self):
        self.request("POST", "/api/learning/preferences", {
            "aggregate_telemetry": False,
        })
        before = len(self.store.by_kind("/api/telemetry/ingest", 10000))
        self.request("GET", "/health")
        after = len(self.store.by_kind("/api/telemetry/ingest", 10000))
        self.assertEqual(before, after)
        _, improvements = self.request("GET", "/api/learning/improvements")
        self.assertEqual(improvements["telemetry"]["sample_count"], 0)

    def test_feedback_can_be_deleted_by_opaque_session_id(self):
        for i in range(2):
            self.request("POST", "/api/interaction/feedback", {
                "event_id": f"delete-{i}", "session_id": "opaque-session-delete",
                "domain": "general", "task_type": "chat", "outcome": "success",
            })
        request = Request(
            self.base + "/api/interaction/feedback?session_id=opaque-session-delete",
            method="DELETE",
        )
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read())
        self.assertEqual(result["deleted_feedback_events"], 2)
        self.assertEqual(result["scope"], "categorical feedback for this opaque session only")
        _, improvements = self.request("GET", "/api/learning/improvements")
        self.assertEqual(improvements["feedback"]["sample_count"], 0)

    def test_unqualified_personalization_cannot_be_enabled(self):
        request = Request(
            self.base + "/api/learning/preferences",
            data=json.dumps({"personalization": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("not implemented or qualified", json.loads(caught.exception.read())["detail"])

    def test_invalid_feedback_is_rejected_without_raw_text_storage(self):
        request = Request(
            self.base + "/api/interaction/feedback",
            data=json.dumps({
                "session_id": "session-3", "task_type": "chat",
                "outcome": "excellent", "prompt": "secret text",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertNotIn("secret text", json.dumps(self.store.recent(20)))


if __name__ == "__main__":
    unittest.main()
