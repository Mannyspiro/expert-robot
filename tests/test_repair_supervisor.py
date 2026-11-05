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
