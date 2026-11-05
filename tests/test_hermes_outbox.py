import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_outbox import HermesOutboxConsumer


class HermesOutboxConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "events.sqlite3")
        self.consumer = HermesOutboxConsumer(self.outbox)

    def tearDown(self):
        self.temp.cleanup()

    def test_handler_result_is_durably_acknowledged(self):
        event = self.outbox.enqueue("hermes:1", "merlin.hermes.task",
                                    {"task_id": "proof-1"}, now=1)
        result = self.consumer.consume_one(
            "hermes-worker", lambda payload: {"artifact": payload["payload"]["task_id"]}, now=2
        )
        self.assertEqual(result["state"], "acknowledged")
        self.assertEqual(result["result"]["artifact"], "proof-1")
        self.assertEqual(self.outbox.get(event["event_id"])["state"], "acknowledged")

    def test_unrelated_telemetry_is_not_consumed(self):
        self.outbox.enqueue("telemetry:1", "merlin.telemetry.task.progress",
                            {"run_id": "r"}, now=1)
        self.assertIsNone(self.consumer.consume_one("hermes-worker", lambda _: {"ok": True}, now=2))
        self.assertEqual(self.outbox.counts()["pending"], 1)

    def test_handler_failure_is_retried_and_quarantined_at_limit(self):
        event = self.outbox.enqueue("hermes:fail", "merlin.hermes.task", {}, now=1)
        result = self.consumer.consume_one(
            "hermes-worker", lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
            max_attempts=1, now=2,
        )
        self.assertEqual(result["state"], "quarantined")
        self.assertEqual(self.outbox.get(event["event_id"])["state"], "quarantined")


if __name__ == "__main__":
    unittest.main()
