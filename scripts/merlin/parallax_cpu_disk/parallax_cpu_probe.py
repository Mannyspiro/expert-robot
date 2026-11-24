#!/usr/bin/env python3
"""Recovered Parallax CPU experiment support; new source requires fresh evidence.

The previous successful receipts were lost. This reconstruction preserves the
fixed FP32 numerical checks but does not recreate or claim those missing files.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import resource
import sys
import types


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(value) for key, value in item.items()}
        if isinstance(item, (set, frozenset)):
            return [normalize(value) for value in sorted(item, key=repr)]
        if isinstance(item, (list, tuple)):
            return [normalize(value) for value in item]
        return item
    raw = json.dumps(normalize(value), indent=2, sort_keys=True, allow_nan=False) + "\n"
    with path.open("x") as stream:
        stream.write(raw)


def verify_payloads(base: Path, name: str, expected_lock_hash: str) -> list[dict]:
    from setup_cpu_candidate import verify_file
    lock_path = base / name
    if sha256_file(lock_path) != expected_lock_hash:
        raise ValueError("payload lock differs from frozen protocol")
    lock = json.loads(lock_path.read_text())
    if lock.get("schema") != "merlin-public-payload-lock-v1" or not 1 <= len(lock["files"]) <= 80:
        raise ValueError("invalid or unbounded payload lock")
    rows = []
    for entry in lock["files"]:
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("payload path escaped candidate")
        path = base.joinpath(*relative.parts)
        if base.resolve() not in path.resolve().parents:
            raise ValueError("payload path escaped candidate")
        rows.append(verify_file(path, entry))
    return rows


def import_author(checkpoint: Path):
    package_name = "_merlin_pinned_parallax_author"
    package = types.ModuleType(package_name)
    package.__path__ = [str(checkpoint)]
    sys.modules[package_name] = package
    for name in ("configuration_parallax", "modeling_parallax"):
        full_name = package_name + "." + name
        spec = importlib.util.spec_from_file_location(full_name, checkpoint / (name + ".py"))
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot import audited author module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
    return (sys.modules[package_name + ".configuration_parallax"].ParallaxConfig,
            sys.modules[package_name + ".modeling_parallax"].ParallaxForCausalLM)


def tensor_digest(tensor) -> str:
    array = tensor.detach().cpu().contiguous().numpy()
    return hashlib.sha256(memoryview(array).cast("B")).hexdigest()


def memory_snapshot() -> dict:
    import psutil
    value = psutil.Process().memory_full_info()
    return {"rss_bytes": value.rss, "uss_bytes": value.uss,
            "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


def assert_meta(model) -> dict:
    values = list(model.named_parameters(remove_duplicate=False))
    if len(values) != 367 or any(param.device.type != "meta" for _, param in values):
        raise ValueError("offloaded parameter did not return to meta")
    return {"named_parameter_paths": len(values), "all_meta": True}


def verify_r_parameters(model, checkpoint: Path) -> list[dict]:
    import torch
    from safetensors import safe_open
    parameters = dict(model.named_parameters(remove_duplicate=False))
    rows = []
    with safe_open(str(checkpoint / "model-00001-of-00001.safetensors"), framework="pt", device="cpu") as source:
        for layer in range(28):
            for suffix, shape in (("r_proj.weight", [2048, 1024]), ("r_norm.weight", [128])):
                name = f"model.layers.{layer}.self_attn.{suffix}"
                original = source.get_tensor(name)
                loaded = parameters[name]
                if list(original.shape) != shape or original.dtype != torch.bfloat16:
                    raise ValueError("unexpected learned R layout")
                if loaded.dtype != torch.float32 or loaded.device.type != "cpu" or not torch.equal(original.float(), loaded):
                    raise ValueError("loaded R differs from source conversion")
                nonzero = torch.count_nonzero(loaded).item()
                if nonzero == 0 or not torch.isfinite(loaded).all():
                    raise ValueError("R tensor is zero or non-finite")
                rows.append({"name": name, "shape": shape, "nonzero_values": nonzero,
                             "loaded_sha256": tensor_digest(loaded)})
    return rows


def run_steps(model, input_ids, protocol: dict, forced: list[int] | None, require_meta: bool):
    import time
    import torch
    from transformers.cache_utils import DynamicCache
    cache = DynamicCache(config=model.config)
    logits, rows, tokens = {}, [], []
    total, current = input_ids.shape[1], input_ids
    for step in range(protocol["cached_decode_steps"] + 1):
        started = time.monotonic()
        with torch.inference_mode():
            output = model(input_ids=current, attention_mask=torch.ones((1, total), dtype=torch.long, device="cpu"),
                           past_key_values=cache, use_cache=True, return_dict=True)
        cache = output.past_key_values
        values = output.logits.detach().cpu().contiguous()
        if values.dtype != torch.float32 or not torch.isfinite(values).all():
            raise ValueError("logits are not finite FP32")
        lengths = [int(cache.get_seq_length(layer)) for layer in range(28)]
        if lengths != [total] * 28 or len(cache.layers) != 28:
            raise ValueError("cache length mismatch")
        for layer in cache.layers:
            for value in (layer.keys, layer.values):
                if (value.device.type != "cpu" or value.dtype != torch.float32
                        or list(value.shape) != [1, 8, total, 128] or not torch.isfinite(value).all()):
                    raise ValueError("cache layout, device, dtype or finite-value check failed")
        token = int(values[0, -1].argmax().item())
        tokens.append(token)
        name = "prefill" if step == 0 else f"decode_{step}"
        logits[name] = values
        row = {"stage": name, "logits_shape": list(values.shape), "logits_sha256": tensor_digest(values),
               "top_token_id": token, "cache_lengths": lengths, "cache_cpu_fp32_shape_finite_verified": True,
               "forward_seconds": time.monotonic() - started}
        if require_meta:
            row["post_forward_parameters"] = assert_meta(model)
        rows.append(row)
        selected = token if forced is None else forced[step]
        current = torch.tensor([[selected]], dtype=torch.long, device="cpu")
        total += 1
        del output
    return logits, rows, tokens


def compare_logits(actual: dict, expected: dict, protocol: dict) -> list[dict]:
    import torch
    if set(actual) != set(expected):
        raise ValueError("logit stage sets differ")
    rows = []
    for name, reference in expected.items():
        value = actual[name]
        if value.shape != reference.shape:
            raise ValueError("logit shapes differ")
        finite = bool(torch.isfinite(reference).all() and torch.isfinite(value).all())
        delta = (value - reference).abs()
        rows.append({"stage": name, "same_shape": True, "finite": finite,
                     "allclose": finite and torch.allclose(value, reference, atol=protocol["atol"], rtol=protocol["rtol"]),
                     "bitwise_equal": tensor_digest(value) == tensor_digest(reference),
                     "max_absolute_error": delta.max().item(), "mean_absolute_error": delta.mean().item()})
    return rows


def r_zero_control(model, inputs, baseline, protocol):
    import torch
    calls = [0]
    def zero(module, args, output):
        calls[0] += 1
        return torch.zeros_like(output)
    handles = [layer.self_attn.r_norm.register_forward_hook(zero) for layer in model.model.layers]
    try:
        with torch.inference_mode():
            logits = model(input_ids=inputs, attention_mask=torch.ones_like(inputs), use_cache=False, return_dict=True).logits.detach().cpu().contiguous()
        finite = bool(torch.isfinite(logits).all())
        changed = not torch.allclose(logits, baseline, atol=protocol["atol"], rtol=protocol["rtol"])
        result = {"hook_calls": calls[0], "finite": finite, "differs_beyond_tolerance": changed,
                  "max_absolute_difference": (logits - baseline).abs().max().item()}
        if calls[0] != 28 or not finite or not changed:
            raise ValueError("R-zero use-control failed")
        return logits, result
    finally:
        for handle in handles:
            handle.remove()
