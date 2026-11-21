"""Fail-closed, evidence-bound Merlin release readiness report (stdlib only).

This is a reporting gate, not an approval, deployment or source verifier.
Input is an explicit JSON manifest; no missing evidence is inferred as passed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED = (
    "browser_native_socket",
    "browser_retained_state_recovery",
    "python_compatible_runtime",
    "studio_111_product_tests",
    "real_model_response",
    "offline_restart_readback",
    "ui_rendered_smoke",
    "package_install_rollback",
    "provider_preservation",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def assess(manifest: object) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    gates = manifest.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("gates must be an object")
    report = {}
    for name in REQUIRED:
        entry = gates.get(name)
        if not isinstance(entry, dict):
            report[name] = "missing"
            continue
        status = entry.get("status")
        digest = entry.get("evidence_sha256")
        locator = entry.get("evidence_locator")
        source = entry.get("source_commit")
        valid = (
            status == "passed"
            and isinstance(digest, str) and SHA256.fullmatch(digest) is not None
            and isinstance(locator, str) and bool(locator.strip())
            and isinstance(source, str) and SHA256.fullmatch(source) is not None
        )
        report[name] = "evidence_reported" if valid else "unqualified"
    return {
        "ready_for_independent_review": all(v == "evidence_reported" for v in report.values()),
        "gate_status": report,
        "warning": "Reported evidence identifiers are not independently verified by this tool.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        report = assess(json.loads(args.manifest.read_text(encoding="utf-8")))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"invalid release evidence: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_independent_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
