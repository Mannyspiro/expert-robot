#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "route_crl_research.py"

spec = importlib.util.spec_from_file_location("router", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

hept = module.route_program(ROOT / "config" / "examples" / "heptameron_circle.crl")
assert "magic_circle_or_occult" in hept["routes"]
assert "alchemy_material_transformation" not in hept["routes"]
assert "portal_evidence" not in hept["routes"]

alc = module.route_program(ROOT / "config" / "examples" / "alchemy_safe_phase_separation.crl")
assert "alchemy_material_transformation" in alc["routes"]
assert "alchemy" in alc["packets"]

portal = module.route_program(ROOT / "config" / "examples" / "portal_p2_boundary_null.crl")
assert "portal_evidence" in portal["routes"]
assert portal["packets"]["portal_requirements"]["requested_class"] == "P2_field_energy"
assert portal["packets"]["portal_requirements"]["status"] == "REQUIREMENTS_ONLY_NOT_SATISFIED"
assert portal["epistemic_status"] == "routing_and_experiment_design_only"

print("CRL research router: PASS")
