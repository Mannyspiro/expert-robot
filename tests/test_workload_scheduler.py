import unittest
from datetime import datetime, timezone

from merlin.cpu_fabric.leases import CapacitySnapshot, LeaseBook, ResourceRequest, WorkloadRequest
from merlin.cpu_fabric.workload_scheduler import WorkloadScheduler

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)


def capacity(cpu=2, memory=1024, budget=100):
    return CapacitySnapshot(
        cpu, memory, None, None, budget, NOW.isoformat(),
        "synthetic-scheduler-test", "d" * 64,
    )


def request(workload_id, *, cpu=1, memory=128, budget=10, priority=0, wall=20):
    return WorkloadRequest(
        workload_id, "cad.wire_route_proposal",
        ResourceRequest(cpu, memory), wall, budget, priority,
    )


class WorkloadSchedulerTests(unittest.TestCase):
    def test_priority_then_fifo_order(self):
        scheduler = WorkloadScheduler(LeaseBook(capacity()))
        scheduler.submit(request("low", priority=1))
        scheduler.submit(request("high-first", priority=10))
        scheduler.submit(request("high-second", priority=10))
        result = scheduler.dispatch(now=NOW, ttl_seconds=20, max_grants=2)
        self.assertEqual(
            [item["workload_id"] for item in result["granted"]],
            ["high-first", "high-second"],
        )
        self.assertEqual(result["pending"], ["low"])
        self.assertFalse(result["promotion_authority"])

    def test_unfit_high_priority_job_does_not_block_small_job(self):
        scheduler = WorkloadScheduler(LeaseBook(capacity(cpu=2)))
        scheduler.submit(request("large", cpu=3, priority=100))
        scheduler.submit(request("small", cpu=1, priority=1))
        result = scheduler.dispatch(now=NOW, ttl_seconds=20)
        self.assertEqual([item["workload_id"] for item in result["granted"]], ["small"])
        self.assertIn("large", result["blocked"])
        self.assertEqual(result["pending"], ["large"])

    def test_pending_workload_can_dispatch_after_capacity_is_released(self):
        book = LeaseBook(capacity(cpu=2))
        held = book.grant(request("held", cpu=2), now=NOW, ttl_seconds=20)
        scheduler = WorkloadScheduler(book)
        scheduler.submit(request("waiting", cpu=1))
        blocked = scheduler.dispatch(now=NOW, ttl_seconds=20)
        self.assertEqual(blocked["granted"], [])
        self.assertEqual(blocked["pending"], ["waiting"])
        book.complete(held.lease_id, now=NOW)
        granted = scheduler.dispatch(now=NOW, ttl_seconds=20)
        self.assertEqual([x["workload_id"] for x in granted["granted"]], ["waiting"])

    def test_cancel_and_duplicate_submission(self):
        scheduler = WorkloadScheduler(LeaseBook(capacity()))
        scheduler.submit(request("cancel-me"))
        self.assertTrue(scheduler.cancel("cancel-me"))
        self.assertFalse(scheduler.cancel("cancel-me"))
        with self.assertRaisesRegex(ValueError, "already been submitted"):
            scheduler.submit(request("cancel-me"))

    def test_invalid_max_grants_rejected(self):
        scheduler = WorkloadScheduler(LeaseBook(capacity()))
        with self.assertRaises(ValueError):
            scheduler.dispatch(now=NOW, ttl_seconds=20, max_grants=0)


if __name__ == "__main__":
    unittest.main()
