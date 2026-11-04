import unittest
from merlin.cpu_fabric.leases import CapacitySnapshot, LeaseBook, LeaseError, ResourceRequest, WorkloadRequest
from merlin.resource_probe import (
    build_mcfc_capacity_snapshot, effective_memory_bytes,
    parse_cpu_capacity, parse_gpu_capacity,
)


class ResourceProbeTests(unittest.TestCase):
    def test_cgroup_v2_cpu_quota_caps_host_cores(self):
        self.assertEqual(parse_cpu_capacity("400000 100000", 8), (4, 4.0))

    def test_unlimited_cpu_uses_host_count(self):
        self.assertEqual(parse_cpu_capacity("max 100000", 8), (8, None))

    def test_fractional_cpu_quota_is_floored_conservatively(self):
        self.assertEqual(parse_cpu_capacity("50000 100000", 8), (0, 0.5))

    def test_cgroup_v1_cpu_quota_supported(self):
        self.assertEqual(parse_cpu_capacity(None, 8, v1_quota="250000", v1_period="100000"), (2, 2.5))

    def test_memory_uses_lower_cgroup_or_host_limit(self):
        meminfo = "MemTotal:       2097152 kB\nMemAvailable:   1000000 kB"
        self.assertEqual(effective_memory_bytes("536870912", meminfo), 536870912)
        self.assertEqual(effective_memory_bytes("max", meminfo), 2 * 1024**3)

    def test_unknown_memory_is_zero_not_guessed(self):
        self.assertEqual(effective_memory_bytes(None, None), 0)

    def test_gpu_capacity_parsed_in_bytes(self):
        count, memory, names = parse_gpu_capacity("GPU A, 8192\nGPU B, 16384")
        self.assertEqual(count, 2)
        self.assertEqual(memory, 24 * 1024**3)
        self.assertEqual(names, ["GPU A", "GPU B"])

    def test_unavailable_gpu_probe_remains_unknown(self):
        self.assertEqual(parse_gpu_capacity(None), (None, None, []))

    def test_empty_gpu_probe_is_measured_zero(self):
        self.assertEqual(parse_gpu_capacity(""), (0, 0, []))

    def test_probe_document_loads_into_mcfc_and_unknown_budget_blocks(self):
        observed_at = "2026-11-04T18:00:00Z"
        raw = {"cpu_max": "400000 100000"}
        probe = {
            "mcfc_capacity": build_mcfc_capacity_snapshot(
                cpu_cores=4, memory_bytes=1024, gpu_count=None,
                gpu_memory_bytes=None, observed_at=observed_at,
                raw_measurements=raw,
            )
        }
        capacity = CapacitySnapshot.from_probe_document(probe)
        self.assertEqual(capacity.cpu_cores, 4)
        self.assertIsNone(capacity.gpu_count)
        self.assertIsNone(capacity.compute_budget_units)
        book = LeaseBook(capacity)
        request = WorkloadRequest(
            "probe-job", "cad.wire_route_proposal",
            ResourceRequest(1, 128), 5, 1,
        )
        with self.assertRaisesRegex(LeaseError, "compute budget capacity is unknown"):
            book.grant(request, now=observed_at, ttl_seconds=5)

    def test_capacity_evidence_hash_is_deterministic(self):
        args = dict(cpu_cores=4, memory_bytes=1024, gpu_count=None,
                    gpu_memory_bytes=None, observed_at="2026-11-04T18:00:00Z",
                    raw_measurements={"cpu_max": "400000 100000", "mem": 1024})
        first = build_mcfc_capacity_snapshot(**args)
        self.assertEqual(first, build_mcfc_capacity_snapshot(**args))
        self.assertIsNone(first["compute_budget_units"])
        self.assertEqual(len(first["evidence_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
