#!/usr/bin/env python3
"""Portable source-only Merlin Studio startup and restart on the actual target OS.

Uses the exact prebuilt archive; no model, browser, accounts or external fetch.
Win/mac/Linux execution is a different gate on each corresponding native host.
"""
from __future__ import annotations
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

ID32 = re.compile(r"[0-9a-f]{32}\Z")
URL_LINE = re.compile(r"Merlin Studio: http://127\.0\.0\.1:([0-9]{1,5})/studio/\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RESPONSE = 256 * 1024
MAX_ZIP = 2 * 1024 * 1024


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def request(port, method, path, *, token=None, value=None):
    require(path.startswith("/api/") and len(path) < 95, "API path outside loopback fixture")
    encoded = None if value is None else json.dumps(value, allow_nan=False).encode()
    require(encoded is None or len(encoded) < 4096, "oversized local request")
    headers = {"Connection": "close"}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["X-Merlin-Token"] = token
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        conn.request(method, path, body=encoded, headers=headers)
        result = conn.getresponse()
        body = result.read(MAX_RESPONSE + 1)
        require(len(body) <= MAX_RESPONSE, "oversized local response")
        return result.status, json.loads(body)
    finally:
        conn.close()


def terminate(proc):
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    for stream in (proc.stdout, proc.stderr):
        if stream is not None:
            stream.close()


def start(app, data_dir, home):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8", "HOME": str(home),
           "USERPROFILE": str(home), "TEMP": str(home), "TMP": str(home)}
    # Windows uses SystemRoot to load DLLs and resolve its local Python runtime.
    if "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    if "LANG" in os.environ:
        env["LANG"] = os.environ["LANG"]
    proc = subprocess.Popen(
        [sys.executable, "-B", str(app / "server.py"), "--port", "0", "--data-dir", str(data_dir)],
        cwd=str(app), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1)
    output = queue.Queue(maxsize=1)
    def capture():
        try:
            output.put(proc.stdout.readline(), timeout=1)
        except (OSError, ValueError, queue.Full):
            pass
    threading.Thread(target=capture, daemon=True).start()
    try:
        try:
            first = output.get(timeout=24).strip()
        except queue.Empty as exc:
            raise RuntimeError("Studio did not announce loopback startup") from exc
        match = URL_LINE.fullmatch(first)
        require(match is not None, "Studio announced unexpected startup endpoint")
        port = int(match.group(1))
        require(1 <= port <= 65535, "invalid loopback port")
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("Studio process exited during health readiness")
            try:
                code, health = request(port, "GET", "/api/health")
                if code == 200 and health.get("ready") is True:
                    return proc, port
            except (OSError, ValueError, http.client.HTTPException, RuntimeError):
                pass
            time.sleep(0.1)
        raise RuntimeError("Studio HTTP health not ready")
    except BaseException:
        terminate(proc)
        raise


def verify_archive(package, expected):
    require(package.is_file() and not package.is_symlink(), "regular ZIP required")
    require(re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "exact source SHA required")
    require(0 < package.stat().st_size <= MAX_ZIP, "source-only ZIP size outside reviewed bound")
    data = package.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    require(digest == "750d76f09b5659622d62e557d8cf9f3341c42255d7de4d11ffa13ff6a1997e2d",
            "reviewed source ZIP SHA-256 differs")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)) and len(names) <= 31,
                "ZIP members duplicated or excessive")
        for member in archive.infolist():
            require(member.filename.startswith("Merlin_Studio/")
                    and not member.filename.endswith("/")
                    and ".." not in Path(member.filename).parts and "\\" not in member.filename
                    and not member.flag_bits & 1 and member.file_size <= MAX_ZIP,
                    "unsafe ZIP extraction entry")
        manifest = json.loads(archive.read("Merlin_Studio/PACKAGE_MANIFEST.json"))
        require(manifest.get("schema") == "merlin-studio-portable/1"
                and manifest.get("native_protocol", {}).get("included") is False
                and manifest.get("contains_model_weights") is False
                and manifest.get("contains_user_state") is False
                and len(manifest.get("files", [])) == 29,
                "source-only reviewed manifest identity differs")
    return digest


