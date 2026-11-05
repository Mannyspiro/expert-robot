import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_outbox import HermesOutboxWorker


class HermesOutboxWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "events.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_handler_result_is_durably_acknowledged(self):
        event = self.outbox.enqueue("hermes:1", "merlin.hermes.task", {"task_id": "proof-1"}, now=1)
        worker = HermesOutboxWorker(self.outbox, lambda payload: {"artifact": payload["task_id"]})
        result = worker.process_one(now=2)
        self.assertEqual(result["state"], "acknowledged")
        self.assertEqual(result["result"]["artifact"], "proof-1")
        self.assertEqual(self.outbox.get(event["event_id"])["state"], "acknowledged")

    def test_only_hermes_task_topic_is_claimed(self):
        self.outbox.enqueue("telemetry:1", "merlin.telemetry.task.progress", {"run_id": "r"}, now=1)
        worker = HermesOutboxWorker(self.outbox, lambda payload: {"ok": True})
        self.assertIsNone(worker.process_one(now=2))
        self.assertEqual(self.outbox.counts()["pending"], 1)

    def test_handler_failure_retries_then_quarantines(self):
        self.outbox.enqueue("hermes:fail", "merlin.hermes.task", {"task_id": "fail"}, now=1)
        worker = HermesOutboxWorker(self.outbox, lambda payload: (_ for _ in ()).throw(RuntimeError("boom")),
                                    max_attempts=1)
        result = worker.process_one(now=2)
        self.assertEqual(result["state"], "quarantined")


if __name__ == "__main__":
    unittest.main()
