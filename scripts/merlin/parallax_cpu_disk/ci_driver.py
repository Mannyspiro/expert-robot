#!/usr/bin/env python3
"""Clean-runner acquisition, offline setup, real-model replay and bounded evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import run_replay
import setup_cpu_candidate as setup

LOG_LIMIT = 128 * 1024


def run_stage(name, argv, root, env, report, deadline):
    report["stage"] = name
    log = root / (name + ".log")
    start = time.monotonic()
    row = {"name": name, "elapsed_seconds": None, "exit_code": None}
    report["stages"].append(row)
    with log.open("xb") as output:
        process = subprocess.Popen(argv, env=env, cwd=root, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        row["pid"] = process.pid
        try:
            row["exit_code"] = process.wait(timeout=max(1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            row["exit_code"] = process.wait()
            row["timed_out"] = True
        finally:
            row["elapsed_seconds"] = time.monotonic() - start
    if row["exit_code"] != 0 or row.get("timed_out"):
        raise RuntimeError(name + " failed; retained bounded stage log")


def retain(source, target, entries, limit, truncate=False):
    if not source.is_file() or source.is_symlink():
        return
    size, original = source.stat().st_size, run_replay.digest(source)
    if size > limit and not truncate:
        entries.append({"path": str(target), "retained": False, "reason": "exceeds artifact bound",
                        "original_bytes": size, "original_sha256": original})
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if size > limit:
        marker = b"\n[bounded evidence: middle of log omitted]\n"
        head = 16 * 1024
        with source.open("rb") as stream:
            first = stream.read(head)
            stream.seek(-(limit - head - len(marker)), os.SEEK_END)
            raw = first + marker + stream.read()
        target.write_bytes(raw)
    else:
        shutil.copyfile(source, target)
    entries.append({"path": str(target), "retained": True, "original_bytes": size,
                    "original_sha256": original, "retained_bytes": target.stat().st_size,
                    "retained_sha256": run_replay.digest(target), "truncated": size > limit})


def collect(root, artifact):
    rows = []
    for name in ("acquire-runtime", "acquire-wheel", "acquire-checkpoint", "offline-setup", "replay", "boundary-tests"):
        retain(root / (name + ".log"), artifact / "logs" / (name + ".log"), rows, LOG_LIMIT, True)
    for name in ("runtime-smoke", "venv-create", "offline-install", "pip-check", "cpu-import-smoke"):
        retain(root / "install" / (name + ".log"), artifact / "logs" / (name + ".log"), rows, LOG_LIMIT, True)
    for name in ("resident", "direct", "generation", "token-bound-negative"):
        retain(root / "replay" / (name + ".log"), artifact / "logs" / (name + ".log"), rows, LOG_LIMIT, True)
        for leaf in ("receipt.json", "logits.safetensors", "r-zero-logits.safetensors", "failure-traceback.txt"):
            limit = 8 * 1024**2 if leaf.endswith(".safetensors") else 1024**2
            retain(root / "replay" / name / leaf, artifact / "replay" / name / leaf, rows, limit)
    for name in ("acquire-runtime.json", "acquire-wheel.json", "acquire-checkpoint.json", "ci-result.json",
                 "source-identity.json", "install/setup-receipt.json", "install/runtime-inventory.json", "replay/launch-receipt.json"):
        retain(root / name, artifact / name, rows, 2 * 1024**2)
    for row in rows:
        row["path"] = str(Path(row["path"]).relative_to(artifact))
    setup.write_json(artifact / "artifact-manifest.json", {"schema": "merlin-parallax-ci-artifacts/1", "files": rows,
        "scope": "Allowlisted stage logs, receipts, source hashes and actual logits only; no weights, wheels or installed environment."})
    if sum(p.stat().st_size for p in artifact.rglob("*") if p.is_file()) > 64 * 1024**2:
        raise ValueError("bounded evidence exceeded 64 MiB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    checkout = Path(subprocess.check_output(["git", "-C", str(source), "rev-parse", "--show-toplevel"], text=True).strip())
    artifact = args.artifacts.absolute()
    artifact.mkdir(mode=0o700)
    root = Path(tempfile.mkdtemp(prefix="merlin-parallax-ci-", dir=os.environ.get("RUNNER_TEMP")))
    report = {"schema": "merlin-parallax-clean-install-ci/1", "success": False, "stage": "source", "stages": []}
    deadline = time.monotonic() + 25 * 60
    try:
        git = lambda *a: subprocess.check_output(["git", "-C", str(checkout), *a], text=True).strip()
        actual = git("rev-parse", "HEAD")
        if actual != args.expected_sha or git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("checkout differs from the exact requested clean head")
        paths = [p for p in git("ls-files", "-z", "--", str(source.relative_to(checkout))).split("\0") if p]
        if not 1 <= len(paths) <= 256:
            raise ValueError("unbounded source closure")
        inventory = []
        for path in paths:
            file = checkout / path
            if file.is_symlink() or not file.is_file():
                raise ValueError("profile source must be regular files")
            inventory.append({"path": path, "bytes": file.stat().st_size, "sha256": run_replay.digest(file)})
        if sum(row["bytes"] for row in inventory) > 16 * 1024**2:
            raise ValueError("source closure exceeds 16 MiB")
        setup.write_json(root / "source-identity.json", {"expected_sha": args.expected_sha, "head": actual,
            "tree": git("rev-parse", actual + "^{tree}"), "tracked_clean": True, "profile_files": inventory})
        env = run_replay.constructed_environment(root / "environment")
        network = dict(env)
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR"):
            if key in os.environ:
                network[key] = os.environ[key]
        base = root / "payloads"
        base.mkdir(mode=0o700)
        for name in setup.LOCKS:
            if run_replay.digest(source / name) != setup.LOCKS[name]:
                raise ValueError("source lock differs from audited setup")
            shutil.copyfile(source / name, base / name)
        run_stage("boundary-tests", [sys.executable, "-B", str(source / "test_profile.py"), "-v"], root, env, report, deadline)
        for short, lock in (("runtime", "runtime-lock.json"), ("wheel", "wheel-lock.json"), ("checkpoint", "checkpoint-lock.json")):
            run_stage("acquire-" + short, [sys.executable, "-B", str(source / "acquire_locked.py"),
                "--lock", str(base / lock), "--root", str(base), "--receipt", str(root / ("acquire-" + short + ".json"))], root, network, report, deadline)
        run_stage("offline-setup", [sys.executable, "-B", str(source / "setup_cpu_candidate.py"),
            "--payload-root", str(base), "--destination", str(root / "install")], root, env, report, deadline)
        run_stage("replay", [sys.executable, "-B", str(source / "run_replay.py"), "--python", str(root / "install/venv/bin/python"),
            "--base", str(base), "--output", str(root / "replay")], root, env, report, deadline)
        receipt = json.loads((root / "replay/launch-receipt.json").read_text())
        if receipt.get("success") is not True:
            raise ValueError("actual replay receipt did not succeed")
        report["replay_receipt_sha256"] = run_replay.digest(root / "replay/launch-receipt.json")
        report["stage"], report["success"] = "complete", True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        setup.write_json(root / "ci-result.json", report)
        collect(root, artifact)
        print(json.dumps({"success": report["success"], "stage": report["stage"], "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