def execute(package, expected):
    checksum = verify_archive(package, expected)
    result = {"schema": "merlin-studio-cross-platform-loopback/1",
              "source_commit": expected, "package_sha256": checksum,
              "os": platform.system(), "platform": platform.platform(),
              "python": platform.python_version(), "native_protocol": False,
              "model_calls": 0, "external_network_calls": 0,
              "production_qualified": False, "status": "blocked"}
    with tempfile.TemporaryDirectory(prefix="merlin-cross-os-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(package) as archive:
            archive.extractall(root)
        app = root / "Merlin_Studio"
        check = subprocess.run([sys.executable, "-B", str(app / "VERIFY.py")],
                               cwd=str(app), capture_output=True, timeout=15)
        require(check.returncode == 0 and b'"verified": true' in check.stdout.lower(),
                "extracted Studio hashes differ")
        require((app / "START.bat").is_file() and (app / "START.command").is_file()
                and (app / "START.sh").is_file(), "platform launcher entrypoints missing")
        data_dir = root / "state"
        proc = None
        try:
            proc, port = start(app, data_dir, root)
            code, status = request(port, "GET", "/api/status")
            require(code == 200 and status.get("ready") is True
                    and status.get("model", {}).get("configured") is False,
                    "offline status invented an AI model or failed")
            token = status.get("session_token")
            require(isinstance(token, str) and len(token) > 30, "session token missing")
            code, created = request(port, "POST", "/api/conversations", token=token,
                                    value={"title": "Cross-platform source ZIP"})
            require(code == 201 and isinstance(created.get("conversation"), dict),
                    "conversation creation failed")
            cid = created["conversation"]["id"]
            require(ID32.fullmatch(cid) is not None, "conversation ID differs")
            code, sent = request(port, "POST", "/api/chat", token=token,
                                 value={"conversation_id": cid, "message": "/help"})
            require(code == 202 and ID32.fullmatch(sent.get("run_id", "")) is not None,
                    "built-in offline help was not accepted")
            rid = sent["run_id"]
            deadline = time.monotonic() + 12
            complete = None
            while time.monotonic() < deadline:
                code, item = request(port, "GET", "/api/runs/" + rid)
                require(code == 200 and isinstance(item.get("run"), dict),
                        "run status unavailable")
                complete = item["run"]
                if complete["status"] != "running" and complete["status"] != "pending":
                    break
                time.sleep(0.1)
            require(complete is not None and complete.get("status") == "completed",
                    "offline help did not complete")
            code, before = request(port, "GET", "/api/conversations/" + cid)
            require(code == 200 and len(before["conversation"]["messages"]) == 2,
                    "offline message history differs")
            messages = before["conversation"]["messages"]
            terminate(proc)
            proc = None
            proc, other_port = start(app, data_dir, root)
            code, after = request(other_port, "GET", "/api/status")
            require(code == 200 and after.get("ready") is True
                    and after.get("session_token") != token,
                    "restart did not rotate local mutation token")
            code, restored = request(other_port, "GET", "/api/conversations/" + cid)
            require(code == 200 and restored["conversation"]["messages"] == messages,
                    "conversation restoration diverged")
            code, _ = request(other_port, "POST", "/api/conversations", token=token,
                              value={"title": "stale token must fail"})
            require(code == 403, "old token unexpectedly authorized post-restart write")
            result.update(status="passed",extracted_files_verified=29,
                          persisted_messages=len(messages), restart_verified=True,
                          stale_write_token_rejected=True, model_configured=False,
                          launcher_entrypoints_present=True)
        finally:
            terminate(proc)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, type=Path)
    ap.add_argument("--source-sha", required=True)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = execute(args.package, args.source_sha)
    except (OSError, ValueError, RuntimeError, TimeoutError, zipfile.BadZipFile) as exc:
        result = {"schema": "merlin-studio-cross-platform-loopback/1",
                  "status": "blocked", "error_type": type(exc).__name__,
                  "error": str(exc)[:300], "os": platform.system(),
                  "production_qualified": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"], "os": result.get("os"),
                      "restart_verified": result.get("restart_verified", False),
                      "production_qualified": False}))
    return 0 if result["status"] == "passed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
