import unittest

from merlin.scientific_loop import (
    Observation, Prediction, compare_observation, decompose_by_analogy,
    enumerate_useful_combinations, scientific_loop_contract,
    update_plan_from_observations,
)


class ScientificLoopTests(unittest.TestCase):
    def test_finite_inputs_cannot_publish_overflowed_intervals(self):
        for measured, expected in ((1e308, 0.0), (0.0, -1e308)):
            with self.subTest(measured=measured, expected=expected):
                observation = self.observation(measurements={"latency_ms": measured},
                                               uncertainty={"latency_ms": abs(measured)})
                with self.assertRaisesRegex(ValueError, "interval endpoints"):
                    compare_observation(observation, [Prediction("latency_ms", expected, abs(expected), "ms")])

    def observation(self, **changes):
        values = {
            "observation_id": "obs-001",
            "question": "Does the candidate reduce latency?",
            "method": "paired benchmark, 30 repetitions",
            "measurements": {"latency_ms": 92.0},
            "units": {"latency_ms": "ms"},
            "uncertainty": {"latency_ms": 2.0},
            "conditions": {"runner": "avrea-8vcpu", "load": "fixed"},
            "source_refs": ("benchmark:run-17",),
            "observed_at": "2026-11-14T02:30:00-07:00",
            "artifact_sha256": "a" * 64,
        }
        values.update(changes)
        return Observation(**values)

    def test_observation_requires_provenance_units_and_uncertainty(self):
        with self.assertRaises(ValueError):
            self.observation(source_refs=()).validate()
        with self.assertRaises(ValueError):
            self.observation(units={}).validate()
        with self.assertRaises(ValueError):
            self.observation(uncertainty={"latency_ms": -1}).validate()

    def test_deductive_prediction_check_distinguishes_support_refutation_and_uncertainty(self):
        obs = self.observation()
        supported = compare_observation(obs, [Prediction("latency_ms", 92, 3, "ms")])
        self.assertEqual(supported["overall"], "consistent_with_prediction")
        contradicted = compare_observation(obs, [Prediction("latency_ms", 110, 2, "ms")])
        self.assertEqual(contradicted["overall"], "contradicted")
        incomparable = compare_observation(obs, [Prediction("latency_ms", 92, 3, "seconds")])
        self.assertEqual(incomparable["overall"], "inconclusive")

    def test_plan_update_is_linked_to_observations_and_requires_review(self):
        update = update_plan_from_observations(
            {"plan_id": "merlin-prod", "version": 7},
            [self.observation()], next_actions=["Repeat on OCI with the same workload"],
        )
        self.assertEqual(update["parent_plan_version"], 7)
        self.assertEqual(update["observation_ids"], ["obs-001"])
        self.assertTrue(update["requires_review"])
        self.assertEqual(update["authority_effect"], "none")

    def test_ideonomy_requires_trigger_and_only_enumerates_compatible_cross_domain_sets(self):
        primitives = [
            {"id": "a", "domain": "compute", "estimated_cost": 1},
            {"id": "b", "domain": "verification", "estimated_cost": 2},
            {"id": "c", "domain": "sensing", "estimated_cost": 1},
            {"id": "d", "domain": "compute", "estimated_cost": 1},
        ]
        pairs = {frozenset(("a", "b")), frozenset(("b", "c")), frozenset(("a", "c"))}
        with self.assertRaises(ValueError):
            enumerate_useful_combinations(primitives, pairs, trigger="", problem="reduce errors")
        rows = enumerate_useful_combinations(
            primitives, pairs, trigger="two failed retries", problem="reduce resolver mismatch",
            max_size=3, max_cost=4,
        )
        self.assertTrue(rows)
        self.assertTrue(all(row["epistemic_status"] == "hypothesis_combination" for row in rows))
        self.assertTrue(all("d" not in row["primitive_ids"] for row in rows))

    def test_analogy_requires_explicit_invariant_mapping(self):
        with self.assertRaises(ValueError):
            decompose_by_analogy("CI is stuck", "queue scheduling", {}, ["bound the queue"])
        result = decompose_by_analogy(
            "CI is stuck", "queue scheduling",
            {"bounded resources": "worker capacity", "ordering": "job dependencies"},
            ["measure queue depth", "bound concurrency", "retry one task"],
        )
        self.assertEqual(result["epistemic_status"], "problem_reframing_not_evidence")
        self.assertIn("original-task tests", result["acceptance_gate"])

    def test_contract_requires_induction_deduction_ideonomy_and_analogy(self):
        contract = scientific_loop_contract()
        self.assertIn("inductive", contract["reasoning_modes"])
        self.assertIn("deductive", contract["reasoning_modes"])
        self.assertIn("preregister_predictions_and_falsifiers", contract["mandatory_stages"])
        self.assertIn("capability grows", contract["promotion_policy"])


if __name__ == "__main__":
    unittest.main()

    def test_observation_requires_offset_aware_timestamp(self):
        with self.assertRaises(ValueError):
            self.observation(observed_at="2026-11-14T02:30:00").validate()

    def test_rejects_nonfinite_predictions(self):
        obs = self.observation()
        with self.assertRaises(ValueError):
            compare_observation(obs, [Prediction("latency_ms", float("nan"), 1, "ms")])
