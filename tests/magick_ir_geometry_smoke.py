#!/usr/bin/env python3
"""Dependency-free smoke tests for Magick IR exact geometry compilation."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compile_magick_geometry.py"
EXAMPLE = ROOT / "config" / "examples" / "hygromanteia_water_divination.magick.json"
SCHEMA = ROOT / "config" / "schemas" / "magick_experiment.schema.json"


spec = importlib.util.spec_from_file_location("compile_magick_geometry", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

# Schema and example must remain syntactically valid JSON.
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
assert schema["properties"]["schema_version"]["const"] == "0.1"

payload = module.load_json(EXAMPLE)
compiled = module.compile_magick(payload)

assert compiled["schema_version"] == 1
assert compiled["epistemic_guards"]["floating_geometry_emitted"] is False
assert compiled["epistemic_guards"]["missing_visual_features_imputed"] is False
assert len(compiled["source_sha256"]) == 64

by_id = {item["id"]: item for item in compiled["exact_primitives"]}

circle = by_id["outer_circle"]
assert circle["exact_type"] == "Circle3"
assert circle["center"] == ["0", "0", "0"]
assert circle["normal"] == ["0", "0", "1"]
assert circle["radiusSquared"] == "1"
assert circle["lean_formalized"] is True

square = by_id["inner_square"]
assert square["exact_type"] == "Polygon3ExactVertices"
assert square["vertices"][0] == ["-1/2", "-1/2", "0"]
assert square["vertices"][2] == ["1/2", "1/2", "0"]
assert square["lean_formalized"] is False

center = by_id["vessel_center"]
assert center["exact_type"] == "Point3"
assert center["point"] == ["0", "0", "0"]

# Until Polygon3 is formalized, this example must truthfully expose the gap.
assert compiled["formalization"]["fully_formalized"] is False
assert any(g["id"] == "inner_square" for g in compiled["formalization"]["gaps"])

# Fail closed on forbidden reconstruction of a missing visual witness.
bad = json.loads(EXAMPLE.read_text(encoding="utf-8"))
bad["source"]["witnesses"][0]["provenance_status"] = "missing"
bad["source"]["witnesses"][0]["visual_features_imputed"] = True
try:
    module.compile_magick(bad)
except module.CompileError:
    pass
else:
    raise AssertionError("missing visual evidence was incorrectly accepted as imputed")

print("magick IR exact geometry: PASS")
