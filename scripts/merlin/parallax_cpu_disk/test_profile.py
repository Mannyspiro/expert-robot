#!/usr/bin/env python3
"""Small adversarial checks for the offline setup and direct-loader boundaries."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import acquire_locked as acquire
import parallax_cpu_probe as support
import parallax_direct_disk as direct
import parallax_disk_generate as generation
import run_replay
import setup_cpu_candidate as setup


class ProfileBoundaries(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, rows):
        path = self.root / "runtime.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, content, link in rows:
                info = tarfile.TarInfo(name)
                if link is not None:
                    info.type, info.linkname = tarfile.SYMTYPE, link
                    archive.addfile(info)
                else:
                    info.size = len(content)
                    archive.addfile(info, io.BytesIO(content))
        return path, {"bytes": path.stat().st_size, "sha256": support.sha256_file(path)}

    def test_runtime_retains_files_and_contained_links_excludes_only_bytecode(self):
        path, entry = self.archive([("python/lib/source.py", b"pass\n", None),
            ("python/LICENSE", b"notice", None), ("python/lib/alias.py", b"", "source.py"),
            ("python/lib/__pycache__/source.pyc", b"cache", None)])
        result = setup.safe_extract_runtime(path, self.root / "extract", entry)
        self.assertEqual(result["retained_members"], 3)
        self.assertEqual(len(result["excluded_bytecode"]), 1)
        self.assertEqual((self.root / "extract/python/lib/alias.py").read_bytes(), b"pass\n")
        self.assertFalse((self.root / "extract/python/lib/__pycache__").exists())

    def test_runtime_parent_traversal_rejected_before_extraction(self):
        path, entry = self.archive([("python/../../escape", b"bad", None)])
        with self.assertRaisesRegex(ValueError, "escapes"):
            setup.safe_extract_runtime(path, self.root / "extract", entry)
        self.assertFalse((self.root / "extract").exists())

    def test_runtime_escaping_symlink_rejected(self):
        path, entry = self.archive([("python/lib/alias", b"", "../../../outside")])
        with self.assertRaisesRegex(ValueError, "escapes"):
            setup.safe_extract_runtime(path, self.root / "extract", entry)

    def test_runtime_member_through_link_rejected(self):
        path, entry = self.archive([("python/lib/alias", b"", "target"),
            ("python/lib/alias/child", b"bad", None)])
        with self.assertRaisesRegex(ValueError, "descends through a symlink"):
            setup.safe_extract_runtime(path, self.root / "extract", entry)

    def test_runtime_wrong_hash_rejected_before_extraction(self):
        path, entry = self.archive([("python/LICENSE", b"notice", None)])
        entry["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "integrity"):
            setup.safe_extract_runtime(path, self.root / "extract", entry)
        self.assertFalse((self.root / "extract").exists())

    def test_downloader_parent_link_rejected_before_mkdir_or_network(self):
        base, outside = self.root / "base", self.root / "outside"
        base.mkdir()
        outside.mkdir()
        (base / "link").symlink_to(outside, target_is_directory=True)
        entry = {"path": "link/new/file", "bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest(),
                 "url": "https://huggingface.co/public/file"}
        with self.assertRaisesRegex(ValueError, "escaped"):
            acquire.acquire(entry, base, None)
        self.assertFalse((outside / "new").exists())

    def test_downloader_corrupt_cached_payload_rejected_without_replacing(self):
        target = self.root / "file"
        target.write_bytes(b"y")
        entry = {"path": "file", "bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest(),
                 "url": "https://huggingface.co/public/file"}
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            acquire.acquire(entry, self.root, None)
        self.assertEqual(target.read_bytes(), b"y")

    def test_checkpoint_alternate_directory_rejected_before_payload_read(self):
        (self.root / "checkpoint").mkdir()
        alternate = self.root / "alternate"
        alternate.mkdir()
        with patch.object(support, "verify_payloads") as read:
            with self.assertRaisesRegex(ValueError, "canonical nonsymlink"):
                direct.verify_fixed_checkpoint(alternate)
            read.assert_not_called()

    def test_checkpoint_symlink_rejected_before_payload_read(self):
        original = self.root / "actual"
        original.mkdir()
        link = self.root / "checkpoint"
        link.symlink_to(original, target_is_directory=True)
        with patch.object(support, "verify_payloads") as read:
            with self.assertRaisesRegex(ValueError, "canonical nonsymlink"):
                direct.verify_fixed_checkpoint(link)
            read.assert_not_called()

    def test_meta_inventory_requires_every_parameter_path(self):
        parameter = SimpleNamespace(device=SimpleNamespace(type="meta"))
        model = SimpleNamespace(named_parameters=lambda remove_duplicate: [(str(i), parameter) for i in range(366)])
        with self.assertRaisesRegex(ValueError, "meta"):
            support.assert_meta(model)
        model.named_parameters = lambda remove_duplicate: [(str(i), parameter) for i in range(367)]
        self.assertEqual(support.assert_meta(model)["named_parameter_paths"], 367)

    def test_generation_enforces_byte_and_output_bounds_before_model_load(self):
        for prompt, tokens in (("", 1), ("x" * 4097, 1), ("hello", 17), ("hello", True)):
            with self.subTest(prompt_bytes=len(prompt), tokens=tokens), self.assertRaises(ValueError):
                generation.validate_request(prompt, tokens)
        generation.validate_request("hello", 16)

    def test_replay_environment_drops_inherited_python_and_credentials(self):
        with patch.dict("os.environ", {"PYTHONPATH": "/untrusted", "HF_TOKEN": "synthetic-test-value"}):
            env = run_replay.constructed_environment(self.root / "env")
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("HF_TOKEN", env)
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(env["OMP_NUM_THREADS"], "2")


if __name__ == "__main__":
    unittest.main()
