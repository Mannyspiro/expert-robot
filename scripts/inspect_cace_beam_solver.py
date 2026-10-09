#!/usr/bin/env python3
"""Read-only pinned CACE algebraic-contract inspection for the beam adapter."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "0e7aa229d3bb57174e281b883ee8af5445f15f75"

def inspect(root):
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise ValueError("CACE source does not match the qualified pin")
    source = (root / "cace_studio/modules/fem_nd.py").read_text()
    classes = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name in {"LinearSolverND", "AlgebraicResidualND"}:
            classes[node.name] = ast.get_source_segment(source, node)
    if set(classes) != {"LinearSolverND", "AlgebraicResidualND"} or sum(map(len, classes.values())) > 20000:
        raise ValueError("missing or oversized algebraic contract")
    return {"cace_commit": head, "module_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "promotion_authority": False, "classes": classes}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cace_root", type=Path)
    parser.add_argument("-o", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.cace_root)
    args.o.write_text(json.dumps(result, indent=2) + "\n")
    print("CACE_BEAM_CONTRACT_BEGIN")
    print(json.dumps(result))
    print("CACE_BEAM_CONTRACT_END")
