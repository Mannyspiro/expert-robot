#!/usr/bin/env python3
"""Bounded, offline regressions for pinned OpenAI Lean import closure scanner.

No network, upstream checkout or kernel claim. Test syntax, missing imports,
scope, and exact 200-target accounting using temporary synthetic files.
"""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "closure", ROOT / "scripts/profile_openai_lean_closure.py")
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)

VALID = (
    "OAI.Topology.ArtinGroups.Realizations.MulBlockDiagonal'Entry",
    "OAI.Geometry.WeakHessian.Entropy.IntegralDensityMeasureLp'",
)
assert all(closure.MOD.fullmatch(p) for p in VALID)
for invalid in ("OAI..Entry", "OAI.2Bad", "OAI.Entry@", "OAI.Foo/Bar", ".OAI",
                "OAI.Foo;", "OAI.Foo#"):
    assert not closure.MOD.fullmatch(invalid), invalid


def exercise(import_line, extra=()):
    with TemporaryDirectory() as scratch:
        upstream = Path(scratch)
        root = upstream / "lean"
        def write(module, source):
            path = root / (module.replace(".", "/") + ".lean")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        write("OAI.Test.Main", import_line + "\ntheorem t : True := trivial\n")
        for dep in extra:
            write(dep, "-- fixture\n")
        catalog = {
            "source_commit": closure.COMMIT,
            "declared_results": [
                {"declaration": f"OAI.Test.t{i}",
                 "module_file": "OAI/Test/Main.lean",
                 "comparator_config": "fixture.json"}
                for i in range(200)
            ],
        }
        return closure.profile(upstream, catalog)


valid = exercise("import Mathlib " + " ".join(VALID) + " -- prime paths", VALID)
assert valid["failure_count"] == 0, valid["import_resolution_failures"]
assert valid["results_profiled"] == 200
assert valid["source_modules_inspected"] == 3
assert valid["targets_with_missing_imports"] == 0
assert len(valid["batches"]) == 50
assert all(x["local_modules"] == 3 for x in valid["cases"])
assert valid["kernel_checks_completed"] == 0
assert valid["mathematical_truth_claimed"] is False

missing = exercise("import OAI.Test.Nonexistent")
assert missing["failure_count"] > 0
assert missing["targets_with_missing_imports"] == 200
assert any(f["reason"] == "missing source"
           for f in missing["import_resolution_failures"])
malformed = exercise("import OAI.Test.Bad@")
assert malformed["failure_count"] > 0
assert any(f["reason"] == "unrecognized import syntax"
           for f in malformed["import_resolution_failures"])
print("Lean import primes, 200-target accounting and fail-closed regression: PASS")
