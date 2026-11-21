import gc
import hashlib
import sqlite3
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from merlin import project_registry as registry_module
from merlin.project_registry import MerlinRegistry


class MerlinRegistryTests(unittest.TestCase):
    def test_content_addressed_artifact_roundtrip_and_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("merlin", "Merlin", metadata={"domain": "research"})
            digest = registry.put_artifact("merlin", "notes/idea.md", b"research idea", "text/markdown")
            self.assertTrue(registry.verify_artifact(digest))
            inventory = registry.inventory("merlin")
            self.assertEqual(inventory["artifacts"][0]["digest"], digest)
            self.assertEqual(inventory["artifacts"][0]["logical_path"], "notes/idea.md")

    def test_blob_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "x.bin", b"original")
            blob = registry.blobs / digest[:2] / digest[2:]
            blob.write_bytes(b"changed")
            self.assertFalse(registry.verify_artifact(digest))

    def test_rejects_path_traversal_and_unknown_project(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            with self.assertRaises(ValueError):
                registry.put_artifact("missing", "../escape", b"x")
            with self.assertRaises(KeyError):
                registry.put_artifact("missing", "valid.bin", b"x")


    def test_artifact_versions_are_append_only_and_reversion_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            first = registry.put_artifact("p", "math/result.json", b'{"value":1}', "application/json")
            second = registry.put_artifact("p", "math/result.json", b'{"value":2}', "application/json")
            self.assertEqual(registry.put_artifact(
                "p", "math/result.json", b'{"value":2}', "application/json"), second)
            third = registry.put_artifact("p", "math/result.json", b'{"value":1}', "application/json")
            history = registry.artifact_history("p", "math/result.json")
            self.assertEqual([item["version"] for item in history], [1, 2, 3])
            self.assertEqual([item["digest"] for item in history], [first, second, third])
            self.assertEqual([item["previous_digest"] for item in history],
                             [None, first, second])
            inventory = registry.inventory("p")
            self.assertEqual(inventory["artifacts"][0]["version"], 3)
            self.assertEqual(inventory["artifacts"][0]["digest"], third)

    def test_artifact_version_rows_reject_update_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "result.bin", b"v1")
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "UPDATE artifact_versions SET digest=? "
                        "WHERE project_id=? AND logical_path=? AND version=1",
                        ("0" * 64, "p", "result.bin"),
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with sqlite3.connect(registry.db_path) as db:
                    db.execute(
                        "DELETE FROM artifact_versions WHERE project_id=? "
                        "AND logical_path=? AND version=1", ("p", "result.bin")
                    )
            self.assertEqual(registry.artifact_history("p", "result.bin")[0]["digest"], digest)

    def test_legacy_current_artifact_is_backfilled_as_version_one(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "legacy.txt", b"legacy")
            with sqlite3.connect(registry.db_path) as db:
                db.execute("DROP TABLE artifact_versions")
            registry._initialize()
            history = registry.artifact_history("p", "legacy.txt")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["version"], 1)
            self.assertEqual(history[0]["digest"], digest)
            self.assertIsNone(history[0]["previous_digest"])

    def test_artifact_history_rejects_unknown_project_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            with self.assertRaises(KeyError):
                registry.artifact_history("missing", "result.bin")
            registry.register_project("p", "Project")
            with self.assertRaises(ValueError):
                registry.artifact_history("p", "../outside")

    def test_relation_identity_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
            registry.relate("p", "contains", "artifact:x", {"scope": "v1"})
            with self.assertRaisesRegex(ValueError, "different metadata"):
                registry.relate("p", "contains", "artifact:x", {"scope": "v2"})

    def test_verification_matches_full_hash_at_buffer_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            for size in (0, 4095, 4096, 4097, 262143, 262144, 262145):
                with self.subTest(size=size):
                    content = (bytes(range(256)) * (size // 256 + 1))[:size]
                    digest = registry.put_artifact("p", f"data/{size}.bin", content)
                    self.assertEqual(digest, hashlib.sha256(content).hexdigest())
                    self.assertTrue(registry.verify_artifact(digest))

    def test_large_blob_verification_and_resolution_have_bounded_peak_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "large.bin", b"x" * (8 * 1024 * 1024))
            ref = registry.artifact_ref("p", "large.bin")
            for operation in ("verify", "resolve"):
                with self.subTest(operation=operation):
                    gc.collect()
                    already_tracing = tracemalloc.is_tracing()
                    if not already_tracing:
                        tracemalloc.start()
                    start, _ = tracemalloc.get_traced_memory()
                    tracemalloc.reset_peak()
                    try:
                        value = (registry.verify_artifact(digest) if operation == "verify"
                                 else registry.resolve_artifact_ref(ref))
                        _, peak = tracemalloc.get_traced_memory()
                    finally:
                        if not already_tracing:
                            tracemalloc.stop()
                    self.assertTrue(value is True if operation == "verify" else value["verified"])
                    self.assertLess(peak - start, 1024 * 1024)

    def test_each_verification_rereads_corrupted_truncated_and_appended_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            original = b"exact canonical bytes"
            digest = registry.put_artifact("p", "data.bin", original)
            blob = registry.blobs / digest[:2] / digest[2:]
            for changed in (b"!" + original[1:], original[:-1], original + b"!"):
                with self.subTest(changed_bytes=len(changed)):
                    blob.write_bytes(original)
                    self.assertTrue(registry.verify_artifact(digest))
                    blob.write_bytes(changed)
                    self.assertFalse(registry.verify_artifact(digest))

    def test_unknown_and_missing_blobs_keep_rejection_behavior(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            self.assertFalse(registry.verify_artifact("0" * 64))
            digest = registry.put_artifact("p", "data.bin", b"present")
            ref = registry.artifact_ref("p", "data.bin")
            blob = registry.blobs / digest[:2] / digest[2:]
            blob.rename(blob.with_suffix(".retained-for-test"))
            self.assertFalse(registry.verify_artifact(digest))
            with self.assertRaisesRegex(RuntimeError, "content failed SHA-256 verification"):
                registry.resolve_artifact_ref(ref)

    def test_historical_reference_keeps_exact_bytes_after_version_append(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            registry.put_artifact("p", "data.bin", b"old bytes")
            ref = registry.artifact_ref("p", "data.bin")
            before = registry.resolve_artifact_ref(ref)
            registry.put_artifact("p", "data.bin", b"new bytes")
            result = registry.read_artifact_ref(ref)
            self.assertEqual(result["content"], b"old bytes")
            self.assertEqual(result["resolution"], {**before, "is_current": False})

    def test_read_rechecks_bytes_after_successful_resolution(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "data.bin", b"fresh bytes")
            ref = registry.artifact_ref("p", "data.bin")
            blob = registry.blobs / digest[:2] / digest[2:]
            resolve = registry.resolve_artifact_ref

            def resolve_then_mutate(value):
                result = resolve(value)
                blob.write_bytes(b"other bytes")
                return result

            with patch.object(registry, "resolve_artifact_ref", side_effect=resolve_then_mutate):
                with self.assertRaisesRegex(RuntimeError, "content digest changed during read"):
                    registry.read_artifact_ref(ref)

    def test_file_size_hint_never_skips_bytes_or_enlarges_buffer_without_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            content = b"x" * (512 * 1024 + 1)
            digest = registry.put_artifact("p", "data.bin", content)
            blob = registry.blobs / digest[:2] / digest[2:]
            for hint in (0, 1 << 60):
                with self.subTest(size_hint=hint):
                    blob.write_bytes(content)
                    with patch.object(registry_module.os, "fstat", return_value=SimpleNamespace(st_size=hint)):
                        self.assertTrue(registry.verify_artifact(digest))
                        with blob.open("r+b") as stream:
                            stream.seek(-1, 2)
                            stream.write(b"!")
                        self.assertFalse(registry.verify_artifact(digest))

    def test_read_errors_propagate_and_close_the_file(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MerlinRegistry(temp)
            registry.register_project("p", "Project")
            digest = registry.put_artifact("p", "data.bin", b"data")
            blob = registry.blobs / digest[:2] / digest[2:]
            stream = blob.open("rb")

            class FailedRead:
                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    stream.close()

                def fileno(self):
                    return stream.fileno()

                def read(self, *args):
                    raise OSError("synthetic read failure")

                readinto = read

            with patch.object(Path, "open", return_value=FailedRead()):
                with self.assertRaisesRegex(OSError, "synthetic read failure"):
                    registry.verify_artifact(digest)
            self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
