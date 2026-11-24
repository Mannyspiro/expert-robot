#!/usr/bin/env python3
"""Bounded Parallax continuation using paged weights and a CPU logical device."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import parallax_cpu_probe as support
import parallax_direct_disk as direct
import parallax_direct_probe as runtime
from parallax_disk_generate import validate_request, MAX_PROMPT_TOKENS

CHECKPOINT_LOCK_SHA256 = "bc21d1390c2c68001aa4c1ad2e2a72441b4a82125bdc0d2ffde8f98ef801deb5"
WHEEL_LOCK_SHA256 = "a3ff9c700b1bde73972b5b9f9cad0e6d62e541291fc6e14f748a79c21ea83412"


def generate(base, output, prompt, max_new_tokens, *, device="cpu", managed_bytes=32 * 1024**2, tile_rows=4096):
    validate_request(prompt, max_new_tokens)
    from parallax_virtual_memory import validate_budget, load_ram_managed
    validate_budget(managed_bytes, tile_rows)
    versions = runtime.configure(base, {"checkpoint_lock_sha256": CHECKPOINT_LOCK_SHA256,
                                         "wheel_lock_sha256": WHEEL_LOCK_SHA256})
    import torch
    from tokenizers import Tokenizer
    from transformers.cache_utils import DynamicCache
    from parallax_virtual_device import select_backend, ExecutionLimits
    accelerator = select_backend(device, limits=ExecutionLimits(max_forward_calls=max_new_tokens))
    checkpoint = base / "checkpoint"
    tokenizer = Tokenizer.from_file(str(checkpoint / "tokenizer.json"))
    ids = tokenizer.encode(prompt, add_special_tokens=False).ids
    if not 1 <= len(ids) <= MAX_PROMPT_TOKENS:
        raise ValueError("this virtual resource profile accepts at most 64 prompt tokens")
    inputs = torch.tensor([ids], dtype=torch.long, device="cpu")
    model, provenance, manager = load_ram_managed(checkpoint, output / "offload-index", managed_bytes, tile_rows)
    try:
        cache = DynamicCache(config=model.config)
        current, total, generated, steps = inputs, len(ids), [], []
        eos = model.config.eos_token_id
        eos = set(eos if isinstance(eos, list) else [eos])
        for step in range(max_new_tokens):
            started = time.monotonic()
            result = accelerator.forward(model, input_ids=current,
                attention_mask=torch.ones((1, total), dtype=torch.long, device="cpu"),
                past_key_values=cache, use_cache=True, return_dict=True)
            cache, logits = result.past_key_values, result.logits
            for layer in range(28):
                if cache.get_seq_length(layer) != total:
                    raise ValueError("KV cache length differs from the accepted input")
                for value in (cache.layers[layer].keys, cache.layers[layer].values):
                    if (tuple(value.shape) != (1, 8, total, 128) or value.dtype != torch.float32
                            or value.device.type != "cpu" or not torch.isfinite(value).all()):
                        raise ValueError("invalid finite CPU FP32 KV cache")
            token = int(logits[0, -1].argmax().item())
            generated.append(token)
            steps.append({"step": step + 1, "input_tokens_in_cache": total,
                          "seconds": time.monotonic() - started,
                          "post_forward_inventory": direct.meta_inventory(model),
                          "virtual_memory": manager.snapshot(), "logical_accelerator": accelerator.snapshot()})
            del result, logits
            if token in eos:
                break
            current = torch.tensor([[token]], dtype=torch.long, device="cpu")
            total += 1
        if support.sha256_file(output / "offload-index/index.json") != provenance["index_sha256"]:
            raise ValueError("offload index changed during generation")
        direct.check_unchanged(checkpoint, provenance)
        return {"schema": "merlin-parallax-virtual-continuation/1", "success": True,
                "runtime": versions, "model_id": provenance["model_id"], "revision": provenance["revision"],
                "input_tokens": len(ids), "generated_tokens": generated,
                "continuation": tokenizer.decode(generated, skip_special_tokens=True),
                "stopped_at_eos": generated[-1] in eos, "generation_steps": steps, "loader": provenance,
                "virtual_memory": manager.snapshot(), "logical_accelerator": accelerator.snapshot(),
                "process_memory_after_generation": support.memory_snapshot(),
                "scope": "Experimental plain-text continuation. CPU performs arithmetic; owned row-buffer budget excludes other weights, full outputs, KV, activations, runtime and OS cache. No GPU hardware or assistant-quality qualification."}
    finally:
        manager.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                        help="cpu is the qualified software backend; cuda requests fail without hardware and a qualified GPU profile")
    parser.add_argument("--managed-mib", type=int, default=32,
                        help="budget for owned weight-row buffers, not whole-process RAM")
    parser.add_argument("--tile-rows", type=int, default=4096)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=False)
    try:
        receipt = generate(args.base, args.output, args.prompt, args.max_new_tokens,
                           device=args.device, managed_bytes=args.managed_mib * 1024**2, tile_rows=args.tile_rows)
    except Exception as exc:
        receipt = {"schema": "merlin-parallax-virtual-continuation/1", "success": False,
                   "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
    support.write_json(args.output / "receipt.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("success", "continuation", "error") if key in receipt}))
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
