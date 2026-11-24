#!/usr/bin/env python3
"""Run the frozen virtual-resource protocol in separate locked processes."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import runpy
import selectors
import signal
import subprocess
import sys
import time

from parallax_virtual_probe import take_lock, verify_protocol
from run_replay import constructed_environment, digest, read_success

LOG_LIMIT = 128 * 1024
CHILD_TIMEOUT = 600
CHILDREN = ("resident", "direct", "virtual", "generation", "cuda-negative", "tiny-budget-negative", "token-bound-negative")


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_child(name, argv, output, env, report, expected_exit=0):
    log = output / (name + ".log")
    row = {"name": name, "argv": argv, "started_utc": stamp(), "expected_exit": expected_exit}
    report["launches"].append(row)
    started, total, captured = time.monotonic(), 0, 0
    complete_hash = hashlib.sha256()
    with log.open("xb") as stream:
        process = subprocess.Popen(argv, env=env, cwd=env["TMPDIR"], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True, bufsize=0)
        row["pid"] = process.pid
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    if time.monotonic() - started > CHILD_TIMEOUT:
                        row["timed_out"] = True
                        os.killpg(process.pid, signal.SIGKILL)
                        break
                    for key, _ in selector.select(timeout=0.2):
                        block = os.read(key.fileobj.fileno(), 65536)
                        if not block:
                            selector.unregister(key.fileobj)
                            continue
                        complete_hash.update(block)
                        total += len(block)
                        retained = block[:max(0, LOG_LIMIT - captured)]
                        stream.write(retained)
                        captured += len(retained)
            row["exit_code"] = process.wait(timeout=5)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
            raise
        finally:
            process.stdout.close()
            row["elapsed_seconds"] = time.monotonic() - started
            row["finished_utc"] = stamp()
    row["log"] = {"bytes": log.stat().st_size, "sha256": digest(log),
                  "stream_bytes_observed": total, "stream_sha256_observed": complete_hash.hexdigest(),
                  "captured_prefix_only": total > captured}
    if row.get("timed_out") or row["exit_code"] != expected_exit:
        raise RuntimeError(name + " did not meet its required exit status")


def verify_negative(output, name, message):
    path = output / name / "receipt.json"
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError(name + " did not retain a bounded refusal receipt")
    value = json.loads(path.read_text())
    if (value.get("success") is not False or message not in value.get("error", {}).get("message", "")
            or (output / name / "offload-index").exists()):
        raise ValueError(name + " did not refuse before model-index creation")
    return {"receipt_sha256": digest(path), "refused_before_index": True,
            "error_type": value["error"]["type"], "expected_reason_observed": True}


def locked_cli():
    """Fixed sibling CLI only, with a lock spanning its complete model run."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock-path", type=Path, required=True)
    parser.add_argument("cli_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(sys.argv[2:])
    if not args.cli_args or args.cli_args[0] != "--":
        raise ValueError("locked CLI arguments require a separator")
    cli = Path(__file__).resolve().parent / "parallax_virtual_generate.py"
    with take_lock(args.lock_path):
        sys.argv = [str(cli)] + args.cli_args[1:]
        runpy.run_path(str(cli), run_name="__main__")


def main():
    source = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--lock-path", type=Path, required=True)
    args = parser.parse_args()
    base, python = args.base.resolve(strict=True), args.python.absolute()
    if not python.is_file():
        raise ValueError("explicit installed Python executable is missing")
    output = args.output.absolute()
    output.mkdir(mode=0o700, parents=False)
    report = {"schema": "merlin-parallax-virtual-replay/1", "success": False,
              "started_utc": stamp(), "launches": [], "environment_inheritance": "none",
              "launcher_sha256": digest(Path(__file__)), "stage": "verify_protocol",
              "shared_resource_lock": str(args.lock_path.absolute())}
    try:
        protocol = verify_protocol(args.protocol, source)
        if protocol["managed_bytes"] % (1024**2):
            raise ValueError("CLI budget must be an exact whole MiB")
        report["protocol_sha256"] = digest(args.protocol)
        report["source_sha256"] = protocol["source_sha256"]
        env = constructed_environment(output / "private-environment")
        report["constructed_environment"] = env
        prefix = [str(python), "-B"]
        probe = [str(source / "parallax_virtual_probe.py"), "--base", str(base),
                 "--protocol", str(args.protocol.resolve()), "--lock-path", str(args.lock_path.absolute())]
        receipts = {}
        for mode, reference in (("resident", None), ("direct", "resident"), ("virtual", "direct")):
            report["stage"] = mode
            argv = prefix + probe + ["--mode", mode, "--output", str(output / mode)]
            if reference:
                argv += ["--reference", str(output / reference), "--reference-sha256",
                         digest(output / reference / "receipt.json")]
            run_child(mode, argv, output, env, report)
            receipts[mode] = read_success(output / mode / "receipt.json")
        original, direct, virtual = (receipts[name] for name in ("resident", "direct", "virtual"))
        for value in (direct, virtual):
            if (value["greedy_tokens"] != original["greedy_tokens"]
                    or len(value["comparison"]) != 4
                    or not all(row["finite"] and row["allclose"] for row in value["comparison"])):
                raise ValueError("full-logit equivalence or exact greedy token sequence failed")
        cli = prefix + [str(Path(__file__).resolve()), "--locked-cli", "--lock-path",
                        str(args.lock_path.absolute()), "--", "--base", str(base),
                        "--managed-mib", str(protocol["managed_bytes"] // (1024**2)),
                        "--tile-rows", str(protocol["tile_rows"])]
        report["stage"] = "generation"
        run_child("generation", cli + ["--output", str(output / "generation"), "--prompt", protocol["prompt"],
                  "--max-new-tokens", "4"], output, env, report)
        generated = read_success(output / "generation" / "receipt.json")
        if (generated["generated_tokens"] != protocol["expected_token_ids"]
                or generated["generated_tokens"] != original["greedy_tokens"]
                or generated["logical_accelerator"]["actual_device"] != "cpu"
                or generated["logical_accelerator"]["hardware_acceleration"] is not False
                or generated["virtual_memory"]["managed_current_bytes"] != 0
                or generated["virtual_memory"]["managed_peak_bytes"] > protocol["managed_bytes"]):
            raise ValueError("bounded virtual continuation did not meet token/device/resource acceptance")
        negatives = [
            ("cuda-negative", ["--device", "cuda"], protocol["prompt"], "CUDA is unavailable"),
            ("tiny-budget-negative", ["--managed-mib", "1"], protocol["prompt"], "required tile buffers"),
            ("token-bound-negative", [], "word " * 100, "64 prompt tokens"),
        ]
        refusals = {}
        for name, extra, prompt, reason in negatives:
            report["stage"] = name
            run_child(name, cli + ["--output", str(output / name), "--prompt", prompt,
                      "--max-new-tokens", "1"] + extra, output, env, report, expected_exit=1)
            refusals[name] = verify_negative(output, name, reason)
        report["checks"] = {"finite_full_logits_allclose": True,
            "direct_full_logits_bitwise_equal": all(row["bitwise_equal"] for row in direct["comparison"]),
            "virtual_full_logits_bitwise_equal": all(row["bitwise_equal"] for row in virtual["comparison"]),
            "exact_greedy_tokens": original["greedy_tokens"], "bounded_cli_equal": True,
            "managed_peak_bytes": virtual["virtual_memory"]["managed_peak_bytes"],
            "managed_budget_bytes": protocol["managed_bytes"], "refusals": refusals}
        report["process_peak_rss_bytes"] = {name: value["memory"]["after_inference"]["process_peak_rss_bytes"]
                                             for name, value in receipts.items()}
        # Refuse edits made while a run was in progress, even after valid results.
        verify_protocol(args.protocol, source)
        if digest(args.protocol) != report["protocol_sha256"]:
            raise ValueError("protocol changed during the experiment")
        report["stage"], report["success"] = "complete", True
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
    finally:
        report["finished_utc"] = stamp()
        report["memory_scope"] = (
            "Separate process peaks include initialization. Resident additionally performs an R-zero control; "
            "direct and virtual hold reference arrays. Owned row buffers are a separate limited subset, not whole-process RAM. "
            "Timing and memory are descriptive; no equal-workload speed, physical-SSD, cold-cache or GPU-acceleration claim.")
        report["artifacts"] = {}
        for child in CHILDREN:
            for name in ("receipt.json", "logits.safetensors", "r-zero-logits.safetensors", "failure-traceback.txt", "offload-index/index.json"):
                path = output / child / name
                if path.is_file():
                    report["artifacts"][child + "/" + name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        with (output / "launch-receipt.json").open("x") as stream:
            stream.write(raw)
        print(json.dumps({"success": report["success"], "stage": report["stage"], "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--locked-cli":
        locked_cli()
    else:
        raise SystemExit(main())
