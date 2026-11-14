import hashlib
import json
import os
import sqlite3
from pathlib import Path
import tempfile
import unittest
import zipfile

from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.qualification_evidence_dag import SnapshotHistory, build_snapshot, make_node
from merlin.qualification_publication import QualificationSnapshotPublisher
from merlin.registry_backup import MerlinRegistryBackup


class MerlinRegistryBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "registry"
        self.registry = MerlinRegistry(self.root)
        self.registry.register_project("merlin", "Merlin")
        self.content = b"verified immutable research artifact\x00\x01"
        self.digest = self.registry.put_artifact(
            "merlin", "research/input.bin", self.content,
            media_type="application/octet-stream",
            provenance={
                "schema": "merlin-artifact-provenance/1",
                "source_repo": "Mannyspiro/expert-robot",
                "source_commit": "a" * 40,
                "artifact_id": "input-bin-v1",
                "artifact_kind": "research-input",
                "artifact_schema": "binary/1",
            },
        )
        self.artifact_ref = self.registry.artifact_ref("merlin", "research/input.bin")
        self.snapshot = build_snapshot([
            make_node(
                "source_commit",
                {"repository": "Mannyspiro/expert-robot", "commit": "b" * 40},
                "c" * 64, "source-control", "qualified",
            )
        ], [])
        self.publisher = QualificationSnapshotPublisher(self.registry.db_path)
        self.published = self.publisher.publish(self.snapshot, now=10)
        self.backup = MerlinRegistryBackup(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_restore_preserves_artifacts_snapshots_and_outbox(self):
        archive_path = Path(self.temp.name) / "merlin-backup.zip"
        receipt = self.backup.backup_to(archive_path)
        self.assertTrue(archive_path.is_file())
        self.assertEqual(receipt["blob_count"], 1)
        verified = MerlinRegistryBackup.verify_archive(archive_path)
        self.assertTrue(verified["verified"])
        self.assertEqual(verified["snapshot_count"], 1)

        restored_root = Path(self.temp.name) / "restored-registry"
        restored = MerlinRegistryBackup.restore_to(archive_path, restored_root)
        self.assertEqual(restored["archive_sha256"], receipt["archive_sha256"])
        restored_registry = MerlinRegistry(restored_root)
        resolved = restored_registry.read_artifact_ref(self.artifact_ref)
        self.assertEqual(resolved["content"], self.content)
        self.assertEqual(resolved["resolution"]["provenance"]["artifact_id"], "input-bin-v1")

        restored_history = SnapshotHistory(restored_registry.db_path)
        self.assertEqual(
            restored_history.get(self.snapshot["snapshot_sha256"]), self.snapshot,
        )
        restored_outbox = MerlinEventOutbox(restored_registry.db_path)
        event = restored_outbox.get(self.published["event_id"])
        self.assertEqual(event["payload"]["snapshot_sha256"], self.snapshot["snapshot_sha256"])
        self.assertEqual(event["state"], "pending")

    def test_backup_and_restore_never_overwrite_existing_paths(self):
        archive_path = Path(self.temp.name) / "merlin-backup.zip"
        self.backup.backup_to(archive_path)
        with self.assertRaises(FileExistsError):
            self.backup.backup_to(archive_path)
        existing_root = Path(self.temp.name) / "existing"
        existing_root.mkdir()
        with self.assertRaises(FileExistsError):
            MerlinRegistryBackup.restore_to(archive_path, existing_root)

    def test_backup_fails_closed_when_a_referenced_blob_is_missing(self):
        blob = self.root / "blobs" / "sha256" / self.digest[:2] / self.digest[2:]
        blob.unlink()
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            self.backup.backup_to(Path(self.temp.name) / "missing-blob.zip")

    def test_backup_fails_closed_when_a_referenced_blob_is_tampered(self):
        blob = self.root / "blobs" / "sha256" / self.digest[:2] / self.digest[2:]
        blob.write_bytes(b"substituted bytes")
        with self.assertRaisesRegex(RuntimeError, "integrity check"):
            self.backup.backup_to(Path(self.temp.name) / "tampered-source.zip")


    def test_backup_rejects_symlinked_blob_directory(self):
        blob_root = self.root / "blobs" / "sha256"
        real_root = Path(self.temp.name) / "sha256-real"
        blob_root.rename(real_root)
        blob_root.symlink_to(real_root, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            self.backup.backup_to(Path(self.temp.name) / "symlinked-blob-dir.zip")

    def test_verifier_rejects_tampered_archive_blob(self):
        archive_path = Path(self.temp.name) / "original.zip"
        self.backup.backup_to(archive_path)
        tampered_path = Path(self.temp.name) / "tampered.zip"
        with zipfile.ZipFile(archive_path, "r") as source:
            with zipfile.ZipFile(tampered_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename.endswith("/" + self.digest[2:]):
                        data = b"tampered archive content"
                    target.writestr(info.filename, data)
        with self.assertRaisesRegex(ValueError, "blob failed integrity check"):
            MerlinRegistryBackup.verify_archive(tampered_path)

    def test_verifier_rejects_path_traversal_and_duplicate_entries(self):
        traversal = Path(self.temp.name) / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../escape", b"x")
        with self.assertRaisesRegex(ValueError, "unsafe path|traversal"):
            MerlinRegistryBackup.verify_archive(traversal)

        duplicate = Path(self.temp.name) / "duplicate.zip"
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("manifest.json", b"{}")
            archive.writestr("manifest.json", b"{}")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            MerlinRegistryBackup.verify_archive(duplicate)


    def test_backup_rejects_outbox_event_that_does_not_bind_its_snapshot(self):
        event_id = self.published["event_id"]
        with sqlite3.connect(self.registry.db_path) as db:
            row = db.execute(
                "SELECT payload_json FROM event_outbox WHERE event_id=?", (event_id,)
            ).fetchone()
            payload = json.loads(row[0])
            payload["snapshot_sha256"] = "f" * 64
            db.execute(
                "UPDATE event_outbox SET payload_json=? WHERE event_id=?",
                (json.dumps(payload, sort_keys=True, separators=(",", ":")), event_id),
            )
        destination = Path(self.temp.name) / "bad-outbox-backup.zip"
        with self.assertRaisesRegex(ValueError, "idempotency identity mismatch"):
            self.backup.backup_to(destination)
        self.assertFalse(destination.exists())

    def test_backup_manifest_binds_exact_database_and_blob_inventory(self):
        archive_path = Path(self.temp.name) / "inventory.zip"
        self.backup.backup_to(archive_path)
        with zipfile.ZipFile(archive_path, "r") as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["blob_count"], 1)
            self.assertEqual(manifest["blobs"][0]["sha256"], self.digest)
            self.assertEqual(manifest["database"]["path"], "merlin.sqlite3")
            self.assertEqual(
                hashlib.sha256(archive.read("merlin.sqlite3")).hexdigest(),
                manifest["database"]["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
