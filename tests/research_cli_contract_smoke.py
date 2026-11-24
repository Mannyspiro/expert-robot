#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, tempfile, sys

ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/"cpp/src/research_cli_main.cpp").read_text()
cmake=(ROOT/"CMakeLists.txt").read_text()
runtime=(ROOT/"cpp/src/runtime.cpp").read_text()

for needle in (
    "LlamaServerProcess",
    "LlamaCliBackend",
    "LeanSubprocessRunner",
    "MathResearchService",
    "ModelFormalizationProposer",
    "formalization_proposal.schema.json",
    "lemma_decomposition.schema.json",
    "--model",
    "--claim",
    "--plan",
    "validate_merlin_plan",
    "merlin_engineering_plan.py",
    "Merlin plan validation failed",
):
    assert needle in src, needle

assert "add_executable(expert_robot_research" in cmake
assert "model backend not connected yet" not in runtime
assert "use expert_robot_research" in runtime

binary=ROOT/"build"/"expert_robot_research"
assert binary.exists(), "research CLI binary missing"
with tempfile.TemporaryDirectory() as td:
    tmp=Path(td)
    invalid=tmp/"invalid-plan.json"; invalid.write_text("{}")
    blocked=subprocess.run([str(binary),"--model",str(tmp/"missing.gguf"),"--claim","test claim","--plan",str(invalid),"--repo-root",str(ROOT)],capture_output=True,text=True)
    assert blocked.returncode==2 and "Merlin plan validation failed" in blocked.stderr, blocked.stderr
    sys.path.insert(0,str(ROOT/"scripts"))
    from merlin_engineering_plan import template
    plan=template("cpp-dispatch-smoke")
    plan["objective"]="Test direct C++ dispatch gate"
    plan["domain_scope"]["primary_domain"]="computer-information"
    plan["requirements"][0].update(statement="A valid plan passes the gate",acceptance="CLI reaches model-file validation.")
    plan["design"]["method"]="Direct CLI contract test"
    plan["design"]["limitations"]="No model execution is attempted."
    rp=plan["problem_representation"]
    rp["original_problem"]="Test direct dispatch"
    rp["decomposition"]["subproblems"][0].update(objective="Prepare claim",interface="Claim input",acceptance="Claim specified")
    rp["decomposition"]["subproblems"][1].update(objective="Validate plan",interface="Plan",acceptance="Plan accepted")
    rp["representations"][0].update(encoding="Claim text",mapping="Identity",preserved_invariants=["claim"],lost_information=[],validity_conditions=["same claim"],validation_method="Compare exact text")
    rp["representations"][1].update(encoding="Typed plan graph",mapping="Sections and dependencies form typed nodes and edges",preserved_invariants=["requirements","dependencies"],lost_information=["prose ordering"],validity_conditions=["links explicit"],validation_method="Check schema and links")
    valid=tmp/"valid-plan.json"; valid.write_text(json.dumps(plan))
    passed=subprocess.run([str(binary),"--model",str(tmp/"missing.gguf"),"--claim","test claim","--plan",str(valid),"--repo-root",str(ROOT)],capture_output=True,text=True)
    assert passed.returncode==2 and "model file does not exist" in passed.stderr, passed.stderr
print("research CLI plan-gate and contract smoke: PASS")
