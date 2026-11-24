#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def load(name):
 p=root/"scripts"/name; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
policy=json.loads((root/"research/science/merlin-research-governance.v1.json").read_text())
assert "engineering_plan_before_creation" in policy["non_bypassable_gates"]
assert "problem_decomposition_and_reframing" in policy["non_bypassable_gates"]
assert "fuzzy_and_n_valued_logic_lens_review" in policy["non_bypassable_gates"]
assert "bounded_ideonomy_and_hypothesis_enumeration" in policy["non_bypassable_gates"]
assert "confirmation_bias" in policy["bias_and_fallacy_review"]["cognitive_biases"]
assert "affirming_the_consequent" in policy["bias_and_fallacy_review"]["logical_fallacies"]
assert policy["youtube_policy"]["cc_by_nc_sa_requires_explicit_noncommercial_use"] is True
plan=load("merlin_engineering_plan.py")
sample=plan.template("smoke")
sample["objective"]="Verify the plan gate"
sample["requirements"][0]["statement"]="The plan validator accepts a complete plan"
sample["requirements"][0]["acceptance"]="The fixture returns no validation errors"
sample["domain_scope"]["primary_domain"]="computer-information"
sample["design"]["method"]="contract test"
sample["design"]["limitations"]="smoke-test only"
sample["research_methods"]["applicable"]=True
sample["research_methods"]["ideonomy"]["enumeration_scope"]="domain x operation x relation"
sample["research_methods"]["logic_lenses"]["include_fuzzy"]=True
sample["research_methods"]["ranking_criteria"]=["semantic_fit","testability"]
sample["research_methods"]["hypothesis_disconfirmation"]="Construct a counterexample"
sample["problem_representation"]["original_problem"]="Test governance plan"
sample["problem_representation"]["decomposition"]["subproblems"][0].update(objective="Define the test",interface="Test input",acceptance="Input defined")
sample["problem_representation"]["decomposition"]["subproblems"][1].update(objective="Validate the test",interface="Validation output",acceptance="Output checked")
sample["problem_representation"]["representations"][0].update(encoding="Test plan",mapping="Identity",preserved_invariants=["requirements"],lost_information=[],validity_conditions=["same plan"],validation_method="Inspect requirements")
sample["problem_representation"]["representations"][1].update(encoding="Test dependency graph",mapping="Tasks to nodes and dependencies to edges",preserved_invariants=["dependency order"],lost_information=["narrative"],validity_conditions=["dependencies explicit"],validation_method="Check graph")
assert plan.validate(sample)==[]
bad=plan.template("bad"); bad["reasoning_plan"].pop("inductive")
assert any("inductive" in x for x in plan.validate(bad))
audit=load("merlin_domain_audit.py")
tax=json.loads((root/"research/science/discipline-taxonomy.v1.json").read_text())
result=audit.audit(tax,policy)
assert result["domain_count"]>=10 and result["ok"]
assert len(result["cross_domain_relationships"])==5
assert result["duplicate_primary_assignments"]==[]
storage=load("merlin_storage_guard.py")
r=storage.check(root/"state"/"merlin-storage-smoke",10**9,1000,0)
assert r["ok"]
projected=storage.check(root/"state"/"merlin-storage-projection-smoke",10,1000,0,additional_bytes=11,additional_files=1)
assert not projected["ok"] and any("byte quota" in e for e in projected["errors"])
yt=load("merlin_youtube_discover.py")
try: yt.validate_transcript(Path("x.vtt"),"unknown")
except ValueError: pass
else: raise AssertionError("unlicensed transcript accepted")
import tempfile
with tempfile.TemporaryDirectory() as td:
    vtt=Path(td)/"captions.vtt"
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nA short authorized caption.\n")
    try: yt.validate_transcript(vtt,"open_license_verified","CC-BY-NC-SA-4.0","unknown")
    except ValueError: pass
    else: raise AssertionError("NC-SA transcript accepted without noncommercial use context")
    licensed=yt.validate_transcript(vtt,"open_license_verified","CC-BY-NC-SA-4.0","noncommercial")
    assert licensed["license_id"]=="CC-BY-NC-SA-4.0"
video=json.loads((root/"research/science/video-transcript-index.v1.json").read_text())
assert len(video["items"])>=4
assert all(not x["media_downloaded"] for x in video["items"])
assert all(x["transcript_text_stored"] is False for x in video["items"] if x["provider"]=="MIT OpenCourseWare")
print("Merlin governance, plan gate, domain audit, storage guard and YouTube transcript rights smoke passed.")
