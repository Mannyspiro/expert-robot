import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.repair_supervisor import RepairSupervisor


class RepairSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("p", "Project")
        self.outbox = MerlinEventOutbox(self.root / "outbox.sqlite3")

    def test_failure_creates_tested_candidate_without_canonical_mutation(self):
        original = self.registry.put_artifact("p", "src/main.py", b"original source")
        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=lambda payload: {
                "files": [{"path": "src/main.py", "content": b"proposed repair",
                           "media_type": "text/x-python"}]
            },
            test_runner=lambda refs, budget: {"passed": True, "tests": 12, "failures": 0},
            approval_validator=lambda ref, payload: ref == "approved",
            lease_validator=lambda ref, budget: ref == "lease",
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        queued = supervisor.observe_failure(
            {"event_id": "failure-1", "kind": "system.error",
             "payload": {"summary": "seeded test failure"}},
            project_id="p", commit_sha="a" * 40, approval_ref="approved",
            lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        self.assertEqual(queued["state"], "pending")
        consumed = supervisor.consume_one()
        self.assertEqual(consumed["state"], "acknowledged")
        result = consumed["result"]
        self.assertEqual(result["status"], "candidate_tested_unverified")
        self.assertFalse(result["canonical_mutation"])
        self.assertTrue(result["candidate_refs"][0]["candidate_path"].startswith("_repair-candidates/"))
        self.assertEqual(self.registry.get_artifact_bytes(original), b"original source")
        self.assertEqual(self.registry.get_artifact_head("p", "src/main.py")["digest"], original)

    def test_worker_crash_retries_and_recovers_without_canonical_mutation(self):
        original = self.registry.put_artifact("p", "src/main.py", b"canonical")
        attempts = {"count": 0}

        def builder(payload):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("injected worker crash")
            return {"files": [{"path": "src/main.py", "content": b"candidate"}]}

        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=builder,
            test_runner=lambda refs, budget: {"passed": True, "tests": 1, "failures": 0},
            approval_validator=lambda ref, payload: ref == "approved",
            lease_validator=lambda ref, budget: ref == "lease",
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        queued = supervisor.submit(
            task_id="crash-retry", project_id="p", commit_sha="b" * 40,
            failure_event={"event_id": "crash-1", "kind": "system.error"},
            approval_ref="approved", lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        first = supervisor.consume_one(now=100)
        self.assertEqual(first["state"], "pending")
        self.assertIn("injected worker crash", first["error"])
        second = supervisor.consume_one(now=111)
        self.assertEqual(second["state"], "acknowledged")
        self.assertEqual(attempts["count"], 2)
        self.assertEqual(self.registry.get_artifact_head("p", "src/main.py")["digest"], original)
        self.assertEqual(self.registry.get_artifact_bytes(original), b"canonical")
        self.assertFalse(second["result"]["canonical_mutation"])

    def test_lease_expiry_after_enqueue_blocks_worker_execution(self):
        original = self.registry.put_artifact("p", "src/main.py", b"canonical")
        lease = {"active": True}
        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=lambda payload: {"files": [{"path": "src/main.py", "content": b"candidate"}]},
            test_runner=lambda refs, budget: {"passed": True},
            approval_validator=lambda ref, payload: ref == "approved",
            lease_validator=lambda ref, budget: lease["active"] and ref == "lease",
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        supervisor.submit(
            task_id="lease-expiry", project_id="p", commit_sha="c" * 40,
            failure_event={"event_id": "lease-1", "kind": "system.error"},
            approval_ref="approved", lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        lease["active"] = False
        result = supervisor.consume_one(now=200)
        self.assertEqual(result["state"], "pending")
        self.assertIn("lease expired or was revoked", result["error"])
        self.assertEqual(self.registry.get_artifact_head("p", "src/main.py")["digest"], original)

    def test_duplicate_failure_event_is_idempotently_queued(self):
        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=lambda payload: {"files": [{"path": "x", "content": b"x"}]},
            test_runner=lambda refs, budget: {"passed": True},
            approval_validator=lambda ref, payload: True,
            lease_validator=lambda ref, budget: True,
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        failure = {"event_id": "duplicate-failure", "kind": "system.error"}
        args = dict(
            project_id="p", commit_sha="d" * 40, approval_ref="approved",
            lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        first = supervisor.observe_failure(failure, **args)
        second = supervisor.observe_failure(failure, **args)
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertEqual(first["event_id"], second["event_id"])

    def test_failed_candidate_test_is_a_safe_rollback_boundary(self):
        original = self.registry.put_artifact("p", "src/main.py", b"canonical")
        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=lambda payload: {"files": [{"path": "src/main.py", "content": b"bad candidate"}]},
            test_runner=lambda refs, budget: {"passed": False, "failures": 1},
            approval_validator=lambda ref, payload: True,
            lease_validator=lambda ref, budget: True,
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        supervisor.submit(
            task_id="rollback-boundary", project_id="p", commit_sha="e" * 40,
            failure_event={"event_id": "test-failure", "kind": "system.error"},
            approval_ref="approved", lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        result = supervisor.consume_one(now=300)
        self.assertEqual(result["state"], "acknowledged")
        self.assertEqual(result["result"]["status"], "candidate_rejected")
        self.assertEqual(self.registry.get_artifact_head("p", "src/main.py")["digest"], original)
        self.assertEqual(self.registry.get_artifact_bytes(original), b"canonical")
        self.assertFalse(result["result"]["canonical_mutation"])

    def test_non_failure_event_is_ignored(self):
        supervisor = RepairSupervisor(
            registry=self.registry, outbox=self.outbox,
            candidate_builder=lambda payload: {"files": [{"path": "x", "content": b"x"}]},
            test_runner=lambda refs, budget: {"passed": True},
            approval_validator=lambda ref, payload: True,
            lease_validator=lambda ref, budget: True,
            repository="Mannyspiro/expert-robot", requester_id="test-agent",
        )
        result = supervisor.observe_failure(
            {"event_id": "ok-1", "kind": "task.completed", "payload": {"status": "completed"}},
            project_id="p", commit_sha="a" * 40, approval_ref="approved",
            lease_ref="lease",
            resource_budget={"cpu_cores": 1, "memory_bytes": 1024,
                             "max_wall_seconds": 30, "compute_budget_units": 1},
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
