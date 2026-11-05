#!/usr/bin/env python3
import importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("reframe",root/"scripts/merlin_problem_reframing.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
x=m.template("smoke")
x["original_problem"]="Solve a coupled nonlinear system"
x["decomposition"]["subproblems"][0].update(objective="Identify variables and constraints",interface="Variable/constraint set",acceptance="All variables enumerated")
x["decomposition"]["subproblems"][1].update(objective="Solve reduced system",interface="Reduced equations",acceptance="Residual meets tolerance")
x["representations"][0].update(encoding="F(x)=0",mapping="Identity mapping",preserved_invariants=["solution set"],lost_information=[],validity_conditions=["same domain"],validation_method="Substitute solutions")
x["representations"][1].update(encoding="Constraint graph",mapping="Variables map to nodes; constraints to factors",preserved_invariants=["incidence structure"],lost_information=["coordinate order"],validity_conditions=["finite variable set"],validation_method="Compare graph constraints with equations")
assert m.validate(x)==[]
bad=m.template("bad"); bad["representations"][1]["relationship"]="structural_analogy"; bad["representations"][1].pop("non_transferable_properties")
assert any("non-transferable" in e for e in m.validate(bad))
bad2=m.template("bad2"); bad2["decomposition"]["subproblems"]=bad2["decomposition"]["subproblems"][:1]
assert any("at least two" in e for e in m.validate(bad2))
no_split=m.template("no-split"); no_split["decomposition"]={"needed":False,"not_needed_rationale":"Already atomic","subproblems":[]}
no_split["multiple_representations_useful"]=False
no_split["representations"]=no_split["representations"][:1]
no_split["representations"][0].update(encoding="x=1",mapping="Identity",preserved_invariants=["solution"],lost_information=[],validity_conditions=["over reals"],validation_method="Direct substitution")
assert m.validate(no_split)==[]
print("Merlin problem decomposition, representation mapping and reframe validation passed.")
