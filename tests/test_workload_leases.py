import unittest
from datetime import datetime, timedelta, timezone

from merlin.cpu_fabric.leases import (
    CapacitySnapshot, LeaseBook, LeaseError, ResourceRequest, WorkloadRequest,
    cad_wire_route_request,
)

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)
CAPACITY = CapacitySnapshot(
    cpu_cores=8,
    memory_bytes=16 * 1024**3,
    gpu_count=None,
    gpu_memory_bytes=None,
    compute_budget_units=100,
    observed_at=NOW.isoformat(),
    source="synthetic-test-fixture",
    evidence_sha256="a" * 64,
)


def request(workload_id="route-001", cpu=1, memory=256 * 1024**2,
            gpu=0, gpu_memory=0, budget=20, wall=10):
    return WorkloadRequest(
        workload_id, "cad.wire_route_proposal",
        ResourceRequest(cpu, memory, gpu, gpu_memory), wall, budget,
    )


class MCFCLeaseTests(unittest.TestCase):
    def test_cad_route_request_is_cpu_only_and_explicit(self):
        item = cad_wire_route_request(
            "route-001", estimated_memory_bytes=256 * 1024**2,
            max_wall_seconds=10, compute_budget_units=20,
        )
        self.assertEqual(item.capability, "cad.wire_route_proposal")
        self.assertEqual(item.resources.cpu_cores, 1)
        self.assertEqual(item.resources.gpu_count, 0)
        self.assertEqual(item.resources.memory_bytes, 256 * 1024**2)

    def test_grants_expiring_execution_only_lease(self):
        book = LeaseBook(CAPACITY)
        lease = book.grant(request(), now=NOW, ttl_seconds=15)
        self.assertEqual(lease.status, "active")
        self.assertEqual(lease.authority, "execution_only")
        self.assertFalse(lease.promotion_authority)
        self.assertTrue(book.validate_start(lease.lease_id, now=NOW + timedelta(seconds=2)))
        self.assertFalse(book.validate_start(lease.lease_id, now=NOW + timedelta(seconds=11)))

    def test_reservations_are_bounded_and_released_on_completion(self):
        book = LeaseBook(CAPACITY)
        first = book.grant(request("one", cpu=4, memory=8 * 1024**3, budget=60),
                           now=NOW, ttl_seconds=15)
        snapshot = book.snapshot(now=NOW)
        self.assertEqual(snapshot["available"]["cpu_cores"], 4)
        self.assertEqual(snapshot["available"]["memory_bytes"], 8 * 1024**3)
        with self.assertRaisesRegex(LeaseError, "CPU reservation"):
            book.grant(request("two", cpu=5, memory=1, budget=10), now=NOW, ttl_seconds=15)
        book.complete(first.lease_id, now=NOW + timedelta(seconds=1))
        second = book.grant(request("two", cpu=5, memory=1, budget=10),
                            now=NOW + timedelta(seconds=2), ttl_seconds=15)
        self.assertEqual(second.status, "active")

    def test_compute_budget_is_enforced(self):
        book = LeaseBook(CAPACITY)
        book.grant(request("one", budget=70), now=NOW, ttl_seconds=15)
        with self.assertRaisesRegex(LeaseError, "compute budget"):
            book.grant(request("two", budget=40), now=NOW, ttl_seconds=15)

    def test_gpu_requirement_is_not_assigned_when_capacity_unknown(self):
        book = LeaseBook(CAPACITY)
        with self.assertRaisesRegex(LeaseError, "GPU capacity is unknown"):
            book.grant(request(gpu=1, gpu_memory=1024), now=NOW, ttl_seconds=15)

    def test_stale_capacity_snapshot_is_rejected(self):
        stale = CapacitySnapshot(
            8, 16 * 1024**3, None, None, 100,
            (NOW - timedelta(minutes=2)).isoformat(),
            "synthetic-test-fixture", "b" * 64,
        )
        with self.assertRaisesRegex(LeaseError, "stale"):
            LeaseBook(stale).grant(request(), now=NOW, ttl_seconds=15)

    def test_expiry_releases_resources(self):
        book = LeaseBook(CAPACITY)
        lease = book.grant(request(), now=NOW, ttl_seconds=15)
        expired = book.expire(NOW + timedelta(seconds=11))
        self.assertEqual(expired[0].lease_id, lease.lease_id)
        self.assertEqual(book.get(lease.lease_id).status, "expired")
        self.assertEqual(book.snapshot(now=NOW + timedelta(seconds=11))["active_lease_count"], 0)

    def test_revoke_releases_resources(self):
        book = LeaseBook(CAPACITY)
        lease = book.grant(request(), now=NOW, ttl_seconds=15)
        self.assertEqual(book.revoke(lease.lease_id, now=NOW).status, "revoked")
        self.assertEqual(book.snapshot(now=NOW)["active_lease_count"], 0)

    def test_workload_id_is_idempotent_but_cannot_change_requirements(self):
        book = LeaseBook(CAPACITY)
        first = book.grant(request(), now=NOW, ttl_seconds=15)
        again = book.grant(request(), now=NOW, ttl_seconds=15)
        self.assertEqual(first.lease_id, again.lease_id)
        with self.assertRaisesRegex(LeaseError, "different requirements"):
            book.grant(request(cpu=2), now=NOW, ttl_seconds=15)

    def test_runtime_telemetry_is_source_labelled_and_metadata_only(self):
        events = []
        book = LeaseBook(CAPACITY, event_sink=events.append)
        lease = book.grant(request(), now=NOW, ttl_seconds=15)
        book.complete(lease.lease_id, now=NOW + timedelta(seconds=1))
        self.assertEqual([e["source"] for e in events], ["runtime", "runtime"])
        self.assertTrue(all(e["kind"] == "resource.sample" for e in events))
        self.assertTrue(all(e["payload"]["promotion_authority"] is False for e in events))

    def test_invalid_resources_and_ttl_rejected(self):
        with self.assertRaises(ValueError):
            ResourceRequest(0, 1024)
        with self.assertRaises(ValueError):
            ResourceRequest(1, 1024, gpu_count=0, gpu_memory_bytes=1)
        with self.assertRaisesRegex(ValueError, "TTL"):
            LeaseBook(CAPACITY).grant(request(wall=10), now=NOW, ttl_seconds=5)


if __name__ == "__main__":
    unittest.main()
