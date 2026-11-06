"""HTTP contract tests for the Merlin intent compiler preview endpoint."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

from python.merlin.app import EventStore, make_handler


class IntentCompileApiTests(unittest.TestCase):
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

    def post(self, payload):
        request = Request(
            self.base + "/api/intents/compile",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_compiles_reviewable_cross_domain_directive_without_execution(self):
        status, result = self.post({
            "intent": {
                "goal": "Create a continuous product demonstration",
                "domain": "video",
                "deliverable": "A resumable sequence of short clips",
                "constraints": ["Preserve character identity"],
                "success_criteria": ["Continuity is checked between segments"],
                "target_backend": "generic-video",
                "duration_seconds": 30,
            },
            "assets": [{
                "asset_id": "character-ref-1",
                "name": "Character reference",
                "kind": "image",
                "sha256": "a" * 64,
                "role": "identity_authority",
                "locator": "references/character.png",
            }],
            "continuity": {
                "checkpoint_id": "scene-001",
                "prior_state": "Character is standing beside the product.",
                "stable_entity_ids": ["character-1", "product-1"],
                "next_step": "Continue the demonstration without resetting the scene.",
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(result["schema"], "merlin-directive-bundle/1")
        self.assertEqual(result["bundle"]["domain"], "video")
        self.assertIn("character-ref-1", result["bundle"]["asset_ids"])
        self.assertIn("scene-001", result["bundle"]["directive"])
        self.assertEqual(len(result["bundle"]["directive_sha256"]), 64)
        self.assertEqual(result["storage_status"], "preview_only")
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["promotion_authorized"])
        events = self.store.recent(20)
        self.assertTrue(any(row["kind"] == "/api/intents/compile" for row in events))
        self.assertNotIn("Create a continuous product demonstration", json.dumps(events))

    def test_accepts_supported_non_media_domains(self):
        _, result = self.post({
            "goal": "Prove a matrix identity",
            "domain": "mathematics",
            "deliverable": "A Lean proof candidate",
        })
        self.assertEqual(result["bundle"]["domain"], "mathematics")
        self.assertFalse(result["execution_authorized"])

    def test_rejects_unsupported_domain(self):
        request = Request(
            self.base + "/api/intents/compile",
            data=json.dumps({
                "goal": "Do something",
                "domain": "unknown",
                "deliverable": "A result",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(json.loads(caught.exception.read())["error"], "invalid_request")

    def test_rejects_malformed_asset_and_non_string_constraints(self):
        for payload in (
            {"goal": "Build", "domain": "cad", "deliverable": "Model",
             "assets": [{"asset_id": "x", "name": "bad", "kind": "file", "sha256": "not-a-hash"}]},
            {"goal": "Build", "domain": "cad", "deliverable": "Model", "constraints": "not-a-list"},
            {"goal": "Build", "domain": "cad", "deliverable": "Model", "duration_seconds": True},
        ):
            request = Request(
                self.base + "/api/intents/compile",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 400)

    def test_capability_registry_exposes_preview_not_executor(self):
        with urlopen(self.base + "/api/capabilities", timeout=5) as response:
            capabilities = json.loads(response.read())["capabilities"]
        row = next(item for item in capabilities if item["id"] == "intent.compile.preview")
        self.assertEqual(row["status"], "AVAILABLE")
        self.assertIn("no persistence or external execution authority", row["evidence"])


if __name__ == "__main__":
    unittest.main()
