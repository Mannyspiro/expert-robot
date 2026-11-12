import os
import tempfile
import unittest

from merlin.hermes_outbox import HermesOutbox
from merlin.runtime_contracts import RunRecord
from merlin.sqlite_registry import SQLiteRunStore


class HermesOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = SQLiteRunStore(os.path.join(self.temp.name, "merlin.sqlite3"))
        self.registry.create_run(RunRecord(
            run_id="run-1", conversation_id="conv-1", request_id="req-1",
            idempotency_key="run-idem", capability_id="research.search",
            capability_version="1.0", policy_hash="policy", state="queued",
            created_at="2026-11-06T12:00:00Z", max_steps=5,
            max_runtime_seconds=120, max_cost_units=20), request_digest="req-hash")
        self.queue = HermesOutbox(self.registry)

    def tearDown(self):
        self.temp.cleanup()

    def publish(self):
        return self.queue.publish_task(task_id="task-1", run_id="run-1",
            step_id="step-1", idempotency_key="task-idem",
            payload={"query": "test"}, created_at="2026-11-06T12:00:01Z")

    def claim(self, worker="worker-a", at="2026-11-06T12:00:02Z"):
        return self.queue.claim(worker_id=worker, now=at, lease_seconds=30)[0]

    def test_publish_is_atomic_and_idempotent(self):
        first = self.publish()
        replay = self.publish()
        self.assertEqual(first["task_id"], replay["task_id"])
        self.assertEqual(len(self.registry.list_run_events("run-1")), 1)
        self.assertEqual(first["status"], "pending")

    def test_conflicting_idempotency_reuse_is_rejected(self):
        self.publish()
        with self.assertRaises(ValueError):
            self.queue.publish_task(task_id="task-2", run_id="run-1",
                step_id="step-1", idempotency_key="task-idem",
                payload={"query": "different"}, created_at="2026-11-06T12:00:03Z")

    def test_claim_and_acknowledge_are_fenced_and_idempotent(self):
        self.publish()
        task = self.claim()
        self.assertEqual(task["payload"], {"query": "test"})
        result = self.queue.acknowledge(task_id="task-1", worker_id="worker-a",
            lease_token=task["lease_token"], idempotency_key="result-1",
            message_digest="message-hash", result_digest="artifact-hash",
            received_at="2026-11-06T12:00:03Z")
        self.assertEqual(result, "acknowledged")
        duplicate = self.queue.acknowledge(task_id="task-1", worker_id="worker-a",
            lease_token="old-token", idempotency_key="result-1",
            message_digest="message-hash", result_digest="artifact-hash",
            received_at="2026-11-06T12:00:04Z")
        self.assertEqual(duplicate, "duplicate")
        self.assertEqual(self.queue.get("task-1")["status"], "acknowledged")
        self.assertEqual(len(self.registry.list_run_events("run-1")), 2)

    def test_result_key_cannot_be_reused_for_different_message(self):
        self.publish()
        task = self.claim()
        self.queue.acknowledge(task_id="task-1", worker_id="worker-a",
            lease_token=task["lease_token"], idempotency_key="result-1",
            message_digest="message-hash", result_digest="artifact-hash",
            received_at="2026-11-06T12:00:03Z")
        with self.assertRaises(ValueError):
            self.queue.acknowledge(task_id="task-1", worker_id="worker-a",
                lease_token="stale", idempotency_key="result-1",
                message_digest="changed", result_digest="artifact-hash",
                received_at="2026-11-06T12:00:04Z")

    def test_expired_lease_can_be_reclaimed_and_old_worker_is_fenced(self):
        self.publish()
        first = self.claim()
        second = self.claim(worker="worker-b", at="2026-11-06T12:00:33Z")
        self.assertNotEqual(first["lease_token"], second["lease_token"])
        with self.assertRaises(ValueError):
            self.queue.acknowledge(task_id="task-1", worker_id="worker-a",
                lease_token=first["lease_token"], idempotency_key="result-old",
                message_digest="m", result_digest="r",
                received_at="2026-11-06T12:00:34Z")

    def test_retry_then_dead_letter_after_attempt_limit(self):
        self.queue.publish_task(task_id="task-1", run_id="run-1", step_id="step-1",
            idempotency_key="task-idem", payload={}, created_at="2026-11-06T12:00:01Z",
            max_attempts=2)
        first = self.claim()
        self.assertEqual(self.queue.retry(task_id="task-1", lease_token=first["lease_token"],
            now="2026-11-06T12:00:03Z", error="temporary", backoff_seconds=0), "retry")
        second = self.claim(at="2026-11-06T12:00:04Z")
        self.assertEqual(self.queue.retry(task_id="task-1", lease_token=second["lease_token"],
            now="2026-11-06T12:00:05Z", error="still failing"), "dead_letter")


    def test_final_attempt_lease_expiry_moves_task_to_dead_letter(self):
        self.queue.publish_task(task_id="task-1", run_id="run-1", step_id="step-1",
            idempotency_key="task-idem", payload={}, created_at="2026-11-06T12:00:01Z",
            max_attempts=1)
        self.claim()
        self.assertEqual(self.queue.claim(worker_id="worker-b",
            now="2026-11-06T12:00:33Z"), ())
        self.assertEqual(self.queue.get("task-1")["status"], "dead_letter")

    def test_lease_renewal_extends_expiry_and_fences_stale_workers(self):
        self.publish()
        task = self.claim()
        expiry = self.queue.renew_lease(task_id="task-1", worker_id="worker-a",
            lease_token=task["lease_token"], now="2026-11-06T12:00:10Z", lease_seconds=90)
        self.assertEqual(expiry, "2026-11-06T12:01:40+00:00")
        with self.assertRaises(ValueError):
            self.queue.renew_lease(task_id="task-1", worker_id="worker-b",
                lease_token=task["lease_token"], now="2026-11-06T12:00:11Z")

    def test_expired_lease_cannot_be_renewed(self):
        self.publish()
        task = self.claim()
        with self.assertRaises(ValueError):
            self.queue.renew_lease(task_id="task-1", worker_id="worker-a",
                lease_token=task["lease_token"], now="2026-11-06T12:00:33Z")

    def test_retry_delay_is_deterministic_and_capped(self):
        delay = self.queue.retry_delay_seconds(task_id="task-1", attempt=3)
        self.assertEqual(delay, self.queue.retry_delay_seconds(task_id="task-1", attempt=3))
        self.assertGreaterEqual(delay, 0)
        self.assertLessEqual(delay, 900)
        self.assertLessEqual(self.queue.retry_delay_seconds(task_id="task-1", attempt=50), 900)

    def test_operator_can_inspect_and_requeue_dead_letter(self):
        self.queue.publish_task(task_id="task-1", run_id="run-1", step_id="step-1",
            idempotency_key="task-idem", payload={}, created_at="2026-11-06T12:00:01Z",
            max_attempts=1)
        task = self.claim()
        self.queue.retry(task_id="task-1", lease_token=task["lease_token"],
            now="2026-11-06T12:00:03Z", error="terminal", backoff_seconds=0)
        self.assertEqual(len(self.queue.list_dead_letters()), 1)
        self.assertTrue(self.queue.requeue_dead_letter(task_id="task-1",
            operator_id="operator-1", now="2026-11-06T12:00:04Z"))
        self.assertEqual(self.queue.get("task-1")["status"], "pending")
        self.assertEqual(self.queue.get("task-1")["attempts"], 0)
        self.assertEqual(self.queue.list_dead_letters(), ())
    def test_cancelled_task_is_not_claimed(self):
        self.publish()
        self.assertTrue(self.queue.cancel(task_id="task-1", now="2026-11-06T12:00:02Z"))
        self.assertEqual(self.queue.claim(worker_id="worker-a",
            now="2026-11-06T12:00:03Z"), ())

    def test_stale_worker_cannot_acknowledge(self):
        self.publish()
        task = self.claim()
        with self.assertRaises(ValueError):
            self.queue.acknowledge(task_id="task-1", worker_id="worker-b",
                lease_token=task["lease_token"], idempotency_key="result-1",
                message_digest="m", result_digest="r",
                received_at="2026-11-06T12:00:03Z")


if __name__ == "__main__":
    unittest.main()
