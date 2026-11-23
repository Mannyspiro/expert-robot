#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_occult_experiment_packet.py"

spec = importlib.util.spec_from_file_location("packet", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

path = ROOT / "config" / "examples" / "portal_p2_boundary_null.crl"
packet = module.build(path)

assert packet["magick_ir"]["claim"]["portal_class"] == "P2_field_energy"
assert packet["magick_ir"]["evidence"]["status"] == "UNTESTED"
assert packet["epistemic_status"] == "experiment_design_not_evidence"
assert any(x["id"] == "semantics-vs-waveform" for x in packet["ablation_plan"]["axes"])
assert any(x["id"] == "orientation-reference" for x in packet["ablation_plan"]["axes"])
assert "maxwell_em" in packet["magick_ir"]["simulation"]["known_physics_models"]

print("portal P2 null packet: PASS")
