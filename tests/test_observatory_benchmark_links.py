import tempfile
import unittest
from pathlib import Path

from merlin.observatory_integrity import verify_database, verify_theorem_dag
from merlin.proof_observatory import ProofObservatory, canonical_json, sha256_text


def receipt():
    payload = {
        "schema": "merlin-cross-domain-benchmark-receipt-v1",
        "source_commit": "a" * 40,
        "domains": {
            "geometry": {"passed": True},
            "xmg": {"passed": True},
            "equation_atlas": {"passed": True},
            "cad": {"passed": True},
        },
        "all_passed": True,
    }
    payload["receipt_sha256"] = sha256_text(canonical_json(payload))
    return payload


def dag():
    payload = {
        "schema": "merlin-theorem-dependency-dag-v1",
        "nodes": [
            {"id": "MathAI.Geometry.frame_identity", "domain": "geometry", "tags": [],
             "dependencies": []},
            {"id": "MathAI.XMG.double_negation", "domain": "algebra", "tags": ["xmg"],
             "dependencies": []},
            {"id": "MathAI.EquationAtlas.square_nonnegative", "domain": "algebra",
             "tags": ["equation_atlas"], "dependencies": []},
            {"id": "MathAI.WireQualification.current_bound", "domain": "electrical",
             "tags": [], "dependencies": []},
        ],
        "node_count": 4,
        "edge_count": 0,
        "edges": [],
        "topological_order_dependencies_first": [
            "MathAI.Geometry.frame_identity", "MathAI.XMG.double_negation",
            "MathAI.EquationAtlas.square_nonnegative", "MathAI.WireQualification.current_bound"
        ],
    }
    payload["dag_sha256"] = sha256_text(canonical_json(payload))
    return payload


class ObservatoryBenchmarkLinkTests(unittest.TestCase):
    def test_receipt_is_stored_and_linked_to_dag_and_engineering_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofObservatory(Path(tmp) / "observatory.sqlite3")
            evidence = receipt()
            graph = dag()
            revision = "b" * 64
            links = store.record_benchmark_theorem_links(
                evidence, graph, "fixture-project", revision,
                {
                    "geometry": ["cartesian-frame"],
                    "xmg": ["glyph:double-negation"],
                    "equation_atlas": ["equation:square-nonnegative"],
                    "cad": ["assembly:observatory-fixture"],
                },
            )
            self.assertEqual(len(links), 4)
            self.assertEqual(len(store.links_for_theorem("MathAI.Geometry.frame_identity")), 1)
            self.assertTrue(store.verify_chain())
            store.close()

    def test_rejects_tampered_benchmark_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofObservatory(Path(tmp) / "observatory.sqlite3")
            evidence = receipt()
            evidence["domains"]["geometry"]["passed"] = False
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                store.record_benchmark_receipt(evidence)
            store.close()

    def test_rejects_tampered_theorem_dag(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProofObservatory(Path(tmp) / "observatory.sqlite3")
            graph = dag()
            graph["nodes"][0]["domain"] = "tampered"
            with self.assertRaisesRegex(ValueError, "DAG SHA-256 mismatch"):
                store.record_benchmark_theorem_links(
                    receipt(), graph, "fixture-project", "b" * 64, {"geometry": ["frame"]},
                )
            store.close()

    def test_independent_integrity_verifier_accepts_valid_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observatory.sqlite3"
            store = ProofObservatory(path)
            evidence = receipt()
            store.record_benchmark_receipt(evidence)
            store.record_benchmark_theorem_links(
                evidence, dag(), "fixture-project", "b" * 64, {"geometry": ["frame"]},
            )
            store.close()
            report = verify_database(path, dag())
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["counts"]["benchmark_receipts"], 1)

    def test_independent_verifier_detects_receipt_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observatory.sqlite3"
            store = ProofObservatory(path)
            store.record_benchmark_receipt(receipt())
            store.db.execute("UPDATE benchmark_receipts SET payload=?", (canonical_json({
                **receipt(), "all_passed": False
            }),))
            store.db.commit()
            store.close()
            report = verify_database(path)
            self.assertFalse(report["ok"])
            self.assertTrue(any("benchmark receipt" in item and "digest mismatch" in item
                                for item in report["errors"]))

    def test_independent_verifier_detects_dangling_receipt_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observatory.sqlite3"
            store = ProofObservatory(path)
            evidence = receipt()
            store.record_benchmark_theorem_links(
                evidence, dag(), "fixture-project", "b" * 64, {"geometry": ["frame"]},
            )
            store.db.execute("DELETE FROM benchmark_receipts")
            store.db.commit()
            store.close()
            report = verify_database(path)
            self.assertFalse(report["ok"])
            self.assertTrue(any("dangling benchmark receipt" in item for item in report["errors"]))

    def test_independent_verifier_detects_link_payload_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observatory.sqlite3"
            store = ProofObservatory(path)
            store.record_benchmark_theorem_links(
                receipt(), dag(), "fixture-project", "b" * 64, {"geometry": ["frame"]},
            )
            store.db.execute("UPDATE cross_domain_links SET payload=?", (canonical_json({
                "theorem_id": "tampered"
            }),))
            store.db.commit()
            store.close()
            report = verify_database(path)
            self.assertFalse(report["ok"])
            self.assertTrue(any("cross-domain link" in item and "digest mismatch" in item
                                for item in report["errors"]))

    def test_engineering_hash_preimage_limit_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "observatory.sqlite3"
            store = ProofObservatory(path)
            store.close()
            report = verify_database(path)
            self.assertIn("preimages not stored", report["engineering_revision_hashes"])

    def test_dag_integrity_checks_dependency_graph(self):
        graph = dag()
        graph["nodes"][0]["dependencies"] = ["missing"]
        errors = verify_theorem_dag(graph)
        self.assertTrue(any("digest mismatch" in item for item in errors))
        self.assertTrue(any("dangling theorem dependency" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
