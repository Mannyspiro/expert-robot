#!/usr/bin/env python3
"""Native ZIP acceptance with bounded, non-authorizing failure diagnostics.

The primary /help then arithmetic conversation and its standalone-4 oracle are
unchanged. Secondary probes never rescue that oracle. Only synthetic answer
previews and allowlisted metadata are emitted; no status/settings dump, token,
tool arguments, inventory, error body or reasoning field is retained.
"""
import hashlib
import http.client
import json
import re
import socket
import sys
import threading
import time

STUDIO = "http://127.0.0.1:18771"
MODEL = "http://127.0.0.1:8772"
PROMPT = "What is 2 + 2? Reply with a single digit, no other text."
MAX_BODY = 2 * 1024 * 1024
MAX_PREVIEW = 512
MAX_EVENTS = 256
MAX_REPORT = 16 * 1024
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
STATES = TERMINAL | {"running", "waiting_approval", "deadline_exceeded"}
EVENT_TYPES = {"started", "completed", "failed", "cancelled", "interrupted",
               "model_request", "model_tool_adapter", "assistant_note",
               "tool_denied", "tool_started", "tool_result", "tool_error",
               "approval_required", "approval_decided"}


class SmokeFailure(Exception):
    """A fixed diagnostic code; never an upstream error/body string."""


def require(value, code):
    if not value:
        raise SmokeFailure(code)


def request(path, method="GET", value=None, token=None, base=STUDIO, timeout=5):
    """Direct fixed-loopback HTTP, bounded body and total wall-clock deadline."""
    require(base in (STUDIO, MODEL) and path.startswith("/")
            and not path.startswith("//") and "\r" not in path and "\n" not in path,
            "invalid_loopback_request")
    require(method in ("GET", "POST") and 0 < timeout <= 180, "invalid_request_budget")
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection("127.0.0.1", 18771 if base == STUDIO else 8772,
                                            timeout=timeout)
    response = channel = None
    expired = threading.Event()

    def remaining():
        value = deadline - time.monotonic()
        require(value > 0 and not expired.is_set(), "http_deadline")
        return value

    def abort():
        expired.set()
        if channel is not None:
            try:
                channel.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()

    timer = threading.Timer(timeout, abort)
    timer.daemon = True
    timer.start()
    try:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Merlin-Token"] = token
        data = None if value is None else json.dumps(value).encode()
        connection.connect()
        channel = connection.sock
        channel.settimeout(remaining())
        connection.request(method, path, body=data, headers=headers)
        channel.settimeout(remaining())
        response = connection.getresponse()
        require(response.status in (200, 201, 202), "http_status_rejected")
        lengths = response.headers.get_all("Content-Length", [])
        require(len(lengths) <= 1, "ambiguous_response_length")
        if lengths:
            require(lengths[0].isascii() and lengths[0].isdigit()
                    and len(lengths[0]) <= 20 and int(lengths[0]) <= MAX_BODY,
                    "response_body_limit")
        chunks, size = [], 0
        while not response.isclosed():
            channel.settimeout(remaining())
            block = response.read1(min(65536, MAX_BODY + 1 - size))
            if not block:
                break
            size += len(block)
            require(size <= MAX_BODY, "response_body_limit")
            chunks.append(block)
        remaining()
        require(not lengths or size == int(lengths[0]), "short_response_body")
        result = json.loads(b"".join(chunks))
        require(isinstance(result, dict), "malformed_response_object")
        remaining()
        return response.status, result
    finally:
        timer.cancel()
        if response is not None:
            response.close()
        connection.close()


def ready(path, base=STUDIO, seconds=150):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            code, data = request(path, base=base, timeout=min(4, deadline - time.monotonic()))
            if code == 200:
                return data
        except (OSError, ValueError, http.client.HTTPException, SmokeFailure):
            pass
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise SmokeFailure("readiness_deadline")


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value),
            "malformed_local_identity")
    return value


def finished(run_id, seconds=160):
    run_id = identifier(run_id)
    deadline = time.monotonic() + seconds
    result = {}
    while time.monotonic() < deadline:
        _, result = request("/api/runs/" + run_id, timeout=min(5, deadline - time.monotonic()))
        state = result["run"]["status"]
        require(isinstance(state, str) and state in STATES, "malformed_completion_state")
        if state in TERMINAL:
            return state, result
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    return "deadline_exceeded", result


