"""Fail-closed local-model launching and offline Studio survival checks.

All model files and subprocesses here are synthetic; real Qwen/ABI acceptance
remains separately required before qualifying a self-contained archive.
"""
from __future__ import annotations
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
import model as model_module
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
