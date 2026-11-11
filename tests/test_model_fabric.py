import unittest

from merlin.model_fabric import (
    ModelBackend, ModelFabricError, ModelMeasurement,
    ModelQualificationReceipt, ModelRouteRequest, route_model,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def backend(backend_id="vllm", **changes):
    values = dict(
        backend_id=backend_id, engine="vllm", model_id="Qwen/example",
        model_revision="model@abc", engine_revision="vllm@1",
        task_scopes=("council", "chat"), data_classes=("public", "internal"),
        state="available", supports_streaming=True, supports_tools=True,
        context_window=32768, max_concurrency=8,
        estimated_ram_bytes=8_000_000_000, estimated_vram_bytes=12_000_000_000,
    )
    values.update(changes)
    return ModelBackend(**values)


def measurement(backend_id="vllm", task_scope="council", **changes):
    values = dict(
        backend_id=backend_id, task_scope=task_scope, p95_latency_ms=900,
        tokens_per_second=45, quality_score=0.91, cost_per_1k_tokens=0.002,
        peak_ram_bytes=9_000_000_000, peak_vram_bytes=11_000_000_000,
        sample_count=100, eval_suite_sha256=HASH_A, result_sha256=HASH_B,
        measured_at="2026-11-11T12:00:00Z",
    )
    values.update(changes)
    return ModelMeasurement(**values)


def receipt(backend_id="vllm", **changes):
    values = dict(
        backend_id=backend_id, model_revision="model@abc", engine_revision="vllm@1",
        heldout_eval_sha256=HASH_A, eval_result_sha256=HASH_B,
        security_review_sha256=HASH_C, issued_at="2026-11-11T12:00:00Z",
        approved=True,
    )
    values.update(changes)
    return ModelQualificationReceipt(**values)


class ModelFabricTests(unittest.TestCase):
    def test_selects_only_qualified_measured_backend(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council", require_streaming=True),
            [backend()], [measurement()], [receipt()],
        )
        self.assertEqual(decision.selected_backend_id, "vllm")

    def test_configured_backend_is_not_qualified(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council"),
            [backend(state="configured")], [measurement()], [receipt()],
        )
        self.assertIsNone(decision.selected_backend_id)
        self.assertIn(("vllm", "backend_not_available"), decision.excluded)

    def test_missing_receipt_fails_closed(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council"),
            [backend()], [measurement()], [],
        )
        self.assertEqual(decision.excluded[0][1], "no_matching_approved_qualification_receipt")

    def test_receipt_must_bind_exact_model_and_engine_revision(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council"),
            [backend()], [measurement()], [receipt(model_revision="model@other")],
        )
        self.assertIsNone(decision.selected_backend_id)

    def test_receipt_must_bind_exact_heldout_eval_and_result(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council"),
            [backend()], [measurement()], [receipt(eval_result_sha256=HASH_C)],
        )
        self.assertIsNone(decision.selected_backend_id)

    def test_quality_is_primary_ranking(self):
        better_quality = backend("better", model_id="model/better")
        worse_latency = measurement("better", quality_score=0.94, p95_latency_ms=1400)
        decision = route_model(
            ModelRouteRequest(task_scope="council"),
            [backend(), better_quality],
            [measurement(), worse_latency],
            [receipt(), receipt("better")],
        )
        self.assertEqual(decision.selected_backend_id, "better")

    def test_data_class_and_resource_budgets_are_enforced(self):
        decision = route_model(
            ModelRouteRequest(task_scope="council", data_class="restricted", max_vram_bytes=1),
            [backend()], [measurement()], [receipt()],
        )
        self.assertIsNone(decision.selected_backend_id)
        self.assertIn(("vllm", "data_class_not_permitted"), decision.excluded)

    def test_task_specific_measurement_required(self):
        decision = route_model(
            ModelRouteRequest(task_scope="chat"),
            [backend()], [measurement(task_scope="council")], [receipt()],
        )
        self.assertIsNone(decision.selected_backend_id)

    def test_streaming_and_tools_are_explicit_requirements(self):
        no_stream = backend(supports_streaming=False)
        decision = route_model(
            ModelRouteRequest(task_scope="council", require_streaming=True),
            [no_stream], [measurement()], [receipt()],
        )
        self.assertIsNone(decision.selected_backend_id)

    def test_duplicate_backend_ids_rejected(self):
        with self.assertRaises(ModelFabricError):
            route_model(
                ModelRouteRequest(task_scope="council"),
                [backend(), backend()], [measurement()], [receipt()],
            )

    def test_non_finite_measurements_rejected(self):
        with self.assertRaises(ModelFabricError):
            route_model(
                ModelRouteRequest(task_scope="council"),
                [backend()], [measurement(quality_score=float("nan"))], [receipt()],
            )


if __name__ == "__main__":
    unittest.main()
