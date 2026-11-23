#!/usr/bin/env python3
"""Run Studio's real local HTTP action approval/denial flow with OpenSandbox.

No language model, external web service or real user data. This integration
uses HTTP routes, session-token/Host boundaries, durable events/ArtifactRef,
and native Docker only in the separately configured disposable CI environment.
Not a rendered browser user-interaction test.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
import server as studio_server
from native_sandbox_acceptance import all_managed_containers, runtime_volumes, confirm_absent


def request(port, method, path, data=None, *, token=None, origin=None):
    raw = json.dumps(data, allow_nan=False).encode() if data is not None else None
    headers = {"Connection": "close"}
    if raw is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["X-Merlin-Token"] = token
    if origin:
        headers["Origin"] = origin
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        c.request(method, path, body=raw, headers=headers)
        r = c.getresponse()
        payload = r.read()
        return r.status, json.loads(payload)
    finally:
        c.close()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def wait_for(port, run_id, states, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, payload = request(port, "GET", "/api/runs/" + run_id)
        require(status == 200, "Cannot read run state")
        if payload["run"]["status"] in states:
            return payload["run"]
        time.sleep(0.04)
    raise AssertionError("Run failed to enter an expected state in time")


def start_run(port, token, cid, text):
    status, body = request(port, "POST", "/api/chat",
                           {"conversation_id": cid, "message": text}, token=token)
    require(status == 202 and body.get("run_id"), "Cannot start chat command")
    return body["run_id"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    args = p.parse_args()
    require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
            "Explicit OpenSandbox backend required")
    require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
            "Digest-pinned sandbox image required")
    before_containers, before_volumes = all_managed_containers(), runtime_volumes()
    require(not before_containers and not before_volumes, "Native CI runner not clean")
    receipt = {"schema": "merlin-native-studio-http-approval/1",
               "real_http": True, "real_docker": True,
               "interactive_browser_test": False, "model_calls": 0,
               "checks": [], "complete": False}
    with tempfile.TemporaryDirectory(prefix="merlin-http-native-") as directory:
        data_dir = Path(directory) / "data"
        srv = studio_server.create_server(data_dir=data_dir, start_bundled=False)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        port = srv.server_port
        token = None
        try:
            status, payload = request(port, "GET", "/api/status")
            require(status == 200 and payload.get("ready") is True,
                    "Studio HTTP status was not healthy")
            require(payload.get("capabilities", {}).get("python_sandbox") is True,
                    "Studio did not advertise configured sandbox")
            token = payload["session_token"]
            status, _ = request(port, "POST", "/api/conversations",
                                {"title": "blocked cross-origin"}, token=token,
                                origin="https://untrusted.invalid")
            require(status == 403, "Cross-origin Studio mutation was not rejected")
            status, convo = request(port, "POST", "/api/conversations",
                                    {"title": "Merlin native HTTP acceptance"}, token=token)
            require(status == 201, "Create conversation failed")
            cid = convo["conversation"]["id"]
            code = "print('MERLIN_HTTP_NATIVE_OK')\n"
            status, write = request(port, "POST", "/api/tool",
                                    {"tool": "write_file", "args": {
                                        "path": "native.py", "content": code}}, token=token)
            require(status == 200 and write.get("result", {}).get("artifact_ref"),
                    "Approved script fixture creation failed")
            source_hash = hashlib.sha256(code.encode()).hexdigest()

            # Denial must yield a recorded decision and never dispatch Docker.
            declined = start_run(port, token, cid, "/python native.py")
            pending = wait_for(port, declined, {"waiting_approval"})
            approval = pending.get("pending_approval") or {}
            binding = approval.get("arguments") or {}
            require(binding.get("backend") == "opensandbox"
                    and binding.get("sandbox_image") == os.environ["MERLIN_SANDBOX_IMAGE"]
                    and binding.get("script_sha256") == source_hash,
                    "HTTP pending approval did not bind backend, image and source")
            wrong, _ = request(port, "POST", "/api/runs/" + declined + "/approve",
                               {"approval_id": "incorrect", "approved": True}, token=token)
            require(wrong == 400, "Unmatched approval ID was accepted")
            status, _ = request(port, "POST", "/api/runs/" + declined + "/approve",
                                {"approval_id": approval["id"], "approved": False}, token=token)
            require(status == 200, "Approval denial was not recorded")
            done = wait_for(port, declined, {"completed", "failed"})
            require(done["status"] == "completed"
                    and any(e["type"] == "tool_denied" for e in done["events"])
                    and not any(e["type"] == "tool_started" for e in done["events"]),
                    "Denied script was executed or not auditable")
            require(not all_managed_containers() and not runtime_volumes(),
                    "Denial created Docker resources")
            receipt["checks"].append("denial_no_execution")

            # Cancelling an undecided action must not create Docker resources.
            cancelled = start_run(port, token, cid, "/python native.py")
            pending = wait_for(port, cancelled, {"waiting_approval"})
            pending_id = pending["pending_approval"]["id"]
            status, _ = request(port, "POST", "/api/runs/" + cancelled + "/cancel", {}, token=token)
            require(status == 200, "Pending cancellation was rejected")
            terminated = wait_for(port, cancelled, {"cancelled", "failed"})
            require(terminated["status"] == "cancelled", "Cancellation not durable")
            status, _ = request(port, "POST", "/api/runs/" + cancelled + "/approve",
                                {"approval_id": pending_id, "approved": True}, token=token)
            require(status == 400, "Stale approval was accepted after cancellation")
            require(not all_managed_containers() and not runtime_volumes(),
                    "Cancelled approval spawned Docker resources")
            receipt["checks"].append("cancel_pending_invalidates_approval")

            # Modified source after pending approval must be rejected before Docker.
            stale = start_run(port, token, cid, "/python native.py")
            pending = wait_for(port, stale, {"waiting_approval"})
            p_id = pending["pending_approval"]["id"]
            status, _ = request(port, "POST", "/api/tool",
                                {"tool": "write_file", "args": {
                                    "path": "native.py", "content": "print('changed')\n"}},
                                token=token)
            require(status == 200, "Cannot modify source fixture")
            status, _ = request(port, "POST", "/api/runs/" + stale + "/approve",
                                {"approval_id": p_id, "approved": True}, token=token)
            require(status == 200, "Could not deliver stale approval")
            stale_run = wait_for(port, stale, {"completed", "failed"})
            require(stale_run["status"] == "completed"
                    and any(e["type"] == "tool_error" for e in stale_run["events"])
                    and not any(e["type"] == "tool_result" for e in stale_run["events"]),
                    "Stale source approval bypassed hash verification")
            require(not all_managed_containers() and not runtime_volumes(),
                    "Stale source approval spawned Docker resources")
            receipt["checks"].append("stale_source_denied")

            # Real approved script dispatch through the full HTTP app flow.
            status, _ = request(port, "POST", "/api/tool",
                                {"tool": "write_file", "args": {
                                    "path": "native.py", "content": code}}, token=token)
            require(status == 200, "Failed to restore approved source bytes")
            allowed = start_run(port, token, cid, "/python native.py")
            pending = wait_for(port, allowed, {"waiting_approval"})
            approval = pending["pending_approval"]
            require(approval["arguments"]["script_sha256"] == source_hash,
                    "Allowed source hash differs from fixture")
            started = time.monotonic()
            status, _ = request(port, "POST", "/api/runs/" + allowed + "/approve",
                                {"approval_id": approval["id"], "approved": True}, token=token)
            require(status == 200, "Valid action approval failed")
            completed = wait_for(port, allowed, {"completed", "failed"}, timeout=40)
            require(completed["status"] == "completed", "Approved native command did not complete")
            events = [e for e in completed["events"] if e["type"] == "tool_result"]
            require(len(events) == 1 and events[0].get("artifact_ref"),
                    "Native tool result lacks canonical artifact reference")
            result = events[0]["result"]
            require(result.get("exit_code") == 0
                    and "MERLIN_HTTP_NATIVE_OK" in result.get("stdout", "")
                    and result.get("script_sha256") == source_hash
                    and result.get("os_sandbox") is True
                    and bool(result.get("sandbox_id")),
                    "HTTP-approved tool result does not attest actual sandbox execution")
            raw = srv.app.store.registry.read_artifact_ref(events[0]["artifact_ref"])["content"]
            persisted = json.loads(raw)
            require(persisted["result"].get("sandbox_id") == result["sandbox_id"],
                    "Persistent artifact differs from live sandbox identity")
            confirm_absent(result["sandbox_id"])
            require(not all_managed_containers() and not runtime_volumes(),
                    "Completed HTTP-approved task leaked a managed sandbox")
            receipt["checks"].append("real_http_approval_native_tool_and_artifact")
            receipt["approval_execution_seconds"] = round(time.monotonic() - started, 2)
            receipt["sandbox_id"] = result["sandbox_id"]
            receipt["script_sha256"] = source_hash

            # A graceful restart must not replay the already settled action.
            before_count = len(srv.app.store.conversation(cid)["messages"])
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=5)
        restarted = studio_server.create_server(data_dir=data_dir, start_bundled=False)
        restart_thread = threading.Thread(target=restarted.serve_forever, daemon=True)
        restart_thread.start()
        try:
            status, new_status = request(restarted.server_port, "GET", "/api/status")
            require(status == 200 and new_status["session_token"] != token,
                    "Server restart reused the mutation token")
            status, _ = request(restarted.server_port, "POST", "/api/conversations",
                                {"title": "replayed stale token"}, token=token)
            require(status == 403, "Stale session token still authorizes writes")
            status, after = request(restarted.server_port, "GET", "/api/conversations/" + cid)
            require(status == 200 and len(after["conversation"]["messages"]) == before_count,
                    "Restart replayed or dropped an approved native tool result")
            receipt["checks"].append("restart_no_replay_and_token_rotated")
        finally:
            restarted.shutdown()
            restarted.server_close()
            restart_thread.join(timeout=5)
        require(not all_managed_containers() and not runtime_volumes(),
                "Native HTTP test leaked managed runtime resources")
        receipt["complete"] = True
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"native_studio_http": "passed", "checks": receipt["checks"],
                      "interactive_browser_test": False,
                      "approval_execution_seconds": receipt["approval_execution_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
