#!/usr/bin/env python3
"""Inventory candidate PQC provider availability without installing packages or claiming validation."""
from __future__ import annotations
import importlib.metadata
import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone

PROVIDERS = {
    "liboqs_python": {"module": "oqs", "distribution": "liboqs-python", "algorithms": ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024", "ML-DSA-44", "ML-DSA-65", "ML-DSA-87", "SLH-DSA"]},
    "pqcrypto": {"module": "pqcrypto", "distribution": "pqcrypto", "algorithms": ["provider-specific; inspect exact installed package and version"]},
    "cryptography": {"module": "cryptography", "distribution": "cryptography", "algorithms": ["classical primitives only for this probe; not a PQC provider assertion"]},
}

def main() -> int:
    results = []
    for key, item in PROVIDERS.items():
        present = importlib.util.find_spec(item["module"]) is not None
        try:
            version = importlib.metadata.version(item["distribution"]) if present else None
        except importlib.metadata.PackageNotFoundError:
            version = "module-present-distribution-version-unresolved"
        results.append({"provider": key, "module": item["module"], "present": present, "version": version, "algorithm_scope": item["algorithms"]})
    report = {
        "schema_version": 1,
        "probe": "availability_inventory_only",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "providers": results,
        "known_answer_tests_run": False,
        "cryptographic_operations_run": False,
        "pqc_conformance_claim": False,
        "status": "provider_inventory_complete",
        "limitations": [
            "Package presence does not establish algorithm availability, correctness, constant-time behavior, validation, or security.",
            "No dependencies were installed and no cryptographic keys or secrets were generated.",
            "Known-answer tests require pinned provider versions and authoritative test-vector provenance."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
