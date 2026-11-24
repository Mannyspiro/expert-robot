"""Actual loopback Studio persistence; only model readiness is a fixture here.

The separate native matrix runs the same recorder against the real restarted
bundle/model. These tests cannot qualify model execution or its CPU ABI.
"""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable/merlin_studio"))
sys.path.insert(0, str(ROOT / "scripts/merlin"))
from server import create_server
import studio_restart_smoke as smoke
import native_self_contained_smoke as native


class StudioRestartTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.checkpoint = self.root / "checkpoint.json"
        self.server = self.thread = None
        self.start()
        self.addCleanup(self.stop)
        original_connection = http.client.HTTPConnection
        self.connection_patch = patch.object(native.http.client, "HTTPConnection",
            side_effect=lambda host, port, **kwargs: original_connection(host, self.server.server_port if port == 18771 else port, **kwargs))
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.original_ready = smoke.ready
        self.model_requests = 0

        def ready(path, **kwargs):
            if kwargs.get("base") == smoke.MODEL:
                self.model_requests += 1
                return {"data": [{"id": "local"}]}
            return self.original_ready(path, **kwargs)
        self.ready_patch = patch.object(smoke, "ready", side_effect=ready)
        self.ready_patch.start()
        self.addCleanup(self.ready_patch.stop)

    def start(self):
        self.server = create_server(port=0, data_dir=self.state, start_bundled=False)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(3)
            self.server = None

    def capture_restart(self):
        self.assertEqual(smoke.capture(self.state, self.checkpoint)["result"], "pass")
        self.stop()
        self.start()

    def test_actual_server_restart_keeps_workspace_history_and_completed_run(self):
        self.capture_restart()
        receipt = smoke.verify(self.state, self.checkpoint)
        self.assertEqual(receipt["result"], "pass")
        self.assertTrue(receipt["workspace_preserved"])
        self.assertTrue(receipt["history_preserved"])
        self.assertEqual(self.model_requests, 1)
        raw = json.dumps(receipt)
        self.assertNotIn("session_token", raw)
        self.assertFalse(receipt["model_answer_retested"])

    def test_corrupted_workspace_is_not_a_successful_restart(self):
        self.capture_restart()
        (self.state / "workspace" / smoke.FILE).write_text("Changed fixture")
        with self.assertRaises(native.SmokeFailure):
            smoke.verify(self.state, self.checkpoint)
        self.assertEqual(self.model_requests, 0)

    def test_changed_persisted_history_is_rejected(self):
        self.capture_restart()
        checkpoint = json.loads(self.checkpoint.read_text())
        with self.server.app.store.db() as db:
            db.execute("UPDATE studio_messages SET content=? WHERE conversation_id=?", ("Changed fixture", checkpoint["conversation_id"]))
        with self.assertRaisesRegex(native.SmokeFailure, "persisted_bytes_changed"):
            smoke.verify(self.state, self.checkpoint)

    def test_model_unavailable_after_restart_cannot_be_rescued_by_persistence(self):
        self.capture_restart()
        def unavailable(path, **kwargs):
            if kwargs.get("base") == smoke.MODEL:
                return {"data": []}
            return self.original_ready(path, **kwargs)
        with patch.object(smoke, "ready", side_effect=unavailable):
            with self.assertRaisesRegex(native.SmokeFailure, "restarted_model_unavailable"):
                smoke.verify(self.state, self.checkpoint)

    def test_checkpoint_symlink_is_rejected(self):
        self.capture_restart()
        other = self.root / "other.json"
        self.checkpoint.rename(other)
        self.checkpoint.symlink_to(other)
        with self.assertRaisesRegex(native.SmokeFailure, "checkpoint_invalid"):
            smoke.verify(self.state, self.checkpoint)


if __name__ == "__main__":
    unittest.main()
