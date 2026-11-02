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

    def test_events_store_metadata_not_request_text(self):
        self.post("/api/ideonomy/rank", {"ideas": []})
        with urlopen(self.base + "/api/events", timeout=5) as response:
            payload = json.loads(response.read())
        self.assertGreaterEqual(len(payload["events"]), 1)
        self.assertNotIn("Mesh reduction", json.dumps(payload["events"]))


if __name__ == "__main__":
    unittest.main()
