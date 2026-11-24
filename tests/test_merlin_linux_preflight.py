"""Host/ABI/launcher boundaries; fixtures never execute a model."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
sys.path.insert(0, str(ROOT / "scripts/merlin"))
import linux_preflight as preflight
import linux_build_requirements as build_requirements


def elf(machine):
    raw = bytearray(64)
    raw[:6] = b"\x7fELF\x02\x01"
    raw[18:20] = struct.pack("<H", machine)
    return raw


class LinuxPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def stage(self, target="linux-x86_64"):
        raw = elf(preflight.PLATFORMS[target])
        for relative in ("bin/llama-server", "runtime/python/bin/python3"):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o755)
        digest = hashlib.sha256(raw).hexdigest()
        baseline, features = preflight.CPU_BASELINES[target]
        self.manifest = {"schema": "merlin-linux-offline-profile/1", "platform": target,
                         "llama_expected_sha256": digest, "python_expected_sha256": digest,
                         "runtime_requirements": {"schema": preflight.REQUIREMENTS_SCHEMA,
                          "platform": target, "cpu_baseline": baseline, "cpu_features": features,
                          "engine_sha256": digest, "python_sha256": digest, "system_libraries": ["libc.so.6"]}}
        self.write_manifest()
        (self.root / "OFFLINE_PLATFORM").write_text(target + "\n")
        return target, features

    def write_manifest(self):
        (self.root / "OFFLINE_PROFILE_MANIFEST.json").write_text(json.dumps(self.manifest))

    def check(self, target, features, **kwargs):
        with patch.object(preflight, "_host_platform", return_value=target), \
                patch.object(preflight, "_cpu_features", return_value=set(features)):
            return preflight.check_linux_host(self.root, **kwargs)

    def test_source_only_status_has_no_native_or_gpu_claim_and_spawns_nothing(self):
        with patch.object(preflight.subprocess, "Popen") as spawn:
            result = preflight.check_linux_host(self.root)
        spawn.assert_not_called()
        self.assertEqual(result["status"], "not_applicable")
        self.assertIsNone(result["model_ready"])
        self.assertFalse(result["gpu_execution_qualified"])

    def test_both_architecture_static_reports_are_read_only(self):
        for target in preflight.PLATFORMS:
            with self.subTest(target=target):
                _, features = self.stage(target)
                before = sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*"))
                with patch.object(preflight.subprocess, "Popen") as spawn:
                    result = self.check(target, features, data_dir=self.root / "new-state")
                spawn.assert_not_called()
                self.assertEqual(result["status"], "pass")
                self.assertFalse(result["abi"]["probe_performed"])
                self.assertEqual(before, sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*")))

    def test_wrong_architecture_and_cpu_flags_reject_before_probe(self):
        target, features = self.stage()
        with patch.object(preflight, "_version_probe") as probe:
            self.assertEqual(self.check("linux-aarch64", features, probe_binary=True)["status"], "blocked")
            result = self.check(target, features[:-1], probe_binary=True)
            self.assertEqual(result["cpu"]["missing"], ["sse4_2"])
        probe.assert_not_called()

    def test_executable_integrity_can_be_checked_without_an_abi_subprocess(self):
        target, features = self.stage()
        with patch.object(preflight.subprocess, "Popen") as spawn:
            result = self.check(target, features, verify_executables=True)
            self.assertEqual(result["status"], "pass")
            self.assertTrue(result["integrity"]["executable_digests_match"])
            self.assertFalse(result["abi"]["probe_performed"])
            with (self.root / "bin/llama-server").open("ab") as output:
                output.write(b"changed")
            result = self.check(target, features, verify_executables=True)
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["engine_compatible"])
        spawn.assert_not_called()

    def test_missing_requirements_wrong_elf_and_changed_bytes_reject(self):
        target, features = self.stage()
        with patch.object(preflight, "_version_probe") as probe:
            self.manifest.pop("runtime_requirements")
            self.write_manifest()
            self.assertEqual(self.check(target, features)["status"], "blocked")
            self.stage()
            (self.root / "bin/llama-server").write_bytes(elf(183))
            self.assertEqual(self.check(target, features)["status"], "blocked")
            self.stage()
            with (self.root / "bin/llama-server").open("ab") as output:
                output.write(b"changed")
            self.assertEqual(self.check(target, features, probe_binary=True)["status"], "blocked")
        probe.assert_not_called()

    def test_late_hash_read_failure_revokes_static_engine_compatibility(self):
        target, features = self.stage()
        for failure in (OSError("unreadable executable"), ValueError("changed during read")):
            with self.subTest(failure=type(failure).__name__), \
                    patch.object(preflight, "_sha256", side_effect=failure), \
                    patch.object(preflight, "_version_probe") as probe:
                self.assertTrue(self.check(target, features)["engine_compatible"])
                result = self.check(target, features, verify_executables=True)
                self.assertEqual(result["status"], "blocked")
                self.assertIs(result["engine_compatible"], False)
                self.assertIs(result["integrity"]["executable_digests_checked"], False)
                self.assertEqual(result["checks"][-1]["id"], "input_read")
                probe.assert_not_called()

    def test_marker_symlink_escape_duplicate_and_oversize_metadata_reject(self):
        target, features = self.stage()
        marker = self.root / "OFFLINE_PLATFORM"
        marker.write_text("linux-aarch64\n")
        self.assertEqual(self.check(target, features)["status"], "blocked")
        marker.unlink()
        marker.symlink_to("OFFLINE_PROFILE_MANIFEST.json")
        self.assertEqual(self.check(target, features)["status"], "blocked")
        marker.unlink()
        marker.write_text(target + "\n")
        manifest = self.root / "OFFLINE_PROFILE_MANIFEST.json"
        for raw in ('{"platform":"linux-x86_64","platform":"linux-aarch64"}', "x" * (1024**2 + 1)):
            manifest.write_text(raw)
            self.assertEqual(self.check(target, features)["status"], "blocked")
        self.stage()
        python = self.root / "runtime/python/bin/python3"
        python.unlink()
        python.symlink_to(self.root / "bin/llama-server")
        self.assertEqual(self.check(target, features)["status"], "blocked")

    def script(self, body):
        path = self.root / "fake-version"
        path.write_text("#!" + sys.executable + "\n" + body)
        path.chmod(0o755)
        return path

    def test_actual_version_probe_isolated_environment_and_nonzero_exit(self):
        path = self.script("import os,sys\nassert sys.argv[1:]==['--version']\nassert 'MERLIN_TEST_SECRET' not in os.environ\nprint('version fixture')\n")
        with patch.dict(os.environ, {"MERLIN_TEST_SECRET": "must-not-propagate"}):
            result = preflight._version_probe(path, self.root)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["output_sha256"], hashlib.sha256(b"version fixture\n").hexdigest())
        path = self.script("raise SystemExit(7)\n")
        result = preflight._version_probe(path, self.root)
        self.assertFalse(result["compatible"])
        self.assertEqual(result["returncode"], 7)

    def test_actual_version_probe_output_and_deadline_are_bounded(self):
        path = self.script("import sys,time\nsys.stdout.buffer.write(b'x'*20000)\nsys.stdout.flush()\ntime.sleep(5)\n")
        result = preflight._version_probe(path, self.root)
        self.assertEqual(result["reason"], "version_probe_output_limit")
        self.assertLessEqual(result["output_bytes"], 16385)
        path = self.script("import time\ntime.sleep(5)\n")
        self.assertEqual(preflight._version_probe(path, self.root, timeout=0.05)["reason"], "version_probe_timeout")

    def test_shell_rejects_wrong_arch_before_executing_python(self):
        actual = preflight._host_platform()
        wrong = "linux-aarch64" if actual == "linux-x86_64" else "linux-x86_64"
        self.stage(wrong)
        shutil.copyfile(ROOT / "portable/merlin_studio/START.sh", self.root / "START.sh")
        python = self.root / "runtime/python/bin/python3"
        python.write_text("#!/bin/sh\ntouch executed-unexpectedly\n")
        result = subprocess.run(["sh", str(self.root / "START.sh"), "--check"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)
        self.assertFalse((self.root / "executed-unexpectedly").exists())


class BuildRequirementsTests(unittest.TestCase):
    def test_actual_compile_flags_must_match_declared_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            options = {name: "OFF" for name in ("GGML_NATIVE", "GGML_CUDA", "GGML_VULKAN", "LLAMA_BUILD_UI", "LLAMA_USE_PREBUILT_UI", "BUILD_SHARED_LIBS")}
            options["GGML_CPU_ARM_ARCH"] = "armv8-a"
            (root / "CMakeCache.txt").write_text("\n".join(key + ":STRING=" + value for key, value in options.items()))
            commands = root / "compile_commands.json"
            commands.write_text(json.dumps([{"file": "/source/ggml-cpu/test.c", "command": "cc -march=armv8-a -c test.c"}]))
            with patch.object(build_requirements.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "(NEEDED) Shared library: [libc.so.6]")):
                requirement, evidence = build_requirements.configuration(root, "linux-aarch64", "a"*64, "b"*64)
                self.assertEqual(requirement["cpu_features"], ["asimd"])
                self.assertEqual(evidence["cpu_compile_flags"], ["-march=armv8-a"])
                commands.write_text(json.dumps([{"file": "/source/ggml-cpu/test.c", "command": "cc -march=native -c test.c"}]))
                with self.assertRaisesRegex(ValueError, "host-native"):
                    build_requirements.configuration(root, "linux-aarch64", "a"*64, "b"*64)
                commands.write_text(json.dumps([{"file": "/source/ggml-cpu/test.c", "command": "cc -march=armv9-a+sve2 -c test.c"}]))
                with self.assertRaisesRegex(ValueError, "differ"):
                    build_requirements.configuration(root, "linux-aarch64", "a"*64, "b"*64)


if __name__ == "__main__":
    unittest.main()
