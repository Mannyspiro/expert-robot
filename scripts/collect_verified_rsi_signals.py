#!/usr/bin/env python3
"""Extract non-authoritative RSI baseline signals from CACE/Expert Robot reports.

A raw observation is not a parent-child improvement. This adapter NEVER
fabricates deltas, attests external evidence or triggers automatic promotion.
Inputs may be attacker-controlled; numerical fields are tightly screened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ADAPTERS = {
    "cace_bridge": ("solver-sparse-operator", "geometry-adaptive-refinement"),
    "modeler": ("modeler-topology",),
    "quantum": ("quantum-basis-scheduler",),
    "browser": ("browser-visual-acquisition",),
}


def provenance(value):
    return hashlib.sha256(json.dumps(
        value,sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode("utf-8")).hexdigest()


def number(value, label, minimum=None):
    if isinstance(value,bool) or not isinstance(value,(float,int)):
        raise ValueError(f"{label}: finite number required")
    v=float(value)
    if not math.isfinite(v) or (minimum is not None and v<minimum):
        raise ValueError(f"{label}: invalid numeric value")
    return v


def collect(kind, payload):
    if kind not in ADAPTERS:
        raise ValueError("unknown evidence source type")
    if not isinstance(payload,dict):
        raise ValueError("report must be a JSON object")
    out={
        "schema_version":1,
        "input_type":kind,
        "source_artifact_sha256":provenance(payload),
        "route_ids":list(ADAPTERS[kind]),
        "has_matched_parent_child_baseline":False,
        "measured_capability_delta":None,
        "independent_holdout_verified":False,
        "candidate_qualifies_for_promotion":False,
        "epistemic_status":"observation_only_not_evidence_of_improvement",
    }
    signals={}
    if kind=="cace_bridge":
        summary=payload.get("summary")
        if not isinstance(summary,dict):
            raise ValueError("CACE bridge report summary required")
        signals["algebraic_residual_inf"]=number(
            summary["residual_inf"],"residual_inf",0
        )
        if "mesh_elements" in summary:
            signals["mesh_elements"]=int(number(
                summary["mesh_elements"],"mesh_elements",1
            ))
        history=summary.get("convergence_history",{})
        if isinstance(history,dict) and isinstance(history.get("records"),list):
            records=history["records"]
            signals["observed_mesh_levels"]=len(records)
            if records:
                values=[number(x["h_max"],"h_max",0) for x in records]
                signals["observed_h_max_initial"]=values[0]
                signals["observed_h_max_final"]=values[-1]
        out["source_cace_commit"]=payload.get("cace_source_commit")
    elif kind=="modeler":
        rows=payload.get("ranked_truss_results")
        if not isinstance(rows,list):
            raise ValueError("modeler truss ranking required")
        signals["solved_candidates"]=int(number(
            payload["truss_solved_count"],"solved_count",0
        ))
        signals["qualified_candidates"]=sum(
            x.get("passes_declared_truss_limits") is True for x in rows
        )
        signals["rejected_candidates"]=len(
            payload.get("truss_rejected",[])
        )
        if rows:
            signals["min_compliance_j"]=min(
                number(x["compliance_j"],"compliance_j",0) for x in rows
            )
            signals["max_reported_stress_pa"]=max(
                number(x["max_abs_axial_stress_pa"],"stress",0) for x in rows
            )
    elif kind=="quantum":
        calculations=payload.get("scf_results")
        if not isinstance(calculations,list) or not calculations:
            raise ValueError("quantum SCF results required")
        signals["basis_jobs"]=len(calculations)
        signals["scf_converged"]=sum(x.get("converged") is True
                                     for x in calculations)
        signals["energies_hartree"]=[
            number(x["total_electronic_energy_hartree"],"energy")
            for x in calculations
        ]
        if "serial_replay" in payload:
            signals["serial_replay_passed"]=(
                payload["serial_replay"].get("passed") is True
            )
    elif kind=="browser":
        pages=payload.get("pages")
        if not isinstance(pages,list):
            raise ValueError("browser evidence pages required")
        signals["screenshots"]=sum(
            isinstance(p.get("screenshot_sha256"),str) and
            len(p["screenshot_sha256"])==64 for p in pages
        )
        signals["pages_collected"]=len(pages)
        signals["untrusted_page_text"]=True
        signals["vision_model_interpretation_verified"]=False
    out["observed_signals"]=signals
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--kind",choices=sorted(ADAPTERS),required=True)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("-o","--output",type=Path,required=True)
    args=parser.parse_args()
    report=json.loads(args.input.read_text(encoding="utf-8"))
    output=collect(args.kind,report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",
                           encoding="utf-8")
    print(json.dumps({
        "routes":output["route_ids"],
        "improvement_measured":False,
        "source_artifact_sha256":output["source_artifact_sha256"]
    },sort_keys=True))


if __name__=="__main__":
    main()
