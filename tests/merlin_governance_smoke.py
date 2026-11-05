#!/usr/bin/env python3
import importlib.util, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def load(name):
 p=root/"scripts"/name; spec=importlib.util.spec_from_file_location(name,p); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
policy=json.loads((root/"research/science/merlin-research-governance.v1.json").read_text())
assert "engineering_plan_before_creation" in policy["non_bypassable_gates"]
assert "confirmation_bias" in policy["bias_and_fallacy_review"]["cognitive_biases"]
assert "affirming_the_consequent" in policy["bias_and_fallacy_review"]["logical_fallacies"]
plan=load("merlin_engineering_plan.py")
sample=plan.template("smoke")
sample["objective"]="Verify the plan gate"\nsample["requirements"][0]["statement"]="The plan validator accepts a complete plan"\nsample["requirements"][0]["acceptance"]="The fixture returns no validation errors"
sample["domain_scope"]["primary_domain"]="computer-information"
sample["design"]["method"]="contract test"
sample["design"]["limitations"]="smoke-test only"
assert plan.validate(sample)==[]
bad=plan.template("bad"); bad["reasoning_plan"].pop("inductive")
assert any("inductive" in x for x in plan.validate(bad))
audit=load("merlin_domain_audit.py")
tax=json.loads((root/"research/science/discipline-taxonomy.v1.json").read_text())
result=audit.audit(tax,{"known_cross_domain_labels":["neuroscience","systems biology","geochemistry","logic"]})
assert result["domain_count"]>=10 and result["ok"]
storage=load("merlin_storage_guard.py")
r=storage.check(root/"state"/"merlin-storage-smoke",10**9,1000,0)
assert r["ok"]
yt=load("merlin_youtube_discover.py")
try: yt.validate_transcript(Path("x.vtt"),"unknown")
except ValueError: pass
else: raise AssertionError("unlicensed transcript accepted")
print("Merlin governance, plan gate, domain audit, storage guard and YouTube contract smoke passed.")
