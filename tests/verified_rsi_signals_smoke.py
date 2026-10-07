#!/usr/bin/env python3
"""Read-only RSI evidence signals: one source is never an improvement claim."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "rsi_signals",ROOT/"scripts"/"collect_verified_rsi_signals.py"
)
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

cases={
"cace_bridge":{
    "cace_source_commit":"12345",
    "summary":{
       "residual_inf":8e-16,"mesh_elements":190,
       "convergence_history":{"records":[
           {"level":0,"h_max":0.75},{"level":1,"h_max":0.375}
       ]}
    }
},
"modeler":{
  "truss_solved_count":2,
  "truss_rejected":[{"candidate_id":"r","rejection_reason":"singular"}],
  "ranked_truss_results":[
    {"passes_declared_truss_limits":True,"compliance_j":0.004,
     "max_abs_axial_stress_pa":1e6},
    {"passes_declared_truss_limits":False,"compliance_j":0.003,
     "max_abs_axial_stress_pa":2e8}
  ]
},
"quantum":{
  "scf_results":[
    {"basis":"sto-3g","converged":True,
     "total_electronic_energy_hartree":-74.9},
    {"basis":"6-31g","converged":True,
     "total_electronic_energy_hartree":-75.9}
  ],
  "serial_replay":{"passed":True}
},
"browser":{
  "pages":[{"screenshot_sha256":"a"*64,
            "page_content_authority":"untrusted_evidence_only"}]
}
}
for kind,payload in cases.items():
    result=mod.collect(kind,payload)
    assert result["measured_capability_delta"] is None
    assert result["independent_holdout_verified"] is False
    assert result["candidate_qualifies_for_promotion"] is False
    assert result["has_matched_parent_child_baseline"] is False
    assert len(result["source_artifact_sha256"])==64
    assert len(result["route_ids"])>=1
    assert mod.collect(kind,payload)==result

assert mod.collect("cace_bridge",cases["cace_bridge"])["observed_signals"][
    "observed_mesh_levels"
]==2
assert mod.collect("modeler",cases["modeler"])["observed_signals"][
    "qualified_candidates"
]==1
assert mod.collect("quantum",cases["quantum"])["observed_signals"][
    "basis_jobs"
]==2
assert mod.collect("browser",cases["browser"])["observed_signals"][
    "vision_model_interpretation_verified"
] is False

def rejected(kind,payload):
    try:
        mod.collect(kind,payload)
    except (ValueError,TypeError,KeyError):
        return
    raise AssertionError("invalid evidence accepted")

rejected("cace_bridge",{"summary":{"residual_inf":float("nan")}})
rejected("quantum",{"scf_results":[{"converged":True,
    "total_electronic_energy_hartree":float("inf")}]})
rejected("browser",{"pages":"not-a-list"})
rejected("unregistered",{})

print("CACE cross-domain RSI read-only signals: PASS")
