#!/usr/bin/env python3
"""Opt-in Merlin Studio OpenSandbox Python execution boundary.

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
import threading
import time

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


def _interruptible_command(sandbox, options, timeout, cancelled, state):
    """Monitor a sync SDK stream off-thread, with explicit remote termination.

    The SDK's kill() acknowledgement can precede actual Docker cleanup.
    Real cleanup is independently inspected by native CI, not inferred here.
    """
    finished = threading.Event()
    outcome = {}

    def command_worker():
        try:
            outcome["response"] = sandbox.commands.run(
                "python -I -B /tmp/merlin_approved.py", opts=options)
        except Exception as exc:
            outcome["error"] = exc
        finally:
            finished.set()

    thread = threading.Thread(target=command_worker, daemon=True,
                              name="merlin-sandbox-command")
    thread.start()
    # Command deadline plus a small SDK/control-plane completion grace. The
    # control plane may itself remain unavailable; no global hard-stop claim.
    deadline = time.monotonic() + timeout + 10
    while not finished.wait(0.05):
        reason = ("cancelled" if cancelled() else
                  "deadline" if time.monotonic() >= deadline else None)
        if reason is None:
            continue
        # Kill remote execution *before* accepting cancellation. There must
        # never be a fallback to the host worker or a reported clean cancel
        # when the control plane could not accept the termination.
        sandbox.kill()
        state["remote_kill_accepted"] = True
        if not finished.wait(5):
            raise SandboxBoundaryError(
                "Remote kill accepted but SDK command stream did not terminate")
        if reason == "cancelled":
            raise InterruptedError("Sandbox execution cancelled; remote termination accepted")
        raise TimeoutError("Sandbox SDK command exceeded bounded completion grace")

    if cancelled():
        raise InterruptedError("Sandbox execution cancelled before result was reported")
    if "error" in outcome:
        raise outcome["error"]
    return outcome["response"]


def execute_approved(data, *, image, port=8080, timeout=15, sdk=None, cancelled=lambda: False):
    """Execute already-approved bytes once, without sharing host mounts.

    SDK is optional dependency loaded only when the operator calls this.
    An injected SDK fixture supports contract tests without a Docker daemon.
    """
    validate_config(image, port, timeout)
    if cancelled():
        raise InterruptedError("Sandbox cancelled before create")
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
    state = {"remote_kill_accepted": False}
    try:
        if cancelled():
            raise InterruptedError("Sandbox cancelled after create")
        # If the server cannot affirm that all egress is denied, fail before
        # transferring bytes or executing commands. No host volumes or env
        # credentials are supplied by this adapter.
        if not policy_is_deny_only(sandbox.get_egress_policy()):
            raise SandboxBoundaryError("sandbox egress policy is not deny-all")
        if cancelled():
            raise InterruptedError("Sandbox cancelled before file transfer")
        sandbox.files.write_files([WriteEntry(path="/tmp/merlin_approved.py", data=data, mode=600)])
        if cancelled():
            raise InterruptedError("Sandbox cancelled before command dispatch")
        response = _interruptible_command(sandbox, RunCommandOpts(
            timeout=timedelta(seconds=timeout)), timeout, cancelled, state)
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
        # Do not send a duplicate kill if the cancellation path already
        # received an irreversible remote termination acknowledgement.
        # Always close the local transport. Normal paths still destroy().
        if state["remote_kill_accepted"]:
            sandbox.close()
        else:
            sandbox.destroy()
    return result


