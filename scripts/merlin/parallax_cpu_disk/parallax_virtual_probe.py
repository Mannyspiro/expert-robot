#!/usr/bin/env python3
"""Fresh, locked acceptance for resident, direct and managed logical CPU paths."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import time
import traceback

import parallax_cpu_probe as support
import parallax_direct_disk as direct
import parallax_direct_probe as original


def verify_protocol(path, source):
    protocol = json.loads(bounded_read(path, 65536), object_pairs_hook=_unique_object)
    required = {"schema": "merlin-parallax-virtual-protocol/1", "prompt": "The capital of France is",
                "cached_decode_steps": 3, "atol": 1e-5, "rtol": 1e-5,
                "device": "cpu", "dtype": "float32", "attention": "eager",
                "torch_threads": 2, "interop_threads": 1, "seed": 0,
                "managed_bytes": 32 * 1024**2, "tile_rows": 4096,
                "expected_token_ids": [12095, 11, 323, 279]}
    if any(protocol.get(key) != value for key, value in required.items()):
        raise ValueError("protocol differs from the predeclared virtual experiment")
    expected = protocol.get("source_sha256", {})
    must_cover = {"parallax_virtual_probe.py", "parallax_virtual_device.py", "parallax_virtual_memory.py",
                  "run_virtual_replay.py", "parallax_virtual_generate.py", "parallax_cpu_probe.py",
                  "parallax_direct_disk.py", "parallax_direct_probe.py", "parallax_disk_generate.py",
                  "setup_cpu_candidate.py", "run_replay.py"}
    if not must_cover <= set(expected) or not len(expected) <= 24:
        raise ValueError("protocol does not cover the executed source closure")
    for name, wanted in expected.items():
        if Path(name).name != name or support.sha256_file(source / name) != wanted:
            raise ValueError("source differs from the frozen protocol")
    return protocol


def take_lock(path):
    """The descriptor stays open through model work; no nested outer lock."""
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ValueError("experiment lock must be a regular nonsymlink file")
    stream = os.fdopen(fd, "r+b", buffering=0)
    try:
        fcntl.flock(stream, fcntl.LOCK_EX)
    except BaseException:
        stream.close()
        raise
    return stream


REFERENCE_SHAPES = {"prefill": [1, 5, 151936], **{f"decode_{i}": [1, 1, 151936] for i in range(1, 4)}}
REFERENCE_DATA_BYTES = 4861952
REFERENCE_HEADER_BYTES = 65536


def _stamp(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def bounded_read(path, cap):
    """Return exact bytes from one bounded, stable regular descriptor."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= cap:
        raise ValueError("reference file is not regular or exceeds its byte bound")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _stamp(opened) != _stamp(before):
            raise ValueError("reference changed while opening")
        result = bytearray()
        while len(result) < opened.st_size:
            block = os.read(fd, min(65536, opened.st_size - len(result)))
            if not block:
                raise ValueError("reference was truncated")
            result.extend(block)
        if (os.read(fd, 1) or _stamp(os.fstat(fd)) != _stamp(opened)
                or _stamp(path.lstat()) != _stamp(opened)):
            raise ValueError("reference changed during bounded read")
        return bytes(result)
    finally:
        os.close(fd)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate reference JSON key")
        result[key] = value
    return result


def validate_reference_arrays(raw):
    if not 8 < len(raw) <= 8 + REFERENCE_HEADER_BYTES + REFERENCE_DATA_BYTES:
        raise ValueError("reference arrays exceed fixed byte bound")
    header_bytes = struct.unpack("<Q", raw[:8])[0]
    if not 0 < header_bytes <= REFERENCE_HEADER_BYTES or 8 + header_bytes + REFERENCE_DATA_BYTES != len(raw):
        raise ValueError("reference array header or data size differs")
    header = json.loads(raw[8:8 + header_bytes], object_pairs_hook=_unique_object)
    if not isinstance(header, dict) or set(header) - {"__metadata__"} != set(REFERENCE_SHAPES):
        raise ValueError("reference array stage names differ")
    ranges = []
    for name, shape in REFERENCE_SHAPES.items():
        entry = header[name]
        offsets = entry.get("data_offsets")
        if (entry.get("dtype") != "F32" or entry.get("shape") != shape
                or not isinstance(offsets, list) or len(offsets) != 2
                or any(type(value) is not int for value in offsets)
                or not 0 <= offsets[0] < offsets[1] <= REFERENCE_DATA_BYTES
                or offsets[1] - offsets[0] != shape[1] * shape[2] * 4):
            raise ValueError("reference array dtype, shape or data range differs")
        ranges.append(tuple(offsets))
    position = 0
    for start, end in sorted(ranges):
        if start != position:
            raise ValueError("reference array ranges overlap or leave gaps")
        position = end
    if position != REFERENCE_DATA_BYTES:
        raise ValueError("reference array payload coverage differs")


