#!/usr/bin/env python3
"""Fail-closed Docker mount validator for the collared RSI sandbox."""

import argparse
import json
import os
import sys

REQUIRED_TMPFS = {
    "/tmp": 512 * 1024 * 1024,
    "/run/expert-robot": 64 * 1024 * 1024,
}
DOCKER_METADATA_BINDS = {"/etc/hosts", "/etc/hostname", "/etc/resolv.conf"}
RUNNER_METADATA_BINDS = {
    "/etc/ssl/certs/avrea-ca.crt": {
        "source": "/opt/avrea/certs/avrea-ca.crt",
        "rw": False,
    },
}

def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(2)

def parse_size(value):
    value = value.strip().lower()
    units = {"k": 1024, "kb": 1024, "m": 1024**2, "mb": 1024**2,
             "g": 1024**3, "gb": 1024**3}
    if value.isdigit():
        return int(value)
    for suffix, multiplier in units.items():
        if value.endswith(suffix) and value[:-len(suffix)].isdigit():
            return int(value[:-len(suffix)]) * multiplier
    fail(f"unsupported tmpfs size: {value!r}")

def validate_tmpfs_options(options, destination, expected_size):
    tokens = {x.strip().lower() for x in (options or "").split(",") if x.strip()}
    for required in ("noexec", "nosuid", "nodev"):
        if required not in tokens:
            fail(f"tmpfs {destination} missing {required}")
    sizes = [x for x in tokens if x.startswith("size=")]
    if len(sizes) != 1:
        fail(f"tmpfs {destination} must have exactly one size")
    if parse_size(sizes[0].split("=", 1)[1]) != expected_size:
        fail(f"tmpfs {destination} size mismatch")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--expected-core", required=True)
    p.add_argument("--expected-workspace", required=True)
    args = p.parse_args()
    payload = json.load(sys.stdin)
    if not isinstance(payload, list) or len(payload) != 1:
        fail("inspect payload must contain exactly one container")
    obj = payload[0]
    expected = {
        "/opt/expert-robot/core": (os.path.realpath(args.expected_core), False),
        "/work": (os.path.realpath(args.expected_workspace), True),
    }
    seen = set()
    for m in obj.get("Mounts") or []:
        dest = m.get("Destination")
        typ = m.get("Type")
        source = m.get("Source") or ""
        rw = bool(m.get("RW"))
        if dest in expected:
            exp_source, exp_rw = expected[dest]
            if typ != "bind" or os.path.realpath(source) != exp_source or rw != exp_rw:
                fail(f"required bind mismatch at {dest}")
            seen.add(dest)
        elif dest in REQUIRED_TMPFS:
            if typ != "tmpfs" or not rw:
                fail(f"tmpfs mount mismatch at {dest}")
        elif dest in DOCKER_METADATA_BINDS:
            if typ != "bind":
                fail(f"Docker metadata mount type mismatch at {dest}")
        elif dest in RUNNER_METADATA_BINDS:
            expected_runner = RUNNER_METADATA_BINDS[dest]
            if typ != "bind":
                fail(f"runner metadata mount type mismatch at {dest}")
            if source != expected_runner["source"]:
                fail(f"runner metadata source mismatch at {dest}")
            if rw is not expected_runner["rw"]:
                fail(f"runner metadata RW mismatch at {dest}")
        else:
            fail(f"unexpected mount: type={typ!r} source={source!r} destination={dest!r} rw={rw!r}")
    missing = set(expected) - seen
    if missing:
        fail("missing required bind mounts: " + ", ".join(sorted(missing)))
    tmpfs = (obj.get("HostConfig") or {}).get("Tmpfs") or {}
    if set(tmpfs) != set(REQUIRED_TMPFS):
        fail("tmpfs destination set mismatch")
    for dest, size in REQUIRED_TMPFS.items():
        validate_tmpfs_options(tmpfs[dest], dest, size)
    print("mount-policy-pass")

if __name__ == "__main__":
    main()
