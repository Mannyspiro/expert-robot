import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace

from merlin.runtime_contracts import ApprovalRecord, RunRecord
from merlin.sqlite_registry import SQLiteRunStore


class SQLiteRunStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "merlin.sqlite3")
        self.store = SQLiteRunStore(self.path)
        self.run = RunRecord(
            run_id="run-1", conversation_id="conv-1", request_id="req-1",
            idempotency_key="idem-1", capability_id="research.search",
            capability_version="1.0.0", policy_hash="policy-hash",
            state="queued", created_at="2026-11-06T12:00:00Z",
            max_steps=10, max_runtime_seconds=300, max_cost_units=100,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_run_persists_and_survives_store_reopen(self):
        self.assertEqual(self.store.create_run(self.run, request_digest="request-hash"),
                         ("run-1", True))
        reopened = SQLiteRunStore(self.path)
        self.assertEqual(reopened.get_run("run-1"), self.run)

    def test_exact_idempotent_replay_returns_original_run(self):
        self.store.create_run(self.run, request_digest="request-hash")
        replay = replace(self.run, run_id="run-2", request_id="req-2")
        self.assertEqual(self.store.create_run(replay, request_digest="request-hash"),
                         ("run-1", False))

    def test_idempotency_key_conflict_is_rejected(self):
        self.store.create_run(self.run, request_digest="request-hash")
        with self.assertRaises(ValueError):
            self.store.create_run(self.run, request_digest="different-hash")

    def test_events_persist_in_order_and_verify_after_reopen(self):
        self.store.create_run(self.run, request_digest="request-hash")
        first = self.store.append_run_event(
            run_id="run-1", event_type="run.created",
            occurred_at="2026-11-06T12:00:00Z", actor="api",
            payload={"request_id": "req-1"})
        second = self.store.append_run_event(
            run_id="run-1", event_type="run.started",
            occurred_at="2026-11-06T12:00:01Z", actor="hermes",
            payload={"worker": "avrea"})
        reopened = SQLiteRunStore(self.path)
        self.assertEqual(reopened.list_run_events("run-1"), (first, second))

    def test_event_append_rejects_unknown_run(self):
        with self.assertRaises(ValueError):
            self.store.append_run_event(
                run_id="missing", event_type="run.created",
                occurred_at="2026-11-06T12:00:00Z", actor="api", payload={})

    def test_approval_requires_pending_record_and_is_decided_once(self):
        self.store.create_run(self.run, request_digest="request-hash")
        approval = ApprovalRecord(
            approval_id="approval-1", run_id="run-1", step_id="step-1",
            action_digest="action-hash", policy_hash="policy-hash",
            status="pending", requested_at="2026-11-06T12:00:00Z")
        self.store.create_approval(approval)
        decided = self.store.decide_approval(
            "approval-1", decision="approved",
            decided_at="2026-11-06T12:01:00Z", approver_id="human-1")
        self.assertEqual(decided.status, "approved")
        self.assertEqual(decided.approver_id, "human-1")
        with self.assertRaises(ValueError):
            self.store.decide_approval(
                "approval-1", decision="rejected",
                decided_at="2026-11-06T12:02:00Z", approver_id="human-2")

    def test_invalid_decision_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.decide_approval(
                "missing", decision="maybe",
                decided_at="2026-11-06T12:01:00Z", approver_id="human-1")


if __name__ == "__main__":
    unittest.main()
