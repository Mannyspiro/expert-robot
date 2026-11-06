import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from merlin.cace_adapter import CaceVerificationAdapter
from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.knowledge_graph import MerlinKnowledgeGraph


_TEST_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
_TEST_PUBLIC_PEM = _TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("ascii")
_TEST_RAW_PUBLIC = _TEST_PRIVATE_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
_TEST_KEY_ID = "ed25519:" + hashlib.sha256(_TEST_RAW_PUBLIC).hexdigest()
_TEST_TRUST = {_TEST_KEY_ID: _TEST_PUBLIC_PEM}
_CACE_DOMAIN = b"CACE:SIGNED-ATTESTATION:v1\\0"


def signed_attestation(claim_id, bundle_sha256, bindings, purpose="independent-reproduction"):
    statement = {
        "schema": "cace-attestation-statement-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "verifier_id": "cace:independent-kernel",
        "verifier_key_id": _TEST_KEY_ID,
        "claim_id": claim_id,
        "bundle_sha256": bundle_sha256,
        "created_at_utc": "2026-11-06T19:00:00Z",
        "purpose": purpose,
        "bindings": dict(bindings),
    }
    signing_bytes = _CACE_DOMAIN + json.dumps(
        statement, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "schema": "cace-signed-attestation-v1",
        "signature_algorithm": "ed25519",
        "proof_effect": "none",
        "statement_sha256": hashlib.sha256(signing_bytes).hexdigest(),
        "statement": statement,
        "public_key_pem": _TEST_PUBLIC_PEM,
        "signature_b64": __import__("base64").b64encode(
            _TEST_PRIVATE_KEY.sign(signing_bytes)
        ).decode("ascii"),
    }


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
        "signed_attestation": signed_attestation(
            request["theorem"], request["artifact_sha256"],
            {
                "repository": request["repository"],
                "commit_sha": request["commit_sha"],
                "theorem": request["theorem"],
                "tool_version": request["tool_version"],
            },
        ),
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
            registry=self.registry, outbox=self.outbox, trusted_verifier_keys=_TEST_TRUST,
        )
        result = adapter.verify(project_id="merlin",repository="Mannyspiro/expert-robot",
                                commit_sha=self.commit,artifact_sha256=self.artifact,
                                theorem="MyNamespace.target",requester_id="merlin-agent",tool_version="Lean 4.32.1")
        self.assertEqual(result["verification_status"],"verified")
        self.assertFalse(result["promotion_authority"])
        self.assertTrue(self.registry.verify_artifact(result["receipt_artifact_sha256"]))
        self.assertGreaterEqual(self.outbox.counts()["pending"],4)

    def test_wrong_revision_or_non_independent_verifier_rejected(self):
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request, commit_sha="c"*40),
            registry=self.registry,outbox=self.outbox,trusted_verifier_keys=_TEST_TRUST,
        )
        with self.assertRaisesRegex(ValueError,"different repository revision"):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent",tool_version="Lean 4.32.1")

    def test_unverified_or_incomplete_proof_never_promoted(self):
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request, axiom_audit_passed=False),
            registry=self.registry,outbox=self.outbox,trusted_verifier_keys=_TEST_TRUST,
        )
        with self.assertRaisesRegex(ValueError,"passing axiom audit"):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent",tool_version="Lean 4.32.1")

    def test_unregistered_input_artifact_is_rejected_before_transport(self):
        called = []
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: called.append(request),
            registry=self.registry, outbox=self.outbox, trusted_verifier_keys=_TEST_TRUST,
        )
        with self.assertRaisesRegex(ValueError, "absent from the registry"):
            adapter.verify(project_id="merlin", repository="owner/repo",
                           commit_sha=self.commit, artifact_sha256="c"*64,
                           theorem="T", requester_id="merlin-agent",tool_version="Lean 4.32.1")
        self.assertEqual(called, [])

    def test_receipt_is_linked_to_subject_artifact_in_canonical_graph(self):
        graph = MerlinKnowledgeGraph(Path(self.temp.name) / "graph.sqlite3")
        adapter = CaceVerificationAdapter(
            verify_transport=lambda request: signed_receipt(request),
            registry=self.registry, outbox=self.outbox, graph=graph, trusted_verifier_keys=_TEST_TRUST,
        )
        result = adapter.verify(project_id="merlin", repository="owner/repo",
                                commit_sha=self.commit, artifact_sha256=self.artifact,
                                theorem="MyNamespace.target", requester_id="merlin-agent",
                                tool_version="Lean 4.32.1", logical_path="proofs/target.lean")
        snapshot = graph.export_snapshot()
        self.assertTrue(any(node["node_id"] == result["receipt_graph_node_id"]
                            for node in snapshot["nodes"]))
        self.assertTrue(any(edge["relation"] == "reviews" and
                            edge["source_id"] == result["receipt_graph_node_id"]
                            for edge in snapshot["edges"]))

    def test_generic_cace_artifact_receipt_binds_cad_or_simulation_output(self):
        graph = MerlinKnowledgeGraph(Path(self.temp.name) / "artifact-graph.sqlite3")
        artifact_path = "engineering/assembly.json"
        artifact_digest = self.registry.put_artifact(
            "merlin", artifact_path, b'{"schema":"merlin-freecad-document-mesh/1"}',
            "application/json",
        )
        def transport(request):
            receipt = {
                "schema": "cace-artifact-verification/1",
                "repository": request["repository"],
                "commit_sha": request["commit_sha"],
                "artifact_sha256": request["artifact_sha256"],
                "artifact_kind": request["artifact_kind"],
                "artifact_schema": request["artifact_schema"],
                "logical_path": request["logical_path"],
                "tool_identity": request["tool_identity"],
                "verifier_id": "cace:independent-kernel",
                "source_commit_verified": True,
                "artifact_digest_verified": True,
                "artifact_schema_validated": True,
                "artifact_content_verified": True,
                "verification_status": "verified",
                "signed_attestation": signed_attestation(
                    "artifact:" + request["artifact_kind"],
                    request["artifact_sha256"],
                    {
                        "repository": request["repository"],
                        "commit_sha": request["commit_sha"],
                        "artifact_kind": request["artifact_kind"],
                        "artifact_schema": request["artifact_schema"],
                        "logical_path": request["logical_path"],
                        "tool_identity": request["tool_identity"],
                    },
                    purpose="artifact-integrity",
                ),
            }
            body = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            receipt["receipt_sha256"] = hashlib.sha256(body.encode()).hexdigest()
            return receipt
        adapter = CaceVerificationAdapter(
            verify_transport=transport, registry=self.registry,
            outbox=self.outbox, graph=graph,
        )
        result = adapter.verify_artifact(
            project_id="merlin", repository="owner/repo", commit_sha=self.commit,
            artifact_sha256=artifact_digest, artifact_kind="cad_assembly",
            artifact_schema="merlin-freecad-document-mesh/1",
            requester_id="merlin-agent", logical_path=artifact_path,
            tool_identity="FreeCAD 1.0.0",
        )
        self.assertEqual(result["verification_status"], "verified")
        self.assertFalse(result["promotion_authority"])
        self.assertTrue(self.registry.verify_artifact(result["receipt_artifact_sha256"]))
        self.assertTrue(any(edge["relation"] == "reviews"
                            for edge in graph.export_snapshot()["edges"]))

    def test_missing_cace_transport_fails_closed(self):
        adapter = CaceVerificationAdapter(verify_transport=None,
                                          registry=self.registry,outbox=self.outbox)
        with self.assertRaises(RuntimeError):
            adapter.verify(project_id="merlin",repository="owner/repo",
                           commit_sha=self.commit,artifact_sha256=self.artifact,
                           theorem="T",requester_id="merlin-agent",tool_version="Lean 4.32.1")


if __name__ == "__main__":
    unittest.main()
