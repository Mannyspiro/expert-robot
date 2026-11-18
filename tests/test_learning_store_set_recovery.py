"""Isolated offline drill for a single synthetic LMS/Titan store set."""
import hashlib
import json
import multiprocessing
import os
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


def backup(source, dest, progress=None):
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
        with closing(sqlite3.connect(dest)) as writer:
            reader.backup(writer, pages=8, progress=progress)
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


# Private, single-publisher fixture. Only CURRENT selects a generation.
# A hard child exit leaves all partial output in place for the reader and retry.
PUBLICATION_STAGES = (
    "stage_created", "registry_ready", "learning_backup_in_progress", *DATABASES, "pins_written",
    "generation_named", "pointer_part_written", "pointer_prepared", "pointer_replaced",
)
CRASH_EXIT = 73


def publish_fixture(source, catalog, stop_after=None):
    def checkpoint(stage):
        if stop_after == stage:
            os._exit(CRASH_EXIT)

    stage = Path(tempfile.mkdtemp(prefix=".building-", dir=catalog))
    generation = stage.name.replace(".building-", "generation-", 1)
    checkpoint("stage_created")
    receipt = create_snapshot(source / "registry", stage / "registry")
    pins = {"registry": receipt["manifest_sha256"]}
    checkpoint("registry_ready")
    for name in DATABASES:
        def progress(status, remaining, total):
            if name == DATABASES[0] and 0 < remaining < total:
                checkpoint("learning_backup_in_progress")

        backup(source / name, stage / name, progress=progress)
        pins[name] = digest(stage / name)
        checkpoint(name)
    manifest = stage / "pins.json"
    manifest.write_text(json.dumps(pins, sort_keys=True))
    pointer = {"generation": generation, "manifest_sha256": digest(manifest)}
    checkpoint("pins_written")
    stage.rename(catalog / generation)
    checkpoint("generation_named")
    with tempfile.NamedTemporaryFile(mode="w", prefix=".pointer-", dir=catalog, delete=False) as file:
        # Force some bytes of an incomplete selector into the filesystem.
        encoded = json.dumps(pointer)
        file.write(encoded[:1])
        file.flush()
        checkpoint("pointer_part_written")
        file.write(encoded[1:])
    checkpoint("pointer_prepared")
    os.replace(file.name, catalog / "CURRENT")
    checkpoint("pointer_replaced")
    return pointer


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

    def test_process_exit_during_generation_publication(self):
        def assert_replay(catalog, pointer, destination, original, revision):
            bundle = catalog / pointer["generation"]
            manifest = bundle / "pins.json"
            self.assertEqual(digest(manifest), pointer["manifest_sha256"])
            restore_fixture(bundle, destination, json.loads(manifest.read_text()))
            with closing(sqlite3.connect(destination / DATABASES[0])) as db:
                self.assertEqual(db.execute("SELECT status FROM learning_submissions").fetchall(),
                                 [("pending_review",)])
            replay = run_synthetic_titan_demo(destination, revision)
            for key in ("lab", "frozen_transcript_ref", "manifest_sha256", "recommendation_sha256"):
                self.assertEqual(original[key], replay[key], key)
            self.assertTrue(replay["submission"]["duplicate"])
            self.assertFalse(replay["submission"]["mastery_updated"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline"
            baseline.mkdir()
            versions = ("a" * 40, "b" * 40)
            sources = [root / "source-a", root / "source-b"]
            originals = []
            for source, revision in zip(sources, versions):
                source.mkdir()
                originals.append(run_synthetic_titan_demo(source, revision))
            self.assertNotEqual(originals[0]["lab"]["artifact_ref"], originals[1]["lab"]["artifact_ref"])
            prior = publish_fixture(sources[0], baseline)
            ctx = multiprocessing.get_context("spawn")
            for step in PUBLICATION_STAGES:
                with self.subTest(step=step):
                    case = root / step
                    catalog = case / "catalog"
                    shutil.copytree(baseline, catalog)
                    worker = ctx.Process(target=publish_fixture, args=(sources[1], catalog, step))
                    worker.start()
                    worker.join(20)
                    if worker.is_alive():
                        worker.kill()
                        worker.join()
                        self.fail("publisher timed out at " + step)
                    self.assertEqual(worker.exitcode, CRASH_EXIT)
                    selected = json.loads((catalog / "CURRENT").read_text())
                    committed = step == "pointer_replaced"
                    self.assertEqual(selected == prior, not committed)
                    index = int(committed)
                    assert_replay(catalog, selected, case / "selected", originals[index], versions[index])
                    if committed:
                        assert_replay(catalog, prior, case / "prior", originals[0], versions[0])
                    # Retry with partial directories or an already-selected generation still present.
                    retried = publish_fixture(sources[1], catalog)
                    self.assertEqual(json.loads((catalog / "CURRENT").read_text()), retried)
                    assert_replay(catalog, retried, case / "retried", originals[1], versions[1])
