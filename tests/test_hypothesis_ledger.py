import tempfile
import unittest
from pathlib import Path

from merlin.hypothesis_ledger import HypothesisLedger


class HypothesisLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = HypothesisLedger(Path(self.temp.name) / "hypotheses.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_new_hypothesis_starts_proposed_and_persists(self):
        h = self.ledger.create(
            "H-001", "A spectral invariant is preserved under this transform.",
            mathematical_objects=("graph Laplacian", "linear operator"),
            relation="invariant_under",
            assumptions=("The graph is finite and undirected.",),
        )
        self.assertEqual(h.status, "proposed")
        self.assertEqual(self.ledger.get("H-001").mathematical_objects[0], "graph Laplacian")

    def test_status_requires_matching_evidence(self):
        self.ledger.create("H-002", "A conjectured bound holds.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-002", "literature_checked")
        self.ledger.add_evidence("H-002", "source", "A public paper discusses the bound.",
                                 source_url="https://example.org/paper")
        self.assertEqual(self.ledger.set_status("H-002", "literature_checked").status,
                         "literature_checked")

    def test_formal_verification_requires_proof_hash(self):
        self.ledger.create("H-003", "A lemma follows from stated assumptions.")
        self.ledger.add_evidence("H-003", "proof", "Lean theorem checked.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-003", "formally_verified")
        self.ledger.add_evidence("H-003", "proof", "Lean build artifact.",
                                 artifact_hash="0123456789abcdef0123456789abcdef")
        self.assertEqual(self.ledger.set_status("H-003", "formally_verified").status,
                         "formally_verified")

    def test_refutation_requires_counterexample(self):
        self.ledger.create("H-004", "Every tested graph has this property.")
        with self.assertRaises(ValueError):
            self.ledger.set_status("H-004", "refuted")
        self.ledger.add_evidence("H-004", "counterexample",
                                 "A finite graph violates the universal claim.")
        self.assertEqual(self.ledger.set_status("H-004", "refuted").status, "refuted")

    def test_conditional_status_requires_assumptions(self):
        self.ledger.create("H-005", "A result holds conditionally.")
        self.ledger.add_evidence("H-005", "assumption", "Compactness is assumed.")
        self.assertEqual(self.ledger.set_status("H-005", "conditional").status, "conditional")


    def test_idempotency_key_reuses_exact_evidence_and_rejects_conflicts(self):
        self.ledger.create("H-007", "A deterministic claim.")
        first = self.ledger.add_evidence(
            "H-007", "source", "Exact source.", artifact_hash="a" * 64,
            idempotency_key="evidence-key-1",
        )
        replay = self.ledger.add_evidence(
            "H-007", "source", "Exact source.", artifact_hash="a" * 64,
            idempotency_key="evidence-key-1",
        )
        self.assertEqual(first.evidence_id, replay.evidence_id)
        self.assertEqual(len(self.ledger.evidence("H-007")), 1)
        with self.assertRaisesRegex(ValueError, "different evidence"):
            self.ledger.add_evidence(
                "H-007", "source", "Different source.", artifact_hash="a" * 64,
                idempotency_key="evidence-key-1",
            )

    def test_legacy_ledger_schema_migrates_idempotency_column(self):
        import sqlite3
        path = Path(self.temp.name) / "legacy.sqlite3"
        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE hypotheses (
                    hypothesis_id TEXT PRIMARY KEY,
                    claim TEXT NOT NULL,
                    mathematical_objects_json TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE hypothesis_evidence (
                    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    description TEXT NOT NULL,
                    source_url TEXT NOT NULL DEFAULT '',
                    artifact_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
        migrated = HypothesisLedger(path)
        migrated.create("H-008", "Migrated claim.")
        first = migrated.add_evidence(
            "H-008", "source", "Migrated evidence.", artifact_hash="b" * 64,
            idempotency_key="legacy-migration-key",
        )
        replay = migrated.add_evidence(
            "H-008", "source", "Migrated evidence.", artifact_hash="b" * 64,
            idempotency_key="legacy-migration-key",
        )
        self.assertEqual(first.evidence_id, replay.evidence_id)
        with sqlite3.connect(path) as db:
            columns = {row[1] for row in db.execute("PRAGMA table_info(hypothesis_evidence)")}
        self.assertIn("idempotency_key", columns)

    def test_rejects_non_https_source(self):
        self.ledger.create("H-006", "Claim.")
        with self.assertRaises(ValueError):
            self.ledger.add_evidence("H-006", "source", "Private or unsafe link.",
                                     source_url="http://example.org")


if __name__ == "__main__":
    unittest.main()
