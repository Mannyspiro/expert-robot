#!/usr/bin/env python3
"""Extract compact contracts from selected CACE Python modules.

Read-only static analysis for adapter generation. Emits class/method signatures,
input/param/output key references, and literal return keys.
"""

from __future__ import annotations
import argparse, ast, json, subprocess
from pathlib import Path

TARGET_FILES = [
    "cace_studio/modules/fem.py",
    "cace_studio/modules/fem_cert.py",
    "cace_studio/modules/fem_nd.py",
    "cace_studio/modules/fem_cert2d_general.py",
]

INTEREST = {
    "ArbitraryMesh1D",
    "P1ShapeFunctions",
    "PoissonAssembly1D",
    "LinearPDESolver",
    "AlgebraicResidual",
    "AposterioriEstimator1D",
    "BenchmarkEnergyErrorInterval",
    "AdaptiveRefinement1D",
    "PipelineCertificate",
    "CertifiedPoissonAssembly",
    "IntervalAlgebraicResidual",
    "DiscreteEnergyErrorCertificate",
    "EstimatorReliabilityGate",
    "CPUGPUEquivalence",
    "SimplexMeshND",
    "P1SimplexSpaceND",
    "SimplexQuadratureND",
    "PoissonAssemblyND",
    "LinearSolverND",
    "AlgebraicResidualND",
    "ResidualEstimatorND",
    "UniformRefinementND",
    "ConvergenceStudyND",
    "AdaptiveRefinement2D",
    "FEMNDCertificate",
    "CertifiedDiffusion2D",
    "GeneralIntervalAssembly2D",
    "IntervalGlobalAssembly2D",
    "TheoremRegistry2D",
    "ReusableReliabilityGate2D",
    "MeshShapeCertificate",
    "Poisson1DContinuumCertificate",
    "TotalContinuumErrorCertificate",
    "CertifiedAdaptiveSolveLoop2D",
}

def arg_name(node):
    if isinstance(node, ast.Name):
        return node.id
    return None

def const_key(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def metadata_expression(node: ast.ClassDef):
    for item in node.body:
        if isinstance(item, (ast.Assign, ast.AnnAssign)):
            targets = item.targets if isinstance(item, ast.Assign) else [item.target]
            if any(isinstance(t, ast.Name) and t.id == "metadata" for t in targets):
                value = item.value
                try:
                    expr = ast.unparse(value)
                except Exception:
                    expr = None
                strings = [
                    sub.value
                    for sub in ast.walk(value)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                ]
                return {"expression": expr, "string_literals": strings}
    return None

def analyze_class(node: ast.ClassDef):
    refs = {"inputs": set(), "params": set(), "outputs": set()}
    return_keys = set()
    methods = []

    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript):
            base = arg_name(sub.value)
            key = const_key(sub.slice)
            if base in refs and key:
                refs[base].add(key)
        elif isinstance(sub, ast.Dict):
            for key in sub.keys:
                k = const_key(key)
                if k:
                    return_keys.add(k)

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in item.args.args]
            methods.append({
                "name": item.name,
                "args": args,
                "line": item.lineno,
            })

    return {
        "class": node.name,
        "line": node.lineno,
        "bases": [ast.unparse(b) for b in node.bases],
        "methods": methods,
        "input_keys": sorted(refs["inputs"]),
        "param_keys": sorted(refs["params"]),
        "output_keys_referenced": sorted(refs["outputs"]),
        "literal_dict_keys": sorted(return_keys),
        "metadata": metadata_expression(node),
    }

def extract(root: Path):
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        commit = None
    files = []
    for rel in TARGET_FILES:
        path = root / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name in INTEREST:
                classes.append(analyze_class(node))
        files.append({"path": rel, "classes": classes})
    return {
        "schema_version": 1,
        "repository": "morganaspim/Cace-app",
        "commit": commit,
        "files": files,
        "remote_mutated": False,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", type=Path)
    p.add_argument("-o", "--output", type=Path)
    args = p.parse_args()
    payload = extract(args.root)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

if __name__ == "__main__":
    main()
