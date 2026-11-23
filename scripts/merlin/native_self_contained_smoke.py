#!/usr/bin/env python3
"""Independent native acceptance of the extracted Merlin Studio ZIP, not a mock."""
import json
import re
import time
import urllib.request
import urllib.error

STUDIO = "http://127.0.0.1:18771"
MODEL = "http://127.0.0.1:8772"


def request(path, method="GET", value=None, token=None, base=STUDIO, timeout=5):
    data = None if value is None else json.dumps(value).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Merlin-Token"] = token
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.load(resp)


def ready(path, base=STUDIO, seconds=150):
    deadline = time.monotonic() + seconds
    error = "not ready"
    while time.monotonic() < deadline:
        try:
            status, data = request(path, base=base, timeout=4)
            if status == 200:
                return data
        except (OSError, ValueError) as exc:
            error = type(exc).__name__
        time.sleep(1)
    raise AssertionError(f"readiness failure: {path}: {error}")


def finished(run_id, seconds=160):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        _, result = request("/api/runs/" + run_id)
        state = result["run"]["status"]
        if state in ("completed", "failed", "cancelled", "interrupted"):
            return state, result
        time.sleep(1)
    raise AssertionError("run deadline exceeded")


status = ready("/api/status", seconds=60)
assert status.get("ready") is True, "Studio startup failed"
token = status["session_token"]
assert token, "session token missing"
code, created = request("/api/conversations", "POST", {"title": "Native ZIP test"}, token)
assert code == 201
cid = created["conversation"]["id"]
code, output = request("/api/chat", "POST", {"conversation_id": cid, "message": "/help"}, token)
assert code == 202
state, _ = finished(output["run_id"], 30)
assert state == "completed", f"offline command: {state}"
_, history = request("/api/conversations/" + cid)
assert len(history["conversation"]["messages"]) >= 2, "offline history missing"
models = ready("/v1/models", base=MODEL, seconds=180)
assert models.get("data") and any(m.get("id") == "local" for m in models["data"]), "real model unavailable"
code, settings = request("/api/settings", "POST", {
    "model_url": MODEL + "/v1/chat/completions",
    "model_id": "local",
    "network_enabled": False,
    "python_enabled": False,
    "desktop_enabled": False,
    "max_steps": 1,
    "max_output_tokens": 64,
    "model_timeout_seconds": 120,
    "tool_compatibility": "native"
}, token)
assert code == 200
code, probed = request("/api/model/probe", "POST", {}, token, timeout=15)
assert code == 200, "model probe failed"
code, output = request("/api/chat", "POST", {
    "conversation_id": cid,
    "message": "What is 2 + 2? Reply with a single digit, no other text."
}, token)
assert code == 202
state, body = finished(output["run_id"], 180)
assert state == "completed", f"generated chat: {state}, {body['run'].get('error')}"
_, history = request("/api/conversations/" + cid)
assistant = [m.get("content", "") for m in history["conversation"]["messages"] if m.get("role") == "assistant"]
assert assistant and re.search(r"\b4\b", assistant[-1]), "real GGUF arithmetic oracle failed"
print(json.dumps({
    "fresh_extract_http": "pass",
    "offline_command": "pass",
    "local_model_http": "pass",
    "model_generated_reference": "pass",
    "last_model_answer": assistant[-1][:100],
    "qualification_scope": "single-reference bounded smoke only"
}, sort_keys=True))