def event_summary(body):
    run = body.get("run", {}) if isinstance(body, dict) else {}
    events = run.get("events", []) if isinstance(run, dict) else []
    if not isinstance(events, list):
        return {"malformed": True, "counted": 0, "types": {}}
    counts = {}
    for event in events[:MAX_EVENTS]:
        kind = event.get("type") if isinstance(event, dict) else None
        kind = kind if isinstance(kind, str) and kind in EVENT_TYPES else "other"
        counts[kind] = counts.get(kind, 0) + 1
    return {"counted": min(len(events), MAX_EVENTS), "truncated": len(events) > MAX_EVENTS,
            "types": counts}


def answer_summary(content, token=None):
    if not isinstance(content, str):
        return {"content_state": "missing" if content is None else "malformed",
                "text": "", "length_chars": None, "sha256": None}
    raw = content.encode("utf-8")
    # Some engines place reasoning markup inside content rather than a separate
    # field. Retain only its length/digest, never a possibly hidden-text preview.
    reasoning = bool(re.search(r"<\s*/?\s*(?:think|analysis|reasoning)\b|\[/?(?:THINK|analysis)\]",
                               content, re.IGNORECASE))
    visible = "" if reasoning else (content.replace(token, "[redacted]") if token else content)
    return {"content_state": "text" if content else "empty", "text": visible[:MAX_PREVIEW],
            "length_chars": len(content), "sha256": hashlib.sha256(raw).hexdigest(),
            "preview_truncated": len(visible) > MAX_PREVIEW,
            "preview_omitted_reasoning_markup": reasoning}


def messages(history):
    value = history.get("conversation", {}).get("messages")
    require(isinstance(value, list) and all(isinstance(item, dict) for item in value),
            "malformed_conversation_history")
    return value


def describe_run(state, body, history, token):
    items = messages(history)
    assistants = [item.get("content") for item in items if item.get("role") == "assistant"]
    users = [item.get("content") for item in items if item.get("role") == "user"]
    content = assistants[-1] if assistants else None
    # Preserve the existing standalone-4 criterion, including surrounding text.
    passed = state == "completed" and isinstance(content, str) and bool(re.search(r"\b4\b", content))
    roles = {"system", "user", "assistant", "tool"}
    return {"completion_state": state if state in STATES else "unknown",
            "assistant": answer_summary(content, token), "events": event_summary(body),
            "last_user_matches_prompt": bool(users and users[-1] == PROMPT),
            "history_role_tail": [item.get("role") if item.get("role") in roles else "other"
                                  for item in items[-8:]],
            "standalone_4_oracle_passed": passed}


def failure_summary(exc):
    return {"status": "error", "error_type": type(exc).__name__[:64],
            **({"code": str(exc)} if isinstance(exc, SmokeFailure) else {})}


def direct_diagnostic(token):
    _, value = request("/v1/chat/completions", "POST", {
        "model": "local", "messages": [{"role": "user", "content": PROMPT}],
        "stream": False, "max_tokens": 64, "temperature": 0.3,
    }, base=MODEL, timeout=120)
    choices = value.get("choices")
    require(isinstance(choices, list) and bool(choices) and isinstance(choices[0], dict),
            "malformed_direct_choices")
    choice = choices[0]
    message = choice.get("message")
    require(isinstance(message, dict), "malformed_direct_message")
    content = message.get("content")
    reason = choice.get("finish_reason")
    reason = reason if reason in ("stop", "length", "tool_calls", "content_filter", None) else "other"
    usage = value.get("usage", {})
    tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
    tokens = tokens if type(tokens) is int and 0 <= tokens <= 1000000 else None
    calls = message.get("tool_calls", [])
    reasoning = message.get("reasoning_content", message.get("reasoning"))
    return {"status": "observed", "assistant": answer_summary(content, token),
            "finish_reason": reason, "completion_tokens": tokens,
            "tool_call_count": min(len(calls), 256) if isinstance(calls, list) else None,
            "reasoning_present": reasoning is not None,
            "reasoning_length_chars": len(reasoning) if isinstance(reasoning, str) else None,
            "standalone_4_oracle_passed": isinstance(content, str) and bool(re.search(r"\b4\b", content))}


