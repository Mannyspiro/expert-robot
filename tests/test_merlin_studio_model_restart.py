"""Saved endpoint ownership regression; actual native restart has a separate gate."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
from engine import Application, BUNDLED_MODEL_URL
from storage import Store


class BundledRestart(unittest.TestCase):
    def application(self, saved, env=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        Store(root / "state").save_settings(saved)
        with patch.dict(os.environ, env or {}, clear=True), patch("engine.BundledModel") as bundled:
            bundled.return_value.start.return_value = True
            app = Application(root, root / "state")
            started = bundled.return_value.start.call_count
        self.addCleanup(app.close)
        return app, started

    def test_saved_automatic_endpoint_restarts_owned_model(self):
        app, count = self.application({"model_url": BUNDLED_MODEL_URL})
        self.assertEqual(count, 1)
        self.assertEqual(app.current_settings()["model_url"], BUNDLED_MODEL_URL)
        self.assertTrue(app.current_settings()["start_bundled_model"])

    def test_first_launch_can_select_bundled_model(self):
        app, count = self.application({})
        self.assertEqual(count, 1)
        self.assertEqual(app.current_settings()["model_url"], BUNDLED_MODEL_URL)

    def test_external_endpoint_is_not_claimed(self):
        _, count = self.application({"model_url": "http://127.0.0.1:8080/v1/chat/completions"})
        self.assertEqual(count, 0)

    def test_environment_endpoint_remains_external_even_at_bundled_port(self):
        _, count = self.application({"model_url": BUNDLED_MODEL_URL}, {"MERLIN_MODEL_URL": BUNDLED_MODEL_URL})
        self.assertEqual(count, 0)

    def test_explicit_opt_out_is_persistent(self):
        app, count = self.application({"model_url": BUNDLED_MODEL_URL, "start_bundled_model": False})
        self.assertEqual(count, 0)
        app.save_settings({"model_id": "local"})
        self.assertFalse(app.store.settings()["start_bundled_model"])

    def test_launch_flag_is_not_truthy_text(self):
        with self.assertRaisesRegex(ValueError, "true or false"):
            Application.validate_settings({"start_bundled_model": "false"})


if __name__ == "__main__":
    unittest.main()
