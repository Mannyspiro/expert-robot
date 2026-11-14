import copy
import json
import shutil
import subprocess
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from merlin.project_registry import MerlinRegistry
from merlin.qualification_evidence_dag import (
    SnapshotHistory,
    build_snapshot,
    canonical_json,
    derive_statuses,
    make_node,
    node_id_for,
    prerequisite_first_order,
    transitive_dependents,
    validate_snapshot,
)


class QualificationEvidenceDagTests(unittest.TestCase):
    def setUp(self):
        self.source = make_node(
            "source_commit",
            {"repository": "Mannyspiro/expert-robot", "commit": "a" * 40},
            "1" * 64, "source-control", "qualified",
        )
        self.artifact = make_node(
            "artifact_version",
            {
                "project_id": "merlin", "logical_path": "research/candidate.lean",
                "version": 3, "digest": "2" * 64, "size_bytes": 128,
            },
            "3" * 64, "artifact-integrity", "qualified",
        )
        self.trust = make_node(
            "trust_root",
            {"authority_id": "oci-vault-prod", "version": "root-v4", "root_sha256": "4" * 64},
            "5" * 64, "independent-trust-root", "qualified",
        )
        self.attestation = make_node(
            "cace_attestation",
            {
                "statement_sha256": "6" * 64, "verifier_id": "cace-verifier-v2",
                "key_id": "artifact-ref-key-7", "purpose": "artifact-integrity",
                "source_repo": "Mannyspiro/expert-robot", "source_commit": "a" * 40,
                "artifact_id": "candidate-lean-3", "artifact_kind": "lean-source",
                "artifact_schema": "lean-source/1",
                "artifact_ref": {
                    "schema": "merlin-artifact-ref/1",
                    "project_id": "merlin", "logical_path": "research/candidate.lean",
                    "version": 3, "sha256": "2" * 64,
                },
            },
            "7" * 64, "cace-signed-attestation", "qualified",
        )
        self.verification = make_node(
            "verification_receipt",
            {
                "receipt_sha256": "8" * 64, "verifier_id": "cace-independent-verifier",
                "artifact_ref": {
                    "schema": "merlin-artifact-ref/1",
                    "project_id": "merlin", "logical_path": "research/candidate.lean",
                    "version": 3, "sha256": "2" * 64,
                },
            },
            "9" * 64, "cace-independent-verification", "qualified",
        )
        self.nodes = [
            self.source, self.artifact, self.trust,
            self.attestation, self.verification,
        ]
        self.edges = [
            {"dependent_node_id": self.artifact["node_id"],
             "prerequisite_node_id": self.source["node_id"], "relation": "derived_from"},
            {"dependent_node_id": self.attestation["node_id"],
             "prerequisite_node_id": self.artifact["node_id"], "relation": "attests"},
            {"dependent_node_id": self.verification["node_id"],
             "prerequisite_node_id": self.attestation["node_id"], "relation": "verifies"},
            {"dependent_node_id": self.verification["node_id"],
             "prerequisite_node_id": self.trust["node_id"], "relation": "verifies"},
        ]

    def test_snapshot_is_deterministic_under_node_and_edge_permutation(self):
        first = build_snapshot(self.nodes, self.edges)
        second = build_snapshot(
            list(reversed(self.nodes)), list(reversed(self.edges)),
        )
        self.assertEqual(first, second)
        self.assertEqual(validate_snapshot(first), first)
        self.assertEqual(
            first["snapshot_sha256"],
            __import__("hashlib").sha256(canonical_json({
                key: value for key, value in first.items() if key != "snapshot_sha256"
            })).hexdigest(),
        )

    def test_node_id_binds_full_identity_and_type(self):
        identity = {"repository": "Mannyspiro/expert-robot", "commit": "a" * 40}
        original = node_id_for("source_commit", identity)
        changed = node_id_for("source_commit", {**identity, "branch": "main"})
        other_type = node_id_for("workflow_run", {
            "repository": "Mannyspiro/expert-robot", "workflow_id": "ci.yml",
            "run_id": 7, "attempt": 1, "head_sha": "a" * 40,
            "conclusion": "success", "artifact_digest": "b" * 64,
        })
        self.assertNotEqual(original, changed)
        self.assertNotEqual(original, other_type)

    def test_rejects_duplicate_nodes_edges_and_unknown_endpoints(self):
        with self.assertRaisesRegex(ValueError, "duplicate evidence node"):
            build_snapshot(self.nodes + [copy.deepcopy(self.source)], self.edges)
        with self.assertRaisesRegex(ValueError, "duplicate evidence edge"):
            build_snapshot(self.nodes, self.edges + [copy.deepcopy(self.edges[0])])
        bad = copy.deepcopy(self.edges)
        bad[0]["prerequisite_node_id"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(ValueError, "unknown node"):
            build_snapshot(self.nodes, bad)

    def test_rejects_self_dependency_and_cycles(self):
        self_edge = [{
            "dependent_node_id": self.source["node_id"],
            "prerequisite_node_id": self.source["node_id"],
            "relation": "derived_from",
        }]
        with self.assertRaisesRegex(ValueError, "self-dependency"):
            build_snapshot(self.nodes, self_edge)
        cycle = self.edges + [{
            "dependent_node_id": self.source["node_id"],
            "prerequisite_node_id": self.artifact["node_id"],
            "relation": "derived_from",
        }]
        with self.assertRaisesRegex(ValueError, "cycle"):
            build_snapshot(self.nodes, cycle)

    def test_rejects_tampered_snapshot_digest_and_nonfinite_identity(self):
        snapshot = build_snapshot(self.nodes, self.edges)
        tampered = copy.deepcopy(snapshot)
        tampered["nodes"][0]["evidence_class"] = "forged"
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_snapshot(tampered)
        with self.assertRaisesRegex(ValueError, "floating-point"):
            node_id_for("source_commit", {
                "repository": "repo", "commit": "a" * 40, "score": float("nan"),
            })
        with self.assertRaisesRegex(ValueError, "floating-point"):
            canonical_json({"score": 1.25})
        with self.assertRaisesRegex(ValueError, "safe range"):
            canonical_json({"run_id": 2 ** 60})

    def test_invalidation_is_transitive_and_selective(self):
        snapshot = build_snapshot(self.nodes, self.edges)
        source_dependents = transitive_dependents(snapshot, [self.source["node_id"]])
        self.assertEqual(
            set(source_dependents),
            {self.artifact["node_id"], self.attestation["node_id"], self.verification["node_id"]},
        )
        trust_dependents = transitive_dependents(snapshot, [self.trust["node_id"]])
        self.assertEqual(trust_dependents, [self.verification["node_id"]])
        with self.assertRaisesRegex(ValueError, "non-empty subset"):
            transitive_dependents(snapshot, ["sha256:" + "f" * 64])

    def test_revoked_trust_invalidates_only_dependent_verification_status(self):
        nodes = copy.deepcopy(self.nodes)
        for node in nodes:
            if node["node_id"] == self.trust["node_id"]:
                node["status"] = "revoked"
        snapshot = build_snapshot(nodes, self.edges)
        statuses = derive_statuses(snapshot)
        self.assertEqual(statuses[self.trust["node_id"]], "revoked")
        self.assertEqual(statuses[self.verification["node_id"]], "revoked")
        self.assertEqual(statuses[self.artifact["node_id"]], "qualified")
        self.assertEqual(statuses[self.attestation["node_id"]], "qualified")

    def test_cancelled_or_unqualified_prerequisite_cannot_qualify_dependent(self):
        nodes = copy.deepcopy(self.nodes)
        for node in nodes:
            if node["node_id"] == self.source["node_id"]:
                node["status"] = "unqualified"
        statuses = derive_statuses(build_snapshot(nodes, self.edges))
        self.assertEqual(statuses[self.artifact["node_id"]], "unqualified")
        self.assertEqual(statuses[self.attestation["node_id"]], "unqualified")
        self.assertEqual(statuses[self.verification["node_id"]], "unqualified")



    def test_rejects_incomplete_cace_source_binding_and_malformed_status(self):
        identity = {
            "statement_sha256": "6" * 64, "verifier_id": "cace-verifier-v2",
            "key_id": "artifact-ref-key-7", "purpose": "artifact-integrity",
            "source_repo": "Mannyspiro/expert-robot", "source_commit": "a" * 40,
            "artifact_id": "candidate-lean-3", "artifact_kind": "lean-source",
            "artifact_schema": "lean-source/1",
            "artifact_ref": {
                "schema": "merlin-artifact-ref/1", "project_id": "merlin",
                "logical_path": "research/candidate.lean", "version": 3,
                "sha256": "2" * 64,
            },
        }
        incomplete = dict(identity)
        incomplete.pop("source_commit")
        with self.assertRaisesRegex(ValueError, "source_commit"):
            node_id_for("cace_attestation", incomplete)
        with self.assertRaisesRegex(ValueError, "unknown evidence status"):
            make_node("source_commit", {
                "repository": "repo", "commit": "a" * 40,
            }, "1" * 64, "source", [])



    def test_independent_node_reference_reproduces_snapshot_digest(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is not installed")
        snapshot = build_snapshot(self.nodes, self.edges)
        script = Path(__file__).resolve().parents[1] / "scripts" / "verify_qualification_evidence_dag.js"
        result = subprocess.run(
            [node, str(script)], input=canonical_json(snapshot),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        receipt = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(receipt["status"], "verified")
        self.assertEqual(receipt["snapshot_sha256"], snapshot["snapshot_sha256"])
        self.assertEqual(receipt["node_count"], len(self.nodes))
        self.assertEqual(receipt["edge_count"], len(self.edges))

        tampered = copy.deepcopy(snapshot)
        tampered["nodes"][0]["record_sha256"] = "f" * 64
        rejected = subprocess.run(
            [node, str(script)], input=canonical_json(tampered),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("snapshot SHA-256 mismatch", rejected.stderr.decode("utf-8"))
        noncanonical = canonical_json(snapshot).decode("utf-8").replace('"version":3', '"version":3.0', 1)
        rejected_float = subprocess.run(
            [node, str(script)], input=noncanonical.encode("utf-8"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertNotEqual(rejected_float.returncode, 0)
        self.assertIn("input is not canonical JSON", rejected_float.stderr.decode("utf-8"))

    def test_topological_order_places_prerequisites_before_dependents(self):
        snapshot = build_snapshot(self.nodes, self.edges)
        order = prerequisite_first_order(snapshot)
        positions = {node_id: index for index, node_id in enumerate(order)}
        for edge in self.edges:
            self.assertLess(
                positions[edge["prerequisite_node_id"]],
                positions[edge["dependent_node_id"]],
            )




class QualificationEvidenceDagSnapshotHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = MerlinRegistry(Path(self.temp.name) / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.history = SnapshotHistory(self.registry.db_path)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def snapshot(record_digest):
        node = make_node(
            "source_commit",
            {"repository": "Mannyspiro/expert-robot", "commit": "a" * 40},
            record_digest, "source-control", "qualified",
        )
        return build_snapshot([node], [])

    def test_append_is_atomic_idempotent_and_retrievable(self):
        snapshot = self.snapshot("1" * 64)
        first = self.history.append(snapshot)
        replay = self.history.append(snapshot)
        self.assertEqual(first, replay)
        self.assertEqual(self.history.get(snapshot["snapshot_sha256"]), snapshot)
        self.assertEqual(self.history.get_by_sequence(first), snapshot)
        self.assertEqual(len(self.history.list_history()), 1)

    def test_snapshot_history_rejects_update_and_delete(self):
        snapshot = self.snapshot("2" * 64)
        self.history.append(snapshot)
        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite3.connect(self.registry.db_path) as db:
                db.execute(
                    "UPDATE qualification_evidence_snapshots SET snapshot_json='{}' "
                    "WHERE snapshot_sha256=?",
                    (snapshot["snapshot_sha256"],),
                )
        with self.assertRaises(sqlite3.IntegrityError):
            with sqlite3.connect(self.registry.db_path) as db:
                db.execute(
                    "DELETE FROM qualification_evidence_snapshots WHERE snapshot_sha256=?",
                    (snapshot["snapshot_sha256"],),
                )

    def test_concurrent_appends_preserve_unique_immutable_history(self):
        snapshots = [self.snapshot(f"{index:064x}") for index in range(1, 17)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            sequences = list(pool.map(self.history.append, snapshots))
        self.assertEqual(len(set(sequences)), len(snapshots))
        rows = self.history.list_history(limit=100)
        self.assertEqual(len(rows), len(snapshots))
        self.assertEqual(
            [row["sequence"] for row in rows],
            sorted(row["sequence"] for row in rows),
        )
        for snapshot in snapshots:
            self.assertEqual(
                self.history.get(snapshot["snapshot_sha256"]), snapshot,
            )

    def test_stored_snapshot_is_revalidated_on_read(self):
        snapshot = self.snapshot("3" * 64)
        self.history.append(snapshot)
        with sqlite3.connect(self.registry.db_path) as db:
            db.execute("DROP TRIGGER qualification_evidence_snapshots_no_update")
            db.execute(
                "UPDATE qualification_evidence_snapshots SET snapshot_json='{}' "
                "WHERE snapshot_sha256=?",
                (snapshot["snapshot_sha256"],),
            )
        with self.assertRaises(ValueError):
            self.history.get(snapshot["snapshot_sha256"])

    def test_requires_existing_merlin_registry_database(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(FileNotFoundError):
                SnapshotHistory(Path(other) / "missing.sqlite3")
            unrelated = Path(other) / "unrelated.sqlite3"
            sqlite3.connect(unrelated).close()
            with self.assertRaisesRegex(ValueError, "canonical MerlinRegistry"):
                SnapshotHistory(unrelated)

    def test_history_limit_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            self.history.list_history(0)
        with self.assertRaisesRegex(ValueError, "limit"):
            self.history.list_history(True)


if __name__ == "__main__":
    unittest.main()
