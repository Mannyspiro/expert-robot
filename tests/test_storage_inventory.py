import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from merlin import project_registry as registry_module
from merlin.project_registry import MerlinRegistry
from merlin.registry_queries import MerlinReadAPI
from dot_ai_os.private_runtime import PrivateReadOnlyRegistry


class StorageInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(self.temp.name)
        self.registry.register_project("p", "P")
        self.registry.register_project("q", "Q")

    def shared_fixture(self):
        r = self.registry
        self.old = r.put_artifact("p", "alpha", b"aa")
        self.new = r.put_artifact("p", "alpha", b"bbb")
        r.put_artifact("p", "alias", b"bbb")
        self.other = r.put_artifact("p", "other", b"ccccc")
        self.retired = r.put_artifact("p", "retired", b"ddddddd")
        r.put_artifact("p", "retired", b"bbb")
        r.put_artifact("q", "shared", b"aa")

    def blob(self, digest):
        return self.registry.blobs / digest[:2] / digest[2:]

    def snapshot(self):
        return {str(p.relative_to(self.registry.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.registry.root.rglob("*") if p.is_file() and not p.is_symlink()}

    def test_global_unique_current_and_history_arithmetic(self):
        self.shared_fixture()
        report = self.registry.storage_inventory()
        self.assertEqual(report["scope"], "host_registry")
        self.assertEqual(report["registered"]["digests"], 4)
        self.assertEqual(report["registered"]["declared_bytes"], 17)
        self.assertEqual(report["registered"]["stored"]["bytes"], 17)
        self.assertEqual(report["current"]["references"], 5)
        self.assertEqual(report["current"]["logical_bytes"], 16)
        self.assertEqual(report["current"]["unique_digests"], 3)
        self.assertEqual(report["current"]["unique_declared_bytes"], 10)
        self.assertEqual(report["versions"]["references"], 7)
        self.assertEqual(report["versions"]["logical_bytes"], 25)
        self.assertEqual(report["historical_only"]["digests"], 1)
        self.assertEqual(report["historical_only"]["declared_bytes"], 7)
        self.assertEqual(report["historical_only"]["stored"]["bytes"], 7)
        self.assertEqual(report["unclassified_cas"]["bytes"], 0)

    def test_empty_registry_and_facade_delegation(self):
        api = MerlinReadAPI(self.registry)
        with patch.object(self.registry, "storage_inventory", wraps=self.registry.storage_inventory) as query:
            report = api.storage_inventory(limit=9)
        query.assert_called_once_with(limit=9)
        self.assertEqual(report["registered"]["stored"]["bytes"], 0)
        self.assertEqual(report["current"]["logical_bytes"], 0)
        self.assertEqual(report["historical_only"]["digests"], 0)
        self.assertGreater(report["sqlite_files"]["bytes"], 0)
        self.assertFalse(report["content_integrity_verified"])
        self.assertFalse(report["reclaimability_assessed"])

    def test_reversion_and_new_calls_observe_fresh_metadata(self):
        self.shared_fixture()
        first = self.registry.storage_inventory()
        self.registry.put_artifact("p", "alpha", b"aa")
        second = self.registry.storage_inventory()
        self.assertEqual(second["registered"]["declared_bytes"], first["registered"]["declared_bytes"])
        self.assertEqual(second["current"]["logical_bytes"], 15)
        self.assertEqual(second["versions"]["references"], 8)
        self.assertEqual(second["versions"]["logical_bytes"], 27)
        self.assertEqual(second["historical_only"]["declared_bytes"], 7)
        self.registry.put_artifact("q", "later", b"later")
        self.assertEqual(self.registry.storage_inventory()["registered"]["declared_bytes"], 22)

    def test_missing_files_keep_metadata_and_observed_storage_separate(self):
        self.shared_fixture()
        self.blob(self.retired).unlink()
        report = self.registry.storage_inventory()
        self.assertEqual(report["registered"]["declared_bytes"], 17)
        self.assertEqual(report["registered"]["stored"]["bytes"], 10)
        self.assertEqual(report["registered"]["stored"]["missing_files"], 1)
        self.assertTrue(report["registered"]["stored"]["complete"])
        self.assertEqual(report["historical_only"]["declared_bytes"], 7)
        self.assertEqual(report["historical_only"]["stored"]["bytes"], 0)
        self.assertEqual(report["historical_only"]["stored"]["missing_files"], 1)

    def test_stat_accounting_does_not_read_or_verify_blob_contents(self):
        self.shared_fixture()
        self.blob(self.retired).write_bytes(b"zzzzzzz")  # Same length, wrong content.
        original_open = Path.open

        def no_blob_open(path, *args, **kwargs):
            if self.registry.blobs in path.parents:
                raise AssertionError("accounting opened blob content")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", no_blob_open), patch.object(
                self.registry, "verify_artifact", side_effect=AssertionError("unexpected verification")):
            report = self.registry.storage_inventory()
        self.assertEqual(report["registered"]["stored"]["bytes"], 17)
        self.assertEqual(report["registered"]["size_mismatches"], 0)
        self.assertFalse(report["content_integrity_verified"])
        self.assertFalse(self.registry.verify_artifact(self.retired))
        self.blob(self.retired).write_bytes(b"changed-size")
        changed = self.registry.storage_inventory()
        self.assertEqual(changed["registered"]["size_mismatches"], 1)
        self.assertEqual(changed["registered"]["stored"]["bytes"], 22)
        self.assertEqual(changed["historical_only"]["declared_bytes"], 7)
        self.assertEqual(changed["historical_only"]["stored"]["bytes"], 12)

    def test_metadata_limits_withhold_only_dependent_totals(self):
        self.shared_fixture()
        partial_current = self.registry.storage_inventory(limit=4)
        self.assertFalse(partial_current["scan"]["artifacts_truncated"])
        self.assertTrue(partial_current["scan"]["current_truncated"])
        self.assertEqual(partial_current["current"]["references_observed"], 4)
        self.assertIsNone(partial_current["current"]["logical_bytes"])
        self.assertEqual(partial_current["registered"]["declared_bytes"], 17)
        self.assertIsNone(partial_current["historical_only"]["digests"])
        partial_versions = self.registry.storage_inventory(limit=5)
        self.assertFalse(partial_versions["scan"]["current_truncated"])
        self.assertTrue(partial_versions["scan"]["versions_truncated"])
        self.assertEqual(partial_versions["current"]["logical_bytes"], 16)
        self.assertIsNone(partial_versions["versions"]["references"])
        self.assertIsNone(partial_versions["historical_only"]["stored"])
        partial_artifacts = self.registry.storage_inventory(limit=3)
        self.assertTrue(partial_artifacts["scan"]["artifacts_truncated"])
        self.assertEqual(partial_artifacts["registered"]["digests_observed"], 3)
        self.assertIsNone(partial_artifacts["registered"]["declared_bytes"])
        self.assertIsNone(partial_artifacts["registered"]["stored"]["bytes"])

    def test_cas_entry_limit_is_independent_and_stops_with_one_sentinel(self):
        self.shared_fixture()
        for index in range(20):
            (self.registry.blobs / ("unclassified-" + str(index))).write_bytes(b"x")
        original_scandir = os.scandir
        consumed = 0
        opened = closed = 0

        class LimitedScan:
            def __init__(inner, path):
                nonlocal opened
                opened += 1
                inner.iterator = original_scandir(path)

            def __enter__(inner):
                return inner

            def __exit__(inner, *args):
                nonlocal closed
                closed += 1
                inner.iterator.close()

            def __iter__(inner):
                return inner

            def __next__(inner):
                nonlocal consumed
                entry = next(inner.iterator)
                consumed += 1
                if consumed > 10:
                    raise AssertionError("CAS scan exceeded limit + one sentinel")
                return entry

        with patch.object(registry_module.os, "scandir", LimitedScan):
            report = self.registry.storage_inventory(limit=9)
        self.assertEqual(consumed, 10)
        self.assertEqual(opened, closed)
        self.assertEqual(report["scan"]["cas_entries_observed"], 9)
        self.assertTrue(report["scan"]["cas_entries_truncated"])
        self.assertIsNone(report["unclassified_cas"]["bytes"])
        self.assertEqual(report["registered"]["stored"]["bytes"], 17)
        self.assertEqual(report["historical_only"]["declared_bytes"], 7)

    def test_unclassified_files_and_unexamined_subtrees_are_explicit(self):
        self.shared_fixture()
        (self.registry.blobs / "unfinished.tmp").write_bytes(b"temp")
        orphan = self.blob(hashlib.sha256(b"orphan").hexdigest())
        orphan.parent.mkdir(exist_ok=True)
        orphan.write_bytes(b"orphan")
        outside = self.registry.root / "other-cache"
        outside.mkdir()
        (outside / "outside").write_bytes(b"not-in-accounting")
        report = self.registry.storage_inventory()
        self.assertEqual(report["unclassified_cas"]["files_observed"], 2)
        self.assertEqual(report["unclassified_cas"]["bytes"], 10)
        unknown_dir = self.registry.blobs / "other-layout"
        unknown_dir.mkdir()
        (unknown_dir / "data").write_bytes(b"unexamined")
        (self.registry.blobs / "linked-directory").symlink_to(outside, target_is_directory=True)
        partial = self.registry.storage_inventory()
        self.assertEqual(partial["scan"]["cas_unexamined_directories"], 1)
        self.assertEqual(partial["unclassified_cas"]["non_regular_entries"], 1)
        self.assertIsNone(partial["unclassified_cas"]["bytes"])
        self.assertEqual(partial["unclassified_cas"]["bytes_observed"], 10)

    def test_missing_or_malformed_metadata_remains_visible(self):
        self.shared_fixture()
        with sqlite3.connect(self.registry.db_path) as db:
            db.execute("DELETE FROM artifacts WHERE digest=?", (self.old,))
        report = self.registry.storage_inventory()
        self.assertIsNone(report["current"]["logical_bytes"])
        self.assertEqual(report["current"]["missing_or_invalid_sizes"], 1)
        self.assertFalse(report["historical_only"]["classification_complete"])
        self.assertEqual(report["unclassified_cas"]["bytes"], 2)
        with sqlite3.connect(self.registry.db_path) as db:
            db.execute("INSERT INTO artifacts VALUES(NULL,'test',-1,'unexpected',0)")
        malformed = self.registry.storage_inventory()
        self.assertEqual(malformed["registered"]["stored"]["invalid_paths"], 1)
        self.assertEqual(malformed["registered"]["invalid_sizes"], 1)
        self.assertIsNone(malformed["registered"]["declared_bytes"])
        self.assertIsNone(malformed["registered"]["stored"]["bytes"])

    def test_allocation_observation_and_unavailable_allocation(self):
        size = 1024 * 1024
        digest = self.registry.put_artifact("p", "sparse", bytes(size))
        blob = self.blob(digest)
        with blob.open("wb") as stream:
            stream.truncate(size)
        info = blob.stat()
        report = self.registry.storage_inventory()
        self.assertEqual(report["registered"]["stored"]["bytes"], size)
        self.assertEqual(report["registered"]["stored"]["allocated_bytes"],
                         info.st_blocks * 512 if hasattr(info, "st_blocks") else None)
        original_lstat = Path.lstat

        def no_allocation(path):
            result = original_lstat(path)
            if path == blob:
                return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size)
            return result

        with patch.object(Path, "lstat", no_allocation):
            unavailable = self.registry.storage_inventory()
        self.assertEqual(unavailable["registered"]["stored"]["bytes"], size)
        self.assertIsNone(unavailable["registered"]["stored"]["allocated_bytes"])
        self.assertEqual(unavailable["registered"]["stored"]["allocation_unavailable_files"], 1)

    def test_read_only_registry_and_fixed_database_sidecars_remain_unchanged(self):
        self.shared_fixture()
        (self.registry.root / "merlin.sqlite3-shm").write_bytes(b"synthetic-sidecar")
        before = self.snapshot()
        expected_db_bytes = sum((self.registry.root / p).stat().st_size for p in before
                                if p in ("merlin.sqlite3", "merlin.sqlite3-journal",
                                         "merlin.sqlite3-wal", "merlin.sqlite3-shm"))
        read_only = PrivateReadOnlyRegistry(self.registry.root)
        report = MerlinReadAPI(read_only).storage_inventory()
        self.assertEqual(report["sqlite_files"]["bytes"], expected_db_bytes)
        self.assertEqual(report["registered"]["declared_bytes"], 17)
        self.assertEqual(self.snapshot(), before)

    def test_unreadable_observations_and_invalid_limits_are_not_zero_totals(self):
        self.shared_fixture()
        original_lstat = Path.lstat

        def unreadable(path):
            if path == self.blob(self.retired):
                raise PermissionError("fixture denied stat")
            return original_lstat(path)

        with patch.object(Path, "lstat", unreadable), patch.object(
                registry_module.os, "scandir", side_effect=PermissionError("fixture denied scan")):
            report = self.registry.storage_inventory()
        self.assertEqual(report["registered"]["declared_bytes"], 17)
        self.assertEqual(report["registered"]["stored"]["unreadable_files"], 1)
        self.assertIsNone(report["registered"]["stored"]["bytes"])
        self.assertIsNone(report["historical_only"]["stored"]["bytes"])
        self.assertEqual(report["scan"]["cas_scan_errors"], 1)
        self.assertIsNone(report["unclassified_cas"]["bytes"])
        for value in (0, -1, 4097, True, False, 1.0, "1", None):
            with self.subTest(limit=value), self.assertRaises(ValueError):
                self.registry.storage_inventory(limit=value)


if __name__ == "__main__":
    unittest.main()