def load_reference(args, report):
    from safetensors.torch import load
    expected_mode = "resident" if args.mode == "direct" else "direct"
    if args.reference is None or args.reference_sha256 is None:
        raise ValueError("offloaded mode requires a separately hashed fresh reference")
    raw = bounded_read(args.reference / "receipt.json", 1024**2)
    if hashlib.sha256(raw).hexdigest() != args.reference_sha256:
        raise ValueError("reference receipt hash differs")
    reference = json.loads(raw, object_pairs_hook=_unique_object)
    if (reference.get("success") is not True or reference.get("mode") != expected_mode
            or reference.get("protocol_sha256") != report["protocol_sha256"]
            or reference.get("source_sha256") != report["source_sha256"]):
        raise ValueError("reference did not pass the same source and protocol")
    if expected_mode == "resident":
        if reference.get("r_use_control", {}).get("differs_beyond_tolerance") is not True:
            raise ValueError("resident reference did not pass learned-R use control")
        report["resident_reference_receipt_sha256"] = args.reference_sha256
    else:
        if (reference.get("greedy_tokens_equal") is not True
                or len(reference.get("comparison", [])) != 4
                or not all(row["finite"] and row["allclose"] for row in reference["comparison"])):
            raise ValueError("direct reference did not pass finite full-logit comparison")
        report["direct_reference_receipt_sha256"] = args.reference_sha256
        report["fresh_resident_reference_receipt_sha256"] = reference["resident_reference_receipt_sha256"]
    raw = bounded_read(args.reference / "logits.safetensors", 8 + REFERENCE_HEADER_BYTES + REFERENCE_DATA_BYTES)
    validate_reference_arrays(raw)
    if hashlib.sha256(raw).hexdigest() != reference["artifacts"]["logits.safetensors"]["sha256"]:
        raise ValueError("reference array payload hash differs")
    return reference, load(raw)


