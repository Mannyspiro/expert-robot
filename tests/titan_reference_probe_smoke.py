#!/usr/bin/env python3
"""Smoke tests ensure the provider probe never overstates its evidence."""
import json
import subprocess
import sys

result = subprocess.run([sys.executable, "scripts/titan_reference_probe.py"], check=True, capture_output=True, text=True, timeout=10)
report = json.loads(result.stdout)
assert report["probe"] == "availability_inventory_only"
assert report["known_answer_tests_run"] is False
assert report["cryptographic_operations_run"] is False
assert report["pqc_conformance_claim"] is False
assert report["status"] == "provider_inventory_complete"
assert all({"provider", "present", "algorithm_scope"} <= item.keys() for item in report["providers"])
assert any("does not establish" in item for item in report["limitations"])
print("Titan reference probe smoke tests passed; no cryptographic validation claimed.")
