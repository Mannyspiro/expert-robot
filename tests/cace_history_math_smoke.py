#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

conv=load("conv",ROOT/"scripts"/"cace_history_to_math_dataset.py")
miner=load("miner",ROOT/"scripts"/"mine_experiment_math.py")

report={
    "experiment_id":"fixture",
    "summary":{
        "scope":"fixture",
        "convergence_history":{
            "records":[
                {"level":0,"h_max":1.0,"interior_dofs":4,"residual_inf":1e-14},
                {"level":1,"h_max":0.5,"interior_dofs":16,"residual_inf":1e-14},
                {"level":2,"h_max":0.25,"interior_dofs":64,"residual_inf":1e-14},
                {"level":3,"h_max":0.125,"interior_dofs":256,"residual_inf":1e-14}
            ]
        }
    }
}
dataset=conv.convert(report)
assert dataset["holdout_sealed"] is True
assert len(dataset["samples"])==4
mined=miner.mine(dataset)
by_id={x["candidate_id"].split("::")[-1]:x for x in mined["candidates"]}
rec=by_id["h-geometric-recurrence"]
assert rec["pattern_class"]=="recurrence"
assert rec["empirical_support"]["counterexamples_found"]==0
assert rec["empirical_support"]["fit_score"]>0.999999999
assert "q≈0.5" in rec["informal_statement"]
scale=by_id["dof-vs-h"]
assert scale["empirical_support"]["fit_score"]>0.999999999
assert "k≈-2" in scale["informal_statement"]

print("CACE history -> math discovery: PASS")
