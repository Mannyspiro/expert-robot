#!/usr/bin/env python3
"""Real local ZIP extraction, offline Studio loopback, persistence, and restart smoke.

Runs only against an allowlisted hash-verified Merlin Studio package. No model
weights, account credentials, public networking, host services, or deployment.
The result is scoped Linux host acceptance, not release or cross-platform proof.
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
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

from verify_portable import verify

ID32 = re.compile(r"[0-9a-f]{32}\Z")
URL_LINE = re.compile(r"^Merlin Studio: http://127\.0\.0\.1:([0-9]{1,5})/studio/\s*$")
MAX_RESPONSE = 256 * 1024


def need(value, label):
    if not value:
        raise RuntimeError(label)


def local_request(port, method, path, token=None, data=None):
    need(path.startswith("/api/") and len(path) <= 96, "local API path outside bound")
    body = None if data is None else json.dumps(data, allow_nan=False).encode("utf-8")
    need(body is None or len(body) <= 4096, "test body exceeded 4 KiB")
    headers = {"Connection": "close"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["X-Merlin-Token"] = token
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read(MAX_RESPONSE + 1)
        need(len(raw) <= MAX_RESPONSE, "oversized local response")
        return response.status, json.loads(raw)
    finally:
        conn.close()


def start_studio(app, data_root, work_root):
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "HOME": str(work_root), "TMPDIR": str(work_root),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.Popen(
        [sys.executable, "-B", str(app / "server.py"), "--port", "0",
         "--data-dir", str(data_root)],
        cwd=str(app), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        need(proc.stdout is not None, "Studio startup pipe missing")
        stop = time.monotonic() + 15
        port = None
        while time.monotonic() < stop:
            need(proc.poll() is None, "Studio process terminated before startup")
            ready, _, _ = select.select([proc.stdout], [], [], 0.3)
            if not ready:
                continue
            line = proc.stdout.readline(300).decode("utf-8", "replace")
            match = URL_LINE.fullmatch(line.strip())
            if match:
                port = int(match.group(1))
                break
        need(port is not None and 0 < port < 65536, "Studio never declared loopback port")
        stop = time.monotonic() + 8
        while time.monotonic() < stop:
            try:
                status, result = local_request(port, "GET", "/api/health")
                if status == 200 and result.get("ready") is True:
                    return proc, port
            except (OSError, ValueError, RuntimeError, http.client.HTTPException):
                pass
            time.sleep(0.1)
        raise RuntimeError("Studio health did not become ready")
    except BaseException:
        terminate(proc)
        raise


def terminate(proc):
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=7)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()
    need(proc.poll() is not None, "owned Studio process survived cleanup")


def run(package, source_sha):
    package = Path(package).resolve(strict=True)
    need(package.is_file() and not package.is_symlink(), "regular package ZIP required")
    need(isinstance(source_sha, str) and re.fullmatch(r"[0-9a-f]{40}", source_sha),
         "expected exact 40-hex Git source commit")
    integrity = verify(package)
    need(integrity["verified"], "ZIP integrity preflight failed")
    report = {
        "schema": "merlin-portable-zip-loopback-smoke/1",
        "source_commit": source_sha,
        "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
        "package_bytes": package.stat().st_size,
        "package_files": integrity["file_count"],
        "native_protocol": integrity["native_protocol"],
        "production_qualified": False,
        "external_model_calls": 0,
        "external_network_requests": 0,
        "host_service_mutations": False,
    }
    with tempfile.TemporaryDirectory(prefix="merlin-zip-smoke-") as tmp:
        work_root = Path(tmp)
        app = work_root / "Merlin_Studio"
        data_root = work_root / "merlin-state"
        proc = None
        try:
            with zipfile.ZipFile(package) as archive:
                manifest = json.loads(archive.read("Merlin_Studio/PACKAGE_MANIFEST.json"))
                need(manifest.get("contains_model_weights") is False and
                     manifest.get("contains_user_state") is False,
                     "ZIP contains forbidden model or user data")
                archive.extractall(work_root)
            need(app.is_dir() and (app / "server.py").is_file(), "extracted package missing")
            extracted_integrity = verify(app)
            need(extracted_integrity["verified"], "extracted file integrity failed")
            proc, port = start_studio(app, data_root, work_root)
            code, status = local_request(port, "GET", "/api/status")
            need(code == 200 and status.get("ready") is True, "Studio status failed")
            need(status.get("model", {}).get("configured") is False,
                 "model must not be invented in offline ZIP")
            token = status.get("session_token")
            need(isinstance(token, str) and len(token) >= 32, "missing local write token")
            code, created = local_request(port, "POST", "/api/conversations", token,
                                          {"title": "Offline portable acceptance"})
            need(code == 201 and isinstance(created.get("conversation"), dict),
                 "offline conversation creation failed")
            cid = created["conversation"]["id"]
            need(ID32.fullmatch(cid) is not None, "conversation identity differs")
            code, submitted = local_request(port, "POST", "/api/chat", token,
                                            {"conversation_id": cid, "message": "/help"})
            need(code == 202 and ID32.fullmatch(submitted.get("run_id", "")) is not None,
                 "offline /help was not accepted")
            rid = submitted["run_id"]
            deadline = time.monotonic() + 10
            outcome = None
            while time.monotonic() < deadline:
                code, value = local_request(port, "GET", "/api/runs/" + rid)
                need(code == 200 and isinstance(value.get("run"), dict),
                     "offline run status unavailable")
                outcome = value["run"]
                if outcome["status"] in ("completed", "failed", "interrupted", "cancelled"):
                    break
                time.sleep(0.1)
            need(outcome is not None and outcome["status"] == "completed",
                 "offline /help did not complete")
            code, before = local_request(port, "GET", "/api/conversations/" + cid)
            need(code == 200, "persisted conversation fetch failed")
            messages = before["conversation"]["messages"]
            need(len(messages) == 2 and messages[0]["role"] == "user"
                 and messages[1]["role"] == "assistant"
                 and "/help" in messages[0]["content"]
                 and "Merlin" in messages[1]["content"],
                 "offline response not persisted")
            terminate(proc)
            proc = None
            proc, port2 = start_studio(app, data_root, work_root)
            code, restarted = local_request(port2, "GET", "/api/status")
            need(code == 200 and restarted["session_token"] != token,
                 "restart reused the old mutation token")
            code, after = local_request(port2, "GET", "/api/conversations/" + cid)
            need(code == 200 and after["conversation"]["messages"] == messages,
                 "offline conversation changed after process restart")
            bad_status, _ = local_request(port2, "POST", "/api/conversations", token,
                                          {"title": "old token should fail"})
            need(bad_status == 403, "expired per-process token still authorizes changes")
            report.update(status="passed", offline_messages=len(messages),
                          restarted=True, stale_write_token_rejected=True,
                          extracted_files_verified=extracted_integrity["file_count"],
                          port_one=port, port_two=port2,
                          model_configured=False)
        finally:
            terminate(proc)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = {"schema": "merlin-portable-zip-loopback-smoke/1",
              "status": "failed", "production_qualified": False}
    try:
        report = run(args.package, args.source_sha)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError,
            zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)[:300]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "production_qualified": False}, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
