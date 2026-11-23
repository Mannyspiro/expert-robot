#!/usr/bin/env python3
"""Fault-inject OpenSandbox controller SIGKILL during a real running Merlin task.

Ephemeral GitHub Docker runner only. The controller PID comes from the same
runner's own start step and is verified against its exact config path before
signalling. No user service, model, secret, or host workspace is touched.
The test must not claim safe cancellation after a broken control plane.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from tools import ToolSet
from native_sandbox_acceptance import (
    SANDBOX_LABEL, EGRESS_LABEL, all_managed_containers, docker,
    matching_containers, runtime_volumes
)


def require(condition, text):
    if not condition:
        raise AssertionError(text)


def healthy():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_health(expected, *, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if healthy() is expected:
            return True
        time.sleep(.15)
    return False


def owned_resource_ids(sandbox_id):
    return (matching_containers(SANDBOX_LABEL + "=" + sandbox_id)
            | matching_containers(EGRESS_LABEL + "=" + sandbox_id))


def orphan_present(sandbox_id):
    return bool(owned_resource_ids(sandbox_id)
                or ("opensandbox-runtime-" + sandbox_id) in runtime_volumes())


def rescue_cleanup(sandbox_id):
    """CI-only emergency cleanup, scoped to one observed sandbox identity."""
    attempted = []
    for identifier in sorted(owned_resource_ids(sandbox_id)):
        attempted.append("container:" + identifier)
        docker("rm", "-f", identifier, timeout=18)
    volname = "opensandbox-runtime-" + sandbox_id
    if volname in runtime_volumes():
        attempted.append("volume:" + volname)
        docker("volume", "rm", volname, timeout=18)
    return attempted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report = {"schema": "merlin-native-controller-crash-restoration/1",
              "execution_kind": "native_studio_toolset_and_opensandbox_docker",
              "controller_fault": "verified_test_owned_process_sigkill",
              "source_approval": "synthetic_exact_hash",
              "controller_restarted": False,
              "automatic_expiration_cleanup_verified": False,
              "rescue_cleanup_used": False,
              "complete": False}
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    sandbox_id = None
    restarted = None
    restart_log = None
    thread = None
    marker = threading.Event()
    result = {}
    controller_killed = False
    try:
        require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
                "Explicit sandbox execution backend is required")
        require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
                "Immutable sandbox image is required")
        require(not all_managed_containers() and not runtime_volumes(),
                "Runner contains unmanaged baseline OpenSandbox resources")
        require(healthy(), "Existing test-owned controller was not healthy")
        temp_root = Path(os.environ["RUNNER_TEMP"]).resolve()
        pidpath = temp_root / "merlin-opensandbox.pid"
        config = temp_root / "merlin-opensandbox.toml"
        require(pidpath.is_file() and config.is_file(), "Missing owned controller pid/config")
        pid = int(pidpath.read_text().strip())
        require(pid > 1 and (Path("/proc") / str(pid) / "cmdline").is_file(),
                "Test-owned controller PID not currently running")
        command = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
        require("opensandbox-server" in command and str(config) in command,
                "Controller PID command does not match CI-owned process and configuration")
        with tempfile.TemporaryDirectory(prefix="merlin-controller-fault-") as folder:
            work = Path(folder)
            source = b"import time\nprint('MERLIN_CONTROLLER_FAULT',flush=True)\ntime.sleep(90)\n"
            (work / "long.py").write_bytes(source)
            settings = {"python_enabled": True, "network_enabled": False, "desktop_enabled": False}
            tool = ToolSet(work, object(), settings)
            binding = tool.approval_details("run_python", {"path": "long.py"})
            require(binding["script_sha256"] == hashlib.sha256(source).hexdigest(),
                    "Script approval hash differs")
            def execute():
                try:
                    result["value"] = tool.execute(
                        "run_python", {"path": "long.py"}, "controller-fault-fixture",
                        approved=True, approval_binding=binding, timeout=30,
                        cancelled=marker.is_set)
                except BaseException as exc:
                    result["error"] = type(exc).__name__
            thread = threading.Thread(target=execute, name="merlin-fault-fixture")
            thread.start()
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                for container in matching_containers(SANDBOX_LABEL):
                    try:
                        processes = docker("top", container, timeout=5)
                        details = json.loads(docker("inspect", container, timeout=5))[0]
                    except (RuntimeError, ValueError, IndexError):
                        continue
                    if "/tmp/merlin_approved.py" in processes:
                        candidate = (details.get("Config", {}).get("Labels") or {}).get(SANDBOX_LABEL)
                        if candidate:
                            sandbox_id = candidate
                            break
                if sandbox_id:
                    break
                time.sleep(.15)
            require(sandbox_id is not None, "No independent Docker-top evidence of running Python")
            report["sandbox_id"] = sandbox_id
            report["running_process_observed"] = True

            os.kill(pid, signal.SIGKILL)
            controller_killed = True
            require(wait_health(False, seconds=10),
                    "Controller did not stop after verified owned-process SIGKILL")
            report["controller_outage_observed"] = True
            marker.set()
            thread.join(timeout=34)
            require(not thread.is_alive(),
                    "Unreachable controller caused an unbounded Studio worker")
            require("value" not in result and "error" in result,
                    "Studio reported successful script output while controller was unavailable")
            report["studio_error_type_during_outage"] = result["error"]
            report["studio_reported_success_during_outage"] = False
            require(orphan_present(sandbox_id),
                    "Controller outage did not leave a candidate runtime to restore")

            env = dict(os.environ)
            env["OPENSANDBOX_SERVER_API_KEY"] = env["OPEN_SANDBOX_API_KEY"]
            restart_log = open(temp_root / "merlin-controller-restart.log", "w", encoding="utf-8")
            restarted = subprocess.Popen(
                ["opensandbox-server", "--config", str(config)], env=env,
                cwd=temp_root, stdout=restart_log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True)
            require(wait_health(True, seconds=25), "Controller did not recover after restart")
            report["controller_restarted"] = True
            report["restoration_strategy"] = "pinned OpenSandbox Docker service restores sandbox expiration timers"

            expiry_start = time.monotonic()
            deadline = expiry_start + 85
            while time.monotonic() < deadline and orphan_present(sandbox_id):
                time.sleep(.25)
            report["expiration_cleanup_wait_seconds"] = round(time.monotonic() - expiry_start, 2)
            require(not orphan_present(sandbox_id),
                    "Restarted controller did not expire and clean the orphaned sandbox")
            require(not all_managed_containers() and not runtime_volumes(),
                    "Residual managed resources after restarted controller's expiration")
            report["automatic_expiration_cleanup_verified"] = True
            report["complete"] = True
    finally:
        # Do not hide the result of the scientific experiment; cleanup fallback
        # is reported separately and cannot turn a failed acceptance into pass.
        marker.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=4)
        if sandbox_id and orphan_present(sandbox_id):
            report["rescue_cleanup_used"] = True
            try:
                report["rescue_cleanup_actions"] = rescue_cleanup(sandbox_id)
            except Exception as exc:
                report["rescue_cleanup_error"] = type(exc).__name__
        if restarted is not None:
            if restarted.poll() is None:
                try:
                    os.killpg(restarted.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                restarted.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(restarted.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                restarted.wait(timeout=5)
        if restart_log is not None:
            restart_log.close()
        report["controller_was_killed"] = controller_killed
        output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if not report["complete"]:
        raise AssertionError("Controller recovery acceptance did not pass")
    print(json.dumps({"native_controller_recovery": "passed",
                      "automatic_expiration_cleanup": True,
                      "cleaned_sandbox_id": sandbox_id,
                      "cleanup_wait_s": report["expiration_cleanup_wait_seconds"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
