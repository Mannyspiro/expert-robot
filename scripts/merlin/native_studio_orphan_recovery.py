#!/usr/bin/env python3
"""Crash a test-owned Studio server during native sandbox execution and recover.

This native test proves the controller sees ownership metadata and a restarted
Studio process can terminate only its old pending execution, then invalidate
run/approval/session state. It never uses real user workspaces or model calls.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from storage import Store
from native_studio_http_approval_acceptance import request, wait_for, start_run, require
from native_sandbox_acceptance import (
    SANDBOX_LABEL, all_managed_containers, matching_containers, runtime_volumes,
    docker, confirm_absent
)

ADDRESS = re.compile(r"^Merlin Studio: http://127\.0\.0\.1:(\d+)/studio/$")


def start_owned_process(data_dir):
    proc = subprocess.Popen(
        [sys.executable, "-B", str(STUDIO / "server.py"), "--port", "0",
         "--data-dir", str(data_dir)],
        cwd=STUDIO, env=os.environ.copy(), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            require(proc.poll() is None, "Studio exited during restart reconciliation")
            ready, _, _ = select.select([proc.stdout], [], [], 0.15)
            if ready:
                line = proc.stdout.readline().decode("utf-8", "replace").strip()
                match = ADDRESS.fullmatch(line)
                if match:
                    port = int(match.group(1))
                    for _ in range(30):
                        try:
                            status, _ = request(port, "GET", "/api/health")
                            if status == 200:
                                return proc, port
                        except (OSError, TimeoutError):
                            time.sleep(0.1)
            time.sleep(0.05)
        raise AssertionError("Studio never started after owner reconciliation")
    except BaseException:
        stop(proc)
        raise


def stop(proc):
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=6)
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()


def wait_running_script(before, deadline_seconds=40):
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        for container in matching_containers(SANDBOX_LABEL) - before:
            try:
                table = docker("top", container, timeout=4)
                info = json.loads(docker("inspect", container, timeout=4))[0]
            except (RuntimeError, ValueError, IndexError):
                continue
            if "/tmp/merlin_approved.py" in table:
                sid = (info.get("Config", {}).get("Labels") or {}).get(SANDBOX_LABEL)
                if sid:
                    return sid
        time.sleep(0.15)
    raise AssertionError("Docker did not observe an actual approved running script")


def main():
    require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
            "Native crash recovery requires explicit OpenSandbox backend")
    require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
            "Immutable sandbox image must be provided")
    require(not all_managed_containers() and not runtime_volumes(),
            "Clean Docker start required")
    with tempfile.TemporaryDirectory(prefix="merlin-crashed-remote-owner-") as dirname:
        directory = Path(dirname)
        data = directory / "data"
        proc = None
        restarted = None
        try:
            proc, port = start_owned_process(data)
            code, status = request(port, "GET", "/api/status")
            require(code == 200 and status["capabilities"]["python_sandbox"],
                    "Native owner-tracked Python unavailable on first start")
            original_token = status["session_token"]
            code, result = request(port, "POST", "/api/conversations",
                                   {"title": "Owned crash recovery"}, token=original_token)
            require(code == 201, "Cannot create crash-recovery conversation")
            cid = result["conversation"]["id"]
            source = "import time\nprint('MERLIN_ORPHAN_PROCESS',flush=True)\ntime.sleep(90)\n"
            code, _ = request(port, "POST", "/api/tool",
                              {"tool": "write_file", "args": {
                                  "path": "orphan.py", "content": source}}, token=original_token)
            require(code == 200, "Cannot prepare controlled crash fixture")
            run_id = start_run(port, original_token, cid, "/python orphan.py")
            pending = wait_for(port, run_id, {"waiting_approval"}, timeout=12)
            approval = pending["pending_approval"]
            require(approval["arguments"]["script_sha256"] == hashlib.sha256(source.encode()).hexdigest()
                    and approval["arguments"]["backend"] == "opensandbox",
                    "Actual HTTP approval source binding differs")
            code, _ = request(port, "POST", "/api/runs/" + run_id + "/approve",
                              {"approval_id": approval["id"], "approved": True}, token=original_token)
            require(code == 200, "Cannot approve one controlled orphan fixture")
            sid = wait_running_script(set())
            # The durable record must precede the remote creation.
            before = Store(data)
            owner = before.sandbox_owner()
            pending_rows = before.sandbox_pending()
            require(len(pending_rows) == 1 and pending_rows[0]["run_id"] == run_id,
                    "Remote script ran without a committed owner intent")
            stop(proc)
            proc = None
            require(bool(matching_containers(SANDBOX_LABEL + "=" + sid)),
                    "The remote sandbox did not survive the deliberately crashed Studio process")
            restarted, new_port = start_owned_process(data)
            code, new_status = request(new_port, "GET", "/api/status")
            require(code == 200 and new_status["sandbox_recovery"]["ready"]
                    and new_status["sandbox_recovery"]["pending_count"] == 0
                    and new_status["sandbox_recovery"]["reconciled"]
                    and new_status["capabilities"]["python_sandbox"],
                    "Restart failed to reconcile owned orphan before accepting new Python")
            require(new_status["session_token"] != original_token,
                    "A restarted Studio reused the old session token")
            code, recovered = request(new_port, "GET", "/api/runs/" + run_id)
            require(code == 200 and recovered["run"]["status"] == "interrupted"
                    and not any(x["type"] == "tool_result" for x in recovered["run"]["events"]),
                    "Crash-recovered run was replayed or incorrectly marked completed")
            old, _ = request(new_port, "POST", "/api/runs/" + run_id + "/approve",
                             {"approval_id": approval["id"], "approved": True},
                             token=new_status["session_token"])
            require(old == 400, "Old approval was reusable after crash")
            for _ in range(80):
                if not matching_containers(SANDBOX_LABEL + "=" + sid) and not runtime_volumes():
                    break
                time.sleep(0.2)
            confirm_absent(sid)
            require(not all_managed_containers() and not runtime_volumes(),
                    "Owned remote resource remains after controller reconciliation")
            require(Store(data).sandbox_owner() == owner and not Store(data).sandbox_pending(),
                    "Owner identity changed or pending intent was not cleared")
            print(json.dumps({
                "schema": "merlin-studio-native-owned-orphan-recovery/1",
                "real_docker": True, "real_studio_process_crash": True,
                "remote_sandbox_observed_before_crash": True,
                "remote_sandbox_survived_studio_crash": True,
                "restart_owner_reconciliation": True,
                "old_approval_replayed": False,
                "interrupted_run_replayed": False,
                "old_session_token_accepted": False,
                "pending_intents_after_recovery": 0,
                "sandbox_id": sid,
                "run_id": run_id,
                "model_calls": 0,
                "resources_removed": True,
                "target_host_qualified": False,
            }, sort_keys=True))
        finally:
            stop(proc)
            stop(restarted)
    require(not all_managed_containers() and not runtime_volumes(),
            "Orphan recovery test left managed resources")


if __name__ == "__main__":
    main()
