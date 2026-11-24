"""Fail-closed local-model launching and offline Studio survival checks.

All model files and subprocesses here are synthetic; real Qwen/ABI acceptance
remains separately required before qualifying a self-contained archive.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
import model as model_module
import linux_preflight
from model import BundledModel
from engine import Application


class DummyProcess:
    def poll(self): return 0


class BundledModelLauncherTests(unittest.TestCase):
    def stage(self, base):
        root = Path(base) / "Merlin_Studio"
        (root / "bin").mkdir(parents=True)
        (root / "models").mkdir(parents=True)
        (root / "bin" / "llama-server").write_bytes(b"synthetic no-execute")
        (root / "models" / "merlin-local.gguf").write_bytes(b"GGUF" + b"0" * 32)
        data = root / "data"
        data.mkdir()
        return root, data

    def test_fixed_loopback_and_local_alias_in_launch_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            with patch.dict(model_module.os.environ, {}, clear=True):
                with patch.object(model_module.subprocess, "Popen",
                                  return_value=DummyProcess()) as launch:
                        instance = BundledModel(root, data)
                        self.assertTrue(instance.start())
                        command = launch.call_args.args[0]
                        self.assertEqual(command[:3], [str(root / "bin/llama-server"),
                                                       "--model", str(root / "models/merlin-local.gguf")])
                        self.assertEqual(command[command.index("--alias")+1], "local")
                        self.assertEqual(command[command.index("--host")+1], "127.0.0.1")
                        self.assertEqual(command[command.index("--port")+1], "8772")
                        self.assertEqual(command[command.index("--threads")+1], "2")
                        self.assertEqual(command[command.index("--threads-batch")+1], "2")
                        self.assertIn("--jinja", command)
                        self.assertNotIn("https:", " ".join(command))
                        self.assertIs(launch.call_args.kwargs["stdin"], model_module.subprocess.DEVNULL)
                        instance.close()
                        self.assertIsNone(instance.process)
                        self.assertIsNone(instance.log)
                        self.assertTrue(instance.start())
                        self.assertEqual(launch.call_count, 2)
                        instance.close()

    def test_incompatible_binary_returns_false_without_crashing_offline_studio(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            with patch.dict(model_module.os.environ, {}, clear=True), \
                 patch.object(model_module.subprocess, "Popen", side_effect=PermissionError("secret path")):
                instance = BundledModel(root, data)
                self.assertFalse(instance.start())
                self.assertIsNone(instance.process)
                self.assertIsNone(instance.log)
                log = (data / "local-model.log").read_text()
                self.assertIn("PermissionError", log)
                self.assertNotIn("secret path", log)
                app = Application(root, data, start_bundled=True)
                try:
                    self.assertTrue(app.status()["setup_required"])
                    self.assertFalse(app.status()["model"]["configured"])
                finally:
                    app.close()

    def test_incompatible_profile_is_blocked_before_launch_and_offline_ui_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            (root / "OFFLINE_PROFILE_MANIFEST.json").write_text('{}')
            with patch.dict(model_module.os.environ, {}, clear=True), \
                    patch.object(model_module.subprocess, "Popen") as launch:
                instance = BundledModel(root, data)
                self.assertFalse(instance.start())
                launch.assert_not_called()
                app = Application(root, data, start_bundled=True)
                try:
                    self.assertTrue(app.status()["ready"])
                    self.assertTrue(app.status()["setup_required"])
                    launch.assert_not_called()
                finally:
                    app.close()

    def test_changed_same_architecture_engine_never_launches_and_ui_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            raw = bytearray(64)
            raw[:6] = b"\x7fELF\x02\x01"
            raw[18:20] = struct.pack("<H", 62)
            pin = hashlib.sha256(raw).hexdigest()
            for relative in ("bin/llama-server", "runtime/python/bin/python3"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                path.chmod(0o755)
            baseline, features = linux_preflight.CPU_BASELINES["linux-x86_64"]
            manifest = {"schema": "merlin-linux-offline-profile/1", "platform": "linux-x86_64",
                "llama_expected_sha256": pin, "python_expected_sha256": pin,
                "runtime_requirements": {"schema": linux_preflight.REQUIREMENTS_SCHEMA,
                    "platform": "linux-x86_64", "cpu_baseline": baseline, "cpu_features": features,
                    "engine_sha256": pin, "python_sha256": pin, "system_libraries": []}}
            (root / "OFFLINE_PROFILE_MANIFEST.json").write_text(json.dumps(manifest))
            (root / "OFFLINE_PLATFORM").write_text("linux-x86_64\n")
            # Same ELF/CPU metadata still passes static compatibility. Only the
            # launch-boundary digest check rejects these changed engine bytes.
            with (root / "bin/llama-server").open("ab") as output:
                output.write(b"changed engine bytes")
            with patch.dict(model_module.os.environ, {}, clear=True), \
                    patch.object(linux_preflight, "_host_platform", return_value="linux-x86_64"), \
                    patch.object(linux_preflight, "_cpu_features", return_value=set(features)), \
                    patch.object(model_module.subprocess, "Popen", return_value=DummyProcess()) as launch:
                self.assertTrue(linux_preflight.check_linux_host(root)["engine_compatible"])
                self.assertFalse(BundledModel(root, data).start())
                launch.assert_not_called()
                app = Application(root, data, start_bundled=True)
                try:
                    self.assertTrue(app.status()["ready"])
                    self.assertTrue(app.status()["setup_required"])
                    launch.assert_not_called()
                finally:
                    app.close()

    def test_readonly_runtime_log_path_does_not_crash_offline_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            with patch.dict(model_module.os.environ, {}, clear=True), \
                 patch.object(Path, "open", side_effect=PermissionError("cannot open log")), \
                 patch.object(model_module.subprocess, "Popen") as launch:
                model = BundledModel(root, data)
                self.assertFalse(model.start())
                self.assertIsNone(model.log)
                self.assertIsNone(model.process)
                launch.assert_not_called()

    def test_launch_requires_complete_positive_compatibility_and_integrity(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            (root / "OFFLINE_PROFILE_MANIFEST.json").write_text('{}')
            valid = {"status": "pass", "engine_compatible": True,
                     "integrity": {"executable_digests_checked": True,
                                   "executable_digests_match": True}}
            # The first report reproduces a hash read exception after static
            # compatibility passed. Missing/unknown fields also cannot authorize
            # a subprocess, even if another field is positive.
            rejected = [
                {**valid, "status": "blocked"},
                {**valid, "engine_compatible": None},
                {**valid, "integrity": {"executable_digests_checked": False,
                                         "executable_digests_match": None}},
                {**valid, "integrity": {"executable_digests_checked": True,
                                         "executable_digests_match": False}},
                {"engine_compatible": True}, None,
            ]
            with patch.dict(model_module.os.environ, {}, clear=True), \
                    patch.object(model_module.subprocess, "Popen", return_value=DummyProcess()) as launch:
                for report in rejected:
                    with self.subTest(report=report), \
                            patch.object(linux_preflight, "check_linux_host", return_value=report) as check:
                        self.assertFalse(BundledModel(root, data).start())
                        check.assert_called_once_with(root, data_dir=data, verify_executables=True)
                        launch.assert_not_called()
                with patch.object(linux_preflight, "check_linux_host", return_value=valid):
                    instance = BundledModel(root, data)
                    self.assertTrue(instance.start())
                    launch.assert_called_once()
                    instance.close()

    def test_missing_or_multiple_model_files_never_start_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            root, data = self.stage(directory)
            (root / "models" / "second.gguf").write_bytes(b"GGUF")
            with patch.dict(model_module.os.environ, {}, clear=True), \
                 patch.object(model_module.subprocess, "Popen") as launch:
                self.assertFalse(BundledModel(root, data).start())
                launch.assert_not_called()
                (root / "models" / "second.gguf").unlink()
                (root / "models" / "merlin-local.gguf").unlink()
                self.assertFalse(BundledModel(root, data).start())
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
