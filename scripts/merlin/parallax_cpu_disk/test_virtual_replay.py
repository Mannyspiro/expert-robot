#!/usr/bin/env python3
"""Small real-process checks for bounded evidence and exclusive launch locking."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_virtual_replay as replay
import parallax_virtual_probe as probe


class ReplayBoundaryTests(unittest.TestCase):
    def test_edit_to_imported_environment_helper_breaks_freeze(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            names = ["parallax_virtual_probe.py", "parallax_virtual_device.py", "parallax_virtual_memory.py",
                     "run_virtual_replay.py", "parallax_virtual_generate.py", "parallax_cpu_probe.py",
                     "parallax_direct_disk.py", "parallax_direct_probe.py", "parallax_disk_generate.py",
                     "setup_cpu_candidate.py", "run_replay.py"]
            for name in names:
                (root / name).write_bytes(b"# explicit synthetic source fixture\n")
            protocol = {"schema": "merlin-parallax-virtual-protocol/1", "prompt": "The capital of France is",
                        "cached_decode_steps": 3, "atol": 1e-5, "rtol": 1e-5,
                        "device": "cpu", "dtype": "float32", "attention": "eager", "torch_threads": 2,
                        "interop_threads": 1, "seed": 0, "managed_bytes": 32 * 1024**2,
                        "tile_rows": 4096, "expected_token_ids": [12095, 11, 323, 279],
                        "source_sha256": {name: replay.digest(root / name) for name in names}}
            path = root / "protocol.json"
            path.write_text(json.dumps(protocol))
            probe.verify_protocol(path, root)
            (root / "run_replay.py").write_bytes(b"# changed environment helper fixture\n")
            with self.assertRaisesRegex(ValueError, "source differs"):
                probe.verify_protocol(path, root)
            del protocol["source_sha256"]["run_replay.py"]
            path.write_text(json.dumps(protocol))
            with self.assertRaisesRegex(ValueError, "executed source closure"):
                probe.verify_protocol(path, root)

    def test_oversized_and_symlink_reference_refuse_before_read(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "large"
            with path.open("wb") as stream:
                stream.truncate(1024**2 + 1)
            link = root / "link"
            link.symlink_to(path)
            with patch.object(probe.os, "read", side_effect=AssertionError("unbounded read")):
                for value in (path, link):
                    with self.subTest(value=value.name), self.assertRaisesRegex(ValueError, "regular or exceeds"):
                        probe.bounded_read(value, 1024**2)

    def test_reference_shape_and_payload_bound_precede_tensor_loading(self):
        header, position = {}, 0
        for name, shape in probe.REFERENCE_SHAPES.items():
            size = shape[1] * shape[2] * 4
            header[name] = {"dtype": "F32", "shape": shape, "data_offsets": [position, position + size]}
            position += size
        def payload(value):
            raw = json.dumps(value).encode()
            return struct.pack("<Q", len(raw)) + raw + b"\0" * probe.REFERENCE_DATA_BYTES
        probe.validate_reference_arrays(payload(header))
        header["prefill"]["shape"] = [1, 5000000, 151936]
        with self.assertRaisesRegex(ValueError, "dtype, shape or data range"):
            probe.validate_reference_arrays(payload(header))
        with self.assertRaisesRegex(ValueError, "byte bound"):
            probe.validate_reference_arrays(b"x" * (9 + probe.REFERENCE_HEADER_BYTES + probe.REFERENCE_DATA_BYTES))

    def test_actual_child_log_is_bounded_and_hashed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            env = replay.constructed_environment(root / "private")
            report = {"launches": []}
            count = replay.LOG_LIMIT + 4096
            replay.run_child("no-model-log-fixture", [sys.executable, "-B", "-c",
                f"import sys; sys.stdout.buffer.write(b'x'*{count}); sys.stdout.flush()"], root, env, report)
            row = report["launches"][0]
            self.assertEqual(row["exit_code"], 0)
            self.assertEqual(row["log"]["bytes"], replay.LOG_LIMIT)
            self.assertEqual(row["log"]["stream_bytes_observed"], count)
            self.assertEqual(row["log"]["stream_sha256_observed"], hashlib.sha256(b"x" * count).hexdigest())
            self.assertTrue(row["log"]["captured_prefix_only"])

    def test_timeout_retains_failure_and_kills_child(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            env = replay.constructed_environment(root / "private")
            report = {"launches": []}
            with patch.object(replay, "CHILD_TIMEOUT", 0.1):
                with self.assertRaisesRegex(RuntimeError, "required exit status"):
                    replay.run_child("no-model-timeout-fixture", [sys.executable, "-B", "-c",
                        "import time; print('bounded fixture', flush=True); time.sleep(10)"], root, env, report)
            row = report["launches"][0]
            self.assertTrue(row["timed_out"])
            self.assertLess(row["exit_code"], 0)
            self.assertLess(row["elapsed_seconds"], 5)
            self.assertIn(b"bounded fixture", (root / "no-model-timeout-fixture.log").read_bytes())

    def test_shared_lock_blocks_a_distinct_process(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            env = replay.constructed_environment(root / "private")
            path = root / "experiment.lock"
            code = ("import fcntl,sys; f=open(sys.argv[1],'a+b');\n"
                    "try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
                    "except BlockingIOError: print('blocked'); raise SystemExit(0)\n"
                    "raise SystemExit(4)\n")
            report = {"launches": []}
            with replay.take_lock(path):
                replay.run_child("no-model-lock-fixture", [sys.executable, "-B", "-c", code, str(path)],
                                 root, env, report)
            self.assertEqual((root / "no-model-lock-fixture.log").read_text().strip(), "blocked")


if __name__ == "__main__":
    unittest.main()
