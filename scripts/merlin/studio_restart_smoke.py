#!/usr/bin/env python3
"""Separate bounded persistence/restart gate, after original native acceptance.

Only a fixed public fixture is written to the fresh CI workspace. The receipt
contains hashes and booleans, never a session token, private data, or raw status.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from native_self_contained_smoke import MODEL, SmokeFailure, finished, identifier, messages, ready, request, require

TEXT = "Merlin release persistence fixture.\n"
FILE = "release-restart-check.txt"
SCHEMA = "merlin-studio-restart-smoke/1"


def file_hash(state_dir):
    path = Path(state_dir) / "workspace" / FILE
    require(path.is_file() and not path.is_symlink() and path.stat().st_size == len(TEXT.encode()), "workspace_fixture_missing")
    raw = path.read_bytes()
    require(raw == TEXT.encode(), "workspace_fixture_changed")
    return hashlib.sha256(raw).hexdigest()


def history_hash(history):
    values = [{"role": row["role"], "content": row["content"]} for row in messages(history)]
    require(2 <= len(values) <= 8, "history_size_changed")
    raw = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    require(len(raw) <= 16384, "history_bytes_limit")
    return hashlib.sha256(raw).hexdigest()


def capture(state_dir, checkpoint):
    status = ready("/api/status", seconds=30)
    token = status.get("session_token")
    require(isinstance(token, str) and 1 <= len(token) <= 256, "session_missing")
    _, created = request("/api/conversations", "POST", {"title": "Native restart persistence"}, token)
    cid = identifier(created["conversation"]["id"])
    _, output = request("/api/chat", "POST", {"conversation_id": cid, "message": "/write " + FILE + "\n" + TEXT}, token)
    run_id = identifier(output["run_id"])
    state, _ = finished(run_id, seconds=30)
    require(state == "completed", "workspace_write_failed")
    _, history = request("/api/conversations/" + cid)
    value = {"schema": SCHEMA, "conversation_id": cid, "run_id": run_id,
             "history_sha256": history_hash(history), "workspace_sha256": file_hash(state_dir),
             "original_native_acceptance_modified": False}
    with Path(checkpoint).open("x") as destination:
        json.dump(value, destination, sort_keys=True)
        destination.write("\n")
    return {"schema": SCHEMA, "phase": "capture", "result": "pass"}


def verify(state_dir, checkpoint):
    checkpoint = Path(checkpoint)
    require(checkpoint.is_file() and not checkpoint.is_symlink() and checkpoint.stat().st_size <= 4096, "checkpoint_invalid")
    expected = json.loads(checkpoint.read_bytes())
    require(expected.get("schema") == SCHEMA, "checkpoint_schema")
    cid, run_id = identifier(expected["conversation_id"]), identifier(expected["run_id"])
    ready("/api/health", seconds=30)
    _, history = request("/api/conversations/" + cid)
    _, run = request("/api/runs/" + run_id)
    require(run["run"]["status"] == "completed", "persisted_run_changed")
    history_digest, workspace_digest = history_hash(history), file_hash(state_dir)
    require(history_digest == expected["history_sha256"] and workspace_digest == expected["workspace_sha256"], "persisted_bytes_changed")
    models = ready("/v1/models", base=MODEL, seconds=180)
    require(any(row.get("id") == "local" for row in models.get("data", [])), "restarted_model_unavailable")
    return {"schema": SCHEMA, "phase": "verify", "result": "pass", "workspace_preserved": True,
            "history_preserved": True, "completed_run_preserved": True, "bundled_model_restarted": True,
            "workspace_sha256": workspace_digest, "history_sha256": history_digest,
            "model_weights_loaded_after_restart": True, "model_answer_retested": False,
            "network_namespace_isolation": False, "original_native_acceptance_modified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("capture", "verify"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = (capture if args.phase == "capture" else verify)(args.state_dir, args.checkpoint)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, SmokeFailure) else type(exc).__name__
        value = {"schema": SCHEMA, "phase": args.phase, "result": "fail", "reason": reason}
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    require(len(raw) <= 4096, "restart_report_limit")
    print(raw)
    raise SystemExit(0 if value["result"] == "pass" else 1)


if __name__ == "__main__":
    main()
