#!/usr/bin/env python3
"""Offline validation frontier: mutations and negative controls must fail closed."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/(name+".py"))
    x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)
    return x
def must_reject(fn):
    try:fn()
    except (ValueError,AssertionError,OSError):return
    raise AssertionError("negative control was accepted")

def main():
    net=load("experiment_general_reaction_conservation")
    a=net.experiment()
    assert [x["left_nullity"] for x in a["cases"]]==[2,1,2,1]
    assert a["missing_reactant_mass_defect"]=="1/3"
    assert all(len(x["invariants"])==x["left_nullity"] for x in a["cases"])
    must_reject(lambda:net.left_nullspace([[1,2],[0]],2))
    must_reject(lambda:net.require_amount_units(["amount_mol","mol/L"]))

    bio=load("triage_biomodels_consistency")
    sample={"repo":bio.REPO,"commit":bio.COMMIT,"sbml_git_blob":bio.BLOB,
      "libsbml_severe_issues":3,
      "libsbml_issue_counts_by_id":{"10541":3,"100":37},
      "first_serious_validation_findings":[{"id":10541,"severity":2,
        "line":100+j,"column":1,"message":"kinetic-law units"} for j in range(3)]}
    b=bio.triage(sample)
    assert b["quarantined"] and b["dimension_mismatch_10541_count"]==3
    assert len(b["known_issue_examples"])==3 and not b["promotion_authorized"]
    must_reject(lambda:bio.triage({**sample,"sbml_git_blob":"tampered"}))
    must_reject(lambda:bio.triage({**sample,"first_serious_validation_findings":[]}))
    must_reject(lambda:bio.triage({**sample,"libsbml_severe_issues":2}))

    lean=load("audit_openai_lean_receipt")
    theorem="OAI.Graph.A"
    transcript=theorem+" : Nat\n'"+theorem+"' depends on axioms: [propext, Classical.choice]\n"
    assert lean.audit_transcript(transcript,theorem)==["Classical.choice","propext"]
    assert lean.audit_transcript(theorem+" : Nat\n'"+theorem+
        "' does not depend on any axioms\n",theorem)==[]
    must_reject(lambda:lean.audit_transcript(transcript.replace("propext","sorryAx"),theorem))
    must_reject(lambda:lean.audit_transcript(transcript.replace("propext","Mystery.foo"),theorem))
    must_reject(lambda:lean.audit_transcript(transcript.replace(theorem+" : Nat","B : Nat"),theorem))
    with TemporaryDirectory() as temp:
        root=Path(temp)
        (root/"lean-toolchain").write_text(lean.TOOLCHAIN)
        (root/"lake-manifest.json").write_text(lean.MATHLIB)
        (root/"OAI"/"Graph").mkdir(parents=True)
        (root/"OAI"/"Graph"/"A.lean").write_text("theorem A : True := trivial")
        good=lean.make_receipt(root,"OAI.Graph.A",theorem,transcript,
                                "success","1234","a"*40)
        assert good["kernel_step_reported_success"] and not good["promotion_authorized"]
        must_reject(lambda:lean.make_receipt(root,"OAI.Graph.A",theorem,transcript,
                                              "failure","1234","a"*40))
        must_reject(lambda:lean.make_receipt(root,"OAI.Graph.A",theorem,transcript,
                                              "success","1234","broken"))

    cace=load("qualify_cace_holdout_evidence")
    h="a"*64
    cases=[{"id":str(j),"baseline_input_sha256":h,"candidate_input_sha256":h,
            "independent_residual_check":True,"baseline_seconds":1.,
            "candidate_seconds":0.8,"maximum_allowed_residual":1e-6,
            "baseline_residual":1e-10,"candidate_residual":2e-10}
            for j in range(3)]
    base={"schema_version":1,"kind":"cace-matched-benchmark-v1",
          "sealed_before_candidate":True,"case_manifest_sha256":h,"cases":cases}
    qualified=cace.screen(base)
    assert qualified["candidate_meets_screen"] and not qualified["promotion_authorized"]
    must_reject(lambda:cace.screen({**base,"sealed_before_candidate":False}))
    wrong=[dict(x) for x in cases];wrong[0]["candidate_input_sha256"]="b"*64
    must_reject(lambda:cace.screen({**base,"cases":wrong}))
    wrong=[dict(x) for x in cases];wrong[0]["candidate_residual"]=1e-4
    assert not cace.screen({**base,"cases":wrong})["candidate_meets_screen"]
    wrong=[dict(x) for x in cases];wrong[0]["candidate_seconds"]=2.
    wrong[1]["candidate_seconds"]=2.
    assert not cace.screen({**base,"cases":wrong})["candidate_meets_screen"]
    print(json.dumps({"result":"PASS","exact_networks":4,
        "published_model_quarantined":True,"kernel_attestation_mock_only":True,
        "real_lean_checker_executed":False,"real_cace_benchmark_executed":False,
        "promotion_authorized":False}))

if __name__=="__main__":main()
