#!/usr/bin/env python3
"""Validate theorem-backed h_max forecasts against a live CACE report."""

from __future__ import annotations
import argparse, importlib.util, json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_forecaster():
    path=ROOT/"scripts"/"forecast_cace_refinement.py"
    spec=importlib.util.spec_from_file_location("forecast_cace_refinement",path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load forecast module")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

forecast_mod=load_forecaster()


def validate(report: dict, bridge: dict, tolerance: float=1e-12) -> dict:
    history=report.get("summary",{}).get("convergence_history",{})
    records=history.get("records")
    if not isinstance(records,list) or not records:
        raise ValueError("report has no convergence records")
    records=sorted(records,key=lambda r:int(r["level"]))
    h0=float(records[0]["h_max"])
    rows=[]
    failures=[]
    for row in records:
        level=int(row["level"])
        observed=float(row["h_max"])
        predicted=h0/(2**level)
        error=abs(observed-predicted)
        passed=math.isclose(observed,predicted,rel_tol=tolerance,abs_tol=tolerance)
        item={
            "level":level,
            "observed_h_max":observed,
            "predicted_h_max":predicted,
            "absolute_error":error,
            "passed":passed,
        }
        rows.append(item)
        if not passed:
            failures.append(item)

    return {
        "schema_version":1,
        "experiment_id":report.get("experiment_id"),
        "bridge_id":bridge["bridge_id"],
        "formal_geometry_refs":bridge["formal_geometry_refs"],
        "records_checked":len(rows),
        "max_absolute_error":max(x["absolute_error"] for x in rows),
        "counterexamples_found":len(failures),
        "rows":rows,
        "passed":not failures,
        "evidence_scope":"implementation-equivalence check only; not continuum error certification",
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("report",type=Path)
    p.add_argument(
        "--bridge",
        type=Path,
        default=ROOT/"config"/"cace_refinement_formal_bridge.json",
    )
    p.add_argument("--tolerance",type=float,default=1e-12)
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    report=json.loads(args.report.read_text(encoding="utf-8"))
    bridge=json.loads(args.bridge.read_text(encoding="utf-8"))
    result=validate(report,bridge,args.tolerance)
    rendered=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    else:
        print(rendered,end="")
    if not result["passed"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
