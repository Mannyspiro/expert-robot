#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cfg = json.loads(
    (ROOT / "config" / "external_lean_sources.json").read_text(encoding="utf-8")
)

assert cfg["schema_version"] == 1
ids = [item["id"] for item in cfg["sources"]]
assert len(ids) == len(set(ids))

allowed_classes = {"import_candidate", "benchmark_candidate", "reference_only"}
for source in cfg["sources"]:
    assert source["classification"] in allowed_classes
    assert source["license"]
    assert source["allowed_use"]
    assert source["trust_notes"]
    if "source_commit" in source:
        assert re.fullmatch(r"[0-9a-f]{40}", source["source_commit"])

imo = next(s for s in cfg["sources"] if s["id"] == "axiom-imo2026")
assert imo["license"] == "MIT"
assert imo["classification"] == "import_candidate"
assert imo["lean_toolchain"] == "v4.31.0"

machlib = next(s for s in cfg["sources"] if s["id"] == "machlib-2026-09")
assert machlib["classification"] == "reference_only"
assert "axiomatized reals" in " ".join(machlib["trust_notes"]).lower()

dap = next(s for s in cfg["sources"] if s["id"] == "discover-and-prove-acl2026")
assert "datasets retain upstream licenses" in " ".join(dap["trust_notes"]).lower()

print("external Lean source intake policy: PASS")
