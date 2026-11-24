#!/usr/bin/env python3
"""Run the frozen resident, direct and bounded-generation checks separately.

This launcher never imports Torch. Every model subprocess receives a constructed
offline environment, a private working directory and at most two CPU threads.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def constructed_environment(root: Path) -> dict:
    root.mkdir(mode=0o700)
    for name in ("home", "tmp", "hf-home"):
        (root / name).mkdir(mode=0o700)
    return {
        "PATH": "/usr/bin:/bin", "HOME": str(root / "home"), "TMPDIR": str(root / "tmp"),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1", "HF_HOME": str(root / "hf-home"),
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HUB_DISABLE_XET": "1", "TOKENIZERS_PARALLELISM": "false", "CUDA_VISIBLE_DEVICES": "",
        "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
    }


def verify_protocol(path: Path, source: Path) -> dict:
    if path.stat().st_size > 65536:
        raise ValueError("protocol exceeds bound")
    value = json.loads(path.read_text())
    expected = value["source_sha256"]
    if not 1 <= len(expected) <= 16:
        raise ValueError("unbounded protocol source list")
    for name, wanted in expected.items():
        if Path(name).name != name or digest(source / name) != wanted:
            raise ValueError("source differs from the frozen protocol")
    return value


def run_child(name: str, argv: list[str], root: Path, env: dict, report: dict, expected_exit=0):
    log = root / (name + ".log")
    row = {"name": name, "started_utc": stamp(), "argv": argv, "expected_exit": expected_exit}
    report["launches"].append(row)
    started = time.monotonic()
    with log.open("xb") as stream:
        process = subprocess.Popen(argv, env=env, cwd=env["TMPDIR"], stdout=stream, stderr=subprocess.STDOUT)
        row["pid"] = process.pid
        try:
            row["exit_code"] = process.wait(timeout=600)
        except subprocess.TimeoutExpired:
            process.kill()
            row["exit_code"] = process.wait()
            row["timed_out"] = True
        finally:
            row["elapsed_seconds"] = time.monotonic() - started
            row["finished_utc"] = stamp()
    row["log"] = {"bytes": log.stat().st_size, "sha256": digest(log)}
    if row.get("timed_out") or row["exit_code"] != expected_exit:
        raise RuntimeError(name + " did not meet its required exit status")


def read_success(path: Path) -> dict:
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("unbounded result receipt")
    value = json.loads(path.read_text())
    if value.get("success") is not True:
        raise ValueError("required child did not succeed")
    return value


def main() -> int:
    source = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=source / "direct-protocol-recovery2.json")
    parser.add_argument("--generation-protocol", type=Path, default=source / "generation-protocol-recovery2.json")
    args = parser.parse_args()
    base, python = args.base.resolve(strict=True), args.python.resolve(strict=True)
    output = args.output.absolute()
    output.mkdir(mode=0o700)
    report = {"schema": "merlin-parallax-separate-process-replay/1", "success": False,
              "started_utc": stamp(), "launches": [], "environment_inheritance": "none",
              "launcher_sha256": digest(Path(__file__)), "stage": "verify_protocols"}
    try:
        protocol = verify_protocol(args.protocol, source)
        generation = verify_protocol(args.generation_protocol, source)
        report["protocol_sha256"] = digest(args.protocol)
        report["generation_protocol_sha256"] = digest(args.generation_protocol)
        env = constructed_environment(output / "private-environment")
        report["constructed_environment"] = env
        prefix = [str(python), "-B"]
        probe = [str(source / "parallax_direct_probe.py"), "--base", str(base),
                 "--protocol", str(args.protocol.resolve())]
        resident, direct, continuation = output / "resident", output / "direct", output / "generation"
        report["stage"] = "resident"
        run_child("resident", prefix + probe + ["--mode", "resident", "--output", str(resident)], output, env, report)
        original = read_success(resident / "receipt.json")
        report["stage"] = "direct"
        run_child("direct", prefix + probe + ["--mode", "direct", "--output", str(direct),
                  "--reference", str(resident), "--reference-sha256", digest(resident / "receipt.json")], output, env, report)
        offloaded = read_success(direct / "receipt.json")
        if (offloaded["greedy_tokens"] != original["greedy_tokens"]
                or not all(item["finite"] and item["allclose"] for item in offloaded["comparison"])):
            raise ValueError("full-logit equivalence or exact token sequence failed")
        report["stage"] = "generation"
        cli = [str(source / "parallax_disk_generate.py"), "--base", str(base)]
        run_child("generation", prefix + cli + ["--output", str(continuation), "--prompt", generation["prompt"],
                  "--max-new-tokens", str(generation["max_new_tokens"])], output, env, report)
        generated = read_success(continuation / "receipt.json")
        if generated["generated_tokens"] != generation["expected_token_ids"] or generated["generated_tokens"] != original["greedy_tokens"]:
            raise ValueError("bounded CLI output differs from the frozen oracle or actual resident model")
        report["stage"] = "token_bound_negative"
        negative = output / "token-bound-negative"
        run_child("token-bound-negative", prefix + cli + ["--output", str(negative), "--prompt", "word " * 100,
                  "--max-new-tokens", "1"], output, env, report, expected_exit=1)
        rejection = json.loads((negative / "receipt.json").read_text())
        if (rejection.get("success") is not False or "64 prompt tokens" not in rejection.get("error", {}).get("message", "")
                or (negative / "offload-index").exists()):
            raise ValueError("oversized token request was not rejected before index creation")
        report["checks"] = {"finite_full_logits_allclose": True,
            "all_full_logits_bitwise_equal": all(item["bitwise_equal"] for item in offloaded["comparison"]),
            "exact_greedy_tokens": original["greedy_tokens"], "bounded_cli_equal": True,
            "token_limit_rejected_before_index_creation": True}
        report["process_peak_rss_bytes"] = {"resident": original["memory"]["after_inference"]["process_peak_rss_bytes"],
            "direct": offloaded["memory"]["after_inference"]["process_peak_rss_bytes"]}
        report["stage"], report["success"] = "complete", True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        report["finished_utc"] = stamp()
        report["memory_scope"] = (
            "Separate process peaks include initialization. Resident additionally performs an R-zero forward; "
            "direct holds resident reference arrays. Descriptive process memory only, not equal-workload speed, "
            "total-system RAM, physical SSD, or cold-cache measurement.")
        report["artifacts"] = {}
        for child in ("resident", "direct", "generation", "token-bound-negative"):
            for name in ("receipt.json", "logits.safetensors", "r-zero-logits.safetensors", "failure-traceback.txt"):
                path = output / child / name
                if path.is_file():
                    report["artifacts"][child + "/" + name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        with (output / "launch-receipt.json").open("x") as stream:
            stream.write(raw)
        print(json.dumps({"success": report["success"], "stage": report["stage"], "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
