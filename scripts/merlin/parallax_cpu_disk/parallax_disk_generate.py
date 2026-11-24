#!/usr/bin/env python3
"""Bounded offline continuation with the pinned author Parallax CPU/disk model."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

import parallax_cpu_probe as support
import parallax_direct_disk as direct

CHECKPOINT_LOCK_SHA256 = "bc21d1390c2c68001aa4c1ad2e2a72441b4a82125bdc0d2ffde8f98ef801deb5"
WHEEL_LOCK_SHA256 = "a3ff9c700b1bde73972b5b9f9cad0e6d62e541291fc6e14f748a79c21ea83412"
MAX_PROMPT_TOKENS = 64
MAX_NEW_TOKENS = 16


def validate_request(prompt, max_new_tokens):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode("utf-8")) > 4096:
        raise ValueError("prompt must contain text and fit within 4,096 UTF-8 bytes")
    if type(max_new_tokens) is not int or not 1 <= max_new_tokens <= MAX_NEW_TOKENS:
        raise ValueError("maximum new tokens must be an integer from 1 to 16")


def generate(base, output, prompt, max_new_tokens):
    validate_request(prompt, max_new_tokens)
    if sys.version_info[:2] != (3, 11):
        raise ValueError("this profile requires CPython 3.11")
    for key, value in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                       "HF_HUB_DISABLE_XET": "1", "TOKENIZERS_PARALLELISM": "false", "CUDA_VISIBLE_DEVICES": ""}.items():
        os.environ[key] = value
    support.verify_payloads(base, "checkpoint-lock.json", CHECKPOINT_LOCK_SHA256)
    support.verify_payloads(base, "wheel-lock.json", WHEEL_LOCK_SHA256)
    for row in json.loads((base / "wheel-lock.json").read_text())["files"]:
        if importlib.metadata.version(row["name"]) != row["version"]:
            raise ValueError("installed runtime version differs from the pinned closure")
    import torch
    from tokenizers import Tokenizer
    from transformers.cache_utils import DynamicCache
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    if torch.__version__ != "2.9.1+cpu" or torch.cuda.is_available():
        raise ValueError("unexpected CPU Torch runtime")
    checkpoint = base / "checkpoint"
    tokenizer = Tokenizer.from_file(str(checkpoint / "tokenizer.json"))
    inputs = torch.tensor([tokenizer.encode(prompt, add_special_tokens=False).ids], dtype=torch.long, device="cpu")
    if not 1 <= inputs.shape[1] <= MAX_PROMPT_TOKENS:
        raise ValueError("this CPU profile accepts at most 64 prompt tokens")
    model, provenance = direct.load_direct(checkpoint, output / "offload-index")
    cache = DynamicCache(config=model.config)
    current, total, generated, steps = inputs, inputs.shape[1], [], []
    eos = model.config.eos_token_id
    eos = set(eos if isinstance(eos, list) else [eos])
    for step in range(max_new_tokens):
        started = time.monotonic()
        with torch.inference_mode():
            result = model(input_ids=current, attention_mask=torch.ones((1, total), dtype=torch.long),
                           past_key_values=cache, use_cache=True, return_dict=True)
        cache, logits = result.past_key_values, result.logits
        if logits.dtype != torch.float32 or logits.device.type != "cpu" or not torch.isfinite(logits).all():
            raise ValueError("model returned invalid CPU logits")
        for layer in range(28):
            if cache.get_seq_length(layer) != total:
                raise ValueError("KV cache length differs from input")
            for value in (cache.layers[layer].keys, cache.layers[layer].values):
                if (tuple(value.shape) != (1, 8, total, 128) or value.dtype != torch.float32
                        or value.device.type != "cpu" or not torch.isfinite(value).all()):
                    raise ValueError("KV cache layout/device/finite-value check failed")
        token = int(logits[0, -1].argmax().item())
        generated.append(token)
        steps.append({"step": step + 1, "input_tokens_in_cache": total, "seconds": time.monotonic() - started,
                      "post_forward_inventory": direct.meta_inventory(model)})
        del result, logits
        if token in eos:
            break
        current = torch.tensor([[token]], dtype=torch.long)
        total += 1
    if support.sha256_file(output / "offload-index/index.json") != provenance["index_sha256"]:
        raise ValueError("offload index changed during generation")
    direct.check_unchanged(checkpoint, provenance)
    return {"schema": "merlin-parallax-disk-continuation/1", "success": True,
            "model_id": "YifeiZuo/Parallax-0.6B", "revision": "0cf73e2d49ea1a09a9ef85178b73ad68e019ae36",
            "input_tokens": inputs.shape[1], "generated_tokens": generated,
            "continuation": tokenizer.decode(generated, skip_special_tokens=True), "stopped_at_eos": generated[-1] in eos,
            "generation_steps": steps, "loader": provenance, "memory_after_generation": support.memory_snapshot(),
            "limits": {"prompt_tokens": 64, "new_tokens": 16, "cpu_threads": 2, "device": "cpu", "sampling": "greedy"},
            "scope": "Experimental plain-text continuation; weights offloaded, KV and activations in RAM; no assistant-quality qualification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=8)
    args = parser.parse_args()
    validate_request(args.prompt, args.max_new_tokens)
    args.output.mkdir(mode=0o700, parents=False)
    try:
        receipt = generate(args.base, args.output, args.prompt, args.max_new_tokens)
    except Exception as exc:
        receipt = {"schema": "merlin-parallax-disk-continuation/1", "success": False,
                   "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
    support.write_json(args.output / "receipt.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("success", "continuation", "error") if key in receipt}))
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
