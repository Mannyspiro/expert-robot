import copy
import hashlib
import json
import random
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
        with self.assertRaisesRegex(ValueError, "non-finite"):
            node_id_for("source_commit", {
                "repository": "repo", "commit": "a" * 40, "score": float("nan"),
            })

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



    def test_independent_hash_and_randomized_permutation_invariants(self):
        for seed in range(25):
            rng = random.Random(seed)
            nodes = []
            for index in range(10):
                nodes.append(make_node(
                    "source_commit",
                    {
                        "repository": "Mannyspiro/expert-robot",
                        "commit": f"{index + 1:040x}",
                    },
                    f"{seed * 100 + index + 1:064x}",
                    "source-control",
                    "qualified",
                ))
            edges = []
            for dependent in range(1, len(nodes)):
                for prerequisite in range(dependent):
                    if rng.random() < 0.18:
                        edges.append({
                            "dependent_node_id": nodes[dependent]["node_id"],
                            "prerequisite_node_id": nodes[prerequisite]["node_id"],
                            "relation": "derived_from",
                        })
            original = build_snapshot(nodes, edges)
            shuffled_nodes = list(nodes)
            shuffled_edges = list(edges)
            rng.shuffle(shuffled_nodes)
            rng.shuffle(shuffled_edges)
            permuted = build_snapshot(shuffled_nodes, shuffled_edges)
            self.assertEqual(original, permuted)

            payload = {
                key: value for key, value in original.items()
                if key != "snapshot_sha256"
            }
            independent_bytes = json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            self.assertEqual(
                hashlib.sha256(independent_bytes).hexdigest(),
                original["snapshot_sha256"],
            )
            positions = {
                node_id: position
                for position, node_id in enumerate(prerequisite_first_order(original))
            }
            for edge in edges:
                self.assertLess(
                    positions[edge["prerequisite_node_id"]],
                    positions[edge["dependent_node_id"]],
                )

    def test_oci_execution_identity_accepts_typed_task_and_input_artifact_refs(self):
        task_ref = {
            "schema": "merlin-artifact-ref/1", "project_id": "merlin",
            "logical_path": "jobs/task.json", "version": 4, "sha256": "5" * 64,
        }
        input_ref = {
            "schema": "merlin-artifact-ref/1", "project_id": "merlin",
            "logical_path": "inputs/model.bin", "version": 2, "sha256": "6" * 64,
        }
        identity = {
            "execution_id": "oci-exec-20261114-01",
            "runner_profile": "oci-isolated-cpu",
            "task_ref": task_ref, "input_refs": [input_ref],
        }
        node_id = node_id_for("oci_execution", identity)
        self.assertTrue(node_id.startswith("sha256:"))
        malformed = dict(identity)
        malformed["task_ref"] = "jobs/task.json"
        with self.assertRaisesRegex(ValueError, "task_ref"):
            node_id_for("oci_execution", malformed)
        malformed_inputs = dict(identity)
        malformed_inputs["input_refs"] = ["inputs/model.bin"]
        with self.assertRaisesRegex(ValueError, "ArtifactRef"):
            node_id_for("oci_execution", malformed_inputs)

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
            db.execute("""
                CREATE TRIGGER qualification_evidence_snapshots_no_update
                BEFORE UPDATE ON qualification_evidence_snapshots
                BEGIN SELECT RAISE(ABORT, 'qualification evidence snapshots are append-only'); END
            """)
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


    def test_backup_is_consistent_verified_and_non_overwriting(self):
        snapshots = [self.snapshot(f"{index:064x}") for index in range(1, 4)]
        for snapshot in snapshots:
            self.history.append(snapshot)
        with tempfile.TemporaryDirectory() as backup_dir:
            backup_path = Path(backup_dir) / "merlin-registry.backup.sqlite3"
            receipt = self.history.backup_to(backup_path)
            self.assertEqual(receipt["snapshot_count"], 3)
            self.assertEqual(receipt["integrity"], "ok")
            self.assertEqual(len(receipt["sha256"]), 64)
            self.assertEqual(
                SnapshotHistory.verify_backup(backup_path)["sha256"],
                receipt["sha256"],
            )
            restored = SnapshotHistory(backup_path)
            for snapshot in snapshots:
                self.assertEqual(
                    restored.get(snapshot["snapshot_sha256"]), snapshot,
                )
            with self.assertRaises(FileExistsError):
                self.history.backup_to(backup_path)

    def test_backup_verification_rejects_tampered_snapshot_rows(self):
        snapshot = self.snapshot("4" * 64)
        self.history.append(snapshot)
        with tempfile.TemporaryDirectory() as backup_dir:
            backup_path = Path(backup_dir) / "backup.sqlite3"
            self.history.backup_to(backup_path)
            with sqlite3.connect(backup_path) as db:
                db.execute("DROP TRIGGER qualification_evidence_snapshots_no_update")
                db.execute(
                    "UPDATE qualification_evidence_snapshots SET snapshot_json='{}' "
                    "WHERE snapshot_sha256=?",
                    (snapshot["snapshot_sha256"],),
                )
            with self.assertRaisesRegex(ValueError, "invalid snapshot"):
                SnapshotHistory.verify_backup(backup_path)

    def test_backup_requires_existing_destination_directory(self):
        with tempfile.TemporaryDirectory() as backup_dir:
            missing = Path(backup_dir) / "missing" / "backup.sqlite3"
            with self.assertRaises(FileNotFoundError):
                self.history.backup_to(missing)

    def test_history_limit_is_bounded(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            self.history.list_history(0)
        with self.assertRaisesRegex(ValueError, "limit"):
            self.history.list_history(True)


if __name__ == "__main__":
    unittest.main()
