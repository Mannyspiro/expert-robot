"""Reconciles real observed ARM64 token/latency metrics without false speedup."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.context_pilot_review import inspect_context_receipt


def observed_fixture():
    full=[(659,3125,58.887),(658,3126,1.391),
          (664,3161,1.833),(658,3132,1.516)]
    selected=[(103,340,2.156),(99,345,3.91),
              (104,393,3.924),(100,358,3.957)]
    cases=[]
    for index,((ft,fb,fl),(st,sb,sl)) in enumerate(zip(full,selected)):
        cases.append({
            "id":"ctx.case."+str(index+1),
            "source_id":"source_"+str(index+1),
            "source_sha256":"a"*64,
            "full":{"correct":True,"answer_sha256":"b"*64,
                    "latency_seconds":fl,"prompt_bytes":fb,
                    "prompt_sha256":"c"*64,"prompt_tokens":ft},
            "selected":{"correct":True,"answer_sha256":"b"*64,
                        "latency_seconds":sl,"prompt_bytes":sb,
                        "prompt_sha256":"d"*64,"prompt_tokens":st},
        })
    return {
        "schema":"merlin-private-context-ablation/1",
        "status":"observed",
        "task_count":4,"model_calls":8,
        "source_selection":"frozen-tag-lookup-not-canonical-registry-router",
        "cases":cases,
        "full_correct":4,"selected_correct":4,
        "regressed_count":0,"improved_count":0,
        "full_prompt_tokens":2639,"selected_prompt_tokens":406,
        "full_prompt_bytes":12544,"selected_prompt_bytes":1436,
        "full_wall_seconds":63.627,"selected_wall_seconds":13.947,
        "prompt_token_savings_fraction":0.84615,
        "pilot_gate_met":True,
        "production_qualified":False,
        "model_weights_updated":False,
        "model_quality_improvement_established":False,
        "registry_router_integration_tested":False,
    }


class ContextPilotReviewTests(unittest.TestCase):
    def test_actual_case_metrics_reconcile_with_no_broad_speedup_claim(self):
        report=inspect_context_receipt(observed_fixture())
        self.assertEqual(report["verified_full_correct"],4)
        self.assertEqual(report["verified_selected_correct"],4)
        self.assertEqual(report["verified_prompt_token_savings_fraction"],.84615)
        self.assertTrue(report["token_measurements_reconciled"])
        self.assertTrue(report["large_first_full_request_latency_outlier"])
        self.assertEqual(report["median_later_full_latency_seconds"],1.516)
        self.assertEqual(report["median_selected_latency_seconds"],3.917)
        self.assertTrue(report["pilot_results_eligible_for_further_evaluation"])
        self.assertFalse(report["latency_speedup_generalization_qualified"])
        self.assertFalse(report["source_selector_is_production_registry"])
        self.assertFalse(report["run_or_weight_identity_independently_attested"])
        self.assertFalse(report["production_qualified"])

    def test_tampered_aggregate_token_claim_fails(self):
        for key,value in (("selected_prompt_tokens",40),
                          ("full_prompt_tokens",500),
                          ("prompt_token_savings_fraction",.95),
                          ("full_wall_seconds",.1),
                          ("task_count",5),
                          ("pilot_gate_met",False)):
            with self.subTest(field=key):
                fixture=observed_fixture()
                fixture[key]=value
                with self.assertRaises(ValueError):
                    inspect_context_receipt(fixture)

    def test_wrong_answer_cannot_be_hidden_by_large_token_savings(self):
        fixture=observed_fixture()
        fixture["cases"][0]["selected"]["correct"]=False
        with self.assertRaises(ValueError):
            inspect_context_receipt(fixture)
        fixture["selected_correct"]=3
        fixture["regressed_count"]=1
        fixture["pilot_gate_met"]=False
        result=inspect_context_receipt(fixture)
        self.assertFalse(result["paired_correctness_preserved"])
        self.assertFalse(result["pilot_results_eligible_for_further_evaluation"])
        self.assertFalse(result["production_qualified"])

    def test_blocked_or_promoted_or_unmeasured_receipts_fail(self):
        for key,value in (("status","blocked"),
                          ("production_qualified",True),
                          ("model_weights_updated",True),
                          ("registry_router_integration_tested",True)):
            with self.subTest(field=key):
                fixture=observed_fixture()
                fixture[key]=value
                with self.assertRaises(ValueError):
                    inspect_context_receipt(fixture)
        fixture=observed_fixture()
        fixture["cases"][0]["selected"]["prompt_tokens"]=None
        with self.assertRaises(ValueError):
            inspect_context_receipt(fixture)

    def test_malformed_case_digests_latency_and_ids_fail(self):
        for key,value in (("source_sha256","wrong"),
                          ("source_id",""),
                          ("id","ctx.case.2")):
            fixture=observed_fixture()
            fixture["cases"][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                inspect_context_receipt(fixture)
        for key,value in (("latency_seconds",-1),
                          ("correct",1),
                          ("prompt_bytes",20000),
                          ("answer_sha256","xyz")):
            fixture=observed_fixture()
            fixture["cases"][0]["full"][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                inspect_context_receipt(fixture)


if __name__=="__main__":
    unittest.main(verbosity=2)
