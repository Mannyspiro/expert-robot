"""Offline Linux model+interpreter ZIP fixture and negative integrity tests.

No model weights, network, privileged installation or real executable invocation.
The archive verifier checks exact bytes, not license rights or runtime success.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_offline_profile as profile_builder
from build_offline_profile import build
from verify_offline_profile import verify as verify_profile
from extract_offline_profile import extract as safe_extract


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

    def test_legitimate_runtime_bytecode_cache_is_not_archived(self):
        # python-build-standalone can contain precompiled __pycache__ members.
        # They are derived artifacts; omit, do not publish or use them.
        cache = self.runtime / "lib" / "python3.11" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "site.cpython-311.pyc").write_bytes(b"synthetic bytecode cache")
        records = profile_builder.runtime_records(self.runtime)
        self.assertFalse(any("__pycache__" in Path(row[0]).parts for row in records))
        output = build(**self.inputs)
        self.assertFalse(output["production_qualified"])
        with zipfile.ZipFile(self.inputs["output"]) as archive:
            self.assertFalse(any("__pycache__" in Path(name).parts
                                 for name in archive.namelist()))

    def test_secret_runtime_paths_are_still_rejected_with_cache_present(self):
        cache = self.runtime / "lib" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "site.pyc").write_bytes(b"cache")
        hidden = self.runtime / ".ssh"
        hidden.mkdir()
        (hidden / "id_rsa").write_bytes(b"synthetic test only")
        with self.assertRaisesRegex(ValueError, "secret"):
            profile_builder.runtime_records(self.runtime)
        (hidden / "id_rsa").unlink()
        hidden.rmdir()
        other = self.runtime / "credentials"
        other.mkdir()
        (other / "secret.txt").write_bytes(b"synthetic test only")
        with self.assertRaisesRegex(ValueError, "secret"):
            profile_builder.runtime_records(self.runtime)

    def test_legitimate_large_manifest_accepts_many_runtime_records(self):
        # A real standalone Python runtime has thousands of long-path entries.
        # The verifier's file-count budget must agree with its byte budget.
        root = self.runtime / "lib" / "python3.11" / "site-packages" / "synthetic_pkg"
        root.mkdir(parents=True)
        for i in range(4200):
            filename = "typed_module_%04d_" % i + ("m" * 78) + ".py"
            (root / filename).write_bytes(b"")
        output = build(**self.inputs)
        self.assertEqual(output["status"], "built_unqualified")
        with zipfile.ZipFile(self.inputs["output"]) as archive:
            info = archive.getinfo("Merlin_Studio/OFFLINE_PROFILE_MANIFEST.json")
            self.assertGreater(info.file_size, 1024 * 1024)
            self.assertLess(info.file_size, 4 * 1024 * 1024)
        self.assertTrue(verify_profile(self.inputs["output"])["verified"])

    def test_excessively_large_manifest_is_still_rejected(self):
        build(**self.inputs)
        original = self.inputs["output"]
        altered = original.with_name("oversized-manifest.zip")
        with zipfile.ZipFile(original) as reader, zipfile.ZipFile(altered, "w") as writer:
            for info in reader.infolist():
                raw = reader.read(info)
                if info.filename == "Merlin_Studio/OFFLINE_PROFILE_MANIFEST.json":
                    manifest = json.loads(raw)
                    manifest["extra_unreviewed_payload"] = "x" * (4 * 1024 * 1024 + 1000)
                    raw = (json.dumps(manifest) + "\\n").encode("utf-8")
                writer.writestr(info, raw)
        with self.assertRaisesRegex(ValueError, "unbounded manifest"):
            verify_profile(altered)

    def test_safe_extractor_cli_resolves_sibling_verifier_in_isolated_python(self):
        # The native OCI packaging lane invokes exactly this isolated CLI.
        build(**self.inputs)
        dest = self.inputs["output"].with_name("cli-extracted")
        process = subprocess.run(
            [sys.executable, "-I", "-B",
             str(ROOT / "scripts" / "extract_offline_profile.py"),
             str(self.inputs["output"]), "--destination", str(dest)],
            cwd=str(ROOT), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        observed = json.loads(process.stdout)
        self.assertEqual(observed["status"], "extracted_unqualified")
        self.assertFalse(observed["production_qualified"])
        self.assertTrue((dest / "Merlin_Studio" / "runtime" / "python" / "bin" / "python3").is_symlink())

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

    def test_world_writable_inference_executable_not_admitted(self):
        build(**self.inputs)
        original = self.inputs["output"]
        altered = original.with_name("world-writable.zip")
        with zipfile.ZipFile(original) as reader, zipfile.ZipFile(altered, "w") as writer:
            for member in reader.infolist():
                payload = reader.read(member)
                if member.filename == "Merlin_Studio/bin/llama-server":
                    member.external_attr = (stat.S_IFREG | 0o777) << 16
                writer.writestr(member, payload)
        with self.assertRaisesRegex(ValueError, "permission bits"):
            verify_profile(altered)

    def test_embedded_control_character_archive_path_rejected(self):
        build(**self.inputs)
        with zipfile.ZipFile(self.inputs["output"], "a") as archive:
            name = "Merlin_Studio/runtime/python/bad\nname.py"
            item = zipfile.ZipInfo(name)
            item.create_system = 3
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(item, b"not expected")
        with self.assertRaisesRegex(ValueError, "invalid ZIP path"):
            verify_profile(self.inputs["output"])

    def test_source_file_swap_between_pin_check_and_zip_copy_is_rejected(self):
        # The archive must not silently replace the originally approved model
        # if another process swaps it after the initial SHA check.
        model = self.inputs["gguf_model"]
        original = profile_builder.assert_hash
        changed = []
        def mutate_after_check(path, expected, *, max_size):
            result = original(path, expected, max_size=max_size)
            if Path(path) == model:
                model.write_bytes(b"GGUF" + b"altered later" * 38)
                changed.append(True)
            return result
        with patch.object(profile_builder, "assert_hash", side_effect=mutate_after_check):
            with self.assertRaisesRegex(ValueError, "pinned model changed"):
                build(**self.inputs)
        self.assertEqual(changed, [True])
        self.assertFalse(self.inputs["output"].exists())

    def test_manifest_claims_cannot_disagree_with_actual_asset_digests(self):
        build(**self.inputs)
        for field in ("model_expected_sha256", "python_expected_sha256",
                      "llama_expected_sha256"):
            with self.subTest(field=field):
                original = self.inputs["output"]
                replacement = original.with_name(field + ".zip")
                with zipfile.ZipFile(original) as reader, zipfile.ZipFile(replacement, "w") as writer:
                    for member in reader.infolist():
                        raw = reader.read(member)
                        if member.filename == "Merlin_Studio/OFFLINE_PROFILE_MANIFEST.json":
                            manifest = json.loads(raw)
                            manifest[field] = "0" * 64
                            raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
                        writer.writestr(member, raw)
                with self.assertRaisesRegex(ValueError, "profile expected"):
                    verify_profile(replacement)

    def test_safe_extractor_restores_python_alias_and_file_modes(self):
        build(**self.inputs)
        destination = self.inputs["output"].with_name("extracted")
        receipt = safe_extract(self.inputs["output"], destination)
        self.assertEqual(receipt["status"], "extracted_unqualified")
        self.assertFalse(receipt["runtime_executed"])
        root = destination / "Merlin_Studio"
        py = root / "runtime/python/bin/python3"
        self.assertTrue(py.is_symlink())
        self.assertEqual(py.readlink().as_posix(), "python3.11")
        target = root / "runtime/python/bin/python3.11"
        self.assertEqual(target.read_bytes(), synthetic_elf())
        with zipfile.ZipFile(self.inputs["output"]) as verified:
            archived = verified.getinfo("Merlin_Studio/runtime/python/bin/python3.11")
            manifest = json.loads(verified.read("Merlin_Studio/OFFLINE_PROFILE_MANIFEST.json"))
            record = next(x for x in manifest["files"] if x["path"] == "runtime/python/bin/python3.11")
            self.assertEqual(record["mode"], "0755", "Builder lost source executable declaration")
            self.assertEqual(archived.external_attr >> 16 & 0o777, 0o755, "ZIP lost source execute bits")
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        llama = root / "bin/llama-server"
        self.assertEqual(llama.read_bytes(), synthetic_elf())
        self.assertEqual(llama.stat().st_mode & 0o777, 0o755,
                         "A second executable with different archive order lost its mode")
        for quiet in ("README.md", "models/merlin-local.gguf",
                      "licenses/model.txt", "OFFLINE_PROFILE_MANIFEST.json"):
            self.assertEqual((root / quiet).stat().st_mode & 0o777, 0o644,
                             "A nonexecutable file became executable: " + quiet)
        model = root / "models/merlin-local.gguf"
        self.assertEqual(model.read_bytes(), self.inputs["gguf_model"].read_bytes())
        self.assertEqual(model.stat().st_mode & 0o777, 0o644)
        self.assertEqual((root / "runtime/python/lib/empty-metadata.pth").read_bytes(), b"")

    def test_safe_extractor_rejects_preexisting_destination_without_mutation(self):
        build(**self.inputs)
        destination = self.inputs["output"].with_name("preexisting")
        destination.mkdir()
        existing = destination / "private.txt"
        existing.write_text("keep")
        with self.assertRaisesRegex(ValueError, "must not already exist"):
            safe_extract(self.inputs["output"], destination)
        self.assertEqual(existing.read_text(), "keep")

    def test_safe_extractor_never_unpacks_tampered_model(self):
        build(**self.inputs)
        altered = self.inputs["output"].with_name("bad-model.zip")
        with zipfile.ZipFile(self.inputs["output"]) as source, zipfile.ZipFile(altered, "w") as out:
            for item in source.infolist():
                content = source.read(item)
                if item.filename == "Merlin_Studio/models/merlin-local.gguf":
                    content = b"GGUF" + b"changed bytes"
                out.writestr(item, content)
        destination = self.inputs["output"].with_name("reject-extraction")
        with self.assertRaisesRegex(ValueError, "digest differs"):
            safe_extract(altered, destination)
        self.assertFalse(destination.exists())

    def test_safe_extractor_rolls_back_partial_install_after_symlink_failure(self):
        build(**self.inputs)
        destination = self.inputs["output"].with_name("rollback")
        with patch("extract_offline_profile.os.symlink",
                   side_effect=OSError("forced link creation failure")):
            with self.assertRaisesRegex(OSError, "forced link creation"):
                safe_extract(self.inputs["output"], destination)
        self.assertFalse(destination.exists())

    def test_unreviewed_publisher_origin_or_missing_license_fails(self):
        with self.assertRaisesRegex(ValueError, "HTTPS publisher"):
            build(**{**self.inputs, "model_origin": "file:///tmp/model.gguf"})
        self.inputs["model_license"].unlink()
        with self.assertRaises(ValueError):
            build(**self.inputs)
        self.assertFalse(self.inputs["output"].exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
