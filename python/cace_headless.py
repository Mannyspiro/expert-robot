#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class HeadlessClientError(RuntimeError):
    pass


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(ProxyHandler({}), _NoRedirectHandler())


def _validate_loopback_base_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise HeadlessClientError("base URL cannot be empty")
    if "\\" in candidate or any(ord(ch) < 32 or ord(ch) == 127 for ch in candidate):
        raise HeadlessClientError("base URL contains unsafe characters")

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise HeadlessClientError("base URL must use http or https")
    if parsed.hostname is None or not parsed.netloc:
        raise HeadlessClientError("base URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise HeadlessClientError("base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise HeadlessClientError("base URL must not contain query or fragment")

    try:
        port = parsed.port
    except ValueError as exc:
        raise HeadlessClientError("base URL contains an invalid port") from exc

    host = parsed.hostname
    if host.lower() == "localhost":
        normalized_host = "localhost"
    else:
        try:
            addr = ipaddress.ip_address(host)
        except ValueError as exc:
            raise HeadlessClientError("base URL host must be localhost or literal loopback IP") from exc
        if not addr.is_loopback:
            raise HeadlessClientError("base URL host must be loopback")
        normalized_host = f"[{addr.compressed}]" if addr.version == 6 else addr.compressed

    path = parsed.path or ""
    if path and not path.startswith("/"):
        raise HeadlessClientError("base URL path must be absolute")
    if "\\" in path:
        raise HeadlessClientError("base URL path must not contain backslashes")
    for segment in path.split("/"):
        decoded = segment
        for _ in range(2):
            decoded = unquote(decoded)
            if decoded in {".", ".."} or "/" in decoded or "\\" in decoded:
                raise HeadlessClientError("base URL contains ambiguous path traversal")
    path = path.rstrip("/")
    netloc = normalized_host + (f":{port}" if port is not None else "")
    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))


