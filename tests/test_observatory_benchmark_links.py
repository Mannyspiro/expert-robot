import tempfile
import unittest
from pathlib import Path

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
            {"id": "MathAI.Geometry.frame_identity", "domain": "geometry", "tags": []},
            {"id": "MathAI.XMG.double_negation", "domain": "algebra", "tags": ["xmg"]},
            {"id": "MathAI.EquationAtlas.square_nonnegative", "domain": "algebra",
             "tags": ["equation_atlas"]},
            {"id": "MathAI.WireQualification.current_bound", "domain": "electrical", "tags": []},
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
                evidence,
                graph,
                "fixture-project",
                revision,
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
                    receipt(), graph, "fixture-project", "b" * 64,
                    {"geometry": ["frame"]},
                )
            store.close()


if __name__ == "__main__":
    unittest.main()
