#!/usr/bin/env python3
"""Run the bounded beam with actual pinned CACE algebraic modules."""
import argparse
import json
import math
import sys
from pathlib import Path

from evaluate_research_object_beam import evaluate
from inspect_cace_beam_solver import inspect
from certify_beam_discrete import certify
from run_beam_holdouts import run_holdouts

MODULE_SHA256 = "7d99e7f60353eccc4887754fed0df234247e691751b38551d25416a8c036de2b"


def csr(matrix):
    n = len(matrix)
    data, indices, indptr = [], [], [0]
    for row in matrix:
        for j, value in enumerate(row):
            if value != 0:
                data.append(value)
                indices.append(j)
        indptr.append(len(data))
    return {"shape": [n, n], "data": data, "indices": indices, "indptr": indptr}


def verified(records):
    if not records or any(getattr(getattr(r, "state", None), "value", None) != "pass" for r in records):
        raise ValueError("CACE algebraic verification did not pass")
    return [{"verifier": r.verifier, "state": r.state.value, "metrics": r.metrics} for r in records]


def run(cace_root, spec, holdouts):
    contract = inspect(cace_root)
    if contract["module_sha256"] != MODULE_SHA256:
        raise ValueError("CACE module differs from the inspected pinned source")
    sys.path.insert(0, str(cace_root))
    import numpy as np
    from cace_studio.modules import fem_nd
    if Path(fem_nd.__file__).resolve() != (cace_root / "cace_studio/modules/fem_nd.py").resolve():
        raise ValueError("imported CACE module is not the pinned checkout")
    checks = []

    def backend(matrix, rhs):
        # All equations use N after length-scaling rotations and moments.
        # A common scalar normalization keeps CACE's absolute residual check
        # well-scaled; the beam also checks the original physical system.
        scale = max(sum(abs(v) for v in row) for row in matrix)
        normalized = [[v/scale for v in row] for row in matrix]
        payload = csr(normalized)
        # Fail closed unless the actual CACE decoder round-trips this encoding.
        decoded = fem_nd._dense(payload)
        if not np.array_equal(decoded, np.asarray(normalized)):
            raise ValueError("CACE CSR encoding does not round-trip")
        system = {"matrix": payload, "rhs": [v/scale for v in rhs],
                  "full_dofs": len(rhs)+2, "interior_dofs": list(range(2, len(rhs)+2))}
        solver = fem_nd.LinearSolverND()
        inputs = {"system": system}
        outputs = solver.execute(inputs, {}, {})
        solver_checks = verified(solver.verify(inputs, {}, outputs, {}))
        solution = outputs["solution"]
        if solution["values"] != [0.0, 0.0] + solution["interior"]:
            raise ValueError("CACE clamp reconstruction mismatch")
        residual_module = fem_nd.AlgebraicResidualND()
        residual_inputs = {"system": system, "solution": solution}
        residual = residual_module.execute(residual_inputs, {}, {})
        residual_checks = verified(residual_module.verify(residual_inputs, {}, residual, {}))
        if not math.isfinite(residual["residual_inf"]) or residual["residual_inf"] > 1e-10:
            raise ValueError("CACE beam residual exceeds tolerance")
        certificate = certify(matrix, rhs, solution["interior"])
        checks.append({"free_dofs": len(rhs), "normalization_scale": scale,
                       "scaled_cace_residual_inf": residual["residual_inf"],
                       "discrete_error_certificate": certificate,
                       "solver_verification": solver_checks, "residual_verification": residual_checks})
        return solution["interior"]

    report = evaluate(spec, backend)
    baseline_checks = checks[:]
    coverage = run_holdouts(spec, holdouts, backend)
    offset = len(baseline_checks)
    for case in coverage["cases"]:
        count = len(case["meshes"])
        case["cace_mesh_checks"] = checks[offset:offset+count]
        offset += count
    if offset != len(checks):
        raise ValueError("CACE coverage/mesh evidence mismatch")
    report["holdouts"] = coverage
    report["passed"] = report["passed"] and coverage["passed"]
    report["evidence_ceiling"] = "analytic_checked_beam_with_cace_algebraic_not_continuum_certificate"
    report["cace_algebraic"] = {"commit": contract["cace_commit"], "module_sha256": MODULE_SHA256,
                                "csr_round_trip_checked": True, "mesh_checks": baseline_checks,
                                "discrete_error_certificates_checked": len(checks),
                                "continuum_error_certified": False}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cace_root", type=Path)
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", type=Path, required=True)
    parser.add_argument("--holdouts", type=Path, default=Path(__file__).resolve().parents[1]/"config/examples/research_object_beam_holdouts.json")
    args = parser.parse_args()
    report = run(args.cace_root.resolve(), json.loads(args.spec.read_text()), json.loads(args.holdouts.read_text()))
    args.o.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"beam_cace_passed": report["passed"], "cace_commit": report["cace_algebraic"]["commit"],
                      "holdout_cases_passed": sum(c["passed"] for c in report["holdouts"]["cases"]),
                      "discrete_certificates_checked": report["cace_algebraic"]["discrete_error_certificates_checked"],
                      "mesh_elements": [m["elements"] for m in report["meshes"]]}))
    if not report["passed"]:
        raise SystemExit("CACE beam reference/convergence checks failed")