def fresh_diagnostic(token):
    code, created = request("/api/conversations", "POST", {"title": "Native ZIP fresh diagnostic"}, token)
    require(code == 201, "fresh_conversation_failed")
    cid = identifier(created["conversation"]["id"])
    code, output = request("/api/chat", "POST", {"conversation_id": cid, "message": PROMPT}, token)
    require(code == 202, "fresh_chat_failed")
    state, body = finished(output["run_id"], 180)
    _, history = request("/api/conversations/" + cid)
    return {"status": "observed", **describe_run(state, body, history, token)}


def failure_diagnostics(token):
    results = {}
    for name, probe in (("direct_no_tools", direct_diagnostic), ("fresh_studio", fresh_diagnostic)):
        try:
            results[name] = probe(token)
        except Exception as exc:
            results[name] = failure_summary(exc)
    return results


def run_smoke():
    evidence = {"schema": "merlin-native-self-contained-smoke/2", "result": "fail",
                "synthetic_prompt": PROMPT, "primary": {"completion_state": "not_started"},
                "diagnostics": {"status": "not_run"}, "production_qualified": False,
                "qualification_scope": "single-reference bounded smoke only"}
    stage = "studio_readiness"
    try:
        status = ready("/api/status", seconds=60)
        require(status.get("ready") is True, "studio_startup_failed")
        token = status.get("session_token")
        require(isinstance(token, str) and 0 < len(token) <= 256 and token.isascii()
                and "\r" not in token and "\n" not in token, "session_token_missing")
        evidence["fresh_extract_http"] = "pass"
        stage = "offline_command"
        code, created = request("/api/conversations", "POST", {"title": "Native ZIP test"}, token)
        require(code == 201, "conversation_creation_failed")
        cid = identifier(created["conversation"]["id"])
        code, output = request("/api/chat", "POST", {"conversation_id": cid, "message": "/help"}, token)
        require(code == 202, "offline_chat_failed")
        state, _ = finished(output["run_id"], 30)
        require(state == "completed", "offline_command_failed")
        _, history = request("/api/conversations/" + cid)
        require(len(messages(history)) >= 2, "offline_history_missing")
        evidence["offline_command"] = "pass"
        stage = "model_readiness"
        models = ready("/v1/models", base=MODEL, seconds=180)
        require(models.get("data") and any(m.get("id") == "local" for m in models["data"]),
                "real_model_unavailable")
        code, _ = request("/api/settings", "POST", {
            "model_url": MODEL + "/v1/chat/completions", "model_id": "local",
            "network_enabled": False, "python_enabled": False, "desktop_enabled": False,
            "max_steps": 1, "max_output_tokens": 64, "model_timeout_seconds": 120,
            "tool_compatibility": "native"
        }, token)
        require(code == 200, "model_settings_failed")
        code, _ = request("/api/model/probe", "POST", {}, token, timeout=15)
        require(code == 200, "model_probe_failed")
        evidence["local_model_http"] = "pass"
        stage = "primary_answer"
        code, output = request("/api/chat", "POST", {"conversation_id": cid, "message": PROMPT}, token)
        require(code == 202, "primary_chat_failed")
        state, body = finished(output["run_id"], 180)
        evidence["primary"] = {"completion_state": state, "events": event_summary(body)}
        _, history = request("/api/conversations/" + cid)
        evidence["primary"] = describe_run(state, body, history, token)
        if evidence["primary"]["standalone_4_oracle_passed"]:
            evidence.update(result="pass", model_generated_reference="pass")
        else:
            evidence["model_generated_reference"] = "fail"
            evidence["failure"] = {"stage": stage, "code": "primary_arithmetic_oracle_failed"}
            evidence["diagnostics"] = failure_diagnostics(token)
    except (Exception, KeyboardInterrupt) as exc:
        evidence["failure"] = {"stage": stage, **failure_summary(exc)}
    return evidence


def main():
    evidence = run_smoke()
    encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_REPORT:
        evidence = {"schema": "merlin-native-self-contained-smoke/2", "result": "fail",
                    "failure": {"code": "evidence_limit_exceeded"}, "production_qualified": False}
        encoded = json.dumps(evidence, sort_keys=True)
    print(encoded)
    return 0 if evidence["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
