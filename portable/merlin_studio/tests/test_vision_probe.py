"""Operator local vision evidence probe tests without any real-model claim."""
from __future__ import annotations

from hashlib import sha256
from contextlib import redirect_stderr
import io
from unittest.mock import patch
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import zlib

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO))
from vision_probe import probe_image, save_report, main


def png():
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
            chunk(b"IDAT", zlib.compress(b"\0\x00\xff\x00")) +
            chunk(b"IEND", b""))


class StubModel:
    def __init__(self, settings, *, invalid=False):
        self.settings = settings
        self.invalid = invalid
        self.calls = []

    def describe_png(self, data, *, prompt, timeout):
        self.calls.append((data, prompt, timeout))
        return {"schema": "merlin-local-vision-interpretation/1",
                "source_sha256": "f" * 64 if self.invalid else sha256(data).hexdigest(),
                "model_id": self.settings["model_id"],
                "caption": "synthetic caption; not real vision",
                "independent_verification": False}


class VisionProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "known.png"
        self.data = png()
        self.path.write_bytes(self.data)
        self.kwargs = {
            "image": self.path,
            "expected_sha256": sha256(self.data).hexdigest(),
            "model_url": "http://127.0.0.1:8772/v1/chat/completions",
            "model_id": "synthetic-test",
            "question": "What is the visible color?",
        }

    def test_exact_sha_and_unqualified_receipt_survive_create_only_write(self):
        stubs = []
        def factory(settings):
            stub = StubModel(settings)
            stubs.append(stub)
            return stub
        report = probe_image(**self.kwargs, model_factory=factory)
        self.assertEqual(report["status"], "response_requires_independent_review")
        self.assertFalse(report["real_model_weights_attested"])
        self.assertFalse(report["grounded_visual_accuracy_measured"])
        self.assertFalse(report["promotion_authority"])
        self.assertEqual(report["source_pixels"], [1, 1])
        self.assertEqual(report["endpoint"]["host"], "127.0.0.1")
        self.assertEqual(len(stubs), 1)
        self.assertEqual(stubs[0].calls[0][0], self.data)
        self.assertEqual(stubs[0].calls[0][1], "What is the visible color?")
        out = Path(self.temp.name) / "probe.json"
        save_report(out, report)
        self.assertEqual(json.loads(out.read_text())["source_sha256"], self.kwargs["expected_sha256"])
        with self.assertRaises(FileExistsError):
            save_report(out, report)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)

    def test_source_hash_mismatch_never_invokes_model(self):
        calls = []
        def factory(settings):
            calls.append(settings)
            return StubModel(settings)
        with self.assertRaises(ValueError):
            probe_image(**{**self.kwargs,"expected_sha256":"0"*64}, model_factory=factory)
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            probe_image(**{**self.kwargs,"expected_sha256":"not-a-digest"}, model_factory=factory)
        self.assertEqual(calls, [])

    def test_nonlocal_endpoint_or_invalid_question_fails(self):
        for changed in (
            {"model_url":"https://example.org/v1/chat/completions"},
            {"model_url":"http://example.org/v1/chat/completions"},
            {"model_url":""}, {"question":""},
            {"question":"Q"*1001}, {"timeout":60}, {"timeout":float("nan")},
            {"model_id":""},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    probe_image(**{**self.kwargs,**changed}, model_factory=StubModel)

    def test_invalid_provider_identity_cannot_be_recorded(self):
        with self.assertRaises(ValueError):
            probe_image(**self.kwargs, model_factory=lambda settings: StubModel(settings, invalid=True))

    def test_invalid_png_is_checked_before_model_request(self):
        self.path.write_bytes(b"not-an-image")
        invalid = {**self.kwargs,"expected_sha256":sha256(b"not-an-image").hexdigest()}
        with self.assertRaises(ValueError):
            probe_image(**invalid, model_factory=StubModel)

    def test_command_preserves_failed_attempt_receipt_without_model_claim(self):
        output = Path(self.temp.name) / "blocked.json"
        argv = ["vision_probe.py", "--image", str(self.path),
                "--image-sha256", "0" * 64,
                "--model-url", self.kwargs["model_url"],
                "--model-id", self.kwargs["model_id"],
                "--question", self.kwargs["question"],
                "--out", str(output)]
        with patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
            self.assertEqual(main(), 2)
        record = json.loads(output.read_text())
        self.assertEqual(record["status"], "blocked_requires_review")
        self.assertFalse(record["source_identity_verified"])
        self.assertFalse(record["independent_verification"])
        self.assertFalse(record["promotion_authority"])
        self.assertEqual(record["model_request_effect"], "unknown_or_not_started")

    def test_symlink_and_fifo_are_not_accepted_as_source(self):
        link = Path(self.temp.name) / "shortcut.png"
        try:
            link.symlink_to(self.path)
        except (NotImplementedError, OSError):
            self.skipTest("Symlink unsupported on host")
        with self.assertRaises((OSError, ValueError)):
            probe_image(**{**self.kwargs,"image":link}, model_factory=StubModel)


if __name__ == "__main__":
    unittest.main()
