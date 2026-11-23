#!/usr/bin/env python3
"""Operator CLI over Merlin Studio's canonical opt-in OpenSandbox backend.

The portable Studio module owns source approval, sandbox SDK execution and
results. This CLI is a separate manual experiment runner, not a grant to a
model and not a default Studio execution mode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

STUDIO_SOURCE = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
if str(STUDIO_SOURCE) not in sys.path:
    sys.path.insert(0, str(STUDIO_SOURCE))

from sandbox_backend import (
    MAX_SOURCE, MAX_OUTPUT, IMAGE_PATTERN, SandboxBoundaryError,
    read_approved_source, validate_config, policy_is_deny_only, execute_approved
)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an approved Python file in an isolated OpenSandbox instance")
    parser.add_argument("--script", required=True)
    parser.add_argument("--approved-sha256", required=True)
    parser.add_argument("--image", required=True, help="Explicit immutable image digest, e.g. myregistry/python@sha256:...")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args(argv)
    validate_config(args.image, args.port, args.timeout)
    source = read_approved_source(args.script, args.approved_sha256)
    result = execute_approved(source, image=args.image, port=args.port, timeout=args.timeout)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
