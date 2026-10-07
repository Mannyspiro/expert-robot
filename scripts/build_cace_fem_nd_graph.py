#!/usr/bin/env python3
"""Build a versioned CACE FEM-ND module graph from a simplex experiment spec."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / "config" / "cace_fem_nd_contract_pin.json"


def canonical_sha256(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def build(spec: dict[str, Any], pin: dict[str, Any]) -> dict[str, Any]:
    vertices = spec["vertices"]
    elements = spec["elements"]
    dimension = int(spec["dimension"])
    if dimension not in (1, 2, 3):
        raise ValueError("dimension must be 1, 2, or 3")
    if not vertices or not elements:
        raise ValueError("vertices and elements must be nonempty")
    if any(len(v) != dimension for v in vertices):
        raise ValueError("vertex dimension mismatch")
    if any(len(cell) != dimension + 1 for cell in elements):
        raise ValueError("simplex cell arity mismatch")

    source = float(spec.get("source", 1.0))
    theta = float(spec.get("theta", 0.5))
    levels = int(spec.get("levels", 2))
    residual_tolerance = float(spec.get("residual_tolerance", 1e-8))

    refinement_module = "AdaptiveRefinement2D" if dimension == 2 else "UniformRefinementND"
    refinement_inputs = {"mesh": "mesh.mesh"}
    refinement_params: dict[str, Any] = {}
    if dimension == 2:
        refinement_inputs["estimator"] = "estimator.estimator"
        refinement_params["theta"] = theta

    nodes = [
        {
            "id": "mesh",
            "module": "SimplexMeshND",
            "params": {"vertices": vertices, "elements": elements},
            "inputs": {},
            "outputs": ["mesh"],
        },
        {
            "id": "space",
            "module": "P1SimplexSpaceND",
            "params": {},
            "inputs": {"mesh": "mesh.mesh"},
            "outputs": ["space"],
        },
        {
            "id": "quadrature",
            "module": "SimplexQuadratureND",
            "params": {},
            "inputs": {"mesh": "mesh.mesh"},
            "outputs": ["quadrature"],
        },
        {
            "id": "assembly",
            "module": "PoissonAssemblyND",
            "params": {"source": source},
            "inputs": {"mesh": "mesh.mesh"},
            "outputs": ["system"],
        },
        {
            "id": "solver",
            "module": "LinearSolverND",
            "params": {},
            "inputs": {"system": "assembly.system"},
            "outputs": ["solution"],
        },
        {
            "id": "residual",
            "module": "AlgebraicResidualND",
            "params": {},
            "inputs": {
                "solution": "solver.solution",
                "system": "assembly.system",
            },
            "outputs": ["residual_inf"],
        },
        {
            "id": "estimator",
            "module": "ResidualEstimatorND",
            "params": {"source": source},
            "inputs": {
                "mesh": "mesh.mesh",
                "solution": "solver.solution",
            },
            "outputs": ["estimator"],
        },
        {
            "id": "refinement",
            "module": refinement_module,
            "params": refinement_params,
            "inputs": refinement_inputs,
            "outputs": (
                ["marked", "marked_edges", "refined_mesh"]
                if dimension == 2
                else ["refined_mesh"]
            ),
        },
        {
            "id": "history",
            "module": "ConvergenceStudyND",
            "params": {"levels": levels, "source": source},
            "inputs": {"mesh": "mesh.mesh"},
            "outputs": ["history"],
        },
        {
            "id": "certificate",
            "module": "FEMNDCertificate",
            "params": {"residual_tolerance": residual_tolerance},
            "inputs": {
                "estimator": "estimator.estimator",
                "history": "history.history",
                "mesh": "mesh.mesh",
                "refined_mesh": "refinement.refined_mesh",
                "residual_inf": "residual.residual_inf",
            },
            "outputs": ["certificate_summary"],
        },
    ]

    packet = {
        "schema_version": 1,
        "adapter": "cace_fem_nd_poisson_v1",
        "cace_repository": pin["repository"],
        "cace_commit": pin["commit"],
        "dimension": dimension,
        "nodes": nodes,
        "final_output": "certificate.certificate_summary",
        "epistemic_ceiling": "CACE FEM certificate only; not evidence for unmodeled physics",
    }
    packet["packet_sha256"] = canonical_sha256(packet)
    return packet


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("spec", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    pin = json.loads(PIN.read_text(encoding="utf-8"))
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    result = build(spec, pin)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
