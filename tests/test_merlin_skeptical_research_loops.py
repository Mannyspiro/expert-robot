"""Negative and positive research-loop, scientific-policy and host prompt checks."""
from __future__ import annotations
import copy
import hashlib
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "portable" / "merlin_studio"))
from merlin.bounded_research_loop import Question, ResearchSubloops
from merlin.skeptical_scientist_policy import SCIENTIFIC_POLICY, SCIENTIFIC_POLICY_VERSION
from science_policy import SCIENTIFIC_POLICY as PORTABLE_POLICY
from engine import SYSTEM
from merlin.prompt_contract import PromptCompiler, PromptTask

def task(name, **kwargs):
    return Question(name, "bounded hypothesis", "recorded baseline", "discriminating falsifier",
                    "independent validator", **kwargs)

def measured(t):
    return {"observation":{"source":"simulated","value":1,"units":"arbitrary"},
            "children":[]}

def checked(_t, observation):
    return {"accepted":observation["value"]==1,"checker":"independent_fixture",
            "reason":"matched synthetic reference value; not a formal proof"}

class ResearchSubloopTests(unittest.TestCase):
    def test_budget_and_no_auto_execution(self):
        x=ResearchSubloops(max_steps=1)
        x.add(task("root"))
        x.add(task("another"))
        self.assertEqual(x.step(measured,checked)["status"],"checked")
        self.assertIsNone(x.step(measured,checked))
        self.assertEqual(x.summary()["status"],"paused_budget")
        self.assertFalse(x.summary()["background_worker_running"])
        self.assertFalse(x.summary()["proof_of_novelty"])

    def test_nested_verified_subquestions_with_exact_parent(self):
        x=ResearchSubloops(max_steps=3,max_depth=1)
        x.add(task("root"))
        child={"task_id":"child","hypothesis":"nested","baseline":"baseline",
               "falsifier":"falsifier","independent_check":"independent check"}
        first=x.step(lambda _:{"observation":{"value":1},"children":[child]},checked)
        self.assertEqual(first["children_admitted"],["child"])
        second=x.step(measured,checked)
        self.assertEqual(second["parent_id"],"root")
        self.assertEqual(x.summary()["status"],"ended_with_unverified_claims")
        self.assertFalse(second["novelty_proven"])

    def test_rejected_result_never_spawns_subtasks(self):
        x=ResearchSubloops()
        x.add(task("root"))
        child={"task_id":"child","hypothesis":"a","baseline":"b",
               "falsifier":"c","independent_check":"d"}
        result=x.step(lambda _:{"observation":{"value":1},"children":[child]},
                      lambda _t,_o:{"accepted":False,"checker":"fixture","reason":"counterexample"})
        self.assertEqual(result["status"],"rejected")
        self.assertEqual(x.summary()["tasks"],1)

    def test_invalid_fanout_fails_closed(self):
        x=ResearchSubloops()
        x.add(task("root"))
        r=x.step(lambda _:{"observation":{"value":1},"children":[{}]*5},checked)
        self.assertEqual(r["status"],"error")
        self.assertEqual(r["children_admitted"],[])
        self.assertEqual(len(x.tasks),1)

    def test_checker_exception_preserved_not_evidence(self):
        x=ResearchSubloops()
        x.add(task("root"))
        def fail(_t,_o):raise RuntimeError("bad reference")
        r=x.step(measured,fail)
        self.assertEqual(r["status"],"error")
        self.assertEqual(r["error_type"],"RuntimeError")
        self.assertNotIn("verification",r)

    def test_duplicate_ids_and_invalid_depth_rejected(self):
        x=ResearchSubloops(max_depth=1)
        x.add(task("root"))
        with self.assertRaises(ValueError): x.add(task("root"))
        with self.assertRaises(ValueError): x.add(task("child",parent_id="missing",depth=1))
        with self.assertRaises(ValueError): x.add(task("bad",depth=1))
        with self.assertRaises(ValueError): ResearchSubloops(max_steps=True)

    def test_resume_preserves_checked_history(self):
        x=ResearchSubloops(max_steps=4)
        x.add(task("root"))
        x.step(measured,checked)
        snapshot=x.snapshot()
        y=ResearchSubloops.restore(snapshot)
        self.assertEqual(y.snapshot(),snapshot)
        self.assertEqual(y.summary()["steps_used"],1)
        self.assertIsNone(y.step(measured,checked))

    def test_tampered_checkpoint_rejected_even_after_digest_changes(self):
        x=ResearchSubloops()
        x.add(task("root"))
        x.step(measured,checked)
        s=x.snapshot()
        broken=copy.deepcopy(s)
        broken["receipts"][0]["status"]="checked_by_magic"
        with self.assertRaises(ValueError): ResearchSubloops.restore(broken)
        duplicated=copy.deepcopy(s)
        duplicated["queue"]=["root"]
        from merlin.bounded_research_loop import _hash
        duplicated["sha256"]=_hash({k:v for k,v in duplicated.items() if k!="sha256"})
        with self.assertRaises(ValueError): ResearchSubloops.restore(duplicated)

    def test_policy_same_for_engine_and_core(self):
        self.assertEqual(SCIENTIFIC_POLICY,PORTABLE_POLICY)
        self.assertIn("paradoxes",SYSTEM.lower())
        self.assertIn("simulated physics",SYSTEM.lower())
        self.assertEqual(SCIENTIFIC_POLICY_VERSION,"merlin-skeptical-scientist/1")

    def test_worker_compiler_always_includes_policy_no_authority_expansion(self):
        job=PromptTask(task_id="research-test",recipient="local.math",
                       objective="Measure simulated recurrence cost",context="fixture",
                       input_refs=("ref:local",),required_outputs=("receipt",),
                       constraints=("offline",),acceptance_criteria=("bounded",),
                       evidence_requirements=("independent fixture",),
                       tool_allowlist=(),resource_limits={
                           "cpu_cores":1,"memory_bytes":1048576,
                           "max_wall_seconds":30,"compute_budget_units":1})
        result=PromptCompiler().compile(job)
        self.assertIn(SCIENTIFIC_POLICY,result.prompt_text)
        self.assertIn("Authority scope: draft_only",result.prompt_text)
        self.assertIn("No tools authorized",result.prompt_text)

    def test_portable_package_includes_mandatory_policy(self):
        import importlib.util
        path=ROOT / "portable" / "build_portable.py"
        spec=importlib.util.spec_from_file_location("portable_science_test",path)
        module=importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        payload,_=module.collect_sources()
        self.assertIn("science_policy.py",payload)
        self.assertIn("core/python/merlin/skeptical_scientist_policy.py",payload)
        self.assertEqual(payload["science_policy.py"],
                         payload["core/python/merlin/skeptical_scientist_policy.py"])

if __name__=="__main__":
    unittest.main()
