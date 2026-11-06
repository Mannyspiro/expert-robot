"""Canonical project-registry persistence tests for intent directive bundles."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from python.merlin.app import EventStore, make_handler
from python.merlin.project_registry import MerlinRegistry


class IntentRegistryPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin-test-project", "Merlin test project")
        self.store = EventStore(root / "events.sqlite3")
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(self.store, canonical_registry=self.registry),
        )
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
            return json.loads(response.read())

    def test_persists_directive_as_verified_content_addressed_registry_artifact(self):
        result = self.post({
            "project_id": "merlin-test-project",
            "goal": "Create an engineering drawing",
            "domain": "engineering",
            "deliverable": "A reviewable drawing directive",
        })
        self.assertEqual(result["storage_status"], "canonical_registry")
        ref = result["artifact_ref"]
        self.assertTrue(ref["verified"])
        self.assertEqual(ref["project_id"], "merlin-test-project")
        self.assertTrue(self.registry.verify_artifact(ref["sha256"]))
        inventory = self.registry.inventory("merlin-test-project")
        self.assertEqual(len(inventory["artifacts"]), 1)
        artifact = inventory["artifacts"][0]
        self.assertEqual(artifact["digest"], ref["sha256"])
        self.assertEqual(artifact["logical_path"], ref["logical_path"])
        blob = (self.registry.root / self.registry.blobs.relative_to(self.registry.root)
                / ref["sha256"][:2] / ref["sha256"][2:])
        stored = json.loads(blob.read_text(encoding="utf-8"))
        self.assertEqual(stored["directive_sha256"], result["bundle"]["directive_sha256"])

    def test_repeated_identical_compile_is_idempotent_in_registry(self):
        payload = {
            "project_id": "merlin-test-project",
            "goal": "Prove a theorem",
            "domain": "mathematics",
            "deliverable": "A proof directive",
        }
        first = self.post(payload)
        second = self.post(payload)
        self.assertEqual(first["artifact_ref"]["sha256"], second["artifact_ref"]["sha256"])
        self.assertEqual(len(self.registry.inventory("merlin-test-project")["artifacts"]), 1)

    def test_asset_trust_is_derived_from_registry_not_caller_assertion(self):
        asset_digest = self.registry.put_artifact(
            "merlin-test-project", "references/source.txt", b"registry verified source")
        result = self.post({
            "project_id": "merlin-test-project",
            "goal": "Analyze the supplied source",
            "domain": "research",
            "deliverable": "A provenance-bound research directive",
            "assets": [{
                "asset_id": "source-1", "name": "Source file", "kind": "text",
                "sha256": asset_digest, "authority": "caller_claims_official",
            }],
        })
        self.assertEqual(result["storage_status"], "canonical_registry")
        self.assertIn("authority=canonical_registry_verified", result["bundle"]["directive"])
        self.assertNotIn("caller_claims_official", result["bundle"]["directive"])

    def test_unregistered_asset_digest_is_rejected_for_persisted_directive(self):
        request = Request(
            self.base + "/api/intents/compile",
            data=json.dumps({
                "project_id": "merlin-test-project",
                "goal": "Analyze a source",
                "domain": "research",
                "deliverable": "A report",
                "assets": [{
                    "asset_id": "unverified", "name": "Unverified source",
                    "kind": "text", "sha256": "b" * 64,
                }],
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("verified artifact", json.loads(caught.exception.read())["detail"])

    def test_unknown_project_is_rejected_without_creating_project(self):
        request = Request(
            self.base + "/api/intents/compile",
            data=json.dumps({
                "project_id": "caller-invented-project",
                "goal": "Research",
                "domain": "research",
                "deliverable": "A research plan",
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(json.loads(caught.exception.read())["error"], "invalid_request")
        with self.assertRaises(KeyError):
            self.registry.inventory("caller-invented-project")


if __name__ == "__main__":
    unittest.main()
