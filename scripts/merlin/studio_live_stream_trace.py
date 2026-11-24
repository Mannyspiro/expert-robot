#!/usr/bin/env python3
"""Record one bounded real Studio stream for UI replay after native acceptance.

Only a fixed public prompt, actual text deltas, timing and pinned artifact
identities are emitted. This is a streaming-function check, not a quality oracle.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import re
import socket
import threading
import time

from native_self_contained_smoke import SmokeFailure, identifier, request, require

PROMPT = "In one short sentence, describe what a local AI workspace does."
STUDIO_PORT = 18771
MAX_FRAME = 32768
MAX_STREAM_BYTES = 1024 * 1024
MAX_EVENTS = 128
MAX_TEXT = 16384
MAX_REPORT = 65536
MAX_SECONDS = 150
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
VISIBLE = {"model_request", "text_delta", "model_response"} | TERMINAL


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def digest_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stream_events(run_id, token, after, seconds):
    """Yield complete SSE frames immediately, with total time and byte limits."""
    run_id = identifier(run_id)
    require(type(after) is int and after >= 0 and 0 < seconds <= MAX_SECONDS,
            "invalid_stream_budget")
    connection = http.client.HTTPConnection("127.0.0.1", STUDIO_PORT, timeout=seconds)
    channel = response = None
    deadline = time.monotonic() + seconds
    expired = threading.Event()

    def remaining():
        value = deadline - time.monotonic()
        require(value > 0 and not expired.is_set(), "stream_deadline")
        return value

    def abort():
        expired.set()
        if channel is not None:
            try:
                channel.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        connection.close()

    timer = threading.Timer(seconds, abort)
    timer.daemon = True
    timer.start()
    try:
        connection.connect()
        channel = connection.sock
        channel.settimeout(remaining())
        connection.request("GET", f"/api/runs/{run_id}/events?after={after}",
                           headers={"X-Merlin-Token": token, "Accept": "text/event-stream"})
        response = connection.getresponse()
        require(response.status == 200, "stream_http_status")
        require(response.headers.get_content_type() == "text/event-stream", "stream_content_type")
        total = frame_bytes = 0
        fields = {}
        data = []
        while True:
            channel.settimeout(remaining())
            line = response.readline(MAX_FRAME + 1)
            remaining()
            if not line:
                require(not fields and not data, "incomplete_sse_frame")
                break
            total += len(line)
            frame_bytes += len(line)
            require(total <= MAX_STREAM_BYTES and frame_bytes <= MAX_FRAME, "stream_byte_limit")
            require(line.endswith(b"\n"), "incomplete_sse_line")
            line = line.rstrip(b"\r\n")
            if not line:
                if data:
                    payload = json.loads("\n".join(data), object_pairs_hook=unique)
                    require(isinstance(payload, dict), "malformed_sse_object")
                    yield {"event": fields.get("event", "message"),
                           "id": fields.get("id"), "data": payload}
                fields, data, frame_bytes = {}, [], 0
                continue
            if line.startswith(b":"):
                continue
            key, separator, value = line.partition(b":")
            require(bool(separator), "malformed_sse_field")
            value = value.removeprefix(b" ").decode("utf-8")
            if key == b"data":
                data.append(value)
            elif key in (b"event", b"id"):
                name = key.decode("ascii")
                require(name not in fields, "duplicate_sse_field")
                fields[name] = value
    finally:
        timer.cancel()
        if response is not None:
            response.close()
        connection.close()


def profile_identity(path, expected_model):
    require(re.fullmatch(r"[0-9a-f]{64}", expected_model) is not None, "invalid_model_pin")
    with Path(path).open("rb") as source:
        raw = source.read(1024 * 1024 + 1)
    require(len(raw) <= 1024 * 1024, "profile_manifest_limit")
    profile = json.loads(raw, object_pairs_hook=unique)
    require(profile.get("schema") == "merlin-linux-offline-profile/1"
            and profile.get("model_id") == "local"
            and profile.get("model_expected_sha256") == expected_model,
            "profile_model_pin_mismatch")
    selected = {"model_sha256": expected_model, "profile_manifest_sha256": hashlib.sha256(raw).hexdigest()}
    for key, field in (("engine_sha256", "llama_expected_sha256"),
                       ("python_sha256", "python_expected_sha256")):
        value = profile.get(field)
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
                "profile_runtime_pin_malformed")
        selected[key] = value
    return selected


def run_trace(identity, source_commit, source_tree):
    require(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (source_commit, source_tree)),
            "invalid_source_identity")
    evidence = {"schema": "merlin-studio-live-trace/1", "result": "fail",
                "synthetic_prompt": PROMPT, "source_commit": source_commit,
                "source_tree": source_tree, "artifacts": identity,
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "sampling": {"temperature": 0.3, "seed": None, "seed_control": "not_exposed_by_Studio",
                             "max_output_tokens": 64, "max_steps": 1},
                "events": [], "production_qualified": False,
                "scope": "One actual packaged-model stream; no answer-quality or production qualification."}
    started = time.monotonic()
    token = ""
    try:
        _, status = request("/api/status")
        token = status.get("session_token")
        require(isinstance(token, str) and 0 < len(token) <= 256 and token.isascii()
                and "\r" not in token and "\n" not in token, "session_token_missing")
        request("/api/settings", "POST", {
            "model_url": "http://127.0.0.1:8772/v1/chat/completions", "model_id": "local",
            "network_enabled": False, "python_enabled": False, "desktop_enabled": False,
            "browser_enabled": False, "max_steps": 1, "max_output_tokens": 64,
            "model_timeout_seconds": 120, "tool_compatibility": "native"}, token)
        code, created = request("/api/conversations", "POST", {"title": "Native live-stream UI trace"}, token)
        require(code == 201, "conversation_creation_failed")
        cid = identifier(created["conversation"]["id"])
        code, accepted = request("/api/chat", "POST", {"conversation_id": cid, "message": PROMPT}, token)
        require(code == 202, "trace_chat_failed")
        run_id = identifier(accepted["run_id"])
        evidence.update(conversation_id=cid, run_id=run_id)
        cursor, windows, count = 0, 0, 0
        deltas = []
        live_observed = False
        model_started = model_finished = False
        terminal = None
        while terminal is None:
            left = MAX_SECONDS - (time.monotonic() - started)
            require(left > 0 and windows < 8, "trace_deadline")
            windows += 1
            iterator = stream_events(run_id, token, cursor, min(35, left))
            try:
                for frame in iterator:
                    if frame["event"] == "snapshot":
                        continue
                    require(frame["event"] == "merlin", "unexpected_sse_event")
                    row = frame["data"]
                    ordinal = row.get("ordinal")
                    require(type(ordinal) is int and ordinal > cursor
                            and frame["id"] == str(ordinal), "event_order_or_identity")
                    cursor = ordinal
                    count += 1
                    require(count <= MAX_EVENTS, "event_count_limit")
                    kind = row.get("type")
                    if kind not in VISIBLE:
                        continue
                    created_at = row.get("created_at")
                    require(isinstance(created_at, str) and len(created_at) <= 64,
                            "invalid_event_timestamp")
                    stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    require(stamp.tzinfo is not None, "event_timezone_missing")
                    selected = {"ordinal": ordinal, "type": kind, "created_at": created_at,
                                "received_ms": round((time.monotonic() - started) * 1000, 3)}
                    if kind in {"model_request", "text_delta", "model_response"}:
                        require(type(row.get("step")) is int and row["step"] == 1,
                                "unexpected_model_step")
                        selected["step"] = 1
                    if kind == "model_request":
                        require(not model_started, "duplicate_model_request")
                        model_started = True
                    if kind == "text_delta":
                        require(model_started and not model_finished, "delta_outside_model_response")
                        content = row.get("content")
                        require(isinstance(content, str) and bool(content), "empty_or_malformed_delta")
                        deltas.append(content)
                        require(len("".join(deltas).encode("utf-8")) <= MAX_TEXT, "text_limit")
                        selected["content"] = content
                        if not live_observed:
                            _, current = request("/api/runs/" + run_id, token=token)
                            live_observed = current.get("run", {}).get("status") == "running"
                    if kind == "model_response":
                        require(model_started and not model_finished, "unexpected_model_response")
                        require(row.get("streamed") is True and type(row.get("tool_call_count")) is int
                                and row["tool_call_count"] == 0, "trace_model_not_text_stream")
                        require(row.get("content") == "".join(deltas), "streamed_response_text_mismatch")
                        selected.update(streamed=True, tool_call_count=0,
                                        content_sha256=digest_text(row["content"]))
                        model_finished = True
                    evidence["events"].append(selected)
                    if kind in TERMINAL:
                        terminal = kind
                        break
            finally:
                iterator.close()
        require(terminal == "completed", "trace_run_not_completed")
        require(model_finished, "missing_model_response")
        _, final_run = request("/api/runs/" + run_id, token=token)
        require(final_run.get("run", {}).get("status") == "completed", "final_run_state_mismatch")
        _, history = request("/api/conversations/" + cid, token=token)
        messages = history.get("conversation", {}).get("messages", [])
        users = [m.get("content") for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        assistants = [m.get("content") for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]
        require(users == [PROMPT] and len(assistants) == 1 and isinstance(assistants[0], str),
                "persisted_conversation_mismatch")
        answer = assistants[0]
        require(len(deltas) >= 2 and live_observed, "no_observed_live_stream")
        require("".join(deltas) == answer, "deltas_differ_from_persisted_answer")
        require(token not in answer, "token_in_generated_text")
        evidence.update(result="pass", answer={"text": answer, "sha256": digest_text(answer)},
                        verification={"nonempty_delta_count": len(deltas), "live_running_state_observed_after_delta": True,
                                      "delta_text_matches_persisted_answer": True, "terminal_state": terminal},
                        stream_windows=windows)
    except Exception as exc:
        evidence["failure"] = {"type": type(exc).__name__,
                               **({"code": str(exc)} if isinstance(exc, SmokeFailure) else {})}
    evidence["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
    combined = "".join(row.get("content", "") for row in evidence["events"])
    if token and token in combined:
        evidence["events"] = []
        evidence.pop("answer", None)
        evidence["result"] = "fail"
        evidence["failure"] = {"code": "token_in_generated_text"}
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-manifest", type=Path, required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    try:
        identity = profile_identity(args.profile_manifest, args.model_sha256)
        evidence = run_trace(identity, args.source_commit, args.source_tree)
        evidence["trace_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except Exception as exc:
        evidence = {"schema": "merlin-studio-live-trace/1", "result": "fail", "production_qualified": False,
                    "failure": {"type": type(exc).__name__,
                                **({"code": str(exc)} if isinstance(exc, SmokeFailure) else {})}}
    encoded = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_REPORT:
        encoded = json.dumps({"schema": "merlin-studio-live-trace/1", "result": "fail",
                              "failure": {"code": "report_limit"}, "production_qualified": False})
        evidence["result"] = "fail"
    print(encoded)
    return 0 if evidence["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
