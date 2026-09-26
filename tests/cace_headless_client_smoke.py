#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import cace_headless as ch


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except ch.HeadlessClientError as exc:
        assert text in str(exc)
    else:
        raise AssertionError("expected HeadlessClientError")


def main() -> int:
    assert ch._validate_loopback_base_url("http://127.0.0.1:8765/") == "http://127.0.0.1:8765"
    assert ch._validate_loopback_base_url("http://localhost:8080/v1") == "http://localhost:8080/v1"
    expect_error(lambda: ch._validate_loopback_base_url("https://example.com/v1"), "loopback")
    expect_error(lambda: ch._validate_loopback_base_url("http://localhost.evil.test:8080"), "loopback")
    expect_error(lambda: ch._validate_loopback_base_url("http://127.0.0.1:8080/../admin"), "traversal")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "cace_api": {"base_url": "http://127.0.0.1:8765"},
            "local_llm": {
                "base_url": "http://127.0.0.1:8080/v1",
                "model_id": "Qwen/Qwen3.5-4B",
                "max_tokens_default": 2048,
                "temperature_default": 0.1,
            },
        }), encoding="utf-8")
        config = ch.HeadlessConfig.load(path)

    calls = []
    original = ch._json_request

    def fake(url, *, method="GET", payload=None, timeout=30.0):
        calls.append((url, method, payload, timeout))
        if url.endswith("/api/health"):
            return {"service": "CACE Studio", "status": "ok"}
        if url.endswith("/api/modules"):
            return {"schema": 1, "modules": [{"metadata": {"module_id": "m1"}}]}
        if url.endswith("/api/claims"):
            return {"schema": 1, "claims": [{"claim_id": "c1"}]}
        if url.endswith("/api/connections/validate"):
            return {"valid": True, "reason": None}
        if url.endswith("/api/runs") and method == "POST":
            return {"job_id": "job-1", "status": "queued"}
        if url.endswith("/api/runs/job-1"):
            return {"job_id": "job-1", "status": "completed"}
        if url.endswith("/v1/models"):
            return {"data": [{"id": "Qwen/Qwen3.5-4B"}]}
        if url.endswith("/v1/chat/completions"):
            assert method == "POST"
            assert payload["model"] == "Qwen/Qwen3.5-4B"
            assert payload["messages"][0]["role"] == "system"
            assert "never constitutes PASS" in payload["messages"][0]["content"]
            return {
                "model": "Qwen/Qwen3.5-4B",
                "choices": [{"message": {"content": "propose a typed experiment"}}],
                "usage": {"total_tokens": 12},
            }
        raise AssertionError(url)

    ch._json_request = fake
    try:
        client = ch.CACEHeadlessClient(config, timeout=2.0)
        health = client.health()
        assert health["ok"] is True
        assert health["network_policy"] == "loopback-only"
        assert health["llm_output_trust"] == "untrusted"

        assert client.modules()["modules"]
        assert client.claims()["claims"]
        assert client.validate_connection(
            source_module_id="a",
            source_port="out",
            target_module_id="b",
            target_port="in",
        )["valid"] is True
        assert client.start_run({"experiment": {"nodes": [], "edges": []}})["status"] == "queued"
        assert client.run_status("job-1")["status"] == "completed"

        reply = client.chat([{"role": "user", "content": "hello"}])
        assert reply["untrusted"] is True
        assert reply["can_promote"] is False
        assert reply["can_mark_verified"] is False

        turn = client.research_turn("Find a useful next experiment.")
        assert turn["untrusted"] is True
        chat_payloads = [
            payload for url, method, payload, _timeout in calls
            if url.endswith("/v1/chat/completions") and method == "POST"
        ]
        assert any("available_module_count" in p["messages"][-1]["content"] for p in chat_payloads)

        expect_error(lambda: client.run_status("../escape"), "invalid CACE job id")
    finally:
        ch._json_request = original

    print("CACE headless client smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
