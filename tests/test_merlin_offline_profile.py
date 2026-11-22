"""Offline Linux model+interpreter ZIP fixture and negative integrity tests.

No model weights, network, privileged installation or real executable invocation.
The archive verifier checks exact bytes, not license rights or runtime success.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable"))
sys.path.insert(0, str(ROOT / "scripts"))
from build_offline_profile import build
from verify_offline_profile import verify as verify_profile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def synthetic_elf(machine=62):
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    header[18:20] = struct.pack("<H", machine)
    return bytes(header)


def studio_fixture(path):
    source = b"Offline UI synthetic fixture only\n"
    record = {"path": "README.md", "bytes": len(source), "sha256": digest(source),
              "mode": "0644", "source": "synthetic"}
    manifest = {
        "schema": "merlin-studio-portable/1",
        "archive_root": "Merlin_Studio",
        "native_protocol": {"included": False},
        "contains_model_weights": False,
        "contains_python_runtime": False,
        "files": [record],
    }
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in (
                ("README.md", source),
                ("PACKAGE_MANIFEST.json",
                 (json.dumps(manifest, sort_keys=True) + "\n").encode())):
            info = zipfile.ZipInfo("Merlin_Studio/" + name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, contents)


class OfflineProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        studio = root / "studio.zip"
        studio_fixture(studio)
        runtime = root / "python-runtime"
        (runtime / "bin").mkdir(parents=True)
        python = runtime / "bin" / "python3.11"
        python.write_bytes(synthetic_elf())
        python.chmod(0o755)
        (runtime / "bin" / "python3").symlink_to("python3.11")
        (runtime / "lib").mkdir()
        (runtime / "lib" / "empty-metadata.pth").write_bytes(b"")
        llama = root / "llama-server"
        llama.write_bytes(synthetic_elf())
        llama.chmod(0o755)
        model = root / "model.gguf"
        model.write_bytes(b"GGUF" + b"synthetic GGUF data" * 32)
        licenses = []
        for name in ("model", "inference", "python"):
            destination = root / (name + "-license.txt")
            destination.write_text("Synthetic license fixture for " + name + "\n")
            licenses.append(destination)
        self.runtime = runtime
        self.inputs = {
            "studio_zip": studio, "python_root": runtime,
            "python_sha256": digest(python.read_bytes()),
            "llama_server": llama, "llama_sha256": digest(llama.read_bytes()),
            "gguf_model": model, "gguf_sha256": digest(model.read_bytes()),
            "model_license": licenses[0], "inference_license": licenses[1],
            "python_license": licenses[2],
            "target": "linux-x86_64",
            "model_origin": "https://huggingface.co/Qwen/example-fixture",
            "inference_origin": "https://github.com/ggml-org/llama.cpp",
            "python_origin": "https://github.com/astral-sh/python-build-standalone",
            "output": root / "full.zip",
        }

    def test_complete_profile_reproducible_and_unqualified(self):
        first = build(**self.inputs)
        self.assertEqual(first["status"], "built_unqualified")
        self.assertFalse(first["production_qualified"])
        self.assertFalse(first["native_executable_started"])
        report = verify_profile(self.inputs["output"])
        self.assertTrue(report["verified"])
        self.assertTrue(report["contains_model_weights"])
        self.assertFalse(report["license_review_completed"])
        self.assertFalse(report["authenticity_verified"])
        with zipfile.ZipFile(self.inputs["output"]) as archive:
            info = archive.getinfo("Merlin_Studio/runtime/python/bin/python3")
            self.assertTrue(stat.S_ISLNK(info.external_attr >> 16))
            self.assertEqual(archive.read(info), b"python3.11")
            self.assertEqual(archive.read("Merlin_Studio/runtime/python/lib/empty-metadata.pth"), b"")
            payload = json.loads(archive.read("Merlin_Studio/OFFLINE_PROFILE_MANIFEST.json"))
            self.assertEqual(payload["model_id"], "local")
            self.assertEqual(len(payload["origins"]), 3)
        new_inputs = {**self.inputs, "output": self.inputs["output"].with_name("second.zip")}
        second = build(**new_inputs)
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(self.inputs["output"].read_bytes(), new_inputs["output"].read_bytes())

    def test_wrong_model_digest_and_wrong_elf_architecture_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA256"):
            build(**{**self.inputs, "gguf_sha256": "a" * 64})
        llama = self.inputs["llama_server"]
        llama.write_bytes(synthetic_elf(183))
        with self.assertRaisesRegex(ValueError, "ELF target"):
            build(**{**self.inputs, "llama_sha256": digest(llama.read_bytes())})
        self.assertFalse(self.inputs["output"].exists())

    def test_symlink_escape_is_rejected_before_archive_written(self):
        path = self.runtime / "bad-symlink"
        path.symlink_to("../../outside.txt")
        with self.assertRaisesRegex(ValueError, "escapes"):
            build(**self.inputs)
        self.assertFalse(self.inputs["output"].exists())

    def test_extra_zip_member_is_rejected_on_verify(self):
        build(**self.inputs)
        with zipfile.ZipFile(self.inputs["output"], "a") as archive:
            info = zipfile.ZipInfo("Merlin_Studio/data/secret.json")
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, b"not authorized")
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            verify_profile(self.inputs["output"])

    def test_mutated_model_bytes_rejected_on_verify(self):
        build(**self.inputs)
        path = self.inputs["output"]
        alt = path.with_name("mutated.zip")
        with zipfile.ZipFile(path) as original, zipfile.ZipFile(alt, "w") as changed:
            for info in original.infolist():
                data = original.read(info)
                if info.filename == "Merlin_Studio/models/merlin-local.gguf":
                    data = b"GGUF" + b"changed" * 90
                changed.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "digest differs"):
            verify_profile(alt)

    def test_unreviewed_publisher_origin_or_missing_license_fails(self):
        with self.assertRaisesRegex(ValueError, "HTTPS publisher"):
            build(**{**self.inputs, "model_origin": "file:///tmp/model.gguf"})
        self.inputs["model_license"].unlink()
        with self.assertRaises(ValueError):
            build(**self.inputs)
        self.assertFalse(self.inputs["output"].exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
