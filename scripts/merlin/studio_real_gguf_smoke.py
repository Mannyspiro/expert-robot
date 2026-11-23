#!/usr/bin/env python3
"""Bounded real GGUF inference through the unmodified Merlin Studio HTTP API.

This smoke uses an explicitly downloaded Apache-2.0 Qwen 0.5B checkpoint and
a source-pinned local CPU llama-server. It does not prove general model
quality, trained-tool reliability, self-improvement or production suitability.
No user files or private context are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
sys.path.insert(0, str(STUDIO))
from server import create_server
from native_studio_http_approval_acceptance import request, start_run, wait_for, require


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def peak_rss_kib(pid):
    if not pid:
        return None
    try:
        for line in Path("/proc", str(int(pid)), "status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Native local model GGUF inference through Studio")
    parser.add_argument("--model", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--port", type=int, default=8772)
    parser.add_argument("--model-id", default="merlin-qwen05-smoke")
    args = parser.parse_args(argv)
    model_path = Path(args.model).resolve(strict=True)
    require(model_path.is_file() and 350_000_000 < model_path.stat().st_size < 650_000_000,
            "Expected bounded Qwen2.5 0.5B Q4_K_M GGUF model size")
    with model_path.open("rb") as source:
        require(source.read(4) == b"GGUF", "Downloaded file is not a GGUF checkpoint")
    require(os.environ.get("MERLIN_PYTHON_BACKEND", "host") == "host",
            "Real model-only smoke must not enable Python sandbox or host tools")
    report = {
        "schema": "merlin-studio-real-weight-cpu-smoke/1",
        "model_repository": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "model_revision": "9217f5db79a29953eb74d5343926648285ec7e67",
        "model_filename": model_path.name,
        "model_bytes": model_path.stat().st_size,
        "model_sha256": file_sha256(model_path),
        "model_license": "Apache-2.0",
        "llama_cpp_commit": os.environ.get("MERLIN_LLAMA_CPP_SHA", "unverified"),
        "cpu_only": True, "host": "GitHub ephemeral Linux",
        "real_model_weights": True,
        "real_studio_model_http": True,
        "tools_enabled": False, "cloud_inference_calls": 0,
        "results": [], "complete": False
    }
    cases = [
        {"name": "integer_arithmetic", "prompt": "What is 2 + 2? Reply using one digit and no other words.", "oracle": "4"},
        {"name": "known_capital", "prompt": "What is the capital of France? Reply with the city name only.", "oracle": "paris"}
    ]
    with tempfile.TemporaryDirectory(prefix="merlin-qwen-real-smoke-") as directory:
        srv = create_server(data_dir=Path(directory) / "data", start_bundled=False)
        worker = threading.Thread(target=srv.serve_forever, daemon=True)
        worker.start()
        try:
            port = srv.server_port
            status, ready = request(port, "GET", "/api/status")
            require(status == 200 and ready.get("ready"), "Merlin Studio did not initialize")
            token = ready["session_token"]
            model_url = "http://127.0.0.1:" + str(args.port) + "/v1/chat/completions"
            status, response = request(port, "POST", "/api/settings", {
                "model_url": model_url, "model_id": args.model_id,
                "network_enabled": False, "python_enabled": False,
                "desktop_enabled": False, "max_steps": 2,
                "max_output_tokens": 64, "model_timeout_seconds": 70,
                "tool_compatibility": "native"}, token=token)
            require(status == 200, "Studio rejected bounded inference-only settings")
            status, probe = request(port, "POST", "/api/model/probe", {}, token=token)
            require(status == 200, "Studio could not probe local inference endpoint")
            report["model_probe"] = probe
            for case in cases:
                status, conversation = request(port, "POST", "/api/conversations",
                                               {"title": "Real model " + case["name"]}, token=token)
                require(status == 201, "Cannot create isolated real-model conversation")
                conversation_id = conversation["conversation"]["id"]
                start = time.monotonic()
                rid = start_run(port, token, conversation_id, case["prompt"])
                terminal = wait_for(port, rid, {"completed", "failed"}, timeout=150)
                elapsed = time.monotonic() - start
                status, persisted = request(port, "GET", "/api/conversations/" + conversation_id)
                require(status == 200, "Cannot retrieve actual model response")
                messages = persisted["conversation"]["messages"]
                answer = messages[-1]["content"] if messages else ""
                normalized = re.sub(r"[^a-z0-9]", "", answer.lower())
                correct = normalized == case["oracle"]
                tool_events = [e["type"] for e in terminal["events"]
                               if e["type"].startswith("tool_")]
                report["results"].append({
                    "case": case["name"], "prompt": case["prompt"],
                    "expected_normalized_answer": case["oracle"],
                    "model_answer": answer[:500], "normalized": normalized[:200],
                    "correct": correct, "run_status": terminal["status"],
                    "run_error": terminal.get("error"),
                    "model_http_seconds": round(elapsed, 3),
                    "tool_events": tool_events,
                    "run_id": rid
                })
                if tool_events:
                    raise AssertionError("Inference-only smoke unexpectedly invoked tools")
            report["model_process_peak_rss_kib"] = peak_rss_kib(os.environ.get("MERLIN_LLAMA_SERVER_PID"))
            report["correct_answers"] = sum(1 for case in report["results"] if case["correct"])
            report["total_cases"] = len(cases)
            report["complete"] = all(
                case["correct"] and case["run_status"] == "completed"
                for case in report["results"])
        finally:
            srv.shutdown()
            worker.join(timeout=5)
            srv.server_close()
            report_file = Path(args.report)
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    require(report["complete"], "Real model failed bounded reference-answer acceptance")
    print(json.dumps({
        "real_model_inference": "pass",
        "model_sha256": report["model_sha256"],
        "correct": report["correct_answers"],
        "total": report["total_cases"],
        "peak_rss_kib": report["model_process_peak_rss_kib"]
    }, sort_keys=True))


if __name__ == "__main__":
    main()
