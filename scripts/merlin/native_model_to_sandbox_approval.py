#!/usr/bin/env python3
"""Live local-model HTTP tool-call handshake into actual Merlin OpenSandbox Docker.

A deterministic loopback OpenAI-compatible fixture emits tool_calls; it is NOT
learned inference. Real Studio carries the call through its agent loop, waits
for explicit per-action approval over Studio HTTP, executes approved bytes in
OpenSandbox and sends the real result to the fixture for an assistant turn.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from native_sandbox_acceptance import all_managed_containers, runtime_volumes

MARKER = "MERLIN_MODEL_TO_SANDBOX_NATIVE_OK"
SOURCE = ("print('" + MARKER + "')\n").encode()
FILE = "model_approved.py"


class ScriptedLocalModel(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def respond(self, value):
        raw = json.dumps(value, allow_nan=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        self.respond({"data": [{"id": "merlin-deterministic-native-fixture"}]})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > 128000:
            self.send_error(400)
            return
        data = json.loads(self.rfile.read(length))
        messages = data.get("messages", [])
        with self.server.records_lock:
            self.server.requests_seen += 1
        if not isinstance(messages, list) or not messages:
            self.send_error(400)
            return
        tool_results = [m for m in messages if m.get("role") == "tool"]
        if not tool_results:
            offered = [x.get("function", {}).get("name") for x in data.get("tools", [])]
            if "run_python" not in offered or data.get("parallel_tool_calls") is not False:
                self.send_error(400)
                return
            reply = {"role": "assistant", "content": "",
                     "tool_calls": [{"id": "fixture-call-1", "type": "function",
                                     "function": {"name": "run_python",
                                                  "arguments": json.dumps({"path": FILE})}}]}
            with self.server.records_lock:
                self.server.tool_proposals += 1
        else:
            result = json.loads(tool_results[-1]["content"])
            if result.get("executed") is False and "declined" in result.get("error", ""):
                text = "MERLIN_MODEL_FIXTURE_DENIAL_ACK"
                decision = "denied"
            elif (result.get("os_sandbox") is True
                  and result.get("sandbox_provider") == "OpenSandbox"
                  and result.get("exit_code") == 0
                  and MARKER in result.get("stdout", "")
                  and result.get("script_sha256") == hashlib.sha256(SOURCE).hexdigest()):
                text = "MERLIN_MODEL_FIXTURE_RESULT_VERIFIED"
                decision = "approved"
            else:
                text = "MERLIN_MODEL_FIXTURE_REJECTED_INVALID_TOOL_EVIDENCE"
                decision = "invalid"
            reply = {"role": "assistant", "content": text}
            with self.server.records_lock:
                self.server.consumed_results.append(decision)
        self.respond({"id": "fixture-completion", "object": "chat.completion",
                      "model": "merlin-deterministic-native-fixture",
                      "choices": [{"index": 0, "finish_reason": "stop", "message": reply}]})


def run_case(port, token, *, decline):
    code, value = request(port, "POST", "/api/conversations",
                          {"title": "Native model fixture " + ("denied" if decline else "approved")},
                          token=token)
    require(code == 201, "Could not create independent model conversation")
    cid = value["conversation"]["id"]
    run_id = start_run(port, token, cid,
                       "Use the approved Python tool and summarize its actual observed result.")
    pending = wait_for(port, run_id, {"waiting_approval"}, timeout=20)
    approval = pending["pending_approval"]
    require(approval["tool"] == "run_python"
            and approval["arguments"]["script_sha256"] == hashlib.sha256(SOURCE).hexdigest()
            and approval["arguments"]["backend"] == "opensandbox"
            and approval["arguments"]["sandbox_image"] == os.environ["MERLIN_SANDBOX_IMAGE"],
            "Model-selected approval lost source/backend/image binding")
    require(not all_managed_containers() and not runtime_volumes(),
            "Model proposed a tool and ran code before user approval")
    code, result = request(port, "POST", "/api/runs/" + run_id + "/approve",
                           {"approval_id": approval["id"], "approved": not decline}, token=token)
    require(code == 200 and result["accepted"], "Explicit model-selected approval decision rejected")
    finished = wait_for(port, run_id, {"completed", "failed", "cancelled", "interrupted"}, timeout=35)
    require(finished["status"] == "completed", "Model-selected run failed after decision")
    types = [e["type"] for e in finished["events"]]
    require(types.count("model_request") == 2 and types.count("approval_required") == 1
            and types.count("approval_decided") == 1,
            "Agent model-to-approval-to-followup protocol has unexpected steps")
    require(types.count("tool_denied") == (1 if decline else 0)
            and types.count("tool_started") == (0 if decline else 1)
            and types.count("tool_result") == (0 if decline else 1),
            "Tool execution count differs from approval decision")
    target = "MERLIN_MODEL_FIXTURE_DENIAL_ACK" if decline else "MERLIN_MODEL_FIXTURE_RESULT_VERIFIED"
    code, response = request(port, "GET", "/api/conversations/" + cid)
    require(code == 200 and target in response["conversation"]["messages"][-1]["content"],
            "Model follow-up did not consume actual tool result")
    evidence = None
    if not decline:
        tool_event = next(e for e in finished["events"] if e["type"] == "tool_result")
        evidence = tool_event.get("artifact_ref")
        require(isinstance(evidence, dict) and evidence.get("sha256")
                and tool_event["result"]["script_sha256"] == hashlib.sha256(SOURCE).hexdigest()
                and tool_event["result"]["os_sandbox"] is True
                and MARKER in tool_event["result"]["stdout"], "Canonical native result evidence missing")
    require(not all_managed_containers() and not runtime_volumes(),
            "Model-selected test leaked Docker or sidecar resources")
    return {"run_id": run_id,
            "decision": "denied" if decline else "approved",
            "tool_result_count": types.count("tool_result"),
            "model_request_count": types.count("model_request"),
            "evidence_sha256": evidence["sha256"] if evidence else None,
            "tool_request_source_sha256": approval["arguments"]["script_sha256"],
            "final_assistant_text": target,
            "remote_resources_removed": True}


def main():
    require(os.environ.get("MERLIN_PYTHON_BACKEND") == "opensandbox",
            "The native model-selected test requires explicit OpenSandbox backend")
    require("@sha256:" in os.environ.get("MERLIN_SANDBOX_IMAGE", ""),
            "The native test requires a trusted immutable Python image digest")
    require(not all_managed_containers() and not runtime_volumes(),
            "Dirty CI Docker baseline")
    fixture = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedLocalModel)
    fixture.records_lock = threading.Lock()
    fixture.requests_seen = 0
    fixture.tool_proposals = 0
    fixture.consumed_results = []
    fixture_thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    fixture_thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="merlin-native-model-tool-") as tmp:
            studio = create_server(data_dir=Path(tmp) / "data", start_bundled=False)
            thread = threading.Thread(target=studio.serve_forever, daemon=True)
            thread.start()
            try:
                studio.app.workspace.mkdir(parents=True, exist_ok=True)
                (studio.app.workspace / FILE).write_bytes(SOURCE)
                port = studio.server_port
                code, status = request(port, "GET", "/api/status")
                require(code == 200 and status["capabilities"]["python_sandbox"] is True,
                        "Operator sandbox backend was unavailable")
                token = status["session_token"]
                model_url = "http://127.0.0.1:" + str(fixture.server_port) + "/v1/chat/completions"
                code, saved = request(port, "POST", "/api/settings",
                                      {"model_url": model_url,
                                       "model_id": "merlin-deterministic-native-fixture",
                                       "network_enabled": False, "python_enabled": True,
                                       "desktop_enabled": False}, token=token)
                require(code == 200 and saved["settings"]["model_url"] == model_url,
                        "Actual Studio refused a bounded local model endpoint")
                code, probe = request(port, "POST", "/api/model/probe", {}, token=token)
                require(code == 200 and probe["reachable"] is True
                        and probe["models"][0]["id"] == "merlin-deterministic-native-fixture",
                        "Local OpenAI-compatible model fixture failed real HTTP probe")
                denied = run_case(port, token, decline=True)
                approved = run_case(port, token, decline=False)
                require(not studio.app.store.sandbox_pending(),
                        "Canonical run left a pending sandbox intent")
                with fixture.records_lock:
                    count = fixture.requests_seen
                    proposals = fixture.tool_proposals
                    consumed = list(fixture.consumed_results)
                require(count == 4 and proposals == 2 and consumed == ["denied", "approved"],
                        "Model fixture did not receive exactly the expected four protocol requests")
                receipt = {
                    "schema": "merlin-model-to-native-sandbox-approval/1",
                    "real_docker": True,
                    "real_studio_loopback_http": True,
                    "real_openai_compatible_http_protocol": True,
                    "deterministic_fixture_not_learned_inference": True,
                    "real_model_weights_loaded": False,
                    "browser_clicks_tested": False,
                    "tool_proposals": proposals,
                    "model_http_completions": count,
                    "source_sha256": hashlib.sha256(SOURCE).hexdigest(),
                    "declined_case": denied,
                    "approved_case": approved,
                    "native_resources_removed": True,
                    "user_data_accessed": False,
                    "target_host_qualified": False,
                }
                print(json.dumps(receipt, sort_keys=True))
            finally:
                studio.shutdown()
                studio.server_close()
                thread.join(timeout=5)
    finally:
        fixture.shutdown()
        fixture.server_close()
        fixture_thread.join(timeout=5)
    require(not all_managed_containers() and not runtime_volumes(),
            "Model-selected sandbox acceptance left managed Docker resources")


if __name__ == "__main__":
    main()
