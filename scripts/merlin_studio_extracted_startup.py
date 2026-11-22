#!/usr/bin/env python3
"""Run extracted Merlin Studio over real loopback HTTP and verify restart.

The package must already pass the exact ZIP verifier. No external network,
browser, model weights, AI quality claim or OS desktop control is involved.
"""
from __future__ import annotations
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def request(port, method, path, value=None, token=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    body = None if value is None else json.dumps(value).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Merlin-Token"] = token
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise RuntimeError("unexpected oversized server response")
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status} {method} {path}: {data[:160]!r}")
        if response.getheader("Content-Type", "").startswith("application/json"):
            return json.loads(data)
        return data
    finally:
        conn.close()


def launch(app, state):
    p = subprocess.Popen(
        [sys.executable, "server.py", "--port", "0", "--data-dir", str(state)],
        cwd=app, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                                   "PYTHONUNBUFFERED": "1"},
    )
    try:
        readable, _, _ = select.select([p.stdout], [], [], 10)
        if not readable:
            raise RuntimeError("Studio did not report a loopback address")
        line = p.stdout.readline().strip()
        matched = re.fullmatch(r"Merlin Studio: http://127\.0\.0\.1:([0-9]+)/studio/", line)
        if not matched or p.poll() is not None:
            raise RuntimeError("Studio exited or reported an unexpected address: " + line)
        return p, int(matched.group(1))
    except Exception:
        stop(p)
        raise


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=7)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    for pipe in (proc.stdout, proc.stderr):
        if pipe:
            pipe.close()


def wait_finished(port, run_id):
    for _ in range(120):
        result = request(port, "GET", "/api/runs/" + run_id)
        state = result["run"]["status"]
        if state == "completed":
            return result
        if state in {"failed", "cancelled", "waiting_approval"}:
            raise RuntimeError("offline command ended in unexpected state: " + state)
        time.sleep(0.05)
    raise RuntimeError("offline chat exceeded fixed completion budget")


def run(archive):
    verify = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_portable.py"), str(archive)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if verify.returncode:
        raise RuntimeError("ZIP verification failed: " + verify.stderr[-600:])
    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="merlin-extract-acceptance-") as directory:
        root = Path(directory)
        with zipfile.ZipFile(archive) as source:
            source.extractall(root)
        app = root / "Merlin_Studio"
        state_dir = root / "saved-data"
        first, port = launch(app, state_dir)
        try:
            html = request(port, "GET", "/studio/")
            if b"Merlin" not in html:
                raise RuntimeError("extracted Studio HTML was not served")
            health = request(port, "GET", "/api/health")
            if health.get("ready") is not True or health.get("service") != "merlin-studio":
                raise RuntimeError("extracted Studio failed its real health route")
            status = request(port, "GET", "/api/status")
            token_before = status["session_token"]
            convo = request(port, "POST", "/api/conversations",
                            {"title": "Offline fixture"}, token_before)["conversation"]
            run_id = request(port, "POST", "/api/chat",
                             {"conversation_id": convo["id"],
                              "message": "/write notes/offline.txt\npersisted-checkpoint"},
                             token_before)["run_id"]
            wait_finished(port, run_id)
            expected = state_dir / "workspace" / "notes" / "offline.txt"
            if not expected.is_file() or expected.read_text() != "persisted-checkpoint":
                raise RuntimeError("offline workspace write did not persist")
        finally:
            stop(first)
        second, port2 = launch(app, state_dir)
        try:
            status2 = request(port2, "GET", "/api/status")
            if status2["session_token"] == token_before:
                raise RuntimeError("server restart reused the old request session token")
            saved = request(port2, "GET", "/api/conversations/" + convo["id"])
            messages = saved["conversation"]["messages"]
            if not any("persisted-checkpoint" in item.get("content", "") for item in messages):
                raise RuntimeError("conversation did not survive process restart")
            if (state_dir / "workspace" / "notes" / "offline.txt").read_text() != "persisted-checkpoint":
                raise RuntimeError("workspace content changed after restart")
            request(port2, "GET", "/api/health")
        finally:
            stop(second)
    return {
        "schema": "merlin-studio-extracted-startup/1",
        "zip_sha256": archive_sha,
        "exact_manifest_verified": True,
        "http_loopback_verified": True, "offline_write_verified": True,
        "fresh_process_restore_verified": True, "token_rotated_after_restart": True,
        "model_inference_qualified": False, "desktop_control_qualified": False,
        "public_browser_qualified": False, "release_qualified": False,
        "external_spend_usd": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if destination.exists():
        destination.unlink()
    try:
        result = run(args.zip.resolve())
    except Exception as exc:
        print("extracted startup BLOCKED: " + type(exc).__name__ + ": " + str(exc),
              file=sys.stderr)
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
