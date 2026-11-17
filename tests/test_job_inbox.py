from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import DotContextBridge, canonical, digest
from dot_ai_os.job_inbox import InboxBusy, InboxConflict, ProductionJobInbox


class JobInboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root)
        self.bridge = DotContextBridge(self.registry)
        self.bridge.initialize()
        self.ref = self.source("merlin", "Source context with a private marker.")
        self.inbox = ProductionJobInbox(self.registry, namespaces=("merlin", "rsi"))
        self.request = {"namespace": "merlin", "objective": "Compare a source-grounded retrieval candidate",
                        "source_commit": "a" * 40, "source_refs": [self.ref],
                        "acceptance_criteria": ["Retain exact citations", "No source namespace leakage"],
                        "max_cost_usd": 0}

    def source(self, namespace, text, source_id="source-one"):
        return self.bridge.ingest(namespace=namespace, source_id=source_id, title="Context source",
                                  content=text.encode(), source_url="https://example.org/context",
                                  source_version="snapshot-1", epistemic="source_snapshot",
                                  captured_at="2026-11-17T15:00:00Z")["source_ref"]

    def submit(self, **overrides):
        values = {"principal": "issuer|subject-alice", "idempotency_key": "unique-request-key-001",
                  "request": self.request}
        values.update(overrides)
        return self.inbox.submit(**values)

    def test_accepts_and_reads_same_principal_without_source_body(self):
        result = self.submit()
        self.assertEqual(result["state"], "pending_operator_review")
        self.assertEqual(result["execution_state"], "not_dispatched")
        self.assertEqual(result["approval_state"], "not_requested")
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])
        self.assertNotIn(b"private marker", canonical(result))
        self.assertNotIn(b"subject-alice", canonical(result))
        self.assertEqual(self.inbox.status(principal="issuer|subject-alice", request_id=result["request_id"]), result)

    def test_identical_replay_is_exact_and_does_not_add_versions(self):
        first = self.submit()
        second = self.submit()
        self.assertEqual(first, second)
        paths = [item["logical_path"] for item in self.registry.inventory("dot-ai-os")["artifacts"]
                 if item["logical_path"].startswith("job-inbox/")]
        self.assertEqual(len(paths), 2)
        for path in paths:
            self.assertEqual(len(self.registry.artifact_history("dot-ai-os", path)), 1)

    def test_payload_and_budget_changes_conflict_under_same_key(self):
        self.submit()
        changes = {"objective": "changed objective", "source_commit": "b" * 40,
                   "acceptance_criteria": ["Changed criterion"], "max_cost_usd": 1}
        for field, value in changes.items():
            request = deepcopy(self.request)
            request[field] = value
            with self.subTest(field=field), self.assertRaises(InboxConflict):
                self.submit(request=request)

    def test_same_key_cannot_be_rebound_to_another_principal(self):
        self.submit()
        with self.assertRaises(InboxConflict) as failure:
            self.submit(principal="issuer|subject-bob")
        self.assertNotIn("subject-alice", str(failure.exception))
        self.assertNotIn(self.request["objective"], str(failure.exception))

    def test_other_principal_cannot_read_known_request_id(self):
        request_id = self.submit()["request_id"]
        with self.assertRaises(KeyError):
            self.inbox.status(principal="issuer|subject-bob", request_id=request_id)
        with self.assertRaises(KeyError):
            self.inbox.status(principal="issuer|subject-alice", request_id="f" * 64)

    def test_unknown_authority_and_execution_fields_rejected(self):
        for field in ("approval", "dispatch", "verification", "promotion_authority", "principal", "ready"):
            request = deepcopy(self.request)
            request[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.submit(request=request, idempotency_key="field-" + field)

    def test_malformed_identity_and_request_id_rejected(self):
        for principal in (None, "", " alice ", "alice\nrole=admin", 3):
            with self.subTest(principal=principal), self.assertRaises(ValueError):
                self.submit(principal=principal)
        for key in (None, "", "../escape", "a/b", "a key", True):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.submit(idempotency_key=key)
        for request_id in ("../escape", "short", None, "A" * 64):
            with self.subTest(request_id=request_id), self.assertRaises(ValueError):
                self.inbox.status(principal="alice", request_id=request_id)

    def test_principal_characters_are_hashed_not_used_as_a_path(self):
        principal = "issuer/../../alice"
        result = self.submit(principal=principal)
        self.assertNotIn("..", result["request_ref"]["logical_path"])
        self.assertIn(digest(principal.encode()), result["request_ref"]["logical_path"])

    def test_missing_project_fails_without_provisioning(self):
        empty = MerlinRegistry(self.root / "empty")
        with self.assertRaises(KeyError):
            ProductionJobInbox(empty, namespaces=("merlin",))
        with sqlite3.connect(empty.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 0)

    def test_namespace_and_cross_project_source_scope_is_enforced(self):
        cace = self.source("morgana-cace", "restricted CACE context")
        request = deepcopy(self.request)
        request["source_refs"] = [cace]
        with self.assertRaises(ValueError):
            self.submit(request=request)
        request["namespace"] = "morgana-cace"
        request["source_refs"] = [self.ref]
        with self.assertRaises(ValueError):
            self.submit(request=request)
        self.registry.register_project("another", "Other project")
        self.registry.put_artifact("another", self.ref["logical_path"], b"other project source")
        request = deepcopy(self.request)
        request["source_refs"] = [self.registry.artifact_ref("another", self.ref["logical_path"])]
        with self.assertRaises(ValueError):
            self.submit(request=request)

    def test_allowed_cross_namespace_context_can_support_one_request(self):
        rsi = self.source("rsi", "Related RSI context")
        request = deepcopy(self.request)
        request["source_refs"] = [self.ref, rsi]
        result = self.submit(request=request)
        self.assertEqual(len(result["request"]["source_refs"]), 2)
        narrower = ProductionJobInbox(self.registry, namespaces=("merlin",))
        with self.assertRaises(ValueError):
            narrower.status(principal="issuer|subject-alice", request_id=result["request_id"])

    def test_tampered_reference_and_wrong_artifact_kind_rejected(self):
        request = deepcopy(self.request)
        request["source_refs"][0]["sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self.submit(request=request)
        self.registry.put_artifact("dot-ai-os", "handoffs/not-context.json", b"{}")
        request["source_refs"] = [self.registry.artifact_ref("dot-ai-os", "handoffs/not-context.json")]
        with self.assertRaises(ValueError):
            self.submit(request=request)

    def test_status_rehashes_context_and_rejects_tampered_bytes(self):
        result = self.submit()
        path = self.registry.blobs / self.ref["sha256"][:2] / self.ref["sha256"][2:]
        path.write_bytes(b"tampered source")
        with self.assertRaises(RuntimeError):
            self.inbox.status(principal="issuer|subject-alice", request_id=result["request_id"])

    def test_old_exact_source_version_survives_latest_advancement(self):
        result = self.submit()
        self.source("merlin", "new source revision")
        self.assertEqual(self.inbox.status(principal="issuer|subject-alice", request_id=result["request_id"]), result)

    def test_budget_caps_and_boolean_cost_rejected(self):
        for cost in (False, True, 0.0, 1, -1, "0"):
            request = deepcopy(self.request)
            request["max_cost_usd"] = cost
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                self.submit(request=request)
        request = deepcopy(self.request)
        request["objective"] = "x" * 2001
        with self.assertRaises(ValueError):
            self.submit(request=request)
        request = deepcopy(self.request)
        request["acceptance_criteria"] = ["x" * 1000] * 20
        with self.assertRaises(ValueError):
            self.submit(request=request)

    def test_source_count_duplicates_and_total_context_caps(self):
        request = deepcopy(self.request)
        request["source_refs"] = [self.ref] * 21
        with self.assertRaises(ValueError):
            self.submit(request=request)
        request["source_refs"] = [self.ref, self.ref]
        with self.assertRaises(ValueError):
            self.submit(request=request)
        large = self.source("merlin", "x" * (128 * 1024 + 1), "large")
        request["source_refs"] = [large]
        with self.assertRaises(ValueError):
            self.submit(request=request)
        exact = self.source("merlin", "x" * (128 * 1024), "exact-cap")
        request["source_refs"] = [exact]
        result = self.submit(request=request)
        self.assertEqual(result["context_total_bytes"], 128 * 1024)

    def test_concurrent_identical_submissions_serialize_to_one_request(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.submit(), range(16)))
        self.assertTrue(all(result == results[0] for result in results))
        path = results[0]["request_ref"]["logical_path"]
        self.assertEqual(len(self.registry.artifact_history("dot-ai-os", path)), 1)

    def test_concurrent_principals_cannot_share_one_key(self):
        def submit(principal):
            try:
                return self.submit(principal=principal)["state"]
            except InboxConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ["alice", "bob"]))
        self.assertEqual(sorted(results), ["conflict", "pending_operator_review"])

    def test_partial_local_write_reserves_key_and_identical_retry_finishes(self):
        original = self.inbox._put_once
        def interrupted(path, payload):
            if "/requests/" in path:
                raise RuntimeError("simulated interruption after durable key binding")
            return original(path, payload)
        self.inbox._put_once = interrupted
        with self.assertRaises(RuntimeError):
            self.submit()
        self.inbox._put_once = original
        with self.assertRaises(InboxConflict):
            self.submit(principal="bob")
        result = self.submit()
        self.assertEqual(result["state"], "pending_operator_review")

    def test_changed_immutable_version_is_not_silently_reused(self):
        result = self.submit()
        self.registry.put_artifact("dot-ai-os", result["request_ref"]["logical_path"], canonical({"changed": True}))
        with self.assertRaises(InboxConflict):
            self.inbox.status(principal="issuer|subject-alice", request_id=result["request_id"])
        with self.assertRaises(InboxConflict):
            self.submit()

    def test_lock_symlink_rejected_and_bounded_busy_wait(self):
        target = self.root / "unrelated.txt"
        target.write_text("unchanged")
        lock = self.root / "dot-dual-coder.lock"
        lock.symlink_to(target)
        with self.assertRaises(OSError):
            self.submit()
        self.assertEqual(target.read_text(), "unchanged")
        lock.unlink()
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            inbox = ProductionJobInbox(self.registry, namespaces=("merlin",), lock_timeout_seconds=0.02)
            with self.assertRaises(InboxBusy):
                inbox.submit(principal="alice", idempotency_key="blocked", request=self.request)
        finally:
            os.close(descriptor)

    def test_inbox_never_mutates_canonical_claims_or_receipts(self):
        self.submit()
        with sqlite3.connect(self.registry.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_qualification_receipts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
