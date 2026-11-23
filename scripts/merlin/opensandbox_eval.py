#!/usr/bin/env python3
"""Optional isolated Merlin Python experiment using the OpenSandbox SDK.

This is an operator-driven execution backend, not an automatic replacement
for Studio's run_python. No sandbox is created without explicit source hash
approval and an operator-supplied immutable container image digest.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import stat

MAX_SOURCE = 256 * 1024
MAX_OUTPUT = 65536
IMAGE_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/:@-]{0,230}@sha256:[0-9a-f]{64}$")


class SandboxBoundaryError(ValueError):
    pass


def read_approved_source(filename, approved_sha256):
    if not re.fullmatch(r"[0-9a-f]{64}", str(approved_sha256)):
        raise SandboxBoundaryError("approved SHA-256 is required")
    path = Path(filename).absolute()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_SOURCE:
            raise SandboxBoundaryError("source must be a regular file of at most 256 KiB")
        data = os.read(descriptor, MAX_SOURCE + 1)
    finally:
        os.close(descriptor)
    if len(data) > MAX_SOURCE or hashlib.sha256(data).hexdigest() != approved_sha256:
        raise SandboxBoundaryError("source differs from explicitly approved bytes")
    return data


def validate_config(image, port, timeout):
    if not isinstance(image, str) or not IMAGE_PATTERN.fullmatch(image):
        raise SandboxBoundaryError("an immutable container image @sha256 digest is required")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise SandboxBoundaryError("sandbox API port must be an integer in 1024..65535")
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise SandboxBoundaryError("execution deadline must be an integer in 1..30 seconds")


def policy_is_deny_only(policy):
    return getattr(policy, "default_action", None) == "deny" and not getattr(policy, "egress", None)


def execute_approved(data, *, image, port=8080, timeout=15, sdk=None):
    """Execute already-approved bytes once, without sharing host mounts.

    SDK is optional dependency loaded only when the operator calls this.
    An injected SDK fixture supports contract tests without a Docker daemon.
    """
    validate_config(image, port, timeout)
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SOURCE:
        raise SandboxBoundaryError("approved Python source must be bounded nonempty bytes")
    if sdk is None:
        from opensandbox import SandboxSync
        from opensandbox.config import ConnectionConfigSync
        from opensandbox.models import WriteEntry
        from opensandbox.models.execd import RunCommandOpts
        from opensandbox.models.sandboxes import NetworkPolicy
    else:
        SandboxSync = sdk.SandboxSync
        ConnectionConfigSync = sdk.ConnectionConfigSync
        WriteEntry = sdk.WriteEntry
        RunCommandOpts = sdk.RunCommandOpts
        NetworkPolicy = sdk.NetworkPolicy
    sandbox = SandboxSync.create(
        image,
        timeout=timedelta(seconds=60),
        ready_timeout=timedelta(seconds=20),
        resource={"cpu": "1", "memory": "512Mi"},
        network_policy=NetworkPolicy(default_action="deny", egress=[]),
        connection_config=ConnectionConfigSync(
            domain="127.0.0.1:" + str(port), protocol="http",
            api_key=os.environ.get("OPEN_SANDBOX_API_KEY") or None,
            request_timeout=timedelta(seconds=10), follow_redirects=False),
    )
    result = None
    try:
        # If the server cannot affirm that all egress is denied, fail before
        # transferring bytes or executing commands. No host volumes or env
        # credentials are supplied by this adapter.
        if not policy_is_deny_only(sandbox.get_egress_policy()):
            raise SandboxBoundaryError("sandbox egress policy is not deny-all")
        sandbox.files.write_files([WriteEntry(path="/tmp/merlin_approved.py", data=data, mode=600)])
        response = sandbox.commands.run("python -I -B /tmp/merlin_approved.py",
                                        opts=RunCommandOpts(timeout=timedelta(seconds=timeout)))
        stdout = "".join(getattr(item, "text", "") for item in response.logs.stdout)
        stderr = "".join(getattr(item, "text", "") for item in response.logs.stderr)
        exit_code = response.exit_code
        if type(exit_code) is not int:
            raise SandboxBoundaryError("no independently reported sandbox command exit code")
        result = {
            "exit_code": exit_code,
            "stdout": stdout[:MAX_OUTPUT],
            "stderr": stderr[:MAX_OUTPUT],
            "truncated": len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT,
            "termination": "completed" if exit_code == 0 else "failed",
            "os_sandbox": True,
            "sandbox_provider": "OpenSandbox",
            "sandbox_id": str(sandbox.id),
            "script_sha256": hashlib.sha256(data).hexdigest(),
            "network_policy": "deny",
        }
    finally:
        # Terminate the actual sandbox, not merely the SDK connection.
        # If destroy fails, the call fails; no success is reported.
        sandbox.destroy()
    return result


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
