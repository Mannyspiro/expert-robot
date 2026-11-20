from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import canonical
from dot_ai_os.dual_coder import DualCoderWorkflow, WorkflowConflict


def identity(name):
    return {"provider_id": name, "revision": "fixture-2026-11-17-v1",
            "prompt_sha256": "a" * 64, "config_sha256": "b" * 64,
            "adapter_sha256": "c" * 64}


class DualCoderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root)
        self.registry.register_project("dot-ai-os", "Dot test")
        self.registry.put_artifact("dot-ai-os", "context/parent.txt", b"Parent skill: retain exact source citations.")
        self.source_ref = self.registry.artifact_ref("dot-ai-os", "context/parent.txt")
        self.workflow = DualCoderWorkflow(self.registry)
        self.spec = {"objective": "Improve source-citation skill without losing old behavior",
                     "source_commit": "d" * 40, "context_refs": [self.source_ref],
                     "train_ids": ["train-1", "train-2"],
                     "holdout_ids": ["heldout-1", "heldout-2"],
                     "acceptance_criteria": ["Keep exact citations", "Retain explicit uncertainty"],
                     "max_cost_usd": 0}
        self.providers = {stage: identity(stage) for stage in ("coder_a", "coder_b", "evaluator")}
        self.calls = {stage: 0 for stage in self.providers}
        self.requests = {}

    def coder_a(self, request):
        self.calls["coder_a"] += 1
        self.requests["coder_a"] = deepcopy(request)
        return {"candidate": "cite_exact\nlabel_uncertainty", "rationale": "Use exact source and status"}

    def coder_b(self, request):
        self.calls["coder_b"] += 1
        self.requests["coder_b"] = deepcopy(request)
        return {"candidate": "cite_exact\nlabel_uncertainty\ncheck_stale_source",
                "rationale": "A preserves citations but misses stale-source checks"}

    def evaluator(self, request):
        self.calls["evaluator"] += 1
        self.requests["evaluator"] = deepcopy(request)
        # This independent deterministic fixture actually scores each supplied
        # skill against separate train/holdout requirements; no model calls.
        def score(candidate):
            train = ["cite_exact", "label_uncertainty"]
            holdout = ["cite_exact", "check_stale_source"]
            return {"train_passed": sum(x in candidate for x in train),
                    "holdout_passed": sum(x in candidate for x in holdout),
                    "regressions": int("cite_exact" not in candidate)}
        return {"baseline": score("cite_exact"),
                "coder_a": score(request["candidates"]["coder_a"]["candidate"]),
                "coder_b": score(request["candidates"]["coder_b"]["candidate"]),
                "notes": "Four deterministic fixture requirements only; no capability claim."}

    def run_workflow(self, session="one", **overrides):
        kwargs = {"specification": self.spec, "providers": self.providers,
                  "coder_a": self.coder_a, "coder_b": self.coder_b, "evaluator": self.evaluator}
        kwargs.update(overrides)
        return self.workflow.run(session, **kwargs)

    def test_both_coders_and_evaluator_run_with_exact_context(self):
        result = self.run_workflow()
        self.assertEqual(result["status"], "completed_research_only")
        self.assertEqual(result["recommendation"], "coder_b")
        self.assertFalse(result["qualification"])
        self.assertFalse(result["promotion_authority"])
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})
        self.assertEqual(self.requests["coder_a"]["context"], self.requests["coder_b"]["context"])
        self.assertEqual(self.requests["coder_a"]["context"][0]["artifact_ref"], self.source_ref)
        self.assertNotIn("holdout_ids", self.requests["coder_a"])
        self.assertNotIn("holdout_ids", self.requests["coder_b"])
        self.assertEqual(self.requests["evaluator"]["specification"]["holdout_ids"], self.spec["holdout_ids"])
        self.assertEqual(len(self.requests["coder_a"]["idempotency_key"]), 64)

    def test_completed_run_resumes_without_any_adapter_calls(self):
        first = self.run_workflow()
        fresh = DualCoderWorkflow(MerlinRegistry(self.root))
        second = fresh.run("one", specification=self.spec, providers=self.providers)
        self.assertEqual(first, second)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})
        self.assertEqual(fresh.status("one")["status"], "completed_research_only")

    def test_partial_resume_does_not_repeat_first_coder(self):
        blocked = self.run_workflow(coder_b=None)
        self.assertEqual(blocked["status"], "blocked_missing_adapter")
        self.assertEqual(blocked["stage"], "coder_b")
        self.assertEqual(self.workflow.status("one")["next_stage"], "coder_b")
        completed = self.run_workflow(coder_a=None)
        self.assertEqual(completed["status"], "completed_research_only")
        self.assertEqual(self.calls["coder_a"], 1)

    def test_missing_first_adapter_records_spec_but_no_intent(self):
        blocked = self.run_workflow(coder_a=None)
        self.assertEqual(blocked["status"], "blocked_missing_adapter")
        self.assertEqual(self.calls, {"coder_a": 0, "coder_b": 0, "evaluator": 0})
        status = self.workflow.status("one")
        self.assertEqual(status["stages"]["coder_a"], "not_started")
        self.assertEqual(self.workflow.status("new")["status"], "not_started")

    def test_callback_failure_never_automatically_repeats(self):
        invocations = []
        def failing(request):
            invocations.append(request["idempotency_key"])
            raise RuntimeError("private data must not be logged")
        first = self.run_workflow(coder_a=failing)
        self.assertEqual(first["status"], "reconciliation_required")
        self.assertFalse(first["automatic_retry"])
        second = self.run_workflow(coder_a=failing)
        self.assertEqual(second["status"], "reconciliation_required")
        self.assertEqual(len(invocations), 1)
        files = self.registry.inventory("dot-ai-os")["artifacts"]
        for entry in files:
            if entry["logical_path"].endswith("failure.json"):
                ref = self.registry.artifact_ref("dot-ai-os", entry["logical_path"])
                raw = self.registry.read_artifact_ref(ref)["content"]
                self.assertNotIn(b"private data", raw)

    def test_crash_after_intent_requires_reconciliation(self):
        def crash(_):
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_workflow(coder_a=crash)
        result = self.run_workflow()
        self.assertEqual(result["status"], "reconciliation_required")
        self.assertEqual(self.calls["coder_a"], 0)

    def test_changed_specification_and_provider_are_conflicts(self):
        self.run_workflow(coder_a=None)
        changed = deepcopy(self.spec)
        changed["objective"] = "a different objective"
        with self.assertRaises(WorkflowConflict):
            self.run_workflow(specification=changed)
        providers = deepcopy(self.providers)
        providers["coder_a"]["prompt_sha256"] = "e" * 64
        with self.assertRaises(WorkflowConflict):
            self.run_workflow(providers=providers)

    def test_source_versions_are_pinned_even_after_latest_advances(self):
        self.run_workflow(coder_b=None)
        self.registry.put_artifact("dot-ai-os", "context/parent.txt", b"Changed latest source")
        result = self.run_workflow()
        self.assertEqual(result["status"], "completed_research_only")
        self.assertEqual(self.requests["coder_b"]["context"][0]["text"],
                         "Parent skill: retain exact source citations.")

    def test_train_holdout_overlap_and_paid_budget_rejected_before_callbacks(self):
        for field, value in (("holdout_ids", ["train-1"]), ("max_cost_usd", 1), ("max_cost_usd", False)):
            changed = deepcopy(self.spec)
            changed[field] = value
            with self.assertRaises(ValueError):
                self.run_workflow(specification=changed)
        self.assertEqual(self.calls["coder_a"], 0)

    def test_coder_output_cannot_supply_authority_or_provider_identity(self):
        result = self.run_workflow(coder_a=lambda _: {
            "candidate": "code", "rationale": "text", "qualification": True})
        self.assertEqual(result["status"], "reconciliation_required")
        self.assertFalse(result["qualification"])

    def test_evaluator_counts_are_bounded_and_not_booleans(self):
        def bad_eval(request):
            value = self.evaluator(request)
            value["coder_b"]["holdout_passed"] = True
            return value
        result = self.run_workflow(evaluator=bad_eval)
        self.assertEqual(result["status"], "reconciliation_required")
        self.assertEqual(result["stage"], "evaluator")

    def test_no_better_candidate_retains_parent(self):
        def evaluation(_):
            counts = {"train_passed": 2, "holdout_passed": 2, "regressions": 0}
            return {"baseline": counts, "coder_a": counts, "coder_b": counts,
                    "notes": "No improvement observed"}
        result = self.run_workflow(evaluator=evaluation)
        self.assertEqual(result["recommendation"], "retain_parent")

    def test_training_only_gain_does_not_recommend_successor(self):
        def evaluation(_):
            return {"baseline": {"train_passed": 1, "holdout_passed": 1, "regressions": 0},
                    "coder_a": {"train_passed": 2, "holdout_passed": 1, "regressions": 0},
                    "coder_b": {"train_passed": 2, "holdout_passed": 1, "regressions": 0},
                    "notes": "Only training improved; no measured transfer gain"}
        self.assertEqual(self.run_workflow(evaluator=evaluation)["recommendation"], "retain_parent")

    def test_recursive_dispatch_is_blocked_by_cooperative_lock(self):
        def nested(request):
            with self.assertRaises(WorkflowConflict):
                self.run_workflow()
            return self.coder_a(request)
        result = self.run_workflow(coder_a=nested)
        self.assertEqual(result["status"], "completed_research_only")
        self.assertEqual(self.calls["coder_a"], 1)

    def test_changed_checkpoint_version_fails_instead_of_silent_reuse(self):
        self.run_workflow(coder_a=None)
        self.registry.put_artifact("dot-ai-os", "dual-coder/one/spec.json", canonical({"changed": True}))
        with self.assertRaises(WorkflowConflict):
            self.run_workflow()

    def test_status_rejects_result_without_matching_invocation_intent(self):
        self.run_workflow(coder_a=None)
        self.registry.put_artifact("dot-ai-os", "dual-coder/one/stages/coder_a/result.json", canonical({
            "schema": "dot-dual-coder-result/1", "intent_ref": self.source_ref,
            "payload": {"candidate": "fake", "rationale": "fake"},
            "qualification": True, "promotion_authority": True}))
        with self.assertRaises(WorkflowConflict):
            self.workflow.status("one")

    def test_candidate_recommendation_never_adds_claim_or_receipt(self):
        self.run_workflow()
        with sqlite3.connect(self.registry.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM capability_qualification_receipts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
