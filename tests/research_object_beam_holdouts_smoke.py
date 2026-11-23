#!/usr/bin/env python3
"""Fixed coverage, geometry validation, checksums and wrong-backend rejection."""
import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from run_beam_holdouts import run_holdouts
from evaluate_research_object_truss import solve_dense
from evaluate_research_object_beam import evaluate
from certify_beam_discrete import certify, replay_report
example = json.loads((ROOT/"config/examples/research_object_beam.json").read_text())
manifest = json.loads((ROOT/"config/examples/research_object_beam_holdouts.json").read_text())
certificates = []
def backend(a,b):
    u = solve_dense(a,b)[0]
    certificates.append(certify(a,b,u))
    return u
result = run_holdouts(example,manifest,backend)
assert result["passed"] and len(result["cases"]) == 6
assert len(certificates) == 18
assert not result["statistically_blind"] and not result["promotion_authority"]
assert all(c["passed"] and c["topology_sha256"] for c in result["cases"])
assert len(result["manifest_sha256"]) == 64
baseline = evaluate(example,backend)
assert baseline["passed"] and len(certificates) == 23
def checks(items):
    return [{"free_dofs":c["dofs"],"discrete_error_certificate":c} for c in items]
offset = 0
for case in result["cases"]:
    count = len(case["meshes"])
    case["cace_mesh_checks"] = checks(certificates[offset:offset+count])
    offset += count
saved = {"meshes":baseline["meshes"],"holdouts":result,"promotion_authority":False,
         "cace_algebraic":{"mesh_checks":checks(certificates[18:]),"continuum_error_certified":False,
                           "discrete_error_certificates_checked":23}}
assert replay_report(json.loads(json.dumps(saved))) == 23
bad_inventory = copy.deepcopy(saved)
bad_inventory["cace_algebraic"]["discrete_error_certificates_checked"] = 22
try:
    replay_report(bad_inventory)
except ValueError:
    pass
else:
    raise AssertionError("wrong replay inventory accepted")
for mutate in [lambda m:m["cases"].append(copy.deepcopy(m["cases"][0])),
               lambda m:m["cases"][0].update(meshes=[1,32]),
               lambda m:m["cases"][0].update(q_n_m=float('nan')),
               lambda m:m.update(material_provenance="")]:
    bad = copy.deepcopy(manifest)
    mutate(bad)
    try:
        run_holdouts(example,bad,backend)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid coverage manifest accepted")
try:
    run_holdouts(example,manifest,lambda a,b:[0.]*len(b))
except ValueError:
    pass
else:
    raise AssertionError("wrong backend accepted")
print("beam holdouts: six fixed cases, 18 solves, exact witnesses and negative checks passed")
