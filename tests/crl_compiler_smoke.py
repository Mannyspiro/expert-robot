#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compile_crl.py"

spec = importlib.util.spec_from_file_location("compile_crl", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

for name in ("heptameron_circle.crl", "clavicula_circle.crl"):
    path = ROOT / "config" / "examples" / name
    ir = module.parse(path.read_text(encoding="utf-8"), str(path))
    assert ir["schema_version"] == "0.1"
    assert ir["source"]["witnesses"]
    assert ir["geometry"]["primitives"]
    assert ir["symbols"]["tokens"]
    assert ir["historical_loci"]
    assert ir["measurements"]
    assert ir["controls"]["randomization"] is True
    assert ir["controls"]["preregistered"] is True
    assert ir["controls"]["holdout_fraction"] == 0.2
    assert ir["simulation"]["known_physics_models"]
    assert ir["evidence"]["status"] == "UNTESTED"
    assert all(w["visual_features_imputed"] is False for w in ir["source"]["witnesses"])

# Speech content and waveform representation must remain separable.
h = module.parse(
    (ROOT / "config" / "examples" / "heptameron_circle.crl").read_text(encoding="utf-8"),
    "heptameron_circle.crl",
)
assert h["symbols"]["tokens"][0]["text"] == "<DAY_ANGEL>"
assert h["acoustics"]["utterances"][0]["token"] == "day-angel"
assert h["symbols"]["tokens"][0]["kind"] == "name"

# Unknown channels are explicitly residual-only in the examples.
assert h["unknown_channels"][0]["measurement_policy"] == "residual_only"

print("CACE Ritual Language compiler: PASS")
