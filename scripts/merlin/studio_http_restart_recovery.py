#!/usr/bin/env python3
"""Real subprocess crash/restart of pending Studio HTTP approval, no Docker needed.

An unapproved script must not execute, and restarting the server must invalidate
the old session token and pending action. A process SIGKILL is intentionally
used on only the test-owned loopback server, never on a user's process.
"""
from __future__ import annotations

import hashlib
import http.client
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
URL = re.compile(r"^Merlin Studio: http://127\.0\.0\.1:([0-9]+)/studio/$")
IMAGE = "local-fixture/python@sha256:" + "a" * 64


def require(ok, detail):
    if not ok:
        raise AssertionError(detail)


def request(port, method, path, token=None, body=None):
    headers = {"Host": "127.0.0.1:" + str(port)}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["X-Merlin-Token"] = token
    client = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        client.request(method, path, body=None if body is None else json.dumps(body),
                       headers=headers)
        response = client.getresponse()
        return response.status, json.loads(response.read(262144))
    finally:
        client.close()


def start(data_dir):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "MERLIN_PYTHON_BACKEND": "opensandbox",
           "MERLIN_SANDBOX_IMAGE": IMAGE, "MERLIN_SANDBOX_PORT": "8080"}
    process = subprocess.Popen(
        [sys.executable, "-B", str(STUDIO / "server.py"), "--port", "0",
         "--data-dir", str(data_dir)],
        cwd=STUDIO, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        end = time.monotonic() + 12
        while time.monotonic() < end:
            require(process.poll() is None, "Owned server terminated unexpectedly")
            ready, _, _ = select.select([process.stdout], [], [], .15)
            if ready:
                match = URL.fullmatch(process.stdout.readline().decode().strip())
                if match:
                    port = int(match.group(1))
                    for _ in range(20):
                        try:
                            status, _ = request(port, "GET", "/api/health")
                            if status == 200:
                                return process, port
                        except (OSError, http.client.HTTPException):
                            time.sleep(.1)
        raise AssertionError("Test-owned Studio server failed startup")
    except BaseException:
        stop(process)
        raise


def stop(process):
    if process is None:
        return
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=6)
    if process.stdout:
        process.stdout.close()
    if process.stderr:
        process.stderr.close()


def wait_approval(port, rid, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        code, value = request(port, "GET", "/api/runs/" + rid)
        require(code == 200, "Run polling rejected")
        run = value["run"]
        if run["status"] == "waiting_approval":
            return run["pending_approval"]
        require(run["status"] == "running", "Request finished without approval")
        time.sleep(.05)
    raise AssertionError("Pending approval never appeared")


def main():
    with tempfile.TemporaryDirectory(prefix="merlin-restart-approval-") as tmp:
        data = Path(tmp) / "durable"
        process = None
        try:
            process, port = start(data)
            code, state = request(port, "GET", "/api/status")
            require(code == 200 and state["capabilities"]["python_sandbox"],
                    "Sandbox mode not reported at startup")
            token = state["session_token"]
            code, value = request(port, "POST", "/api/conversations", token,
                                  {"title": "Crash recovery without replay"})
            require(code == 201, "Conversation create rejected")
            cid = value["conversation"]["id"]
            source = b"open('SHOULD_NEVER_EXECUTE','w').write('no')\n"
            workspace = data / "workspace"
            workspace.mkdir(exist_ok=True)
            (workspace / "answer.py").write_bytes(source)
            code, value = request(port, "POST", "/api/chat", token,
                                  {"conversation_id": cid, "message": "/python answer.py"})
            require(code == 202, "Unapproved chat request rejected")
            rid = value["run_id"]
            approval = wait_approval(port, rid)
            require(approval["tool"] == "run_python"
                    and approval["arguments"]["script_sha256"] == hashlib.sha256(source).hexdigest()
                    and approval["arguments"]["backend"] == "opensandbox",
                    "Pending source and backend binding differs")
            require(not (workspace / "SHOULD_NEVER_EXECUTE").exists(), "Script ran before approval")
            stop(process)
            process = None
            process, port = start(data)
            code, state = request(port, "GET", "/api/status")
            require(code == 200 and state["session_token"] != token,
                    "Server reused the previous session token")
            new_token = state["session_token"]
            code, value = request(port, "GET", "/api/runs/" + rid)
            require(code == 200 and value["run"]["status"] == "interrupted"
                    and value["run"]["pending_approval"] is None,
                    "Crash left a replayable pending approval")
            code, _ = request(port, "POST", "/api/runs/" + rid + "/approve",
                              new_token, {"approval_id": approval["id"], "approved": True})
            require(code == 400, "Old approval replayed after restart")
            code, _ = request(port, "POST", "/api/runs/" + rid + "/approve",
                              token, {"approval_id": approval["id"], "approved": True})
            require(code == 403, "Old session token remained valid")
            require(not (workspace / "SHOULD_NEVER_EXECUTE").exists(),
                    "Unapproved workspace script was executed")
            events = value["run"]["events"]
            require(any(e["type"] == "interrupted" for e in events)
                    and not any(e["type"] == "tool_started" for e in events),
                    "Restart did not retain correct nonexecution evidence")
            print(json.dumps({
                "schema": "merlin-studio-real-crash-recovery/1",
                "test_owned_process_sigkill": True, "server_restarted": True,
                "interrupted_pending_run": rid,
                "approved_source_hash": hashlib.sha256(source).hexdigest(),
                "stale_session_token_rejected": True,
                "stale_action_replay_rejected": True,
                "unapproved_execution_count": 0,
                "model_inference_calls": 0, "docker_execution": False
            }, sort_keys=True))
        finally:
            stop(process)


if __name__ == "__main__":
    main()
