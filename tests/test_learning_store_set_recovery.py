"""Isolated offline drill for a single synthetic LMS/Titan store set."""
import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from dot_ai_os.recovery import RecoveryError, create_snapshot, restore_snapshot
from merlin.learning_platform import LearningPlatform
from merlin.learning_titan_course import run_synthetic_titan_demo

DATABASES = ("learning.sqlite3", "hypotheses.sqlite3", "graph.sqlite3")


def backup(source, dest):
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
        with closing(sqlite3.connect(dest)) as writer:
            reader.backup(writer)
            writer.execute("PRAGMA journal_mode=DELETE")
            if writer.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite backup failed integrity check")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_fixture(bundle, destination, pins):
    # Fixed filenames and private, quiescent test directories only.
    for name in DATABASES:
        if digest(bundle / name) != pins[name]:
            raise ValueError("store identity mismatch: " + name)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as stage:
        staged = Path(stage) / "stores"
        staged.mkdir()
        restore_snapshot(bundle / "registry", staged / "registry", pins["registry"])
        for name in DATABASES:
            shutil.copyfile(bundle / name, staged / name)
            if digest(staged / name) != pins[name]:
                raise ValueError("restored database digest mismatch: " + name)
        staged.rename(destination)


class LearningStoreRecoveryTests(unittest.TestCase):
    def test_committed_wal_and_registry_restore_as_one_replayable_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, bundle, restored = (root / name for name in ("source", "bundle", "restored"))
            source.mkdir()
            bundle.mkdir()
            revision = "a" * 40
            learning = source / DATABASES[0]
            LearningPlatform(learning)
            backup(learning, root / "old.sqlite3")
            with closing(sqlite3.connect(learning)) as observer:
                self.assertEqual(observer.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0], 0)
                observer.execute("BEGIN")
                self.assertEqual(observer.execute("SELECT COUNT(*) FROM learning_submissions").fetchone(), (0,))
                before = run_synthetic_titan_demo(source, revision)
                # The old read transaction keeps the committed submission in the WAL.
                self.assertGreater((source / "learning.sqlite3-wal").stat().st_size, 32)
                with closing(sqlite3.connect(learning.as_uri() + "?immutable=1", uri=True)) as main_only:
                    self.assertEqual(main_only.execute("SELECT COUNT(*) FROM learning_submissions").fetchone(), (0,))
                # All application writes have returned. Only our read transaction remains.
                registry = create_snapshot(source / "registry", bundle / "registry")
                pins = {"registry": registry["manifest_sha256"]}
                for name in DATABASES:
                    backup(source / name, bundle / name)
                    pins[name] = digest(bundle / name)
            restore_fixture(bundle, restored, pins)
            for name in DATABASES:
                self.assertEqual(digest(restored / name), pins[name])
            with closing(sqlite3.connect(restored / DATABASES[0])) as db:
                self.assertEqual(db.execute("SELECT status FROM learning_submissions").fetchall(),
                                 [("pending_review",)])
            after = run_synthetic_titan_demo(restored, revision)
            for key in ("lab", "frozen_transcript_ref", "manifest_sha256", "recommendation_sha256"):
                self.assertEqual(before[key], after[key], key)
            self.assertTrue(after["submission"]["duplicate"])
            self.assertFalse(after["submission"]["mastery_updated"])
            with self.assertRaises(FileExistsError):
                restore_fixture(bundle, restored, pins)
            with self.assertRaises(RecoveryError):
                restore_fixture(bundle, root / "wrong-registry", dict(pins, registry="0" * 64))
            self.assertFalse((root / "wrong-registry").exists())
            # An intact but earlier LMS database cannot satisfy this store set's pins.
            shutil.copyfile(root / "old.sqlite3", bundle / DATABASES[0])
            with self.assertRaisesRegex(ValueError, "store identity mismatch: learning.sqlite3"):
                restore_fixture(bundle, root / "stale", pins)
            self.assertFalse((root / "stale").exists())
