#!/usr/bin/env python3
"""Validate OBJ concept preview connectivity and face indexing."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "preview_exporter", ROOT / "scripts" / "export_research_object_obj.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

modeler = mod.load_modeler()
fixture = json.loads((ROOT/"config"/"examples"/"research_object_demo.json").read_text())
out = modeler.generate(fixture)
c = out["ranked_survivors"][0]
preview = mod.render(c, out["assumed_minimum_strut_diameter_m"], 12)
assert preview["evidence_ceiling"] == "visualization_only_nonunioned_cylinder_solid_proxy"
assert preview["vertices"] == 24*len(c["edges"])
assert preview["triangles"] == 44*len(c["edges"])
lines = preview["obj"].splitlines()
assert len([x for x in lines if x.startswith("v ")]) == preview["vertices"]
faces = [x for x in lines if x.startswith("f ")]
assert len(faces) == preview["triangles"]
assert max(int(k) for face in faces for k in face.split()[1:]) == preview["vertices"]
assert "NOT a certified/manufacturing-ready solid" in preview["obj"]
try:
    mod.render({**c, "feasible_geometric_graph": False}, 0.003)
except ValueError:
    pass
else:
    raise AssertionError("Infeasible preview export should be rejected")
print("research object OBJ concept preview: PASS")
