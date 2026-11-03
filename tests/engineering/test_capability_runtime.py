import asyncio
import unittest

from python.merlin.capability_runtime import (
    AsyncStreamingGateway, RuntimeCapabilityRegistry, build_qualification_receipt,
    make_cace_evidence_envelope, paired_heldout_comparison, select_measured_route,
)


class RuntimeCapabilityTests(unittest.TestCase):
    def test_unavailable_configured_and_unqualified_are_distinct(self):
        registry = RuntimeCapabilityRegistry()
        self.assertEqual(registry.set_unavailable("chat", "no_endpoint").state, "unavailable")
        configured = registry.configure("chat", provider_id="local", model_id="qwen",
                                         model_revision="sha256:abc", modalities=["text"])
        self.assertEqual(configured.state, "configured")
        self.assertEqual(registry.mark_unqualified("chat", "no_heldout_run").state, "unqualified")
        self.assertFalse(registry.snapshot()["authority_expanded"])

    def test_qualification_receipt_must_match_exact_identity(self):
        registry = RuntimeCapabilityRegistry()
        registry.configure("chat", provider_id="local", model_id="qwen", model_revision="r1")
        receipt = build_qualification_receipt(
            provider_id="local", model_id="qwen", model_revision="r1",
            artifact_sha256="a"*64, held_out_task_ids=["t1"], held_out_seed_ids=["s1"],
            metrics={"quality": .99, "latency_ms": 100}, privacy_review="approved",
            privacy_policy_sha256="b"*64, evaluator_revision="eval@abc",
            created_at="2026-11-03T00:00:00Z", quality_floor=.95, max_latency_ms=200)
        self.assertEqual(registry.qualify("chat", receipt).state, "qualified")

    def test_failed_privacy_review_cannot_qualify(self):
        registry = RuntimeCapabilityRegistry()
        registry.configure("chat", provider_id="local", model_id="qwen", model_revision="r1")
        receipt = build_qualification_receipt(
            provider_id="local", model_id="qwen", model_revision="r1",
            artifact_sha256="a"*64, held_out_task_ids=["t1"], held_out_seed_ids=["s1"],
            metrics={"quality": .99, "latency_ms": 100}, privacy_review="pending",
            privacy_policy_sha256="b"*64, evaluator_revision="eval@abc",
            created_at="2026-11-03T00:00:00Z", quality_floor=.95, max_latency_ms=200)
        with self.assertRaises(ValueError):
            registry.qualify("chat", receipt)


class StreamingGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_chunks_and_records_timing_callback(self):
        async def source():
            yield b"a"
            yield b"bc"
        seen = []
        gateway = AsyncStreamingGateway(max_concurrency=1)
        result = [chunk async for chunk in gateway.stream(
            "r1", lambda: _ready(source()), on_chunk=seen.append)]
        self.assertEqual(result, [b"a", b"bc"])
        self.assertEqual(seen, result)

    async def test_deadline_applies_to_stream_read(self):
        async def source():
            await asyncio.sleep(.05)
            yield b"late"
        gateway = AsyncStreamingGateway(max_concurrency=1)
        with self.assertRaises(asyncio.TimeoutError):
            _ = [chunk async for chunk in gateway.stream(
                "r2", lambda: _ready(source()), deadline_seconds=.01)]

    async def test_cancellation_releases_concurrency_slot(self):
        entered = asyncio.Event()
        async def source():
            entered.set()
            await asyncio.sleep(10)
            yield b"never"
        gateway = AsyncStreamingGateway(max_concurrency=1)
        async def consume():
            async for _ in gateway.stream("r3", lambda: _ready(source())):
                pass
        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(gateway._slots._value, 1)


async def _ready(value):
    return value


class EvidenceAndRoutingTests(unittest.TestCase):
    def test_paired_heldout_route_is_reproducible_and_advisory(self):
        def baseline(seed):
            return {"quality": .9, "latency_ms": 20 + seed}
        def better(seed):
            return {"quality": .95, "latency_ms": 10 + seed}
        comparison = paired_heldout_comparison(
            {"baseline": baseline, "candidate": better}, [31, 32, 33], order_seed=4)
        self.assertEqual(select_measured_route(comparison)["selected_candidate"], "candidate")
        self.assertFalse(comparison["promotion_authorized"])

    def test_cace_envelope_hashes_typed_evidence(self):
        envelope = make_cace_evidence_envelope(
            source_repository="Mannyspiro/expert-robot", source_revision="abc123",
            artifact_path="reports/test.json", artifact_sha256="c"*64,
            evidence_type="test", evidence={"passed": 12, "failed": 0},
            verifier_id="pytest", verified=True)
        self.assertEqual(len(envelope["envelope_sha256"]), 64)
        self.assertFalse(envelope["authority_expanded"])


if __name__ == "__main__":
    unittest.main()
