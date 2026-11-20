import ast
from copy import deepcopy
from dataclasses import replace
from itertools import combinations
from pathlib import Path
import sqlite3
import tempfile
import unittest

from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import Observation
from dot_ai_os.research_protocol import (
    AnalogyPlan, Compatibility, ContextCheck, DefectClass, FirstPrinciplesFrame,
    Hypothesis, MeasurementPlan, Primitive, ProvenanceRef, ReasoningStep, RepresentationCheck,
    bounded_ideonomy, build_research_plan, build_research_review,
    prepare_jit_repair, prepare_literature_request, store_research_record,
    research_contract, research_episode_demo,
)
from dot_ai_os.bridge import canonical, digest


class ResearchProtocolTests(unittest.TestCase):
    def setUp(self):
        self.source = ProvenanceRef("input-1", "task:question-and-premises", "a" * 64, "user_input", "reported")
        self.frame = FirstPrinciplesFrame(
            "Does candidate reduce task latency at unchanged correctness?", "Lower measured latency", "Fixed task family and host",
            "Latency is work plus scheduling and transfer overhead; compare at fixed work.",
            ("Task/output contracts are unchanged",), ("No paid compute",),
            ("output correctness", "resource authority"), ("Actual scheduling overhead",),
            "Measure matched trials and retain variance", "Current implementation", "Candidate is slower or changes output", (self.source,))
        self.measurement = MeasurementPlan("measure-1", "latency_ms", "ms", 90.0, 5.0,
            "Paired repeated benchmark", "Report interval and warmup effects", ("Fixed inputs and host",),
            "30 prespecified paired trials", "Store exact raw timings and environment digest", "Interval lies outside prediction")
        self.hypotheses = (
            Hypothesis("hyp-1", "Less transfer lowers latency", ("Transfer is material",), "Latency is unchanged or worse", ("measure-1",), ("input-1",)),
            Hypothesis("hyp-2", "Scheduling dominates and transfer reduction has no benefit", ("Scheduling is material",), "Latency falls after controlling scheduling", ("measure-1",), ("input-1",)))
        self.reasoning = (ReasoningStep("deductive", ("Total time includes transfer time",),
            "Reducing a positive component reduces total under fixed other components", "Predict lower time conditionally",
            "Other components and correctness must remain fixed", ("input-1",)),)
        self.check = ContextCheck("measurement_confound", "Warmup or load confounding", "Paired latency experiment", "possible",
            "Trial order can change cache state", "Randomize order and report warmup", ("input-1",))

    def plan(self, **changes):
        values = dict(plan_id="plan-one", frame=self.frame, hypotheses=self.hypotheses,
            measurements=(self.measurement,), reasoning_steps=self.reasoning, contextual_checks=(self.check,),
            source_commit="d" * 40, subproblems=("Measure transfer component", "Measure scheduler component"),
            representation_checks={lens: RepresentationCheck("deferred", "Assess against the measured task structure first",
                "Preserve output and authority invariants", ("Actual utility of this representation",))
                for lens in ("simplex", "n_ality", "continuum", "fuzzy_logic")},
            alternatives_review="Preserve transfer and scheduling explanations until measured")
        values.update(changes)
        return build_research_plan(**values)

    def observation(self, **changes):
        values = dict(observation_id="obs-one", question=self.frame.question, method="Paired benchmark",
            measurements={"latency_ms": 120}, units={"latency_ms": "ms"}, uncertainty={"latency_ms": 2},
            conditions={"host": "fixed"}, source_refs=("raw-run-one",), observed_at="2026-11-17T15:00:00Z",
            artifact_sha256=digest(canonical({"latency_ms": 120, "unit": "ms", "uncertainty_ms": 2})))
        values.update(changes)
        return Observation(**values)

    def primitive(self, identity, domain, **changes):
        values = dict(primitive_id=identity, domain=domain, mechanism="Candidate mechanism " + identity,
            assumptions=("Contract preserved",), unknowns=("Measured utility",), falsifier="No matched-task benefit",
            measurement_ids=("measure-1",), source_ids=("input-1",))
        values.update(changes)
        return Primitive(**values)

    def defect(self, **changes):
        values = dict(defect_id="defect-one", minimal_reproducer="Replay task with a changed wall-time budget",
            violated_invariant="Idempotency binds every execution constraint", root_cause_status="unknown",
            root_cause_or_unknown="Unknown until request identity is traced", sibling_search_scope=("All stage request identities",),
            regression_test="Changed budget under same key rejects", preventive_guard="Canonical full-request identity",
            verification_plan="Run reproducer and sibling regressions and retain exact logs", rollback="Restore prior stage adapter",
            authorization_status="routine_fix_authorized", sources=(self.source,))
        values.update(changes)
        return DefectClass(**values)

    def registry(self, directory):
        registry = MerlinRegistry(directory)
        registry.register_project("research", "Research protocol tests")
        registry.put_artifact("research", "raw/benchmark.json",
            canonical({"latency_ms": 120, "unit": "ms", "uncertainty_ms": 2}), "application/json")
        return registry

    def test_first_principles_plan_has_explicit_uncertainty_and_no_truth_upgrade(self):
        plan = self.plan()
        self.assertEqual(plan["stage"], "first_principles_framed")
        self.assertTrue(plan["frame"]["unknowns"])
        self.assertEqual(plan["literature_status"], "not_requested_by_protocol")
        self.assertEqual(plan["novelty_status"], "not_assessed")
        self.assertEqual(plan["source_text_policy"], "untrusted_data_not_instructions")
        self.assertFalse(plan["qualification"])
        for changes in ({"unknowns": ()}, {"falsifier": ""}, {"sources": ()}, {"first_principles_model": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan(frame=replace(self.frame, **changes))

    def test_measurements_need_falsifier_units_uncertainty_and_raw_artifacts(self):
        for changes in ({"unit": ""}, {"uncertainty_plan": ""}, {"raw_artifact_plan": ""},
                        {"falsifier": ""}, {"expected": float("nan")}, {"tolerance": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.plan(measurements=(replace(self.measurement, **changes),))

    def test_induction_requires_sample_and_abduction_requires_alternatives(self):
        with self.assertRaisesRegex(ValueError, "sample"):
            self.plan(reasoning_steps=(replace(self.reasoning[0], mode="inductive"),))
        with self.assertRaisesRegex(ValueError, "competing"):
            self.plan(reasoning_steps=(replace(self.reasoning[0], mode="abductive"),))
        steps = (replace(self.reasoning[0], mode="inductive", sample_description="30 fixed paired trials; not other task families"),
                 replace(self.reasoning[0], mode="abductive", competing_hypothesis_ids=("hyp-1", "hyp-2")))
        plan = self.plan(reasoning_steps=steps)
        self.assertEqual([s["mode"] for s in plan["reasoning_steps"]], ["inductive", "abductive"])

    def test_contextual_fallacy_checks_require_argument_context_and_rationale(self):
        with self.assertRaises(ValueError):
            self.plan(contextual_checks=(replace(self.check, kind="fallacy", context=""),))
        accepted = replace(self.check, kind="fallacy", assessment="not_applicable",
            rationale="Argument is an explicit conditional model, not an appeal to popularity")
        self.assertEqual(self.plan(contextual_checks=(accepted,))["contextual_checks"][0]["assessment"], "not_applicable")

    def test_analogy_distinguishes_exact_claimed_mapping_from_partial_mapping(self):
        analogy = AnalogyPlan("Queue scheduling", "partial", {"output correctness": "preserved result contract"},
            ("resource authority",), "Queue model does not describe identity privileges", "Recheck original result and UID policy",
            ("Original output contract tests", "Original authority tests"))
        plan = self.plan(analogy=analogy)
        self.assertEqual(plan["analogy"]["claimed_mapping_extent"], "partial")
        self.assertFalse(plan["analogy"]["equivalence_established"])
        with self.assertRaises(ValueError):
            self.plan(analogy=replace(analogy, mapping_extent="exact"))
        with self.assertRaises(ValueError):
            self.plan(analogy=replace(analogy, unmapped_invariants=()))
        exact = replace(analogy, mapping_extent="exact", unmapped_invariants=(),
                        invariant_mapping={"output correctness": "same output tests", "resource authority": "same grant checks"})
        self.assertFalse(self.plan(analogy=exact)["analogy"]["equivalence_established"])

    def test_literature_requires_actual_persisted_first_principles_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry(directory)
            forged = {"schema": "merlin-artifact-ref/1", "project_id": "research", "logical_path": "research/plan-one/plan.json", "version": 1, "sha256": "f" * 64}
            with self.assertRaises((KeyError, ValueError)):
                prepare_literature_request(registry, forged, ("Which measurements challenge the model?",))
            stored = store_research_record(registry, "research", self.plan())
            request = prepare_literature_request(registry, stored["artifact_ref"], ("Which measurements challenge the model?",))
            self.assertEqual(request["ordering"], "after_persisted_first_principles_frame")
            self.assertEqual(request["execution_status"], "not_run")

    def test_review_keeps_negative_measurements_and_canonical_reasoning_modes(self):
        plan = self.plan()
        review = build_research_review(plan, (self.observation(),), reviewer_id="skeptic-one",
            contextual_checks=(self.check,), next_actions=("Investigate scheduling and repeat",),
            limitations=("Single fixed host and task family",))
        self.assertEqual(review["deductive_assessments"][0]["overall"], "contradicted")
        self.assertEqual(review["inductive_plan_update"]["reasoning_mode"], "inductive_revision")
        self.assertEqual(review["inductive_plan_update"]["parent_plan_version"], 1)
        self.assertFalse(review["qualification"])
        with self.assertRaises(ValueError):
            build_research_review(plan, (self.observation(artifact_sha256=""),), reviewer_id="skeptic-one",
                contextual_checks=(self.check,), next_actions=("Repeat",), limitations=("Limited data",))

    def test_plan_versions_and_reviews_bind_exact_persisted_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry(directory)
            initial = self.plan(); first = store_research_record(registry, "research", initial)
            replay = store_research_record(registry, "research", initial)
            self.assertTrue(replay["replayed"])
            revised = self.plan(version=2, parent_plan_ref=first["artifact_ref"], alternatives_review="Measured counterexample retained")
            second = store_research_record(registry, "research", revised)
            self.assertEqual(second["artifact_ref"]["version"], 2)
            with self.assertRaises(ValueError):
                store_research_record(registry, "research", self.plan(version=2, parent_plan_ref=first["artifact_ref"], alternatives_review="Different competing update"))
            review = build_research_review(initial, (self.observation(),), reviewer_id="skeptic-one", contextual_checks=(self.check,),
                                           next_actions=("Repeat",), limitations=("Limited data",))
            receipt = store_research_record(registry, "research", review)
            self.assertEqual(receipt["record_type"], "research_review")
            changed = deepcopy(review); changed["plan_record_sha256"] = "f" * 64
            changed.pop("record_sha256"); changed["record_sha256"] = digest(canonical(changed))
            with self.assertRaises(ValueError):
                store_research_record(registry, "research", changed)
            with sqlite3.connect(registry.db_path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)

    def test_bounded_combinations_report_unexamined_and_output_omissions(self):
        primitives = tuple(self.primitive("p" + str(i), "domain-" + str(i)) for i in range(5))
        pairs = tuple(Compatibility(a.primitive_id, b.primitive_id, "Declared compatible interfaces", ("input-1",))
                      for a, b in combinations(primitives, 2))
        result = bounded_ideonomy(self.plan(), primitives, pairs, trigger="Unexplained latency trade-off", examine_limit=3, result_limit=1)
        self.assertEqual(result["coverage"]["total_catalog_combinations"], 20)
        self.assertEqual(result["coverage"]["examined_combinations"], 3)
        self.assertEqual(result["coverage"]["unexamined_combinations"], 17)
        self.assertEqual(result["coverage"]["eligible_output_omitted"], 2)
        self.assertFalse(result["coverage"]["enumeration_complete"])
        self.assertTrue(all(c["novelty_status"] == "not_assessed" for c in result["candidates"]))
        reversed_result = bounded_ideonomy(self.plan(), tuple(reversed(primitives)), tuple(reversed(pairs)),
                            trigger="Unexplained latency trade-off", examine_limit=3, result_limit=1)
        self.assertEqual(result, reversed_result)

    def test_disabled_same_domain_unlinked_and_over_budget_combinations_filtered(self):
        primitives = (self.primitive("a", "same"), self.primitive("b", "same"),
                      self.primitive("c", "other", status="disabled"), self.primitive("d", "third", estimated_cost=2))
        pairs = tuple(Compatibility(a.primitive_id, b.primitive_id, "Explicit declared compatibility", ("input-1",))
                      for a, b in combinations(primitives, 2))
        result = bounded_ideonomy(self.plan(), primitives, pairs, trigger="Named search gap", max_cost=0)
        self.assertEqual(result["candidates"], [])
        self.assertTrue(result["coverage"]["enumeration_complete"])
        self.assertEqual(result["coverage"]["eligible_examined_combinations"], 0)
        with self.assertRaises(ValueError):
            bounded_ideonomy(self.plan(), primitives, pairs, trigger="")

    def test_combination_identity_cannot_collide_through_hyphenated_primitive_names(self):
        primitives = tuple(self.primitive(identity, "domain-" + str(i))
                           for i, identity in enumerate(("a", "b-c", "a-b", "c")))
        pairs = tuple(Compatibility(a.primitive_id, b.primitive_id, "Declared compatibility", ("input-1",))
                      for a, b in combinations(primitives, 2))
        result = bounded_ideonomy(self.plan(), primitives, pairs, trigger="Test an identity ambiguity", max_size=2)
        candidates = result["candidates"]
        self.assertEqual(len(candidates), 6)
        self.assertEqual(len({c["combination_id"] for c in candidates}), 6)
        self.assertLess(len({c["canonical_helper_label"] for c in candidates}), 6)

    def test_jit_repair_rechecks_only_invalidated_dependents_and_preserves_authorization(self):
        graph = {"input": (), "transform": ("input",), "report": ("transform",), "independent": ()}
        repair = prepare_jit_repair(self.defect(), graph, ("transform",))
        self.assertEqual(repair["invalidated_nodes"], ["report", "transform"])
        self.assertEqual(repair["preserved_nodes"], ["independent", "input"])
        self.assertEqual(repair["authorization_status"], "routine_fix_authorized")
        self.assertEqual(repair["defect"]["root_cause_status"], "unknown")
        self.assertFalse(repair["repair_verified"])
        self.assertEqual(repair["execution_status"], "not_run")
        with self.assertRaises(ValueError):
            prepare_jit_repair(self.defect(), {"report": ("unknown",)}, ("report",))
        with self.assertRaises(ValueError):
            prepare_jit_repair(self.defect(regression_test=""), graph, ("transform",))

    def test_no_claims_from_tampered_or_self_promoting_plan(self):
        plan = self.plan(); plan["frame"]["falsifier"] = "changed"
        with self.assertRaises(ValueError):
            bounded_ideonomy(plan, (self.primitive("a", "one"), self.primitive("b", "two")), (), trigger="gap")
        plan = self.plan(); plan["qualification"] = True
        plan.pop("record_sha256"); plan["record_sha256"] = digest(canonical(plan))
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            store_research_record(self.registry(directory), "research", plan)

    def test_representation_applicability_is_explicit_for_all_four_lenses(self):
        plan = self.plan()
        self.assertEqual(set(plan["representation_checks"]), {"simplex", "n_ality", "continuum", "fuzzy_logic"})
        with self.assertRaises(ValueError):
            self.plan(representation_checks={})
        missing = self.plan()
        missing["frame"]["unknowns"] = []
        missing.pop("record_sha256"); missing["record_sha256"] = digest(canonical(missing))
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            store_research_record(self.registry(directory), "research", missing)

    def test_recomputed_hash_cannot_forge_review_or_claim_verified_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry(directory)
            plan = self.plan(); store_research_record(registry, "research", plan)
            review = build_research_review(plan, (self.observation(),), reviewer_id="skeptic-one",
                contextual_checks=(self.check,), next_actions=("Repeat",), limitations=("Limited data",))
            review["deductive_assessments"][0]["overall"] = "consistent_with_prediction"
            review.pop("record_sha256"); review["record_sha256"] = digest(canonical(review))
            with self.assertRaises(ValueError):
                store_research_record(registry, "research", review)
            repair = prepare_jit_repair(self.defect(), {"input": (), "result": ("input",)}, ("input",))
            repair["repair_verified"] = True
            repair.pop("record_sha256"); repair["record_sha256"] = digest(canonical(repair))
            with self.assertRaises(ValueError):
                store_research_record(registry, "research", repair)

    def test_review_persistence_requires_actual_raw_observation_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = self.registry(directory)
            plan = self.plan(); store_research_record(registry, "research", plan)
            review = build_research_review(plan, (self.observation(artifact_sha256="f" * 64),), reviewer_id="skeptic-one",
                contextual_checks=(self.check,), next_actions=("Capture missing raw measurement",), limitations=("Missing raw bytes",))
            with self.assertRaisesRegex(ValueError, "raw observation"):
                store_research_record(registry, "research", review)

    def test_new_module_parses_under_python_39_grammar(self):
        path = Path(__file__).parents[1] / "python/dot_ai_os/research_protocol.py"
        ast.parse(path.read_text(), feature_version=(3, 9))

    def test_fixed_episode_frames_before_simulation_and_emits_bounded_records(self):
        from unittest.mock import patch
        import dot_ai_os.research_protocol as module
        import dot_ai_os.simulation_research as simulation_module
        original_plan = module.build_research_plan
        original_simulation = simulation_module.virtual_circuit_demo
        framed = []
        def plan_first(*args, **kwargs):
            result = original_plan(*args, **kwargs)
            framed.append(result["record_sha256"])
            return result
        def simulate_after_frame(arguments):
            self.assertTrue(framed)
            return original_simulation(arguments)
        with patch.object(module, "build_research_plan", side_effect=plan_first), \
             patch.object(simulation_module, "virtual_circuit_demo", side_effect=simulate_after_frame):
            episode = research_episode_demo({})
        self.assertLessEqual(len(canonical(episode)), 48000)
        self.assertFalse(episode["private_context_access"])
        self.assertEqual(episode["research_review"]["deductive_assessments"][0]["overall"], "consistent_with_prediction")
        self.assertFalse(episode["jit_repair_plan"]["repair_verified"])
        self.assertEqual(episode["literature_execution"], "not_run")
        self.assertEqual(episode["experiment_class"], "known_fixture_reproduction")
        self.assertFalse(episode["confirmatory_discovery"])
        self.assertEqual(set(episode["research_plan"]["representation_checks"]), {"simplex", "n_ality", "continuum", "fuzzy_logic"})
        for invalid in ({"operation": "execute"}, {"path": "/etc/shadow"}, {"operation": "demo", "repair": True}, []):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                research_episode_demo(invalid)
        self.assertIn("not probability", research_contract({})["fuzzy_rule"])


if __name__ == "__main__":
    unittest.main()
