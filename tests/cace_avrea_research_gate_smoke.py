#!/usr/bin/env python3
"""Static contract for the read-only pinned CACE Avrea probe and OCI bridge."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
probe = (root / ".github/workflows/cace-biochemical-diffusion.yml").read_text()
bridge = (root / ".github/workflows/external-free-runner-bridge.yml").read_text()
assert "runs-on: avrea-ubuntu-latest-8-vcpu" in probe
assert "group: expert-robot-avrea-half-month-slot" in probe
assert "queue: max" in probe
assert "contents: read" in probe and "actions: read" in probe
assert "contents: write" not in probe
assert probe.index("Enforce Avrea half-month budget before credentials") < probe.index(
    "Prepare read-only CACE deploy-key credentials"
) < probe.index("Clone authorized CACE repository")
assert "--reserve-minutes 10" in probe
assert "checkout --detach" in probe
assert "config/cace_fem_nd_contract_pin.json" in probe
assert "git -C \"$RUNNER_TEMP/cace-app\" rev-parse HEAD" in probe
assert "git push " not in probe and "git commit " not in probe
assert "promotion_authorized: true" not in probe.lower()
# Remote OCI bridge must archive only tracked HEAD, and verify request size
# and digest before extracting; no source code is allowed to select tools.
assert "git archive --format=tar" in bridge
assert "archive_sha256" in bridge
assert "source archive or request integrity mismatch" in bridge
assert bridge.index("Enforce Avrea half-month budget") < bridge.index("Prepare deploy key")
assert bridge.index("source archive or request integrity mismatch") < bridge.index(
    'tar -xzf bridge/expert-robot-source.tar.gz'
)
assert "runs-on: [self-hosted, cace, oci, aarch64]" in bridge
print("CACE Avrea + OCI bridge static contract: PASS")
