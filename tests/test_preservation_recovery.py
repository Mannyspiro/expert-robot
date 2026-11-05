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
