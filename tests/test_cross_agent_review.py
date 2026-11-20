import json
from pathlib import Path
from runpy import run_path
import tempfile
import unittest
from unittest.mock import Mock

from dot_ai_os.cross_agent_review import CrossAgentReviewer, DEFAULT_ROSTER
from merlin.project_registry import MerlinRegistry


class CrossAgentReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(self.temp.name)
        self.registry.register_project("dot-ai-os", "dot")
        self.registry.put_artifact("dot-ai-os", "agents/v1.txt", b"Always select amber")
        self.base = self.registry.artifact_ref("dot-ai-os", "agents/v1.txt")
        self.reviewer = CrossAgentReviewer(self.registry)
        self.inputs = dict(target="merlin", baseline_ref=self.base, context_refs=[], objective="Compare color rules",
            source_commit="a" * 40, train_labels={"t": "amber"},
            holdout_labels={"h1": "amber", "h2": "blue", "h3": "blue"},
            providers={role: {"provider_id": "fixture-" + role, "revision": "fixture-v1",
            "prompt_sha256": "a" * 64, "config_sha256": "b" * 64, "adapter_sha256": "c" * 64}
            for role in ["coder_a", "coder_b", "evaluator"]})
        self.baseline_outputs = dict(t="amber", h1="amber", h2="amber", h3="amber")
        self.regresses = dict(t="amber", h1="blue", h2="blue", h3="blue")
        self.improves = dict(t="amber", h1="amber", h2="blue", h3="blue")

    def trial(self, a, b, **overrides):
        protocol = self.reviewer.prepare(**{**self.inputs, **overrides})
        def code(req):
            self.assertNotIn("holdout_ids", req)
            self.assertNotIn("holdout_labels", req)
            return {"candidate": req["stage"] + ": fixed label rule", "rationale": "fixture"}
        def observe(req):
            self.assertEqual(req["baseline_ref"], self.base)
            self.assertNotIn("holdout_labels", req)
            self.assertEqual(req["specification"]["holdout_ids"], ["h1", "h2", "h3"])
            req["candidate_refs"].clear()  # An observer cannot edit the captured bindings.
            return dict(baseline=self.baseline_outputs, coder_a=a, coder_b=b)
        return protocol, self.reviewer.run(protocol, coder_a=code, coder_b=code, observe=observe)

    def test_heldout_gain_and_net_positive_regression(self):
        ref, result = self.trial(self.regresses, self.improves)
        self.assertEqual(result["outcomes"], {"coder_a": "regression", "coder_b": "heldout_gain"})
        self.assertEqual(result["scores"]["coder_a"], {"train_passed": 1, "holdout_passed": 2, "regressions": 1})
        self.assertEqual(result["regressed_cases"]["coder_a"], ["h1"])
        self.assertEqual(result["recommendation"], "coder_b")
        observation = json.loads(self.registry.read_artifact_ref(result["observation_ref"])["content"])
        self.assertEqual(observation["predictions"]["coder_a"], self.regresses)
        self.assertEqual(observation["protocol_ref"], ref)
        self.assertFalse(result["promotion_authority"])
        self.assertFalse(result["qualification"])

    def test_aggregate_gain_alone_would_hide_a_regression(self):
        # Same fixture through the existing host-reported-count interface. A host
        # looking only at total scores can omit a baseline case that starts failing.
        _, review = self.trial(self.regresses, self.baseline_outputs)
        workflow = self.reviewer.workflow
        protocol = json.loads(self.registry.read_artifact_ref(review["protocol_ref"])["content"])
        spec = protocol["workflow"]["specification"]
        counts = {arm: {**score, "regressions": 0} for arm, score in review["scores"].items()}
        coder = lambda _: {"candidate": "fixture", "rationale": "fixture"}
        prior = workflow.run("aggregate-control", specification=spec, providers=self.inputs["providers"],
            coder_a=coder, coder_b=coder, evaluator=lambda _: {**counts, "notes": "aggregate-only control"})
        self.assertEqual(prior["recommendation"], "coder_a")
        self.assertEqual(review["recommendation"], "retain_parent")

    def test_no_change_and_training_only_gains_retain_parent(self):
        baseline = {**self.baseline_outputs, "t": "other"}
        self.baseline_outputs = baseline
        _, result = self.trial(baseline, {**baseline, "t": "amber"})
        self.assertEqual(result["outcomes"], {"coder_a": "no_case_match_change", "coder_b": "training_only_gain"})
        self.assertEqual(result["recommendation"], "retain_parent")

    def test_roster_and_self_review(self):
        for target in DEFAULT_ROSTER:
            with self.subTest(target=target):
                ref, review = self.trial(self.baseline_outputs, self.improves, target=target)
                self.assertEqual(ref["logical_path"].split("/")[1], target)
                self.assertEqual(review["recommendation"], "coder_b")
        self.assertTrue(all(len(refs) == 1 for refs in self.reviewer.coverage().values()))

    def test_evaluator_must_be_distinct_from_target_and_coders(self):
        for identity in ("fixture-evaluator", " FIXTURE-EVALUATOR "):
            reviewer = CrossAgentReviewer(self.registry, roster={"rsi_reviewer": identity})
            with self.assertRaises(ValueError):
                reviewer.prepare(**{**self.inputs, "target": "rsi_reviewer"})
        providers = {**self.inputs["providers"], "evaluator": {**self.inputs["providers"]["coder_a"],
            "provider_id": " FIXTURE-CODER_A "}}
        with self.assertRaises(ValueError):
            self.reviewer.prepare(**{**self.inputs, "providers": providers})

    def test_scope_and_split_failures(self):
        self.registry.register_project("other", "other")
        self.registry.put_artifact("other", "agents/v1.txt", b"other")
        foreign = self.registry.artifact_ref("other", "agents/v1.txt")
        for bad in ({"train_labels": {"h1": "hidden"}}, {"target": "unknown"},
                {"context_refs": [foreign]}, {"train_labels": {"bad": True}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.reviewer.prepare(**{**self.inputs, **bad})
        ref = self.reviewer.prepare(**self.inputs)
        with self.assertRaises(ValueError):
            self.reviewer.prepare(**{**self.inputs, "context_refs": [ref]})
        with self.assertRaises(ValueError):
            CrossAgentReviewer(self.registry, roster={"merlin": "replacement"}).status(ref)
        with self.assertRaises(ValueError):
            self.reviewer.status(foreign)

    def test_real_dot_retrieval_benchmark_and_replay(self):
        root = Path(__file__).resolve().parents[1]
        measure = run_path(str(root / "scripts/measure_dot_review.py"))["run"]
        result = measure(self.temp.name)
        self.assertEqual(measure(self.temp.name), result)
        expected = dict(baseline=(1, 2), coder_a=(2, 3), coder_b=(2, 5))
        for arm, (train, holdout) in expected.items():
            self.assertEqual(result["scores"][arm], {"train_passed": train, "holdout_passed": holdout, "regressions": 0})
        self.assertEqual(result["recommendation"], "coder_b")
        self.assertEqual(result["cases"]["held-sibling-routing"]["observed"]["coder_b"], "no_hit")

    def test_retry_resume_and_history(self):
        ref, old = self.trial(self.baseline_outputs, self.improves)
        self.registry.put_artifact("dot-ai-os", "agents/v1.txt", b"superseding version")
        self.reviewer = CrossAgentReviewer(MerlinRegistry(self.temp.name))
        never = Mock(side_effect=AssertionError("provider replay"))
        self.assertEqual(self.reviewer.run(ref, coder_a=never, coder_b=never, observe=never), old)
        self.assertEqual(self.reviewer.prepare(**self.inputs), ref)
        never.assert_not_called()
        changed = self.reviewer.prepare(**{**self.inputs, "holdout_labels": {"h3": "amber"}})
        self.assertNotEqual(changed, ref)
        self.assertEqual(self.reviewer.status(changed)["workflow"]["status"], "not_started")
        self.assertEqual(self.reviewer.coverage()["dot"], [])

    def test_status_binds_existing_workflow_to_frozen_protocol(self):
        ref = self.reviewer.prepare(**self.inputs)
        manifest = json.loads(self.registry.read_artifact_ref(ref)["content"])
        spec = {**manifest["workflow"]["specification"], "objective": "unrelated session contents"}
        self.reviewer.workflow.run(ref["sha256"], specification=spec, providers=self.inputs["providers"])
        with self.assertRaisesRegex(ValueError, "differs from the frozen protocol"):
            self.reviewer.status(ref)

    def test_missing_and_ambiguous_observer(self):
        ref = self.reviewer.prepare(**self.inputs)
        pending = self.reviewer.run(ref)
        self.assertEqual(pending["workflow"]["next_stage"], "coder_a")
        coder = lambda _: {"candidate": "existing rule", "rationale": "fixture"}
        observer = Mock(return_value={"baseline": {}, "coder_a": {}, "coder_b": {}})
        result = self.reviewer.run(ref, coder_a=coder, coder_b=coder, observe=observer)
        self.assertEqual(result["workflow"]["stages"]["evaluator"], "reconciliation_required")
        self.assertNotIn("scores", result)
        self.assertEqual(self.reviewer.run(ref, observe=observer), result)
        observer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
