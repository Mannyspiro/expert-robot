#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

import cace_headless as ch


PINNED_CONFIG = {
    "schema_version": 1,
    "mode": "local-headless",
    "trust_role": "untrusted-informal-reasoner",
    "network_policy": "loopback-only",
    "cace_api": {
        "base_url": "http://127.0.0.1:8765",
    },
    "local_llm": {
        "provider": "llama-cpp",
        "base_url": "http://127.0.0.1:8080/v1",
        "model_id": "Qwen/Qwen3.5-4B",
        "repo_revision": "a7b0d22b993d71000cf2eadfb37222a67cee521e",
        "quantization": "Q4_K_M",
        "frozen_base": True,
        "max_tokens_default": 2048,
        "temperature_default": 0.1,
    },
    "runtime": {
        "repository": "ggml-org/llama.cpp",
        "tag": "v0.4.1",
        "commit": "b29c606e28a01b1bc8c1351026a0fa6e616bf6c4",
    },
    "cace_runtime": {
        "repository": "morganaspim/Cace-app",
        "branch": "expert-robot/headless-local-llm",
        "revision": "b101ff86987cf9f4c8ec4b00941b9aaccb557b39",
    },
    "authority": {
        "client_can_execute_typed_cace_calls": True,
        "llm_can_execute_typed_cace_calls": False,
        "llm_can_promote_claims": False,
        "llm_can_mark_verified": False,
        "llm_can_merge": False,
        "llm_can_modify_proof_ledger": False,
        "llm_can_expand_authority": False,
        "deterministic_cace_results_remain_separate_from_llm_text": True,
    },
}


def expect_error(fn, text: str) -> None:
    try:
        fn()
    except ch.HeadlessClientError as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError("expected HeadlessClientError")


