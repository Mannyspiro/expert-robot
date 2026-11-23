#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_occult_experiment_packet.py"

spec = importlib.util.spec_from_file_location("occult_packet", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

hept = module.build(ROOT / "config" / "examples" / "heptameron_circle.crl")
assert hept["epistemic_status"] == "experiment_design_not_evidence"
assert hept["magick_ir"]["symbols"]["tokens"]
assert hept["exact_geometry"]["exact_primitives"]
assert hept["cace_request"]["kind"] == "cace_magick_request"
assert hept["historical_locus_priority"]["effective_locus_count"] == 2
assert any(x["id"] == "semantics-vs-waveform" for x in hept["ablation_plan"]["axes"])
assert any(x["id"] == "orientation-reference" for x in hept["ablation_plan"]["axes"])
assert hept["cace_request"]["requested_certificates"][-1] == "input_identity"

clav = module.build(ROOT / "config" / "examples" / "clavicula_circle.crl")
assert any(x["id"] == "boundary-opening" for x in clav["ablation_plan"]["axes"])
assert any(p["exact_type"] == "Circle3" for p in clav["exact_geometry"]["exact_primitives"])
assert any(p["exact_type"] == "Point3" for p in clav["exact_geometry"]["exact_primitives"])

# No generated packet may promote itself to evidence.
assert hept["magick_ir"]["evidence"]["status"] == "UNTESTED"
assert clav["magick_ir"]["evidence"]["status"] == "UNTESTED"

print("occult experiment packet: PASS")
