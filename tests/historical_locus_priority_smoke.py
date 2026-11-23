#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

crl = load("crl", ROOT / "scripts" / "compile_crl.py")
planner = load("locus", ROOT / "scripts" / "prioritize_historical_loci.py")

hpath = ROOT / "config" / "examples" / "heptameron_circle.crl"
hir = crl.parse(hpath.read_text(encoding="utf-8"), str(hpath))
hp = planner.prioritize(hir)
assert hp["effective_locus_count"] == 2
assert hp["ranked_loci"][0]["feature_class"] == "topology"
assert "not probability" in hp["score_semantics"]

cpath = ROOT / "config" / "examples" / "clavicula_circle.crl"
cir = crl.parse(cpath.read_text(encoding="utf-8"), str(cpath))
cp = planner.prioritize(cir)
assert cp["effective_locus_count"] == 2
assert cp["ranked_loci"][0]["locus_id"] == "boundary-opening"

# Correlated mutations must be capped to one effective locus.
dup = dict(hir)
dup["historical_loci"] = list(hir["historical_loci"]) + [
    dict(hir["historical_loci"][0], id="three-rings-derived-copy", confidence=0.8)
]
dp = planner.prioritize(dup)
assert dp["effective_locus_count"] == 2
assert len(dp["suppressed_correlated_loci"]) == 1

print("historical locus prioritization: PASS")
