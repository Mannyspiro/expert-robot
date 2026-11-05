import hashlib
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from merlin.change_manifest import (
    build_change_manifest, create_recovery_snapshot, validate_change_manifest,
)
from merlin.project_registry import MerlinRegistry
from merlin.event_outbox import MerlinEventOutbox
from merlin.recovery_service import RecoveryCoordinator, mcfc_lease_validator
from merlin.recovery_adapters import (
    GitRecoveryAdapter, RegistryRecoveryAdapter, ZipRecoveryAdapter,
)


class PreservationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("p", "Project")

    def test_snapshot_verifies_and_persists_full_inventory(self):
        digest = self.registry.put_artifact("p", "notes/a.md", b"original")
        snapshot = create_recovery_snapshot(self.registry, "p", actor="test")
        self.assertEqual(snapshot["manifest"]["artifacts"][0]["sha256"], digest)
        stored = self.registry.get_recovery_point(snapshot["recovery_id"])
        self.assertEqual(stored["manifest_digest"], snapshot["manifest_digest"])

    def test_change_manifest_marks_deletion_unresolved_and_fails_closed(self):
        before = {"artifacts": [{"path": "keep.txt", "sha256": "a" * 64}]}
        after = {"artifacts": []}
        manifest = build_change_manifest(before, after, operation_id="op", actor="test", reason="test diff")
        with self.assertRaisesRegex(ValueError, "not approved"):
            validate_change_manifest(manifest)

    def test_change_manifest_accepts_recoverable_modification(self):
        before = {"artifacts": [{"path": "a", "sha256": "a" * 64}]}
        after = {"artifacts": [{"path": "a", "sha256": "b" * 64}]}
        manifest = build_change_manifest(before, after, operation_id="op", actor="test", reason="update")
        validate_change_manifest(manifest)

    def test_registry_recovery_restores_exact_bytes_to_quarantine(self):
        data = b"recover me"
        digest = self.registry.put_artifact("p", "original.txt", data)
        result = RegistryRecoveryAdapter(self.registry).recover(
            digest=digest, project_id="p", original_path="original.txt")
        self.assertEqual(result["confidence"], "exact")
        self.assertTrue(result["recovery_path"].startswith("_recovery/"))
        self.assertEqual(self.registry.get_artifact_bytes(digest), data)

    def test_registry_recovers_orphaned_blob_without_metadata_row(self):
        data = b"orphaned but intact blob"
        digest = hashlib.sha256(data).hexdigest()
        blob_path = self.registry.blobs / digest[:2] / digest[2:]
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.write_bytes(data)
        result = RegistryRecoveryAdapter(self.registry).recover(
            digest=digest, project_id="p", original_path="lost/orphan.bin")
        self.assertEqual(result["sha256"], digest)
        self.assertEqual(self.registry.get_artifact_bytes(digest), data)

    def test_zip_recovery_restores_exact_member_without_extracting(self):
        data = b"archived bytes"
        archive_path = self.root / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("docs/important.md", data)
        digest = hashlib.sha256(data).hexdigest()
        result = ZipRecoveryAdapter().recover(
            archive_path=archive_path, member_path="docs/important.md",
            expected_sha256=digest, project_id="p", registry=self.registry)
        self.assertEqual(result["sha256"], digest)
        self.assertEqual(self.registry.get_artifact_bytes(digest), data)

    def test_git_recovery_reads_pinned_commit_and_verifies_bytes(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        data = b"committed source"
        (repo / "important.txt").write_bytes(data)
        subprocess.run(["git", "-C", str(repo), "add", "important.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True, capture_output=True)
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True).stdout.strip()
        digest = hashlib.sha256(data).hexdigest()
        result = GitRecoveryAdapter(repo).recover(
            commit=commit, path="important.txt", expected_sha256=digest,
            project_id="p", registry=self.registry)
        self.assertEqual(result["confidence"], "exact")
        self.assertEqual(self.registry.get_artifact_bytes(digest), data)


    def test_git_tree_manifest_detects_deletion_and_blocks_retirement(self):
        repo = self.root / "tree-repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
        (repo / "keep-me.txt").write_bytes(b"valuable work")
        subprocess.run(["git", "-C", str(repo), "add", "keep-me.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "add work"], check=True, capture_output=True)
        first = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               check=True, capture_output=True, text=True).stdout.strip()
        (repo / "keep-me.txt").unlink()
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "remove work"], check=True, capture_output=True)
        second = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
        adapter = GitRecoveryAdapter(repo)
        before = adapter.tree_manifest(first)
        after = adapter.tree_manifest(second)
        self.assertEqual(before["artifacts"][0]["sha256"], hashlib.sha256(b"valuable work").hexdigest())
        manifest = build_change_manifest(
            before, after, operation_id="tree-diff", actor="test", reason="test deletion audit")
        deleted = [item for item in manifest["items"] if item["change_kind"] == "deleted"]
        self.assertEqual([item["path"] for item in deleted], ["keep-me.txt"])
        with self.assertRaisesRegex(ValueError, "independently validated approval"):
            validate_change_manifest(manifest)

    def test_hermes_recovery_queue_uses_approval_lease_and_quarantine(self):
        outbox = MerlinEventOutbox(self.root / "outbox.sqlite3")
        data = b"source bytes to recover"
        digest = self.registry.put_artifact("p", "source.txt", data)
        coordinator = RecoveryCoordinator(
            registry=self.registry, outbox=outbox,
            approval_validator=lambda ref, payload: ref == "approved",
            lease_validator=lambda ref, budget: ref == "lease-1",
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        queued = coordinator.request(
            task_id="restore-1", project_id="p", source="registry",
            expected_sha256=digest, original_path="deleted/source.txt",
            approval_ref="approved", lease_ref="lease-1",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        self.assertEqual(queued["state"], "pending")
        consumed = coordinator.consume_one()
        self.assertEqual(consumed["state"], "acknowledged")
        result = consumed["result"]
        self.assertEqual(result["status"], "quarantined_unverified")
        self.assertTrue(result["recovery_path"].startswith("_recovery/"))
        self.assertEqual(self.registry.get_artifact_bytes(digest), data)
        self.assertEqual(
            self.registry.get_artifact_bytes(self.registry.get_artifact_head(
                "p", result["recovery_path"])["digest"]), data)

    def test_mcfc_validator_checks_live_lease_and_budget(self):
        from types import SimpleNamespace
        from datetime import datetime, timezone
        lease = SimpleNamespace(
            resources=SimpleNamespace(cpu_cores=2, memory_bytes=4096),
            max_wall_seconds=60, compute_budget_units=10,
            promotion_authority=False, authority="execution_only",
        )
        class LeaseBook:
            def get(self, lease_id):
                if lease_id != "lease":
                    raise KeyError(lease_id)
                return lease
            def validate_start(self, lease_id, *, now):
                return lease_id == "lease"
        validator = mcfc_lease_validator(
            LeaseBook(), clock=lambda: datetime.now(timezone.utc))
        self.assertTrue(validator("lease", {
            "cpu_cores": 1, "memory_bytes": 1024,
            "max_wall_seconds": 30, "compute_budget_units": 2,
        }))
        self.assertFalse(validator("lease", {
            "cpu_cores": 3, "memory_bytes": 1024,
            "max_wall_seconds": 30, "compute_budget_units": 2,
        }))

    def test_wrong_digest_never_restores(self):
        archive_path = self.root / "bundle.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("a.txt", b"real")
        with self.assertRaisesRegex(ValueError, "do not match"):
            ZipRecoveryAdapter().recover(
                archive_path=archive_path, member_path="a.txt",
                expected_sha256="0" * 64, project_id="p", registry=self.registry)


if __name__ == "__main__":
    unittest.main()
