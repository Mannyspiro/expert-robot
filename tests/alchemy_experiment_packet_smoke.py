#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_alchemy_experiment_packet.py"

spec = importlib.util.spec_from_file_location("alchemy", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

path = ROOT / "config" / "examples" / "alchemy_safe_phase_separation.crl"
packet = module.build(path)

assert packet["epistemic_status"] == "material_process_experiment_design_not_evidence"
assert packet["process_graph"]["acyclic_by_construction"] is True
assert len(packet["process_graph"]["nodes"]) == 5
assert packet["process_graph"]["nodes"][0]["kind"] == "dissolve"
assert packet["mass_energy_ledger"]["mass_balance"]["status"].startswith("UNRESOLVED")
assert packet["cace_request"]["kind"] == "cace_alchemy_request"
assert packet["cace_request"]["evidence_ceiling"] == "known_physics_model_result_not_transmutation_claim"

print("alchemy experiment packet: PASS")
