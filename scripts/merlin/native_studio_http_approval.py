#!/usr/bin/env python3
"""End-to-end local HTTP approval and real OpenSandbox execution, no model.

Use only on ephemeral CI runners with a separately started pinned OpenSandbox
controller. This test talks to the *actual* Studio HTTP server and exercises
the full approval/denial pathway, then independently confirms Docker cleanup.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "portable" / "merlin_studio"))
sys.path.insert(0, str(HERE))
from server import create_server
from native_sandbox_acceptance import all_managed_containers, runtime_volumes


def request(port, method, path, *, token=None, body=None, origin=None):
    headers = {"Host": "127.0.0.1:" + str(port)}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["X-Merlin-Token"] = token
    if origin:
        headers["Origin"] = origin
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        response = conn.getresponse()
        data = response.read(262144)
        return response.status, json.loads(data)
    finally:
        conn.close()


def require(value, message):
    if not value:
        raise AssertionError(message)


def run_state(port, run_id, *, expected=None, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, value = request(port, "GET", "/api/runs/" + run_id)
        require(status == 200 and "run" in value, "HTTP run retrieval failed")
        run = value["run"]
        if expected is None and run["status"] in ("completed", "failed", "cancelled", "interrupted"):
            return run
        if expected is not None and run["status"] == expected:
            return run
        if expected is not None and run["status"] in ("completed", "failed", "cancelled", "interrupted"):
            raise AssertionError("Run terminated before " + expected + ": " + run["status"])
        time.sleep(0.05)
    raise AssertionError("Studio HTTP run status deadline exceeded")


def submit(port, token, cid, command="/python answer.py"):
    status, value = request(port, "POST", "/api/chat", token=token,
                            body={"conversation_id": cid, "message": command})
    require(status == 202 and isinstance(value.get("run_id"), str), "HTTP chat submission failed")
    return value["run_id"]


def main():
    if os.environ.get("MERLIN_PYTHON_BACKEND") != "opensandbox":
        raise AssertionError("CI must opt into isolated Python backend")
    image = os.environ.get("MERLIN_SANDBOX_IMAGE")
    require(image and "@sha256:" in image, "Immutable sandbox image required")
    require(not all_managed_containers() and not runtime_volumes(), "Dirty Docker start")
    with tempfile.TemporaryDirectory(prefix="merlin-http-approval-") as directory:
        root = Path(directory)
        server = create_server(port=0, data_dir=root / "data", start_bundled=False)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            code, status = request(port, "GET", "/api/status")
            require(code == 200 and status["capabilities"]["python_sandbox"] is True,
                    "HTTP status did not expose configured sandbox")
            token = status["session_token"]
            require(isinstance(token, str) and len(token) >= 32, "Missing per-session token")
            code, _ = request(port, "POST", "/api/conversations",
                              token="not-the-local-token", body={"title": "forbidden"})
            require(code == 403, "Missing token boundary")
            code, _ = request(port, "POST", "/api/conversations", token=token,
                              body={"title": "forbidden"}, origin="https://another.site")
            require(code == 403, "Missing Origin boundary")
            code, value = request(port, "POST", "/api/conversations",
                                  token=token, body={"title": "CI native approval"})
            require(code == 201, "Failed to create new conversation")
            cid = value["conversation"]["id"]
            workspace = server.app.workspace
            workspace.mkdir(parents=True, exist_ok=True)
            body = b"print('MERLIN_HTTP_APPROVAL_OK')\n"
            (workspace / "answer.py").write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            initial = all_managed_containers()
            before_volumes = runtime_volumes()
            require(not initial and not before_volumes, "CI began with managed containers")

            # Decline: an actual chat-created approval must not run code.
            denied_id = submit(port, token, cid)
            pending = run_state(port, denied_id, expected="waiting_approval")
            approval = pending["pending_approval"]
            require(approval["tool"] == "run_python", "Wrong approval tool")
            require(approval["arguments"]["script_sha256"] == digest, "Source approval digest changed")
            require(approval["arguments"]["backend"] == "opensandbox", "Backend absent from approval")
            require(approval["arguments"]["sandbox_image"] == image, "Image absent from approval")
            bad, _ = request(port, "POST", "/api/runs/" + denied_id + "/approve",
                             token=token, body={"approval_id": "wrong", "approved": True})
            require(bad == 400, "Mismatched approval identity accepted")
            code, _ = request(port, "POST", "/api/runs/" + denied_id + "/approve",
                              token=token, body={"approval_id": approval["id"], "approved": False})
            require(code == 200, "HTTP user denial rejected")
            terminal = run_state(port, denied_id)
            require(terminal["status"] == "completed", "Denied action did not complete without code")
            require(all_managed_containers() == initial and runtime_volumes() == before_volumes,
                    "Denied action unexpectedly left a remote sandbox")
            events = terminal["events"]
            require(any(x["type"] == "tool_denied" for x in events), "Denial evidence missing")
            require(not any(x["type"] == "tool_result" for x in events),
                    "Denied command yielded an execution result")

            # Approve: execute through real OpenSandbox and persist canonical receipt.
            approved_id = submit(port, token, cid)
            pending = run_state(port, approved_id, expected="waiting_approval")
            aid = pending["pending_approval"]["id"]
            code, _ = request(port, "POST", "/api/runs/" + approved_id + "/approve",
                              token=token, body={"approval_id": aid, "approved": True})
            require(code == 200, "Actual HTTP affirmative approval rejected")
            terminal = run_state(port, approved_id)
            require(terminal["status"] == "completed", "Approved real sandbox action did not complete")
            results = [x for x in terminal["events"] if x["type"] == "tool_result"]
            require(len(results) == 1, "Expected exactly one real tool result")
            result = results[0]["result"]
            require(result["exit_code"] == 0 and result["os_sandbox"] is True
                    and result["sandbox_provider"] == "OpenSandbox"
                    and result["script_sha256"] == digest
                    and "MERLIN_HTTP_APPROVAL_OK" in result["stdout"], "Approved result differs")
            require(result["sandbox_id"], "Missing native sandbox identity")
            ref = results[0].get("artifact_ref")
            require(isinstance(ref, dict) and ref.get("sha256"), "Canonical artifact receipt missing")
            require(all_managed_containers() == initial and runtime_volumes() == before_volumes,
                    "Approved execution left remote containers/volumes")
            # A decision is single-use and cannot be replayed through HTTP.
            replay, _ = request(port, "POST", "/api/runs/" + approved_id + "/approve",
                                token=token, body={"approval_id": aid, "approved": True})
            require(replay == 400, "Approval reused after execution")

            # A cancelled pending action cannot create a sandbox or later accept approval.
            cancelled_id = submit(port, token, cid)
            pending = run_state(port, cancelled_id, expected="waiting_approval")
            cancelled_approval = pending["pending_approval"]["id"]
            code, _ = request(port, "POST", "/api/runs/" + cancelled_id + "/cancel",
                              token=token, body={})
            require(code == 200, "HTTP pending cancellation failed")
            require(run_state(port, cancelled_id)["status"] == "cancelled", "Cancelled run not terminal")
            replay, _ = request(port, "POST", "/api/runs/" + cancelled_id + "/approve",
                                token=token, body={"approval_id": cancelled_approval, "approved": True})
            require(replay == 400, "Cancelled pending action accepted later approval")
            require(all_managed_containers() == initial and runtime_volumes() == before_volumes,
                    "Cancelled pending action leaked remote resources")

            print(json.dumps({"schema": "merlin-studio-http-opensandbox-acceptance/1",
                              "real_http": True, "real_docker": True,
                              "host_fallback": False, "real_browser_ui_tested": False,
                              "source_sha256": digest,
                              "canonical_artifact_sha256": ref["sha256"],
                              "affirmative_approval_executions": 1,
                              "denial_executions": 0, "cancelled_pending_executions": 0,
                              "invalid_and_replayed_approval_rejected": True,
                              "origin_and_session_token_rejected": True,
                              "remote_cleanup_verified": True}, sort_keys=True))
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()
            server.app.close()
    require(not all_managed_containers() and not runtime_volumes(),
            "Unowned sandbox resources after HTTP server stop")


if __name__ == "__main__":
    main()
