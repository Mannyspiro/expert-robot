import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox, OutboxConflict
from merlin.research_dispatch import ResearchDispatchCoordinator, ResearchTask
from merlin.research_optimizer import ResearchMetrics


def make_task(task_id="math-1", approval="approval:1", lease="lease:1"):
    return ResearchTask(
        task_id=task_id, hypothesis_id="H-1", objective="Test spectral invariant",
        stage="experiment",
        metrics=ResearchMetrics(4, 2, 1, 0.9, 0.2, 10, 3, 2),
        constraints={"policy": True, "reproducible_input": True},
        resource_budget={"cpu_cores": 1, "memory_bytes": 1048576,
                         "max_wall_seconds": 30, "compute_budget_units": 100},
        approval_ref=approval, lease_ref=lease,
        evidence_refs=("hypothesis:H-1",),
        experiment_spec={"seed": 42, "tolerance": 1e-8},
    )


class ResearchDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "outbox.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def coordinator(self, approval=True, lease=True):
        return ResearchDispatchCoordinator(
            self.outbox,
            approval_validator=lambda ref, task: approval and ref == "approval:1",
            lease_validator=lambda ref, budget: lease and ref == "lease:1",
        )

    def test_dispatch_requires_validated_approval_and_lease(self):
        task = make_task()
        event = self.coordinator().dispatch(task)
        self.assertEqual(event["topic"], "merlin.hermes.task")
        self.assertFalse(event["payload"]["promotion_authority"])
        with self.assertRaises(PermissionError):
            self.coordinator(approval=False).dispatch(make_task(task_id="no-approval"))
        with self.assertRaises(PermissionError):
            self.coordinator(lease=False).dispatch(make_task(task_id="no-lease"))

    def test_hard_constraints_fail_closed(self):
        task = make_task()
        task = ResearchTask(**{**task.__dict__, "constraints": {"budget": False}})
        with self.assertRaises(PermissionError):
            self.coordinator().dispatch(task)

    def test_idempotent_dispatch_and_conflicting_reuse_rejected(self):
        coordinator = self.coordinator()
        first = coordinator.dispatch(make_task())
        second = coordinator.dispatch(make_task())
        self.assertEqual(first["event_id"], second["event_id"])
        changed = make_task()
        changed = ResearchTask(**{**changed.__dict__, "objective": "Changed objective"})
        with self.assertRaises(OutboxConflict):
            coordinator.dispatch(changed)

    def test_rank_is_advisory_and_does_not_dispatch(self):
        coordinator = self.coordinator()
        ranked = coordinator.rank([make_task()])
        self.assertEqual(ranked[0].task_id, "math-1")
        self.assertEqual(self.outbox.counts()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
