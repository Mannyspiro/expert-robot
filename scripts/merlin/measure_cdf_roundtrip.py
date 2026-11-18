"""Optional offline CDF fixture experiment; no application or dependency changes.

Requires the separately licensed lasp/cdflib==1.3.16 and numpy>=1.21 in the
caller's isolated environment. No package installation or network access occurs.
All data are synthetic. Output must be a new directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

SAMPLES = 4096
FILL = -1.0e30
IMPLEMENTATION_VERSION = "1.3.16"
WHEEL_SHA256 = "54d3f525651e9293b65a71b29b6b0b737cfe8e8f2a9191dcb686d261b77fc4f1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def measure(output):
    import numpy as np
    import cdflib
    from cdflib import cdfwrite

    if cdflib.__version__ != IMPLEMENTATION_VERSION:
        raise ValueError("this fixed experiment requires cdflib==1.3.16")
    output.mkdir(mode=0o700)  # Refuse to overwrite an earlier experiment.
    i = np.arange(SAMPLES, dtype=np.int64)
    valid = np.ones(SAMPLES, dtype=np.uint8)
    valid[[17, 1000, 3001]] = 0
    scalar = ((i % 64) - 32).astype(np.float64) / 16
    vector = np.column_stack((i % 16, (i // 16) % 16, (i // 256) % 16)).astype(np.float64) / 8
    sigma = np.full(SAMPLES, 0.125, dtype=np.float64)
    scalar[valid == 0] = FILL
    vector[valid == 0] = FILL
    sigma[valid == 0] = FILL
    # Synthetic nanoseconds in the CDF TT2000 coordinate, with no UTC claim.
    times = i * 7812500
    arrays = {"Epoch": times, "scalar": scalar, "vector": vector,
              "scalar_uncertainty": sigma, "valid": valid}
    units = {"Epoch": "ns", "scalar": "V", "vector": "m",
             "scalar_uncertainty": "V", "valid": "1"}
    types = {"Epoch": cdfwrite.CDF.CDF_TIME_TT2000,
             "valid": cdfwrite.CDF.CDF_UINT1}
    notes = ["ok", "", "  "] + ["ok"] * (SAMPLES - 3)
    manifest = {"schema": "merlin-synthetic-cdf-fixture/1", "samples": SAMPLES,
                "sample_interval_ns": 7812500, "method": "synthetic_not_measured",
                "missing_sample_indices": [17, 1000, 3001],
                "arrays": {name: {"dtype": a.dtype.str, "shape": list(a.shape),
                                   "unit": units[name], "sha256": sha256(a.tobytes())}
                           for name, a in arrays.items()},
                "notes_sha256": sha256(canonical(notes))}
    fixture_sha = sha256(canonical(manifest))
    globals_expected = {"TITLE": "Merlin synthetic scalar/vector CDF fixture",
                        "METHOD": "synthetic_not_measured", "SOURCE_SHA256": fixture_sha,
                        "TIME_COORDINATE": "Synthetic CDF TT2000 nanoseconds; no UTC conversion",
                        "COMMENT": ""}
    rows = []
    for compression, label in ((0, "plain"), (6, "variable_gzip6")):
        path = output / (label + ".cdf")
        start = time.perf_counter()
        with cdfwrite.CDF(path, cdf_spec={"Majority": "row_major", "Checksum": True,
                                        "Compressed": 0}) as writer:
            writer.write_globalattrs({key: {0: value} for key, value in globals_expected.items()})
            for name, array in arrays.items():
                attrs = {"UNITS": units[name], "FIELDNAM": name}
                if name != "Epoch":
                    attrs["DEPEND_0"] = "Epoch"
                if name in {"scalar", "vector", "scalar_uncertainty"}:
                    attrs["FILLVAL"] = [FILL, "CDF_DOUBLE"]
                writer.write_var({"Variable": name,
                    "Data_Type": types.get(name, cdfwrite.CDF.CDF_DOUBLE),
                    "Num_Elements": 1, "Rec_Vary": True,
                    "Dim_Sizes": list(array.shape[1:]), "Compress": compression,
                    "Block_Factor": 128}, var_attrs=attrs, var_data=array)
            writer.write_var({"Variable": "sample_note", "Data_Type": cdfwrite.CDF.CDF_CHAR,
                "Num_Elements": 8, "Rec_Vary": True, "Dim_Sizes": [],
                "Compress": compression, "Block_Factor": 128},
                var_attrs={"DEPEND_0": "Epoch", "UNITS": "1"}, var_data=notes)
        write_seconds = time.perf_counter() - start
        checks, hashes = {}, {}
        start = time.perf_counter()
        with cdflib.CDF(path, validate=True) as reader:
            checks["cdf_checksum_validation"] = True  # MD5 integrity, not authentication.
            checks["sample_count"] = reader.varinq("Epoch").Last_Rec + 1 == SAMPLES
            checks["cdf_time_type"] = reader.varinq("Epoch").Data_Type == types["Epoch"]
            for name, array in arrays.items():
                recovered = np.asarray(reader.varget(name))
                checks[name + "_shape"] = recovered.shape == array.shape
                checks[name + "_values"] = bool(np.array_equal(recovered, array))
                checks[name + "_numeric_type"] = recovered.dtype.kind == array.dtype.kind and recovered.dtype.itemsize == array.dtype.itemsize
                normalized = np.asarray(recovered, dtype=array.dtype)
                hashes[name] = sha256(normalized.tobytes())
                checks[name + "_canonical_bytes"] = hashes[name] == manifest["arrays"][name]["sha256"]
                attributes = reader.varattsget(name)
                checks[name + "_units"] = attributes.get("UNITS") == units[name]
                if name in {"scalar", "vector", "scalar_uncertainty"}:
                    checks[name + "_fill_metadata"] = float(attributes["FILLVAL"]) == FILL
            checks["validity_mask"] = bool(np.array_equal(reader.varget("valid") == 0, valid == 0))
            checks["missing_scalar_matches_mask"] = bool(np.array_equal(reader.varget("scalar") == FILL, valid == 0))
            checks["missing_vector_matches_mask"] = bool(np.array_equal(np.all(reader.varget("vector") == FILL, axis=1), valid == 0))
            recovered_globals = reader.globalattsget()
            for key, expected in globals_expected.items():
                if key != "COMMENT":
                    checks["global_" + key] = recovered_globals.get(key) == [expected]
            recovered_notes = list(reader.varget("sample_note"))
            blank = {"input_note_prefix": notes[:3], "recovered_note_prefix": recovered_notes[:3],
                     "all_notes_exact": recovered_notes == notes,
                     "input_empty_comment": "", "recovered_empty_comment": recovered_globals.get("COMMENT"),
                     "empty_comment_exact": recovered_globals.get("COMMENT") == [""]}
            start_subset = time.perf_counter()
            checks["subset_values"] = bool(np.array_equal(reader.varget("vector", startrec=123, endrec=155), vector[123:156]))
            subset_seconds = time.perf_counter() - start_subset
            compression_observed = {name: reader.varinq(name).Compress for name in arrays}
            checks["requested_compression"] = all(value == compression for value in compression_observed.values())
        rows.append({"mode": label, "file": path.name, "size_bytes": path.stat().st_size,
                     "sha256": sha256(path.read_bytes()), "write_seconds": write_seconds,
                     "read_and_check_seconds": time.perf_counter() - start,
                     "subset_read_seconds": subset_seconds,
                     "checks": checks, "required_checks_passed": all(checks.values()),
                     "recovered_array_hashes": hashes, "blank_observations": blank,
                     "variable_compression_levels": compression_observed})
    raw = (output / "plain.cdf").read_bytes()
    corrupted = bytearray(raw)
    corrupted[-1] ^= 1  # Alter the stored checksum, retaining the same file length.
    corrupt_path = output / "checksum_negative_control.cdf"
    corrupt_path.write_bytes(corrupted)
    rejected, rejection_type = False, None
    try:
        with cdflib.CDF(corrupt_path, validate=True):
            pass
    except Exception as error:
        rejected, rejection_type = True, type(error).__name__
    all_required = all(row["required_checks_passed"] for row in rows) and rejected
    blanks_exact = all(row["blank_observations"]["all_notes_exact"] and
                       row["blank_observations"]["empty_comment_exact"] for row in rows)
    result = {"schema": "merlin-cdf-experiment/1", "experiment": "fixed_synthetic_scalar_vector_roundtrip",
        "status": "completed" if all_required else "required_check_failed",
        "outcome": "exact_fixture_roundtrip" if all_required and blanks_exact else
                   "numeric_roundtrip_with_blank_text_difference" if all_required else "failure",
        "qualification": False, "promotion_authority": False,
        "implementation": {"name": "lasp/cdflib", "version": cdflib.__version__,
            "license": "MIT", "copyright": "2025 Regents of the University of Colorado",
            "source_commit_from_PyPI_publish_record": "cf7553fe93c0684ae461fffb1df0a0b9daa23219",
            "wheel_sha256_from_PyPI": WHEEL_SHA256,
            "license_scope": "Separate pure-Python implementation; NASA native CDF library was not installed or executed",
            "module_sha256": {name: sha256((Path(cdflib.__file__).parent / name).read_bytes())
                for name in ("cdfread.py", "cdfwrite.py")}},
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "system": platform.system(), "machine": platform.machine()},
        "script_sha256": sha256(Path(__file__).read_bytes()), "fixture": manifest,
        "fixture_manifest_sha256": fixture_sha, "files": rows,
        "plain_to_compressed_file_ratio": rows[0]["size_bytes"] / rows[1]["size_bytes"],
        "checksum_negative_control": {"rejected": rejected, "error_type": rejection_type,
            "meaning": "Local stored MD5 integrity check only, not scientific truth or signer authentication"},
        "limits": ["Same library writes and reads: no independent NASA native-library interoperability check",
            "One compressible synthetic fixture; no general storage or speed claim",
            "Single timing samples include warm-cache and validation effects; not a performance benchmark",
            "Blank and whitespace text behavior is measured separately; no exact private-chat preservation claim",
            "No hostile-input parser fuzzing, production dependency change, upload or application integration"]}
    (output / "fixture-manifest.json").write_bytes(canonical(manifest) + b"\n")
    (output / "receipt.json").write_bytes(json.dumps(result, indent=2, sort_keys=True,
        ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = measure(args.output_dir)
    print(json.dumps({"status": result["status"], "outcome": result["outcome"],
        "checks_passed": [row["required_checks_passed"] for row in result["files"]],
        "bytes": {row["mode"]: row["size_bytes"] for row in result["files"]},
        "ratio": result["plain_to_compressed_file_ratio"],
        "blank_observations": [row["blank_observations"] for row in result["files"]],
        "negative_control": result["checksum_negative_control"]}, sort_keys=True))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
