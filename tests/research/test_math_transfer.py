"""Tests for mathematical transfer hypotheses."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from python.merlin.app import EventStore, make_handler
from python.merlin.math_transfer import preview_transfers, compare_measurements
from python.merlin.project_registry import MerlinRegistry


class MathTransferTests(unittest.TestCase):
    def test_graph_theory_generates_explicit_hypotheses_only(self):
        result = preview_transfers({
            "discovery_id": "DISC-001", "title": "Graph sparsification result",
            "structure_families": ["graph_theory"],
            "proof_state": "formal_proof_verified",
            "source_refs": ["sha256:" + "a" * 64],
            "assumptions": ["Finite graph"],
            "limitations": ["Degree constraints apply"],
        })
        self.assertEqual({x["target_subsystem"] for x in result["candidates"]},
                         {"knowledge_graph", "research_branching"})
        self.assertTrue(all(x["qualification_state"] == "hypothesis_only"
                            for x in result["candidates"]))
        self.assertFalse(result["promotion_authorized"])
        self.assertEqual(len(result["preview_sha256"]), 64)

    def test_target_filter_is_deterministic(self):
        discovery = {"discovery_id": "DISC-002", "title": "Optimization result",
                     "structure_families": ["optimization"]}
        first = preview_transfers(discovery, ["hermes_scheduler"])
        self.assertEqual(first, preview_transfers(discovery, ["hermes_scheduler"]))
        self.assertEqual([x["target_subsystem"] for x in first["candidates"]],
                         ["hermes_scheduler"])

    def test_unreviewed_claim_never_becomes_qualified(self):
        result = preview_transfers({
            "discovery_id": "DISC-003", "title": "Potential method",
            "structure_families": ["numerical_analysis"], "proof_state": "unreviewed",
        })
        self.assertTrue(all(x["proof_state"] == "unreviewed" for x in result["candidates"]))
        self.assertTrue(all(x["promotion_authorized"] is False for x in result["candidates"]))

    def test_invalid_claim_and_target_rejected(self):
        with self.assertRaises(ValueError):
            preview_transfers({"discovery_id": "x", "title": "x",
                                "structure_families": ["unknown_family"]})
        with self.assertRaises(ValueError):
            preview_transfers({"discovery_id": "x", "title": "x",
                               "structure_families": ["optimization"]}, ["unknown_target"])
        with self.assertRaises(ValueError):
            preview_transfers({"discovery_id": "x", "title": "x",
                               "structure_families": ["optimization"],
                               "proof_state": "proven_true"})

    def test_numeric_comparison_is_not_promotion(self):
        result = compare_measurements(
            {"metric": "runtime_ms", "value": 100, "preferred_direction": "lower"},
            {"metric": "runtime_ms", "value": 80, "preferred_direction": "lower"},
        )
        self.assertEqual(result["relative_improvement"], 0.2)
        self.assertTrue(result["numerically_better_on_this_metric"])
        self.assertFalse(result["promotion_authorized"])


class MathTransferApiTests(unittest.TestCase):
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
        request = Request(self.base + "/api/research/transfers/preview",
                          data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def test_api_persists_verified_transfer_preview(self):
        result = self.post({
            "project_id": "merlin-test-project",
            "discovery": {
                "discovery_id": "DISC-API-001", "title": "Information theory bound",
                "structure_families": ["information_theory"],
                "proof_state": "numerically_supported",
                "source_refs": ["paper:example"],
                "assumptions": ["Finite alphabet"],
                "limitations": ["Empirical evidence only"],
            },
        })
        self.assertEqual(result["storage_status"], "canonical_registry")
        self.assertTrue(result["artifact_ref"]["verified"])
        self.assertFalse(result["promotion_authorized"])
        self.assertEqual(result["preview"]["candidate_count"], 2)
        self.assertTrue(self.registry.verify_artifact(result["artifact_ref"]["sha256"]))
        self.assertTrue(any(x["kind"] == "/api/research/transfers/preview"
                            for x in self.store.recent(10)))

    def test_api_rejects_unknown_target_and_advertises_capability(self):
        request = Request(
            self.base + "/api/research/transfers/preview",
            data=json.dumps({
                "discovery": {"discovery_id": "DISC-API-002", "title": "Invalid target",
                              "structure_families": ["optimization"]},
                "requested_targets": ["unknown_target"],
            }).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        with urlopen(self.base + "/api/capabilities", timeout=5) as response:
            capabilities = json.loads(response.read())["capabilities"]
        self.assertIn("research.math_transfer.preview", {x["id"] for x in capabilities})


if __name__ == "__main__":
    unittest.main()
