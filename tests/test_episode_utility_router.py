"""MemRL-inspired two-stage selection, with no authority or weight update."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.project_registry import MerlinRegistry
from merlin.episode_utility_router import SCHEMA, OUTPUT_SCHEMA, shortlist


class EpisodeUtilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry=MerlinRegistry(Path(self.temp.name)/"registry")
        self.registry.register_project("research", "Research-only episode router")
        self.refs=[]

    def authorize(self,role,ref):
        return (role=="episode_source"
                and ref.get("project_id")=="research"
                and ref.get("logical_path","").startswith("research/episodes/"))

    def episode(self,identity,strategy,tags,outcome):
        path="research/episodes/"+identity+".json"
        body={"schema":SCHEMA,"strategy_id":strategy,"tags":tags,
              "outcome":outcome,"feedback_class":"unverified_observed"}
        content=(json.dumps(body,sort_keys=True,separators=(",",":"))+"\n").encode()
        self.registry.put_artifact("research",path,content,"application/json")
        ref=self.registry.artifact_ref("research",path)
        self.refs.append(ref)
        return ref

    def test_two_stage_selects_matching_strategy_and_tracks_outcomes(self):
        for idx,outcome in enumerate(("success","success","success","failure")):
            self.episode("deep."+str(idx),"source_recovery",
                         ["restart","evidence"],outcome)
        for idx,outcome in enumerate(("failure","failure")):
            self.episode("bad."+str(idx),"blind_retry",
                         ["restart"],outcome)
        self.episode("unrelated","design_clothes",["image"],"success")
        result=shortlist(self.registry,project_id="research",
                         query_tags=["restart"],episode_refs=self.refs,authorize=self.authorize)
        self.assertEqual(result["schema"],OUTPUT_SCHEMA)
        self.assertEqual(result["episode_refs_examined"],7)
        self.assertEqual(result["episode_refs_matching_query"],6)
        self.assertEqual(result["selected_strategy_ids"],
                         ["source_recovery","blind_retry"])
        chosen=result["selected_strategies"][0]
        self.assertEqual(chosen["feedback_count"],4)
        self.assertEqual(chosen["success_count"],3)
        self.assertEqual(chosen["failure_count"],1)
        self.assertFalse(result["utility_is_calibrated_probability"])
        self.assertFalse(result["model_weights_updated"])
        self.assertFalse(result["strategies_executed"])
        self.assertFalse(result["promotion_authority"])
        self.assertEqual(len(chosen["episode_refs"]),4)

    def test_result_cap_omits_without_impersonating_unexamined_cases(self):
        for idx,name in enumerate(("method_a","method_b","method_c")):
            self.episode("case."+str(idx),name,["mathematics"],"success")
        result=shortlist(self.registry,project_id="research",
                         query_tags=["mathematics"],episode_refs=self.refs,
                         max_strategies=1,authorize=self.authorize)
        self.assertEqual(result["strategies_matching_query"],3)
        self.assertEqual(result["omitted_strategy_count"],2)
        self.assertEqual(result["episode_refs_examined"],3)
        self.assertEqual(result["selected_strategy_ids"],["method_a"])

    def test_duplicate_tampered_and_cross_project_refs_fail(self):
        ref=self.episode("one","method_a",["restart"],"success")
        with self.assertRaises(ValueError):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=[ref,ref],authorize=self.authorize)
        wrong={**ref,"sha256":"0"*64}
        with self.assertRaises((ValueError,RuntimeError)):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=[wrong],authorize=self.authorize)
        with self.assertRaises(PermissionError):
            shortlist(self.registry,project_id="different",
                      query_tags=["restart"],episode_refs=[ref],authorize=self.authorize)

    def test_host_authorization_deny_even_late_source_before_read(self):
        self.episode("one","method_a",["restart"],"success")
        self.episode("two","method_a",["restart"],"failure")
        with patch.object(self.registry,"read_artifact_ref",
                          wraps=self.registry.read_artifact_ref) as read:
            with self.assertRaises(PermissionError):
                shortlist(self.registry,project_id="research",
                          query_tags=["restart"],episode_refs=self.refs,
                          authorize=lambda role,ref: ref["logical_path"].endswith("one.json"))
            read.assert_not_called()
        with self.assertRaises(PermissionError):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=self.refs,
                      authorize=lambda role,ref:1)
        with self.assertRaises(ValueError):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=self.refs,authorize=None)

    def test_reject_unsupported_feedback_claims_and_bad_input(self):
        path="research/episodes/fake.json"
        payload={"schema":SCHEMA,"strategy_id":"method_a","tags":["restart"],
                 "outcome":"success","feedback_class":"independently_verified"}
        self.registry.put_artifact("research",path,
            (json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n").encode(),
            "application/json")
        ref=self.registry.artifact_ref("research",path)
        with self.assertRaises(ValueError):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=[ref],authorize=self.authorize)
        with self.assertRaises(ValueError):
            shortlist(self.registry,project_id="research",
                      query_tags=["restart"],episode_refs=[],authorize=self.authorize)
        with self.assertRaises(ValueError):
            shortlist(self.registry,project_id="research",
                      query_tags=["bad tag!"],episode_refs=[ref],authorize=self.authorize)


if __name__=="__main__":
    unittest.main(verbosity=2)
