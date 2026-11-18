"""Independently read the fixed Merlin CDF science fixture through NASA's native library."""
import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from measure_cdf_roundtrip import canonical

FIXTURE_SHA256 = "35b35baee8fa362e628542bd5ea10b8c107075ce6157ab3f3eaf502fadab361d"


def check(directory):
    import numpy as np
    from spacepy import pycdf

    if version("spacepy") != "0.7.0" or pycdf.lib.version[:3] != (3, 9, 1):
        raise ValueError("this measurement requires SpacePy 0.7.0 and NASA CDF 3.9.1")
    manifest = json.loads((directory / "fixture-manifest.json").read_text())
    if hashlib.sha256(canonical(manifest)).hexdigest() != FIXTURE_SHA256:
        raise ValueError("unexpected fixture definition")
    modes = {}
    for mode in ("plain", "variable_gzip6"):
        checks = {}
        with pycdf.CDF(str(directory / (mode + ".cdf")), readonly=True) as reader:
            for name, spec in manifest["arrays"].items():
                raw = reader.raw_var(name)[...]
                checks[name + "_dtype"] = raw.dtype.str == spec["dtype"]
                checks[name + "_shape"] = list(raw.shape) == spec["shape"]
                checks[name + "_bytes"] = hashlib.sha256(raw.tobytes()).hexdigest() == spec["sha256"]
                checks[name + "_units"] = reader[name].attrs["UNITS"] == spec["unit"]
            notes = [str(value) for value in reader["sample_note"][...]]
            checks["notes_including_blanks"] = hashlib.sha256(canonical(notes)).hexdigest() == manifest["notes_sha256"]
            checks["empty_comment"] = reader.attrs["COMMENT"][0] == ""
            checks["source_identity"] = reader.attrs["SOURCE_SHA256"][0] == FIXTURE_SHA256
            invalid = np.flatnonzero(reader["valid"][...] == 0)
            checks["missing_indices"] = invalid.tolist() == manifest["missing_sample_indices"]
        modes[mode] = checks
    return {"schema": "merlin-cdf-native-reader-check/1", "writer": "cdflib 1.3.16",
            "reader": "SpacePy 0.7.0 via NASA CDF 3.9.1", "fixture_sha256": FIXTURE_SHA256,
            "checks": modes, "passed": all(all(row.values()) for row in modes.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_directory", type=Path)
    result = check(parser.parse_args().fixture_directory)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