def run_offloaded(args, protocol, report):
    virtual = args.mode == "virtual"
    if virtual:
        from parallax_virtual_memory import validate_budget, load_ram_managed
        validate_budget(protocol["managed_bytes"], protocol["tile_rows"])
    report["runtime"] = original.configure(args.base, protocol)
    import torch
    from accelerate.hooks import ModelHook, add_hook_to_module
    from safetensors.torch import save_file
    from tokenizers import Tokenizer
    from parallax_virtual_device import ExecutionLimits, select_backend
    accelerator = select_backend("cpu", limits=ExecutionLimits(max_forward_calls=4)) if virtual else None
    if virtual:
        report["logical_accelerator"] = accelerator.descriptor()
    checkpoint = args.base / "checkpoint"
    reference_report, reference = load_reference(args, report)
    forced = reference_report["greedy_tokens"]
    report["memory"] = {"before_model_load": support.memory_snapshot()}
    report["stage"] = "load_" + args.mode + "_model"
    started = time.monotonic()
    manager = None
    if virtual:
        model, provenance, manager = load_ram_managed(checkpoint, args.output / "offload-index",
                                                     protocol["managed_bytes"], protocol["tile_rows"])
    else:
        model, provenance = direct.load_direct(checkpoint, args.output / "offload-index")
    report["direct_loader"] = provenance
    report["load_seconds"] = time.monotonic() - started
    report["memory"]["after_model_load"] = support.memory_snapshot()
    try:
        if model.config._attn_implementation != "eager" or model.config.attn_type != "parallax":
            raise ValueError("model is not explicit eager Parallax")
        tokenizer = Tokenizer.from_file(str(checkpoint / "tokenizer.json"))
        ids = tokenizer.encode(protocol["prompt"], add_special_tokens=False).ids
        report["inputs"] = {"prompt": protocol["prompt"], "token_ids": ids, "unpadded": True,
                            "raw_tokenizer_sha256": support.sha256_file(checkpoint / "tokenizer.json")}
        if len(ids) != 5 or report["inputs"] != reference_report["inputs"]:
            raise ValueError("inputs differ from the fresh reference")
        observed, snapshots = {}, []

        class ObserveCPU(ModelHook):
            def __init__(self, name):
                self.name = name

            def pre_forward(self, module, *values, **kwargs):
                if module.weight.device.type != "cpu" or module.weight.dtype != torch.float32:
                    raise ValueError("active learned R was not restored to FP32 CPU")
                observed[self.name] = observed.get(self.name, 0) + 1
                return values, kwargs

        for name, module in model.named_modules():
            if name.endswith((".r_proj", ".r_norm")):
                add_hook_to_module(module, ObserveCPU(name), append=True)

        class BoundForward:
            config = model.config

            def named_parameters(self, *args, **kwargs):
                return model.named_parameters(*args, **kwargs)

            def __call__(self, **kwargs):
                result = accelerator.forward(model, **kwargs)
                snapshot = manager.snapshot()
                if (snapshot["managed_current_bytes"] != 0
                        or snapshot["managed_peak_bytes"] > protocol["managed_bytes"]
                        or snapshot["tiles_loaded"] != snapshot["tiles_released"]):
                    raise ValueError("managed row buffers exceed budget or remain live after forward")
                snapshots.append({"virtual_memory": snapshot, "logical_accelerator": accelerator.snapshot()})
                return result

        report["stage"] = args.mode + "_inference"
        inputs = torch.tensor([ids], dtype=torch.long, device="cpu")
        logits, rows, tokens = support.run_steps(BoundForward() if virtual else model, inputs, protocol, forced, True)
        save_file(logits, str(args.output / "logits.safetensors"))
        report["steps"], report["greedy_tokens"] = rows, tokens
        if virtual:
            report["resource_snapshots"] = snapshots
        report["decoded_greedy_continuation"] = tokenizer.decode(tokens, skip_special_tokens=True)
        report["comparison"] = support.compare_logits(logits, reference, protocol)
        report["greedy_tokens_equal"] = tokens == forced
        report["r_cpu_hook_observations"] = observed
        report["post_forward_inventory"] = direct.meta_inventory(model)
        if (len(observed) != 56 or set(observed.values()) != {4} or tokens != forced
                or tokens != protocol["expected_token_ids"]
                or not all(row["finite"] and row["allclose"] for row in report["comparison"])):
            raise ValueError("offloaded numerical or active-R acceptance failed")
        index = args.output / "offload-index"
        if ([p.name for p in index.iterdir()] != ["index.json"]
                or support.sha256_file(index / "index.json") != provenance["index_sha256"]):
            raise ValueError("offload index changed or a copied payload appeared")
        if virtual:
            manager.check_source()
        direct.check_unchanged(checkpoint, provenance)
        if virtual:
            report["virtual_memory"] = manager.snapshot()
            report["logical_accelerator"] = accelerator.snapshot()
        report["memory"]["after_inference"] = support.memory_snapshot()
        report["stage"], report["success"] = "complete", True
    finally:
        if manager is not None:
            manager.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mode", choices=("resident", "direct", "virtual"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-sha256")
    parser.add_argument("--lock-path", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=False)
    report = {"schema": "merlin-parallax-virtual-acceptance/1", "success": False,
              "stage": "verify_source", "mode": args.mode, "fresh_process": True,
              "pid": os.getpid()}
    lock = None
    try:
        protocol = verify_protocol(args.protocol, Path(__file__).resolve().parent)
        report["protocol_sha256"] = support.sha256_file(args.protocol)
        report["source_sha256"] = protocol["source_sha256"]
        report["stage"] = "wait_shared_resource_lock"
        lock = take_lock(args.lock_path)
        report["resource_lock"] = {"path": str(args.lock_path), "exclusive": True, "pid": os.getpid()}
        if args.mode == "resident":
            original.run(args, protocol, report)
        else:
            run_offloaded(args, protocol, report)
        if report["greedy_tokens"] != protocol["expected_token_ids"] or len(report["inputs"]["token_ids"]) != 5:
            report["success"] = False
            raise ValueError("fixed prompt or greedy oracle changed")
    except Exception as exc:
        report["success"] = False
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        (args.output / "failure-traceback.txt").write_text(traceback.format_exc()[-16384:])
    finally:
        if lock is not None:
            lock.close()
        report["limitations"] = [
            "CPU software execution; no GPU acceleration or generic CUDA emulation.",
            "Managed row-buffer budget excludes other weights, returned logits, KV, activations, runtime and OS cache.",
            "All complete hashes warm source files; no cold-storage or physical-SSD measurement.",
            "Resident includes an R-zero control; direct and virtual retain reference arrays. Timing and RSS are descriptive, not equal-workload speed comparisons."]
        report["artifacts"] = {p.name: {"bytes": p.stat().st_size, "sha256": support.sha256_file(p)}
                               for p in args.output.iterdir() if p.is_file()}
        support.write_json(args.output / "receipt.json", report)
        print(json.dumps({"success": report["success"], "mode": args.mode,
                          "stage": report["stage"], "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