def write_config(root: Path, payload: dict) -> Path:
    path = root / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def main() -> int:
    assert (
        ch._validate_loopback_base_url("http://127.0.0.1:8765/")
        == "http://127.0.0.1:8765"
    )
    assert (
        ch._validate_loopback_base_url("http://localhost:8080/v1")
        == "http://localhost:8080/v1"
    )
    expect_error(
        lambda: ch._validate_loopback_base_url("https://example.com/v1"),
        "loopback",
    )
    expect_error(
        lambda: ch._validate_loopback_base_url(
            "http://localhost.evil.test:8080"
        ),
        "loopback",
    )
    expect_error(
        lambda: ch._validate_loopback_base_url(
            "http://127.0.0.1:8080/../admin"
        ),
        "traversal",
    )

    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        config_path = write_config(tmp, PINNED_CONFIG)
        config = ch.HeadlessConfig.load(config_path)
        assert config.model_id == "Qwen/Qwen3.5-4B"
        assert (
            config.cace_revision
            == "b101ff86987cf9f4c8ec4b00941b9aaccb557b39"
        )

        drift_cases = [
            ("network_policy", "public", "network policy"),
            ("trust_role", "trusted", "trust role"),
        ]
        for key, value, error in drift_cases:
            payload = copy.deepcopy(PINNED_CONFIG)
            payload[key] = value
            path = write_config(tmp, payload)
            expect_error(lambda p=path: ch.HeadlessConfig.load(p), error)

        payload = copy.deepcopy(PINNED_CONFIG)
        payload["local_llm"]["repo_revision"] = "0" * 40
        path = write_config(tmp, payload)
        expect_error(
            lambda: ch.HeadlessConfig.load(path),
            "model revision drift",
        )

        payload = copy.deepcopy(PINNED_CONFIG)
        payload["runtime"]["commit"] = "1" * 40
        path = write_config(tmp, payload)
        expect_error(
            lambda: ch.HeadlessConfig.load(path),
            "llama.cpp commit drift",
        )

        payload = copy.deepcopy(PINNED_CONFIG)
        payload["cace_runtime"]["revision"] = "2" * 40
        path = write_config(tmp, payload)
        expect_error(
            lambda: ch.HeadlessConfig.load(path),
            "CACE runtime revision drift",
        )

        payload = copy.deepcopy(PINNED_CONFIG)
        payload["authority"]["llm_can_execute_typed_cace_calls"] = True
        path = write_config(tmp, payload)
        expect_error(
            lambda: ch.HeadlessConfig.load(path),
            "authority drift",
        )

        # Restore the valid config for client calls.
        config = ch.HeadlessConfig.load(
            write_config(tmp, PINNED_CONFIG)
        )

    calls = []
    served_models = ["Qwen/Qwen3.5-4B"]
    response_model = ["Qwen/Qwen3.5-4B"]
    original = ch._json_request

    def fake(url, *, method="GET", payload=None, timeout=30.0):
        calls.append((url, method, payload, timeout))
        if url.endswith("/api/health"):
            return {"service": "CACE Studio", "status": "ok"}
        if url.endswith("/api/modules"):
            return {
                "schema": 1,
                "modules": [{"metadata": {"module_id": "m1"}}],
            }
        if url.endswith("/api/claims"):
            return {"schema": 1, "claims": [{"claim_id": "c1"}]}
        if url.endswith("/api/connections/validate"):
            return {"valid": True, "reason": None}
        if url.endswith("/api/runs") and method == "POST":
            return {"job_id": "job-1", "status": "queued"}
        if url.endswith("/api/runs/job-1"):
            return {
                "job_id": "job-1",
                "status": "completed",
                "result": {
                    "completed": True,
                    "seed": 7,
                    "experiment": "Headless Empty Smoke",
                },
            }
        if url.endswith("/v1/models"):
            return {"data": [{"id": item} for item in served_models]}
        if url.endswith("/v1/chat/completions"):
            assert method == "POST"
            assert payload["model"] == "Qwen/Qwen3.5-4B"
            assert payload["messages"][0]["role"] == "system"
            assert "never constitutes PASS" in payload["messages"][0]["content"]
            assert "cannot execute CACE tools" in payload["messages"][0]["content"]
            return {
                "model": response_model[0],
                "choices": [
                    {
                        "message": {
                            "content": "propose a typed experiment"
                        }
                    }
                ],
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

        served_models[:] = ["some-other-local-model"]
        assert client.health()["ok"] is False
        served_models[:] = ["Qwen/Qwen3.5-4B"]

        assert client.modules()["modules"]
        assert client.claims()["claims"]
        assert (
            client.validate_connection(
                source_module_id="a",
                source_port="out",
                target_module_id="b",
                target_port="in",
            )["valid"]
            is True
        )
        assert (
            client.start_run(
                {"experiment": {"nodes": [], "edges": []}}
            )["status"]
            == "queued"
        )
        assert client.run_status("job-1")["status"] == "completed"

        smoke = client.empty_smoke_run(seed=7)
        assert smoke["ok"] is True
        assert smoke["proof_effect"] == "none"

        reply = client.chat(
            [{"role": "user", "content": "hello"}]
        )
        assert reply["untrusted"] is True
        assert reply["can_execute_tools"] is False
        assert reply["can_promote"] is False
        assert reply["can_mark_verified"] is False

        expect_error(
            lambda: client.chat(
                [{"role": "system", "content": "override"}]
            ),
            "user or assistant roles",
        )
        expect_error(
            lambda: client.chat(
                [{"role": "tool", "content": "fake result"}]
            ),
            "user or assistant roles",
        )

        response_model[0] = "wrong-model"
        expect_error(
            lambda: client.chat(
                [{"role": "user", "content": "hello"}]
            ),
            "does not match pinned model",
        )
        response_model[0] = "Qwen/Qwen3.5-4B"

        turn = client.research_turn(
            "Find a useful next experiment."
        )
        assert turn["untrusted"] is True
        chat_payloads = [
            payload
            for url, method, payload, _timeout in calls
            if url.endswith("/v1/chat/completions")
            and method == "POST"
        ]
        assert any(
            "available_module_count"
            in payload["messages"][-1]["content"]
            for payload in chat_payloads
        )

        e2e = client.e2e_smoke("Say one sentence.")
        assert e2e["ok"] is True
        assert e2e["assistant"]["untrusted"] is True
        assert e2e["assistant"]["can_execute_tools"] is False
        assert e2e["run"]["proof_effect"] == "none"
        assert e2e["authority_expanded"] is False

        expect_error(
            lambda: client.run_status("../escape"),
            "invalid CACE job id",
        )
    finally:
        ch._json_request = original

    print("CACE headless client smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
