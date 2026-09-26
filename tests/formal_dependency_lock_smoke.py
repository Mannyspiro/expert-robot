#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

lock = json.loads(
    (ROOT / "config" / "formal_dependency_lock.json").read_text(encoding="utf-8")
)
manifest = json.loads(
    (ROOT / "formal" / "lake-manifest.json").read_text(encoding="utf-8")
)
toolchain = (ROOT / "formal" / "lean-toolchain").read_text(encoding="utf-8").strip()
lakefile = (ROOT / "formal" / "lakefile.toml").read_text(encoding="utf-8")

assert lock["schema_version"] == 1
assert toolchain == lock["lean_toolchain"]
assert toolchain == "leanprover/lean4:v4.34.0"
assert 'rev = "v4.34.0"' in lakefile
assert not (ROOT / "formal" / "lakefile.lean").exists()

def normalized(packages):
    return sorted(
        (
            item["name"],
            item["type"],
            item["url"],
            item["rev"],
            item.get("inputRev", ""),
        )
        for item in packages
    )

assert normalized(manifest.get("packages", [])) == normalized(lock["packages"])

allowed_prefixes = (
    "https://github.com/leanprover-community/",
    "https://github.com/leanprover/",
)
for item in lock["packages"]:
    assert item["type"] == "git"
    assert item["url"].startswith(allowed_prefixes)
    assert len(item["rev"]) == 40
    int(item["rev"], 16)

mathlib = next(item for item in lock["packages"] if item["name"] == "mathlib")
assert mathlib["rev"] == "5ed2965256430c3649e86755f9576b54eca72435"
assert mathlib["inputRev"] == "v4.34.0"

print("formal dependency lock: PASS")