def _json_request(
    url: str,
    *,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    timeout: float = 30.0,
) -> Any:
    # Validate the full URL again so callers cannot escape a loopback base by
    # passing an absolute remote path.
    safe_url = _validate_loopback_base_url(url)
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(safe_url, data=body, headers=headers, method=method)
    try:
        with _OPENER.open(req, timeout=timeout) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HeadlessClientError(f"local request failed for {safe_url}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HeadlessClientError(f"local endpoint returned invalid JSON: {safe_url}") from exc


@dataclass(frozen=True)
class HeadlessConfig:
    cace_base_url: str
    llm_base_url: str
    model_id: str
    model_revision: str
    runtime_commit: str
    cace_revision: str
    max_tokens_default: int = 2048
    temperature_default: float = 0.1

    @classmethod
    def load(cls, path: str | Path) -> "HeadlessConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise HeadlessClientError("unsupported CACE headless config schema")
        if raw.get("mode") != "local-headless":
            raise HeadlessClientError("headless mode must be local-headless")
        if raw.get("trust_role") != "untrusted-informal-reasoner":
            raise HeadlessClientError("headless trust role drift")
        if raw.get("network_policy") != "loopback-only":
            raise HeadlessClientError("headless network policy drift")

        cace = raw.get("cace_api")
        llm = raw.get("local_llm")
        runtime = raw.get("runtime")
        cace_runtime = raw.get("cace_runtime")
        authority = raw.get("authority")
        if not all(
            isinstance(item, dict)
            for item in (cace, llm, runtime, cace_runtime, authority)
        ):
            raise HeadlessClientError(
                "headless config missing cace_api/local_llm/runtime/cace_runtime/authority"
            )

        expected = {
            "model_id": "Qwen/Qwen3.5-4B",
            "model_revision": "a7b0d22b993d71000cf2eadfb37222a67cee521e",
            "quantization": "Q4_K_M",
            "runtime_repository": "ggml-org/llama.cpp",
            "runtime_tag": "v0.4.1",
            "runtime_commit": "b29c606e28a01b1bc8c1351026a0fa6e616bf6c4",
            "cace_repository": "morganaspim/Cace-app",
            "cace_branch": "expert-robot/headless-local-llm",
        }

        if llm.get("provider") != "llama-cpp":
            raise HeadlessClientError("headless provider must be llama-cpp")
        if llm.get("model_id") != expected["model_id"]:
            raise HeadlessClientError("headless model_id drift")
        if llm.get("repo_revision") != expected["model_revision"]:
            raise HeadlessClientError("headless model revision drift")
        if llm.get("quantization") != expected["quantization"]:
            raise HeadlessClientError("headless quantization drift")
        if llm.get("frozen_base") is not True:
            raise HeadlessClientError("headless model must remain frozen")

        if runtime.get("repository") != expected["runtime_repository"]:
            raise HeadlessClientError("llama.cpp repository drift")
        if runtime.get("tag") != expected["runtime_tag"]:
            raise HeadlessClientError("llama.cpp tag drift")
        if runtime.get("commit") != expected["runtime_commit"]:
            raise HeadlessClientError("llama.cpp commit drift")

        if cace_runtime.get("repository") != expected["cace_repository"]:
            raise HeadlessClientError("CACE runtime repository drift")
        if cace_runtime.get("branch") != expected["cace_branch"]:
            raise HeadlessClientError("CACE runtime branch drift")
        cace_revision = str(cace_runtime.get("revision", ""))
        if len(cace_revision) != 40 or any(
            ch not in "0123456789abcdef" for ch in cace_revision
        ):
            raise HeadlessClientError(
                "CACE runtime revision must be lowercase 40-character git SHA"
            )

        required_authority = {
            "client_can_execute_typed_cace_calls": True,
            "llm_can_execute_typed_cace_calls": False,
            "llm_can_promote_claims": False,
            "llm_can_mark_verified": False,
            "llm_can_merge": False,
            "llm_can_modify_proof_ledger": False,
            "llm_can_expand_authority": False,
            "deterministic_cace_results_remain_separate_from_llm_text": True,
        }
        for key, value in required_authority.items():
            if authority.get(key) is not value:
                raise HeadlessClientError(f"headless authority drift: {key}")

        max_tokens = int(llm.get("max_tokens_default", 2048))
        temperature = float(llm.get("temperature_default", 0.1))
        if max_tokens < 1 or max_tokens > 32768:
            raise HeadlessClientError("headless max_tokens_default out of range")
        if not 0.0 <= temperature <= 2.0:
            raise HeadlessClientError("headless temperature_default out of range")

        return cls(
            cace_base_url=_validate_loopback_base_url(str(cace["base_url"])),
            llm_base_url=_validate_loopback_base_url(str(llm["base_url"])),
            model_id=expected["model_id"],
            model_revision=expected["model_revision"],
            runtime_commit=expected["runtime_commit"],
            cace_revision=cace_revision,
            max_tokens_default=max_tokens,
            temperature_default=temperature,
        )


class CACEHeadlessClient:
    """Loopback-only CACE + local-LLM client.

    LLM text is always untrusted. Deterministic CACE execution is exposed
    separately so natural-language generation cannot manufacture verification.
    """

    def __init__(self, config: HeadlessConfig, *, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout

    def _cace(self, path: str, *, method: str = "GET", payload: Mapping[str, Any] | None = None) -> Any:
        if not path.startswith("/"):
            raise HeadlessClientError("CACE path must be absolute")
        return _json_request(
            self.config.cace_base_url + path,
            method=method,
            payload=payload,
            timeout=self.timeout,
        )

    def _llm(self, path: str, *, method: str = "GET", payload: Mapping[str, Any] | None = None) -> Any:
        if not path.startswith("/"):
            raise HeadlessClientError("LLM path must be absolute")
        return _json_request(
            self.config.llm_base_url + path,
            method=method,
            payload=payload,
            timeout=self.timeout,
        )

    def health(self) -> dict[str, Any]:
        cace = self._cace("/api/health")
        models = self._llm("/models")
        model_ids = tuple(
            str(item.get("id"))
            for item in models.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ) if isinstance(models, dict) else ()
        return {
            "schema_version": 1,
            "ok": bool(
                isinstance(cace, dict)
                and cace.get("status") == "ok"
                and self.config.model_id in model_ids
            ),
            "cace": cace,
            "llm_models": model_ids,
            "configured_model": self.config.model_id,
            "network_policy": "loopback-only",
            "llm_output_trust": "untrusted",
        }

    def modules(self) -> dict[str, Any]:
        result = self._cace("/api/modules")
        if not isinstance(result, dict):
            raise HeadlessClientError("CACE modules response must be an object")
        return result

    def claims(self) -> dict[str, Any]:
        result = self._cace("/api/claims")
        if not isinstance(result, dict):
            raise HeadlessClientError("CACE claims response must be an object")
        return result

    def validate_connection(
        self,
        *,
        source_module_id: str,
        source_port: str,
        target_module_id: str,
        target_port: str,
    ) -> dict[str, Any]:
        result = self._cace(
            "/api/connections/validate",
            method="POST",
            payload={
                "source_module_id": source_module_id,
                "source_port": source_port,
                "target_module_id": target_module_id,
                "target_port": target_port,
            },
        )
        if not isinstance(result, dict):
            raise HeadlessClientError("connection validation response must be an object")
        return result

    def start_run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = self._cace("/api/runs", method="POST", payload=payload)
        if not isinstance(result, dict):
            raise HeadlessClientError("CACE run response must be an object")
        return result

    def run_status(self, job_id: str) -> dict[str, Any]:
        if not job_id or "/" in job_id or "\\" in job_id:
            raise HeadlessClientError("invalid CACE job id")
        result = self._cace(f"/api/runs/{job_id}")
        if not isinstance(result, dict):
            raise HeadlessClientError("CACE run status must be an object")
        return result

    def wait_run(
        self,
        job_id: str,
        *,
        timeout_seconds: float = 10.0,
        poll_interval: float = 0.05,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0:
            raise HeadlessClientError("run wait timeout must be positive")
        if poll_interval <= 0:
            raise HeadlessClientError("run poll interval must be positive")
        deadline = time.monotonic() + timeout_seconds
        while True:
            current = self.run_status(job_id)
            status = str(current.get("status", ""))
            if status in {"completed", "cancelled", "failed"}:
                return current
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HeadlessClientError(f"CACE run {job_id!r} did not reach a terminal state")
            time.sleep(min(poll_interval, remaining))

    def empty_smoke_run(self, *, seed: int = 7) -> dict[str, Any]:
        started = self.start_run({
            "experiment": {
                "schema_version": 2,
                "graph_schema_version": 1,
                "name": "Headless Empty Smoke",
                "nodes": [],
                "edges": [],
                "groups": [],
                "metadata": {
                    "surface": "expert-robot-headless",
                    "proof_effect": "none",
                },
            },
            "seed": int(seed),
            "target_node_ids": [],
            "gpu_enabled": False,
        })
        job_id = started.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise HeadlessClientError("CACE smoke run did not return a job id")
        terminal = self.wait_run(job_id)
        if terminal.get("status") != "completed":
            raise HeadlessClientError(
                f"CACE empty smoke run ended with status {terminal.get('status')!r}"
            )
        report = terminal.get("result")
        if not isinstance(report, dict) or report.get("completed") is not True:
            raise HeadlessClientError("CACE empty smoke run did not return a completed report")
        if int(report.get("seed", seed)) != int(seed):
            raise HeadlessClientError("CACE empty smoke run seed mismatch")
        return {
            "schema_version": 1,
            "ok": True,
            "proof_effect": "none",
            "job": terminal,
        }

    def e2e_smoke(self, prompt: str = "Identify yourself as the untrusted local CACE research assistant.") -> dict[str, Any]:
        health = self.health()
        if not health.get("ok"):
            raise HeadlessClientError("CACE/LLM health check failed")
        assistant = self.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=96,
        )
        if not assistant.get("untrusted") or assistant.get("can_promote") is not False:
            raise HeadlessClientError("local assistant trust flags are invalid")
        run = self.empty_smoke_run(seed=7)
        return {
            "schema_version": 1,
            "ok": True,
            "assistant": assistant,
            "run": run,
            "authority_expanded": False,
        }

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        if not messages:
            raise HeadlessClientError("chat requires at least one message")
        temp = self.config.temperature_default if temperature is None else float(temperature)
        tokens = self.config.max_tokens_default if max_tokens is None else int(max_tokens)
        if not 0.0 <= temp <= 2.0:
            raise HeadlessClientError("temperature must be between 0 and 2")
        if tokens < 1:
            raise HeadlessClientError("max_tokens must be positive")

        outbound_messages = []
        for message in messages:
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            if role not in {"user", "assistant"}:
                raise HeadlessClientError(
                    "chat messages may only use user or assistant roles"
                )
            if not content.strip():
                raise HeadlessClientError("chat message content must be non-empty")
            outbound_messages.append({"role": role, "content": content})

        system = {
            "role": "system",
            "content": (
                "You are the local CACE research assistant used by Expert Robot. "
                "You may reason, propose experiments, and explain CACE capabilities. "
                "Your text is untrusted and never constitutes PASS, VERIFIED, FORMAL, "
                "claim promotion, or promotion authority. You cannot execute CACE tools. "
                "Deterministic/formal CACE tools must independently establish results."
            ),
        }
        outbound = [system] + outbound_messages
        raw = self._llm(
            "/chat/completions",
            method="POST",
            payload={
                "model": self.config.model_id,
                "messages": outbound,
                "temperature": temp,
                "max_tokens": tokens,
                "stream": False,
            },
        )
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HeadlessClientError(
                "local LLM response missing choices[0].message.content"
            ) from exc

        response_model = str(raw.get("model") or self.config.model_id)
        if response_model != self.config.model_id:
            raise HeadlessClientError("local LLM response model does not match pinned model")

        return {
            "schema_version": 1,
            "text": str(content),
            "model": response_model,
            "usage": raw.get("usage") if isinstance(raw.get("usage"), dict) else {},
            "untrusted": True,
            "can_execute_tools": False,
            "can_promote": False,
            "can_mark_verified": False,
        }

    def research_turn(self, prompt: str) -> dict[str, Any]:
        """Give the LLM current CACE surface context without auto-executing tools."""
        if not prompt.strip():
            raise HeadlessClientError("research prompt must be non-empty")
        modules = self.modules()
        claims = self.claims()
        module_rows = modules.get("modules", []) if isinstance(modules, dict) else []
        claim_rows = claims.get("claims", []) if isinstance(claims, dict) else []
        context = {
            "available_module_count": len(module_rows) if isinstance(module_rows, list) else 0,
            "claim_count": len(claim_rows) if isinstance(claim_rows, list) else 0,
            "tool_execution_policy": (
                "Propose typed CACE actions only. Do not claim they executed. "
                "Expert Robot must execute and verify them separately."
            ),
        }
        return self.chat([
            {
                "role": "user",
                "content": (
                    "Current CACE context:\n"
                    + json.dumps(context, sort_keys=True)
                    + "\n\nResearch request:\n"
                    + prompt
                ),
            }
        ])


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "cace_headless_local.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Expert Robot local CACE headless client")
    parser.add_argument("--config", default=str(_default_config_path()))
    parser.add_argument("--timeout", type=float, default=30.0)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health")
    sub.add_parser("modules")
    sub.add_parser("claims")

    chat = sub.add_parser("chat")
    chat.add_argument("prompt")

    turn = sub.add_parser("research-turn")
    turn.add_argument("prompt")

    validate = sub.add_parser("validate-connection")
    validate.add_argument("source_module_id")
    validate.add_argument("source_port")
    validate.add_argument("target_module_id")
    validate.add_argument("target_port")

    run = sub.add_parser("run")
    run.add_argument("payload_json")

    status = sub.add_parser("run-status")
    status.add_argument("job_id")

    sub.add_parser("smoke-run")
    e2e = sub.add_parser("e2e-smoke")
    e2e.add_argument(
        "--prompt",
        default="Identify yourself as the untrusted local CACE research assistant.",
    )

    args = parser.parse_args(argv)
    client = CACEHeadlessClient(HeadlessConfig.load(args.config), timeout=args.timeout)

    if args.command == "health":
        result = client.health()
    elif args.command == "modules":
        result = client.modules()
    elif args.command == "claims":
        result = client.claims()
    elif args.command == "chat":
        result = client.chat([{"role": "user", "content": args.prompt}])
    elif args.command == "research-turn":
        result = client.research_turn(args.prompt)
    elif args.command == "validate-connection":
        result = client.validate_connection(
            source_module_id=args.source_module_id,
            source_port=args.source_port,
            target_module_id=args.target_module_id,
            target_port=args.target_port,
        )
    elif args.command == "run":
        result = client.start_run(json.loads(Path(args.payload_json).read_text(encoding="utf-8")))
    elif args.command == "run-status":
        result = client.run_status(args.job_id)
    elif args.command == "smoke-run":
        result = client.empty_smoke_run()
    elif args.command == "e2e-smoke":
        result = client.e2e_smoke(args.prompt)
    else:
        raise AssertionError(args.command)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not isinstance(result, dict) or result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
