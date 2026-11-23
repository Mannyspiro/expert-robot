#!/usr/bin/env python3
"""End-to-end OpenBot companion smoke with a synthetic model (not real inference).

Starts the actual pinned OpenBot Node daemon, talks to a loopback model
fixture, checks one durable agent turn and recovery after an orderly restart.
All state lives in a temporary directory; no external requests are made.
"""
from __future__ import annotations

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

from run_openbot_companion import plan


class FakeModel(BaseHTTPRequestHandler):
    calls = 0

    def log_message(self, *_):
        pass

    def respond(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            self.respond({"data": [{"id": "merlin-airllm"}]})
        else:
            self.respond({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            return self.respond({"error": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 32768:
                raise ValueError("request size")
            payload = json.loads(self.rfile.read(length))
            if payload.get("model") != "merlin-airllm" or payload.get("stream") is not False:
                raise ValueError("model contract")
            if payload.get("response_format") != {"type": "json_object"}:
                raise ValueError("OpenBot structured call missing")
            if not isinstance(payload.get("messages"), list):
                raise ValueError("messages missing")
        except (TypeError, ValueError, KeyError):
            return self.respond({"error": "fixture rejected model call"}, 400)
        FakeModel.calls += 1
        self.respond({"choices": [{"message": {"role": "assistant",
                              "content": json.dumps({"reply": "MERLIN_OPENBOT_FIXTURE_OK"})}}]})


def query(port, path, *, method="GET", value=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    payload = json.dumps(value) if value is not None else None
    conn.request(method, path, payload, {"Content-Type": "application/json"})
    result = conn.getresponse()
    body = result.read()
    conn.close()
    return result.status, json.loads(body)


def port_available():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_openbot(args, cwd, env, port):
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("OpenBot process exited during startup")
        try:
            status, health = query(port, "/api/health")
            if status == 200 and health.get("online") is True and "merlin-airllm" in health.get("models", []):
                return process
        except (ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=4)
    raise RuntimeError("OpenBot did not establish the local fixture-model connection")


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="merlin-openbot-smoke-") as temporary:
        temp = Path(temporary)
        workspace = temp / "workspace"
        workspace.mkdir()
        fixture = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
        thread = threading.Thread(target=fixture.serve_forever, daemon=True)
        thread.start()
        process = None
        try:
            bot_port = port_available()
            args, cwd, env = plan(repo, model_port=fixture.server_port, bot_port=bot_port, data_dir=temp / "bot-data")
            process = start_openbot(args, cwd, env, bot_port)
            status, result = query(bot_port, "/api/chat", method="POST",
                                   value={"message": "Reply with the fixture contract", "model": "merlin-airllm",
                                          "workspace": str(workspace), "maxTurns": 1})
            if not (status == 200 and result.get("status") == "completed"
                    and result.get("reply") == "MERLIN_OPENBOT_FIXTURE_OK"):
                raise AssertionError("Actual OpenBot agent turn did not pass fixture: " + str(result)[:500])
            task = result.get("taskId")
            if not isinstance(task, str) or not task or FakeModel.calls != 1:
                raise AssertionError("Expected one durable task and one real loopback protocol call")
            stop(process)
            process = None
            process = start_openbot(args, cwd, env, bot_port)
            status, listed = query(bot_port, "/api/tasks")
            if status != 200 or task not in [x.get("id") for x in listed.get("tasks", [])]:
                raise AssertionError("OpenBot failed to restore the completed task on restart")
            print(json.dumps({"integration": "actual_OpenBot_with_synthetic_model",
                              "model_fixture_calls": FakeModel.calls, "task_restored": True,
                              "external_model_calls": 0, "real_inference": False}))
        finally:
            stop(process)
            fixture.shutdown()
            fixture.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    main()
