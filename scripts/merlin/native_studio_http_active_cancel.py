#!/usr/bin/env python3
"""Real HTTP-triggered cancellation of already executing Studio Python task.

Requires an ephemeral CI host running the exact reviewed OpenSandbox controller.
Waits until Docker independently observes the approved Python process, then
POSTs /api/runs/:id/cancel. Never treats the early HTTP acknowledgement as
proof of remote termination; requires separate container and volume cleanup.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from server import create_server
from native_studio_http_approval_acceptance import request, wait_for, start_run, require
from native_sandbox_acceptance import (
    SANDBOX_LABEL, all_managed_containers, matching_containers, runtime_volumes, docker
)


def main():
    require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
            "Real cancellation needs explicitly selected OpenSandbox")
    require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
            "Immutable sandbox image required")
    require(not all_managed_containers() and not runtime_volumes(),
            "CI Docker sandbox resource baseline must be empty")
    with tempfile.TemporaryDirectory(prefix="merlin-http-native-active-cancel-") as directory:
        srv = create_server(data_dir=Path(directory) / "data", start_bundled=False)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        port = srv.server_port
        try:
            code, status = request(port, "GET", "/api/status")
            require(code == 200 and status["capabilities"]["python_sandbox"],
                    "Studio sandbox mode was not reported")
            token = status["session_token"]
            code, value = request(port, "POST", "/api/conversations",
                                  {"title": "Running cancellation test"}, token=token)
            require(code == 201, "Could not create an isolated HTTP conversation")
            cid = value["conversation"]["id"]
            source = "import time\nprint('MERLIN_HTTP_LONG_RUNNING', flush=True)\ntime.sleep(90)\n"
            digest = hashlib.sha256(source.encode()).hexdigest()
            code, _ = request(port, "POST", "/api/tool",
                              {"tool": "write_file", "args": {
                                  "path": "long_running.py", "content": source}}, token=token)
            require(code == 200, "Cannot save approved long-running fixture")
            run_id = start_run(port, token, cid, "/python long_running.py")
            pending = wait_for(port, run_id, {"waiting_approval"}, timeout=15)
            approval = pending["pending_approval"]
            bound = approval["arguments"]
            require(bound["script_sha256"] == digest
                    and bound["backend"] == "opensandbox"
                    and bound["sandbox_image"] == os.environ["MERLIN_SANDBOX_IMAGE"],
                    "HTTP approval does not bind exact script/backend/image")
            code, _ = request(port, "POST", "/api/runs/" + run_id + "/approve",
                              {"approval_id": approval["id"], "approved": True}, token=token)
            require(code == 200, "Explicit HTTP approval was rejected")
            sandbox_id = None
            observed_at = None
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                for container in matching_containers(SANDBOX_LABEL):
                    try:
                        ps = docker("top", container, timeout=5)
                        info = json.loads(docker("inspect", container, timeout=5))[0]
                    except (RuntimeError, IndexError, ValueError):
                        continue
                    if "/tmp/merlin_approved.py" not in ps:
                        continue
                    sandbox_id = (info.get("Config", {}).get("Labels") or {}).get(SANDBOX_LABEL)
                    if sandbox_id:
                        observed_at = time.monotonic()
                        break
                if observed_at is not None:
                    break
                time.sleep(.15)
            require(observed_at is not None and sandbox_id,
                    "No real Docker-top evidence of a running approved Python script")
            code, response = request(port, "POST", "/api/runs/" + run_id + "/cancel",
                                     {}, token=token)
            require(code == 200 and response.get("accepted") is True,
                    "Actual running HTTP request was not cancelled")
            # HTTP cancellation is an early state update. The worker still
            # must interrupt remote execution and leave no resources behind.
            done = wait_for(port, run_id, {"cancelled", "failed"}, timeout=10)
            require(done["status"] == "cancelled", "Cancelled run reported success/failure instead")
            grace = time.monotonic() + 15
            while time.monotonic() < grace:
                with srv.app.threads_lock:
                    worker_active = run_id in srv.app.threads
                if not worker_active and not all_managed_containers() and not runtime_volumes():
                    break
                time.sleep(.15)
            with srv.app.threads_lock:
                worker_active = run_id in srv.app.threads
            require(not worker_active, "Studio worker did not finish after HTTP cancellation")
            require(not all_managed_containers() and not runtime_volumes(),
                    "HTTP-cancelled command leaked Docker/egress/managed-volume resources")
            code, value = request(port, "GET", "/api/runs/" + run_id)
            require(code == 200 and value["run"]["status"] == "cancelled",
                    "Run lost cancellation state")
            events = value["run"]["events"]
            require(any(e["type"] == "tool_started" for e in events),
                    "No durable record that the approved action actually started")
            require(not any(e["type"] == "tool_result" for e in events),
                    "Canceled command was incorrectly reported as completed tool output")
            replay, _ = request(port, "POST", "/api/runs/" + run_id + "/approve",
                                {"approval_id": approval["id"], "approved": True}, token=token)
            require(replay == 400, "Old approval could be reused after cancellation")
            elapsed = time.monotonic() - observed_at
            require(elapsed < 15, "Remote cleanup exceeded 15 seconds after HTTP cancellation")
            print(json.dumps({
                "schema": "merlin-studio-real-http-active-cancel/1",
                "real_http": True,
                "real_docker": True,
                "actual_script_observed_by_docker_top": True,
                "script_sha256": digest,
                "sandbox_id": sandbox_id,
                "run_id": run_id,
                "cancellation_latency_and_cleanup_s": round(elapsed, 2),
                "remote_main_egress_volume_removed": True,
                "no_host_fallback": True,
                "no_completed_tool_result": True,
                "model_inference_calls": 0,
                "real_browser_ui_tested": False
            }, sort_keys=True))
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=4)
    require(not all_managed_containers() and not runtime_volumes(),
            "Native HTTP cancellation left resources after server closure")


if __name__ == "__main__":
    main()
