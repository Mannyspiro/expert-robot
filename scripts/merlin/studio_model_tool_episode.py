#!/usr/bin/env python3
"""Real Studio HTTP + local model protocol + explicit Python approval episode.

The local "model" is a deterministic synthetic OpenAI-compatible HTTP fixture:
it is NOT a real inference engine, model weights, training or quality benchmark.
The tool, human approval decision, host worker, canonical artifact and model's
second HTTP turn are real, on an isolated disposable CI runner.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import uuid

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from server import create_server
from native_studio_http_approval_acceptance import request, wait_for, start_run, require


class FixtureModelHandler(BaseHTTPRequestHandler):
    requests = []
    lock = threading.Lock()
    response_model = "merlin-controlled-fixture"

    def log_message(self, *_):
        pass

    def emit(self, status, value):
        body = json.dumps(value, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            return self.emit(200, {"object": "list", "data": [
                {"id": self.response_model, "object": "model"}]})
        return self.emit(404, {"error": "fixture endpoint not found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.emit(404, {"error": "fixture endpoint not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 100000:
                raise ValueError("model request exceeds fixture budget")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or body.get("model") != self.response_model or body.get("stream") is not False:
                raise ValueError("unexpected local model protocol")
            messages = body.get("messages", [])
            if not isinstance(messages, list) or not messages:
                raise ValueError("messages missing")
            with type(self).lock:
                type(self).requests.append({"message_roles": [x.get("role") for x in messages],
                                            "tools_declared": len(body.get("tools", []))})
            final_tool = next((m for m in reversed(messages) if m.get("role") == "tool"), None)
            if final_tool is None:
                declared = {item.get("function", {}).get("name") for item in body.get("tools", [])}
                if "run_python" not in declared:
                    raise ValueError("Studio must explicitly declare Python before model selection")
                last_user = next((str(m.get("content", "")) for m in reversed(messages)
                                  if m.get("role") == "user"), "")
                chosen = "denied.py" if "deny" in last_user.lower() else "approved.py"
                response = {"role": "assistant", "content": "An approved Python action is required.",
                            "tool_calls": [{"id": uuid.uuid4().hex, "type": "function",
                                            "function": {"name": "run_python",
                                                         "arguments": json.dumps({"path": chosen})}}]}
            else:
                value = json.loads(final_tool.get("content", "{}"))
                if "MERLIN_MODEL_TOOL_RESULT_42" in value.get("stdout", ""):
                    response = {"role": "assistant",
                                "content": "Verified the approved local tool output: 42."}
                elif value.get("executed") is False:
                    response = {"role": "assistant",
                                "content": "The human declined execution; no code ran."}
                else:
                    raise ValueError("model did not receive the expected actual tool result")
            return self.emit(200, {"id": "merlin-model-fixture", "object": "chat.completion",
                                   "model": self.response_model, "choices": [
                                       {"index": 0, "finish_reason": "stop", "message": response}]})
        except (ValueError, KeyError, IndexError, TypeError):
            return self.emit(400, {"error": "rejected synthetic model protocol"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    # Never accidentally reuse the target host's opted-in OpenSandbox settings.
    require(os.environ.get("MERLIN_PYTHON_BACKEND", "host") == "host",
            "Model fixture must run in a disposable host worker mode only")
    FixtureModelHandler.requests = []
    model = ThreadingHTTPServer(("127.0.0.1", 0), FixtureModelHandler)
    model_thread = threading.Thread(target=model.serve_forever, daemon=True)
    model_thread.start()
    server = None
    server_thread = None
    report = {"schema": "merlin-studio-controlled-model-tool-episode/1",
              "local_model_fixture": True, "real_inference": False,
              "real_local_http": True, "actual_user_approval_api": True,
              "model_weights_used": False, "model_provider_spend_usd": 0,
              "actual_host_python_worker": True, "actual_docker": False,
              "checks": [], "complete": False}
    try:
        with tempfile.TemporaryDirectory(prefix="merlin-model-selected-tool-") as directory:
            data_dir = Path(directory) / "studio"
            server = create_server(data_dir=data_dir, start_bundled=False)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            port = server.server_port
            code, status = request(port, "GET", "/api/status")
            require(code == 200, "Studio did not start")
            token = status["session_token"]
            model_url = "http://127.0.0.1:" + str(model.server_port) + "/v1/chat/completions"
            code, _ = request(port, "POST", "/api/settings", {
                "model_url": model_url, "model_id": FixtureModelHandler.response_model,
                "python_enabled": True, "network_enabled": False,
                "desktop_enabled": False, "max_steps": 4,
                "model_timeout_seconds": 30,
                "tool_compatibility": "native"}, token=token)
            require(code == 200, "Studio rejected the bounded local model settings")
            code, _ = request(port, "POST", "/api/model/probe", {}, token=token)
            require(code == 200, "Studio local model fixture probe failed")
            code, c = request(port, "POST", "/api/conversations",
                              {"title": "Controlled model-selected actions"}, token=token)
            require(code == 201, "Cannot create isolated model conversation")
            cid = c["conversation"]["id"]
            allowed_source = "print('MERLIN_MODEL_TOOL_RESULT_42')\n"
            denied_source = (
                "from pathlib import Path\n"
                "Path('DENIED_MODEL_SCRIPT_MARKER').write_text('unapproved')\n")
            for name, text in [("approved.py", allowed_source), ("denied.py", denied_source)]:
                code, response = request(port, "POST", "/api/tool", {
                    "tool": "write_file", "args": {"path": name, "content": text}}, token=token)
                require(code == 200 and response.get("result", {}).get("artifact_ref"),
                        "Manual setup of synthetic workspace file failed")

            # First model call must autonomously select the approved Python
            # tool and wait for a human decision; no code before the decision.
            approved_run = start_run(port, token, cid,
                                    "Use your local Python tool to compute the approved fixture")
            pending = wait_for(port, approved_run, {"waiting_approval"}, timeout=12)
            approval = pending["pending_approval"]
            binding = approval["arguments"]
            require(approval["tool"] == "run_python"
                    and binding["path"] == "approved.py"
                    and binding["script_sha256"] == hashlib.sha256(allowed_source.encode()).hexdigest(),
                    "Model-selected action did not bind the approved source")
            require(not any(e["type"] == "tool_started" for e in pending["events"]),
                    "Model-selected script started before approval")
            code, _ = request(port, "POST", "/api/runs/" + approved_run + "/approve",
                              {"approval_id": "wrong-id", "approved": True}, token=token)
            require(code == 400, "Incorrect human approval identity accepted")
            code, _ = request(port, "POST", "/api/runs/" + approved_run + "/approve",
                              {"approval_id": approval["id"], "approved": True}, token=token)
            require(code == 200, "Human approval did not resume model-selected tool")
            completed = wait_for(port, approved_run, {"completed", "failed"}, timeout=20)
            require(completed["status"] == "completed", "Model-selected approved run failed: " + str(completed.get("error")))
            events = [e for e in completed["events"] if e["type"] == "tool_result"]
            require(len(events) == 1 and events[0]["tool"] == "run_python"
                    and "MERLIN_MODEL_TOOL_RESULT_42" in events[0]["result"]["stdout"],
                    "Model-selected tool result was not observed")
            artifact = events[0].get("artifact_ref")
            require(isinstance(artifact, dict) and artifact.get("sha256"),
                    "Canonical ArtifactRef receipt missing")
            code, persisted = request(port, "GET", "/api/conversations/" + cid)
            require(code == 200 and "Verified the approved local tool output: 42." in
                    persisted["conversation"]["messages"][-1]["content"],
                    "Model did not receive the actual tool result before responding")
            report["checks"].append("model_tool_call_requires_human_approval")
            report["checks"].append("real_worker_artifact_and_model_second_turn")

            # A second model-selected Python action is denied; fixture must
            # observe the denial and return a nonexecution answer.
            denied_run = start_run(port, token, cid, "Please deny running the next Python fixture")
            pending = wait_for(port, denied_run, {"waiting_approval"}, timeout=12)
            approval = pending["pending_approval"]
            require(approval["arguments"]["path"] == "denied.py",
                    "The denied model tool request was not source-bound")
            code, _ = request(port, "POST", "/api/runs/" + denied_run + "/approve",
                              {"approval_id": approval["id"], "approved": False}, token=token)
            require(code == 200, "Human refusal of model tool was rejected")
            done = wait_for(port, denied_run, {"completed", "failed"}, timeout=12)
            require(done["status"] == "completed" and
                    any(e["type"] == "tool_denied" for e in done["events"]) and
                    not any(e["type"] == "tool_result" for e in done["events"]),
                    "Declined model-selected code was falsely reported executed")
            require(not (server.app.workspace / "DENIED_MODEL_SCRIPT_MARKER").exists(),
                    "Declined model-selected code actually ran")
            code, persisted = request(port, "GET", "/api/conversations/" + cid)
            require(code == 200 and "The human declined execution; no code ran." in
                    persisted["conversation"]["messages"][-1]["content"],
                    "Local model did not observe refusal")
            report["checks"].append("model_tool_denial_never_executes")
            report["checks"].append("model_observed_refusal_in_second_turn")

            require(len(FixtureModelHandler.requests) == 4,
                    "Expected two tool requests and two model follow-up responses")
            report.update({
                "model_http_calls": len(FixtureModelHandler.requests),
                "model_saw_actual_result": True,
                "model_saw_human_denial": True,
                "approved_script_sha256": binding["script_sha256"],
                "canonical_artifact_sha256": artifact["sha256"],
                "approved_run_id": approved_run, "denied_run_id": denied_run,
                "approved_tool_executions": 1, "denied_tool_executions": 0,
                "complete": True})
    finally:
        if server is not None:
            server.shutdown()
            if server_thread is not None:
                server_thread.join(timeout=5)
            server.server_close()
        model.shutdown()
        model_thread.join(timeout=5)
        model.server_close()
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    require(report["complete"], "Model-selected episode did not pass")
    print(json.dumps({"model_selected_tool_episode": "pass",
                      "checks": report["checks"],
                      "model_fixture_calls": report["model_http_calls"],
                      "real_model": False}, sort_keys=True))


if __name__ == "__main__":
    main()
