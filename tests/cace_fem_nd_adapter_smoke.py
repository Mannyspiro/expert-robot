#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_cace_fem_nd_graph.py"

spec = importlib.util.spec_from_file_location("builder", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

pin = json.loads((ROOT / "config" / "cace_fem_nd_contract_pin.json").read_text())
payload = json.loads((ROOT / "config" / "examples" / "cace_triangle_poisson_spec.json").read_text())
result = module.build(payload, pin)

assert result["cace_commit"] == pin["commit"]
assert result["nodes"][0]["module"] == "SimplexMeshND"
assert result["nodes"][3]["module"] == "PoissonAssemblyND"
assert result["nodes"][7]["module"] == "AdaptiveRefinement2D"
assert result["nodes"][-1]["module"] == "FEMNDCertificate"
assert result["final_output"] == "certificate.certificate_summary"
assert len(result["packet_sha256"]) == 64

print("CACE FEM-ND adapter builder: PASS")
