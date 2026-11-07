import tempfile
import sqlite3
import unittest
from pathlib import Path
from merlin.event_outbox import MerlinEventOutbox, OutboxConflict, LeaseConflict


class MerlinEventOutboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "outbox.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_idempotency_and_payload_conflict(self):
        a = self.outbox.enqueue("same-key","hermes.event",{"n":1},now=1)
        b = self.outbox.enqueue("same-key","hermes.event",{"n":1},now=2)
        self.assertEqual(a["event_id"],b["event_id"])
        with self.assertRaises(OutboxConflict):
            self.outbox.enqueue("same-key","hermes.event",{"n":2},now=3)

    def test_claim_ack_and_replay(self):
        event = self.outbox.enqueue("ack-key","hermes.event",{"n":2},now=1)
        lease = self.outbox.claim_next("hermes",lease_seconds=10,now=2)
        ack = self.outbox.acknowledge(event["event_id"],"hermes",lease["lease_token"],now=3)
        self.assertEqual(ack["state"],"acknowledged")
        self.assertEqual(self.outbox.acknowledge(event["event_id"],"other","stale",now=4)["state"],"acknowledged")

    def test_expired_lease_redelivery_invalidates_old_token(self):
        event = self.outbox.enqueue("expiry-key","worker.event",{},now=1)
        first = self.outbox.claim_next("worker-a",lease_seconds=2,now=2)
        self.assertEqual(self.outbox.recover_expired(now=5),1)
        second = self.outbox.claim_next("worker-b",lease_seconds=10,now=5)
        self.assertEqual(second["event_id"],event["event_id"])
        with self.assertRaises(LeaseConflict):
            self.outbox.acknowledge(event["event_id"],"worker-a",first["lease_token"],now=6)

    def test_retry_quarantines_after_limit(self):
        event = self.outbox.enqueue("retry-key","avrea.dispatch",{"job":"bounded"},now=1)
        first = self.outbox.claim_next("worker",lease_seconds=10,now=2)
        self.assertEqual(self.outbox.retry(event["event_id"],"worker",first["lease_token"],"retry",max_attempts=2,now=3)["state"],"pending")
        second = self.outbox.claim_next("worker",lease_seconds=10,now=4)
        final = self.outbox.retry(event["event_id"],"worker",second["lease_token"],"failed",max_attempts=2,now=5)
        self.assertEqual(final["state"],"quarantined")

    def test_claim_can_filter_topics_without_leasing_unrelated_events(self):
        outbox = MerlinEventOutbox(Path(self.temp.name) / "topics.sqlite3")
        outbox.enqueue("telemetry:1", "merlin.telemetry.task.progress", {"kind": "task.progress"}, now=1)
        outbox.enqueue("hermes:1", "merlin.hermes.task", {"task": "research"}, now=2)
        claimed = outbox.claim_next("hud", topics=["merlin.telemetry.task.progress"], now=3)
        self.assertEqual(claimed["topic"], "merlin.telemetry.task.progress")
        self.assertEqual(outbox.counts()["pending"], 1)

    def test_heartbeat_extends_lease_and_preserves_current_token(self):
        event = self.outbox.enqueue("heartbeat-key", "worker.event", {}, now=1)
        lease = self.outbox.claim_next("worker", lease_seconds=2, now=2)
        renewed = self.outbox.heartbeat(
            event["event_id"], "worker", lease["lease_token"],
            lease_seconds=10, now=3,
        )
        self.assertEqual(renewed["lease_expires_at"], 13)
        ack = self.outbox.acknowledge(
            event["event_id"], "worker", lease["lease_token"], now=10,
        )
        self.assertEqual(ack["state"], "acknowledged")

    def test_heartbeat_rejects_stale_or_expired_lease(self):
        event = self.outbox.enqueue("heartbeat-expired", "worker.event", {}, now=1)
        lease = self.outbox.claim_next("worker-a", lease_seconds=2, now=2)
        with self.assertRaises(LeaseConflict):
            self.outbox.heartbeat(
                event["event_id"], "worker-b", lease["lease_token"],
                lease_seconds=10, now=3,
            )
        with self.assertRaises(LeaseConflict):
            self.outbox.heartbeat(
                event["event_id"], "worker-a", lease["lease_token"],
                lease_seconds=10, now=5,
            )

    def test_cancel_pending_event_is_terminal_and_not_claimable(self):
        event = self.outbox.enqueue("cancel-pending", "worker.event", {}, now=1)
        cancelled = self.outbox.cancel(event["event_id"], "hermes", "user requested", now=2)
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertEqual(cancelled["cancelled_by"], "hermes")
        self.assertEqual(cancelled["cancel_reason"], "user requested")
        self.assertIsNone(self.outbox.claim_next("worker", now=3))
        self.assertEqual(self.outbox.counts()["cancelled"], 1)
        replay = self.outbox.cancel(event["event_id"], "another-worker", "different", now=4)
        self.assertEqual(replay["cancelled_by"], "hermes")

    def test_cancel_leased_event_invalidates_worker_lease(self):
        event = self.outbox.enqueue("cancel-leased", "worker.event", {}, now=1)
        lease = self.outbox.claim_next("worker", lease_seconds=20, now=2)
        self.outbox.cancel(event["event_id"], "scheduler", "deadline exceeded", now=3)
        with self.assertRaises(LeaseConflict):
            self.outbox.heartbeat(
                event["event_id"], "worker", lease["lease_token"], now=4,
            )
        with self.assertRaises(LeaseConflict):
            self.outbox.acknowledge(
                event["event_id"], "worker", lease["lease_token"], now=4,
            )

    def test_acknowledged_event_cannot_be_cancelled(self):
        event = self.outbox.enqueue("cancel-acked", "worker.event", {}, now=1)
        lease = self.outbox.claim_next("worker", now=2)
        self.outbox.acknowledge(event["event_id"], "worker", lease["lease_token"], now=3)
        with self.assertRaisesRegex(ValueError, "acknowledged"):
            self.outbox.cancel(event["event_id"], "scheduler", now=4)

    def test_migration_preserves_existing_outbox_rows_and_adds_cancel_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "legacy.sqlite3"
            with sqlite3.connect(database) as db:
                db.execute("""CREATE TABLE event_outbox (
                    event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    topic TEXT NOT NULL, payload_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN
                      ('pending','leased','acknowledged','quarantined')),
                    attempts INTEGER NOT NULL DEFAULT 0, available_at REAL NOT NULL,
                    lease_owner TEXT, lease_token TEXT, lease_expires_at REAL,
                    last_error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
                    acknowledged_at REAL, result_json TEXT)""")
                db.execute("CREATE INDEX outbox_ready ON event_outbox(state, available_at, created_at)")
                db.execute("CREATE INDEX outbox_expiry ON event_outbox(state, lease_expires_at)")
                db.execute("""INSERT INTO event_outbox(
                    event_id,idempotency_key,topic,payload_json,state,attempts,
                    available_at,created_at,updated_at)
                    VALUES('evt-legacy','legacy-key','legacy.topic','{}','pending',0,1,1,1)""")
            migrated = MerlinEventOutbox(database)
            preserved = migrated.get("evt-legacy")
            self.assertEqual(preserved["state"], "pending")
            self.assertEqual(preserved["payload"], {})
            cancelled = migrated.cancel("evt-legacy", "migration-test", now=2)
            self.assertEqual(cancelled["state"], "cancelled")
            self.assertEqual(migrated.counts()["cancelled"], 1)
