#!/usr/bin/env python3
"""Extract compact contracts from selected CACE Python modules.

Read-only static analysis for adapter generation. Emits class/method signatures,
input/param/output key references, and literal return keys.
"""

from __future__ import annotations
import argparse, ast, json
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
    "LinearPDESolver",
    "AlgebraicResidual",
    "IntervalAlgebraicResidual",
    "DiscreteEnergyErrorCertificate",
    "GeneralIntervalAssembly2D",
    "IntervalGlobalAssembly2D",
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
    }

def extract(root: Path):
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
    return {"schema_version": 1, "files": files, "remote_mutated": False}

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
