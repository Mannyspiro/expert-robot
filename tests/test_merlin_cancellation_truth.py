"""Cancellation is provisional until the remote-execution cleanup gate is clear."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from storage import Store
from engine import Application


class CancellationTruthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="merlin-stop-contract-")
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name))
        self.cid = self.store.create_conversation("Cancellation lifecycle")["id"]

    def start(self):
        return self.store.start_run(self.cid, "/python prepared.py")

    def test_stop_remains_pending_until_worker_acknowledges_end(self):
        rid = self.start()
        self.assertTrue(self.store.request_cancel(rid))
        self.assertEqual(self.store.run(rid)["status"], "cancelling")
        self.assertFalse(self.store.active(rid))
        self.assertTrue(self.store.request_cancel(rid))  # repeated request, no new event
        self.assertEqual(len([x for x in self.store.events(rid)
                              if x["type"] == "cancel_requested"]), 1)
        self.assertTrue(self.store.finish(rid, status="cancelled"))
        self.assertEqual(self.store.run(rid)["status"], "cancelled")
        self.assertFalse(self.store.request_cancel(rid))

    def test_cancellation_does_not_report_success_when_remote_cleanup_unknown(self):
        rid = self.start()
        self.store.sandbox_reserve(rid, "a" * 64)
        self.assertTrue(self.store.request_cancel(rid))
        self.assertTrue(self.store.finish(rid, status="cancelled"))
        run = self.store.run(rid)
        self.assertEqual(run["status"], "failed")
        self.assertIn("cleanup remains unverified", run["error"])
        self.assertEqual(len(self.store.sandbox_pending()), 1)
        self.assertFalse(any(x["type"] == "cancelled" for x in run["events"]))

    def test_completed_requested_while_cancel_pending_never_claims_success(self):
        rid = self.start()
        self.store.request_cancel(rid)
        self.store.finish(rid, content="Success - synthetic", status="completed")
        run = self.store.run(rid)
        self.assertEqual(run["status"], "cancelled")
        self.assertFalse(any(x["type"] == "completed" for x in run["events"]))
        messages = self.store.conversation(self.cid)["messages"]
        self.assertNotIn("Success - synthetic", [m["content"] for m in messages])

    def test_remote_cleanup_unknown_even_without_stop_is_failed(self):
        rid = self.start()
        self.store.sandbox_reserve(rid, "a" * 64)
        self.store.finish(rid, content="42", status="completed")
        run = self.store.run(rid)
        self.assertEqual(run["status"], "failed")
        self.assertEqual(len(self.store.sandbox_pending()), 1)

    def test_pending_stop_blocks_new_same_conversation_request(self):
        rid = self.start()
        self.store.request_cancel(rid)
        with self.assertRaises(ValueError):
            self.start()
        self.store.finish(rid, status="cancelled")
        self.assertNotEqual(self.start(), rid)

    def test_pending_approval_is_invalidated_before_stop_is_terminal(self):
        rid = self.start()
        aid = self.store.request_approval(rid, "run_python", {"path": "prepared.py"})
        self.store.request_cancel(rid)
        self.assertEqual(self.store.run(rid)["status"], "cancelling")
        self.assertIsNone(self.store.run(rid)["pending_approval"])
        with self.assertRaises(ValueError):
            self.store.approve(rid, aid, True)
        self.store.finish(rid, status="cancelled")
        self.assertEqual(self.store.run(rid)["status"], "cancelled")

    def test_restart_of_stopping_run_is_interrupted_not_replayed(self):
        rid = self.start()
        self.store.request_cancel(rid)
        copied = Store(Path(self.temp.name))
        self.assertEqual(copied.recover_interrupted(), [rid])
        run = copied.run(rid)
        self.assertEqual(run["status"], "interrupted")
        self.assertIsNone(run["pending_approval"])
        self.assertTrue(any(e["type"] == "interrupted" for e in run["events"]))

    def test_application_cancel_does_not_finish_immediately(self):
        with tempfile.TemporaryDirectory(prefix="merlin-app-stop-") as root:
            app = Application(STUDIO, Path(root), start_bundled=False)
            try:
                cid = app.store.create_conversation("App stop")["id"]
                rid = app.store.start_run(cid, "/python example.py")
                self.assertTrue(app.cancel(rid))
                self.assertEqual(app.store.run(rid)["status"], "cancelling")
                self.assertTrue(app.cancelled(rid))
                app.store.finish(rid, status="cancelled")
                self.assertEqual(app.store.run(rid)["status"], "cancelled")
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
