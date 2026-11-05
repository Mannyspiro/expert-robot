import sqlite3
import tempfile
import unittest
from pathlib import Path

from merlin.project_registry import ArtifactConflict, MerlinRegistry


class MerlinRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(self.temp.name)
        self.registry.register_project("p", "Project")

    def test_content_addressed_artifact_roundtrip_and_inventory(self):
        digest = self.registry.put_artifact("p", "notes/idea.md", b"research idea", "text/markdown")
        self.assertTrue(self.registry.verify_artifact(digest))
        inventory = self.registry.inventory("p")
        self.assertEqual(inventory["artifacts"][0]["digest"], digest)
        self.assertEqual(inventory["artifacts"][0]["logical_path"], "notes/idea.md")
        self.assertEqual(inventory["artifacts"][0]["generation"], 1)
        self.assertEqual(self.registry.get_artifact_bytes(digest), b"research idea")

    def test_blob_tampering_is_detected(self):
        digest = self.registry.put_artifact("p", "x.bin", b"original")
        blob = self.registry.blobs / digest[:2] / digest[2:]
        blob.write_bytes(b"changed")
        self.assertFalse(self.registry.verify_artifact(digest))

    def test_rejects_path_traversal_and_unknown_project(self):
        with self.assertRaises(ValueError):
            self.registry.put_artifact("missing", "../escape", b"x")
        with self.assertRaises(KeyError):
            self.registry.put_artifact("missing", "valid.bin", b"x")

    def test_put_is_idempotent_but_refuses_silent_overwrite(self):
        first = self.registry.put_artifact("p", "same.txt", b"v1")
        self.assertEqual(self.registry.put_artifact("p", "same.txt", b"v1"), first)
        with self.assertRaises(ArtifactConflict):
            self.registry.put_artifact("p", "same.txt", b"v2")
        self.assertEqual(self.registry.get_artifact_bytes(first), b"v1")
        self.assertEqual(len(self.registry.artifact_history("p", "same.txt")), 1)

    def test_replace_requires_exact_digest_and_generation_cas(self):
        first = self.registry.put_artifact("p", "same.txt", b"v1")
        head = self.registry.get_artifact_head("p", "same.txt")
        second = self.registry.replace_artifact(
            "p", "same.txt", b"v2", expected_digest=first,
            expected_generation=1, actor="test", operation_id="op-1")
        self.assertNotEqual(first, second)
        self.assertEqual(self.registry.get_artifact_bytes(first), b"v1")
        self.assertEqual(self.registry.get_artifact_bytes(second), b"v2")
        self.assertEqual(self.registry.get_artifact_head("p", "same.txt")["generation"], 2)
        history = self.registry.artifact_history("p", "same.txt")
        self.assertEqual(len(history), 2)
        recovery_id = history[1]["pre_change_recovery_id"]
        self.assertTrue(recovery_id)
        snapshot = self.registry.get_recovery_point(recovery_id)
        self.assertEqual(snapshot["manifest"]["artifacts"][0]["sha256"], first)
        with self.assertRaises(ArtifactConflict):
            self.registry.replace_artifact(
                "p", "same.txt", b"v3", expected_digest=head["digest"],
                expected_generation=head["generation"], actor="stale", operation_id="op-2")
        self.assertEqual(self.registry.get_artifact_bytes(second), b"v2")

    def test_database_triggers_block_history_blob_and_head_deletion(self):
        first = self.registry.put_artifact("p", "protected.txt", b"v1")
        self.registry.replace_artifact(
            "p", "protected.txt", b"v2", expected_digest=first,
            expected_generation=1, actor="test", operation_id="op-protected")
        history = self.registry.artifact_history("p", "protected.txt")
        recovery_id = history[1]["pre_change_recovery_id"]
        with self.registry._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE artifact_versions SET actor='tampered'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM artifact_versions")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM artifacts")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM recovery_points WHERE recovery_id=?", (recovery_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM project_artifacts WHERE project_id='p' AND logical_path='protected.txt'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE project_artifacts SET digest=? WHERE project_id='p' AND logical_path='protected.txt'",
                           (first,))

    def test_database_rejects_head_update_without_matching_version_row(self):
        first = self.registry.put_artifact("p", "guarded.txt", b"v1")
        second = self.registry._store_blob(b"v2", "application/octet-stream")
        with self.registry._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "UPDATE project_artifacts SET digest=?, generation=2 "
                    "WHERE project_id='p' AND logical_path='guarded.txt'",
                    (second,),
                )
        self.assertEqual(self.registry.get_artifact_head("p", "guarded.txt")["digest"], first)
        self.assertEqual(self.registry.artifact_history("p", "guarded.txt")[-1]["digest"], first)

    def test_database_rejects_initial_head_without_version_row(self):
        digest = self.registry._store_blob(b"unversioned", "application/octet-stream")
        with self.registry._connect() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO project_artifacts(project_id,digest,logical_path,generation) "
                    "VALUES('p',?,'unversioned.txt',1)", (digest,),
                )
        self.assertIsNone(self.registry.get_artifact_head("p", "unversioned.txt"))

    def test_concurrent_writers_only_one_cas_wins(self):
        import threading
        first = self.registry.put_artifact("p", "race.txt", b"base")
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def writer(payload, operation):
            barrier.wait()
            try:
                result = self.registry.replace_artifact(
                    "p", "race.txt", payload,
                    expected_digest=first, expected_generation=1,
                    actor="concurrency-test", operation_id=operation,
                )
                outcome = ("won", result)
            except ArtifactConflict:
                outcome = ("conflict", None)
            with lock:
                outcomes.append(outcome)

        workers = [
            threading.Thread(target=writer, args=(b"writer-a", "race-a")),
            threading.Thread(target=writer, args=(b"writer-b", "race-b")),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(sorted(kind for kind, _ in outcomes), ["conflict", "won"])
        history = self.registry.artifact_history("p", "race.txt")
        self.assertEqual([row["generation"] for row in history], [1, 2])
        head = self.registry.get_artifact_head("p", "race.txt")
        self.assertEqual(head["generation"], 2)
        self.assertEqual(head["digest"], next(value for kind, value in outcomes if kind == "won"))

    def test_replace_requires_existing_head(self):
        with self.assertRaises(ArtifactConflict):
            self.registry.replace_artifact(
                "p", "missing.txt", b"x", expected_digest="0" * 64,
                expected_generation=1, actor="test", operation_id="op")

    def test_recovery_point_manifest_is_integrity_checked(self):
        digest = self.registry.put_artifact("p", "a.txt", b"data")
        manifest = {"project_id": "p", "artifacts": [{"path": "a.txt", "sha256": digest}]}
        manifest_digest = self.registry.add_recovery_point("rp-1", "p", manifest)
        result = self.registry.get_recovery_point("rp-1")
        self.assertEqual(result["manifest_digest"], manifest_digest)
        self.assertEqual(result["manifest"], manifest)

    def test_legacy_registry_migrates_without_losing_existing_artifact_heads(self):
        root = Path(self.temp.name) / "legacy"
        blob = b"legacy preserved bytes"
        digest = __import__("hashlib").sha256(blob).hexdigest()
        relative = f"blobs/sha256/{digest[:2]}/{digest[2:]}"
        target = root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(blob)
        database = root / "merlin.sqlite3"
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as db:
            db.executescript("""
                CREATE TABLE projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                  version TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE artifacts(digest TEXT PRIMARY KEY, media_type TEXT NOT NULL,
                  size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE project_artifacts(project_id TEXT NOT NULL, digest TEXT NOT NULL,
                  logical_path TEXT NOT NULL, PRIMARY KEY(project_id, logical_path));
            """)
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?)",
                       ("legacy", "Legacy", "0.1.0", "{}", 1.0))
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, "text/plain", len(blob), relative, 1.0))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?)",
                       ("legacy", digest, "keep.txt"))
        migrated = MerlinRegistry(root)
        self.assertEqual(migrated.get_artifact_bytes(digest), blob)
        head = migrated.get_artifact_head("legacy", "keep.txt")
        self.assertEqual(head["digest"], digest)
        self.assertEqual(head["generation"], 1)
        self.assertEqual(migrated.artifact_history("legacy", "keep.txt")[0]["actor"], "migration")

    def test_legacy_migration_is_idempotent_after_partial_schema_upgrade(self):
        root = Path(self.temp.name) / "interrupted"
        root.mkdir(parents=True)
        blob = b"survives interrupted migration"
        digest = __import__("hashlib").sha256(blob).hexdigest()
        relative = f"blobs/sha256/{digest[:2]}/{digest[2:]}"
        target = root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(blob)
        database = root / "merlin.sqlite3"
        with sqlite3.connect(database) as db:
            db.executescript("""
                CREATE TABLE projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                  version TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE artifacts(digest TEXT PRIMARY KEY, media_type TEXT NOT NULL,
                  size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE project_artifacts(project_id TEXT NOT NULL, digest TEXT NOT NULL,
                  logical_path TEXT NOT NULL, generation INTEGER NOT NULL DEFAULT 1,
                  PRIMARY KEY(project_id, logical_path));
                CREATE TABLE artifact_versions(version_id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL, logical_path TEXT NOT NULL, digest TEXT NOT NULL,
                  parent_version_id TEXT, generation INTEGER NOT NULL, actor TEXT NOT NULL,
                  operation_id TEXT NOT NULL, created_at REAL NOT NULL);
            """)
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", ("p", "P", "0.1", "{}", 1.0))
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, "application/octet-stream", len(blob), relative, 1.0))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?,1)", ("p", digest, "keep.bin"))
        migrated = MerlinRegistry(root)
        migrated_again = MerlinRegistry(root)
        self.assertEqual(migrated_again.get_artifact_bytes(digest), blob)
        history = migrated_again.artifact_history("p", "keep.bin")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["generation"], 1)
        self.assertEqual(history[0]["actor"], "migration")

    def test_legacy_migration_fails_closed_when_blob_file_is_missing(self):
        root = Path(self.temp.name) / "missing-blob"
        root.mkdir(parents=True)
        database = root / "merlin.sqlite3"
        digest = "a" * 64
        relative = f"blobs/sha256/{digest[:2]}/{digest[2:]}"
        with sqlite3.connect(database) as db:
            db.executescript("""
                CREATE TABLE projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                  version TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE artifacts(digest TEXT PRIMARY KEY, media_type TEXT NOT NULL,
                  size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE project_artifacts(project_id TEXT NOT NULL, digest TEXT NOT NULL,
                  logical_path TEXT NOT NULL, PRIMARY KEY(project_id, logical_path));
            """)
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", ("p", "P", "0.1", "{}", 1.0))
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, "application/octet-stream", 3, relative, 1.0))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?)", ("p", digest, "lost.bin"))
        with self.assertRaises((FileNotFoundError, RuntimeError)):
            MerlinRegistry(root)

    def test_migration_rolls_back_schema_and_history_when_history_insert_is_interrupted(self):
        root = Path(self.temp.name) / "migration-interruption"
        root.mkdir(parents=True)
        blob = b"migration rollback bytes"
        digest = __import__("hashlib").sha256(blob).hexdigest()
        relative = f"blobs/sha256/{digest[:2]}/{digest[2:]}"
        target = root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(blob)
        database = root / "merlin.sqlite3"
        with sqlite3.connect(database) as db:
            db.executescript("""
                CREATE TABLE projects(project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                  version TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE artifacts(digest TEXT PRIMARY KEY, media_type TEXT NOT NULL,
                  size_bytes INTEGER NOT NULL, relative_path TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE project_artifacts(project_id TEXT NOT NULL, digest TEXT NOT NULL,
                  logical_path TEXT NOT NULL, PRIMARY KEY(project_id, logical_path));
                CREATE TABLE artifact_versions(version_id TEXT PRIMARY KEY,
                  project_id TEXT NOT NULL, logical_path TEXT NOT NULL, digest TEXT NOT NULL,
                  parent_version_id TEXT, generation INTEGER NOT NULL, actor TEXT NOT NULL,
                  operation_id TEXT NOT NULL, created_at REAL NOT NULL);
            """)
            db.execute("INSERT INTO projects VALUES(?,?,?,?,?)", ("p", "P", "0.1", "{}", 1.0))
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",
                       (digest, "application/octet-stream", len(blob), relative, 1.0))
            db.execute("INSERT INTO project_artifacts VALUES(?,?,?)", ("p", digest, "legacy.bin"))
            db.execute("""
                CREATE TRIGGER interrupt_legacy_history BEFORE INSERT ON artifact_versions
                BEGIN SELECT RAISE(ABORT, 'injected migration interruption'); END
            """)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected migration interruption"):
            MerlinRegistry(root)
        with sqlite3.connect(database) as db:
            head_columns = {row[1] for row in db.execute("PRAGMA table_info(project_artifacts)")}
            version_columns = {row[1] for row in db.execute("PRAGMA table_info(artifact_versions)")}
            self.assertNotIn("generation", head_columns)
            self.assertNotIn("pre_change_recovery_id", version_columns)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM artifact_versions").fetchone()[0], 0)
            db.execute("DROP TRIGGER interrupt_legacy_history")
        migrated = MerlinRegistry(root)
        head = migrated.get_artifact_head("p", "legacy.bin")
        self.assertEqual(head["digest"], digest)
        self.assertEqual(head["generation"], 1)
        self.assertEqual(migrated.artifact_history("p", "legacy.bin")[0]["actor"], "migration")

    def test_relation_identity_is_idempotent_and_immutable(self):
        self.registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
        self.registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
        with self.assertRaisesRegex(ValueError, "different metadata"):
            self.registry.relate("p", "contains", "artifact:x", {"scope": "v2"})


if __name__ == "__main__":
    unittest.main()
