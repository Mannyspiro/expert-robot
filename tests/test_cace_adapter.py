import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from merlin.cace_adapter import CaceVerificationAdapter
from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.knowledge_graph import MerlinKnowledgeGraph


def signed_receipt(request, **overrides):
    receipt = {
        "schema": "cace-independent-verification/1",
        "repository": request["repository"],
        "commit_sha": request["commit_sha"],
        "artifact_sha256": request["artifact_sha256"],
        "theorem": request["theorem"],
        "verifier_id": "cace:independent-kernel",
        "source_commit_verified": True,
        "artifact_digest_verified": True,
        "verification_status": "verified",
        "kernel_checked": True,
        "axiom_audit_passed": True,
        "contains_sorry": False,
        "exact_target_declaration": True,
        "axiom_dependencies": ["propext"],
    }
    receipt.update(overrides)
    body = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    receipt["receipt_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    return receipt


class CaceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.outbox = MerlinEventOutbox(root / "outbox.sqlite3")
        self.commit = "a" * 40
        self.artifact_bytes = b"theorem target : True := True\\n"
        self.artifact = self.registry.put_artifact(
            "merlin", "proofs/target.lean", self.artifact_bytes,
            "text/x-lean",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_verified_receipt_is_bound_and_stored_without_promotion(self):
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request),
            registry=self.registry, outbox=self.outbox,
        )
        result = adapter.verify(project_id="merlin",repository="Mannyspiro/expert-robot",
                                commit_sha=self.commit,artifact_sha256=self.artifact,
                                theorem="MyNamespace.target",requester_id="merlin-agent")
        self.assertEqual(result["verification_status"],"verified")
        self.assertFalse(result["promotion_authority"])
        self.assertTrue(self.registry.verify_artifact(result["receipt_artifact_sha256"]))
        self.assertGreaterEqual(self.outbox.counts()["pending"],4)

    def test_wrong_revision_or_non_independent_verifier_rejected(self):
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request, commit_sha="c"*40),
            registry=self.registry,outbox=self.outbox,
        )
        with self.assertRaisesRegex(ValueError,"different repository revision"):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent")

    def test_unverified_or_incomplete_proof_never_promoted(self):
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request, axiom_audit_passed=False),
            registry=self.registry,outbox=self.outbox,
        )
        with self.assertRaisesRegex(ValueError,"passing axiom audit"):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent")

    def test_unregistered_input_artifact_is_rejected_before_transport(self):
        called = []
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: called.append(request),
            registry=self.registry, outbox=self.outbox,
        )
        with self.assertRaisesRegex(ValueError, "absent from the registry"):
            adapter.verify(project_id="merlin", repository="owner/repo",
                           commit_sha=self.commit, artifact_sha256="c"*64,
                           theorem="T", requester_id="merlin-agent")
        self.assertEqual(called, [])

    def test_receipt_is_linked_to_subject_artifact_in_canonical_graph(self):
        graph = MerlinKnowledgeGraph(Path(self.temp.name) / "graph.sqlite3")
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request),
            registry=self.registry, outbox=self.outbox, graph=graph,
        )
        result = adapter.verify(project_id="merlin", repository="owner/repo",
                                commit_sha=self.commit, artifact_sha256=self.artifact,
                                theorem="MyNamespace.target", requester_id="merlin-agent",
                                logical_path="proofs/target.lean")
        snapshot = graph.export_snapshot()
        self.assertTrue(any(node["node_id"] == result["receipt_graph_node_id"]
                            for node in snapshot["nodes"]))
        self.assertTrue(any(edge["relation"] == "reviews" and
                            edge["source_id"] == result["receipt_graph_node_id"]
                            for edge in snapshot["edges"]))

    def test_missing_cace_transport_fails_closed(self):
        adapter = CaceVerificationAdapter(verify_transport=None,
                                          registry=self.registry,outbox=self.outbox)
        with self.assertRaises(RuntimeError):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent")


if __name__ == "__main__":
    unittest.main()
