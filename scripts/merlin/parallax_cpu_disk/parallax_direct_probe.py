#!/usr/bin/env python3
"""Fresh recovery acceptance: resident R-control and direct-file CPU equivalence."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback

import parallax_cpu_probe as support
import parallax_direct_disk as direct


def configure(base: Path, protocol: dict) -> dict:
    if sys.version_info[:2] != (3, 11):
        raise ValueError("candidate requires CPython 3.11")
    for key, value in {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
                       "HF_HUB_DISABLE_XET": "1", "TOKENIZERS_PARALLELISM": "false", "CUDA_VISIBLE_DEVICES": ""}.items():
        os.environ[key] = value
    for name in ("checkpoint-lock.json", "wheel-lock.json"):
        support.verify_payloads(base, name, protocol[name.replace("-", "_").replace(".json", "_sha256")])
    for row in json.loads((base / "wheel-lock.json").read_text())["files"]:
        if importlib.metadata.version(row["name"]) != row["version"]:
            raise ValueError("installed distribution differs from fixed wheel version")
    import torch
    import accelerate
    import transformers
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    if torch.__version__ != "2.9.1+cpu" or torch.cuda.is_available():
        raise ValueError("unexpected CPU Torch runtime")
    return {"python": sys.version, "torch": torch.__version__, "accelerate": accelerate.__version__,
            "transformers": transformers.__version__, "torch_threads": torch.get_num_threads(),
            "interop_threads": torch.get_num_interop_threads()}


def run(args, protocol, report):
    report["runtime"] = configure(args.base, protocol)
    import torch
    from accelerate.hooks import ModelHook, add_hook_to_module
    from safetensors.torch import load_file, save_file
    from tokenizers import Tokenizer
    checkpoint = args.base / "checkpoint"
    report["memory"] = {"before_model_load": support.memory_snapshot()}
    report["stage"] = "load_model"
    started = time.monotonic()
    if args.mode == "resident":
        Config, Model = support.import_author(checkpoint)
        config = Config.from_pretrained(checkpoint, local_files_only=True)
        model, info = Model.from_pretrained(checkpoint, config=config, local_files_only=True,
            use_safetensors=True, dtype=torch.float32, attn_implementation="eager", output_loading_info=True)
        model.eval()
        if (info.get("unexpected_keys") or info.get("mismatched_keys") or info.get("error_msgs")
                or set(info.get("missing_keys", [])) - {"lm_head.weight"}
                or model.lm_head.weight is not model.model.embed_tokens.weight):
            raise ValueError("resident model loading or tied embedding mismatch")
        if any(p.device.type != "cpu" or p.dtype != torch.float32 for p in model.parameters()):
            raise ValueError("resident parameter has unexpected device/dtype")
        report["loading_info"] = info
        report["resident_unique_parameter_bytes"] = sum(p.numel() * p.element_size() for p in model.parameters())
        report["learned_r"] = support.verify_r_parameters(model, checkpoint)
    else:
        model, report["direct_loader"] = direct.load_direct(checkpoint, args.output / "offload-index")
    report["load_seconds"] = time.monotonic() - started
    report["memory"]["after_model_load"] = support.memory_snapshot()
    if model.config._attn_implementation != "eager" or model.config.attn_type != "parallax":
        raise ValueError("model is not explicit eager Parallax")
    tokenizer = Tokenizer.from_file(str(checkpoint / "tokenizer.json"))
    ids = tokenizer.encode(protocol["prompt"], add_special_tokens=False).ids
    if not 2 <= len(ids) <= protocol["max_prompt_tokens"] or len(set(ids)) < 2:
        raise ValueError("fixed prompt violates token bounds")
    inputs = torch.tensor([ids], dtype=torch.long, device="cpu")
    report["inputs"] = {"prompt": protocol["prompt"], "token_ids": ids, "unpadded": True,
                        "raw_tokenizer_sha256": support.sha256_file(checkpoint / "tokenizer.json")}
    forced = reference = None
    if args.mode == "direct":
        if args.reference is None or args.reference_sha256 is None:
            raise ValueError("direct mode requires an independently hashed resident reference")
        receipt = args.reference / "receipt.json"
        if support.sha256_file(receipt) != args.reference_sha256:
            raise ValueError("resident reference receipt hash differs")
        resident = json.loads(receipt.read_text())
        if (resident.get("success") is not True or resident.get("mode") != "resident"
                or resident.get("protocol_sha256") != report["protocol_sha256"]
                or resident.get("source_sha256") != report["source_sha256"]
                or resident.get("inputs") != report["inputs"]
                or resident.get("r_use_control", {}).get("differs_beyond_tolerance") is not True):
            raise ValueError("resident reference is not the qualified same source/protocol/input")
        logits_path = args.reference / "logits.safetensors"
        if support.sha256_file(logits_path) != resident["artifacts"]["logits.safetensors"]["sha256"]:
            raise ValueError("resident logit payload hash differs")
        reference = load_file(str(logits_path), device="cpu")
        forced = resident["greedy_tokens"]
        report["resident_reference_receipt_sha256"] = args.reference_sha256
    observed = {}
    if args.mode == "direct":
        class ObserveCPU(ModelHook):
            def __init__(self, name):
                self.name = name
            def pre_forward(self, module, *values, **kwargs):
                if module.weight.device.type != "cpu" or module.weight.dtype != torch.float32:
                    raise ValueError("R weight was not restored onto FP32 CPU")
                observed[self.name] = observed.get(self.name, 0) + 1
                return values, kwargs
        for name, module in model.named_modules():
            if name.endswith((".r_proj", ".r_norm")):
                add_hook_to_module(module, ObserveCPU(name), append=True)
    report["stage"] = "inference"
    logits, rows, tokens = support.run_steps(model, inputs, protocol, forced, args.mode == "direct")
    save_file(logits, str(args.output / "logits.safetensors"))
    report["steps"], report["greedy_tokens"] = rows, tokens
    report["decoded_greedy_continuation"] = tokenizer.decode(tokens, skip_special_tokens=True)
    if args.mode == "resident":
        report["stage"] = "r_zero_control"
        control, report["r_use_control"] = support.r_zero_control(model, inputs, logits["prefill"], protocol)
        save_file({"prefill": control}, str(args.output / "r-zero-logits.safetensors"))
        direct.verify_fixed_checkpoint(checkpoint)
    else:
        report["comparison"] = support.compare_logits(logits, reference, protocol)
        report["greedy_tokens_equal"] = tokens == forced
        report["r_cpu_hook_observations"] = observed
        report["post_forward_inventory"] = direct.meta_inventory(model)
        if (len(observed) != 56 or set(observed.values()) != {4} or tokens != forced
                or not all(row["allclose"] for row in report["comparison"])):
            raise ValueError("direct numerical or active-R acceptance failed")
        if support.sha256_file(args.output / "offload-index/index.json") != report["direct_loader"]["index_sha256"]:
            raise ValueError("offload index changed")
        direct.check_unchanged(checkpoint, report["direct_loader"])
    report["memory"]["after_inference"] = support.memory_snapshot()
    report["stage"], report["success"] = "complete", True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--mode", choices=("resident", "direct"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-sha256")
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, parents=False)
    report = {"schema": "merlin-parallax-recovery-acceptance/1", "success": False,
              "stage": "verify_source", "mode": args.mode, "fresh_process": True,
              "historical_receipts_recreated": False}
    try:
        protocol = json.loads(args.protocol.read_text())
        report["protocol_sha256"] = support.sha256_file(args.protocol)
        report["source_sha256"] = {name: support.sha256_file(Path(__file__).parent / name) for name in protocol["source_sha256"]}
        if report["source_sha256"] != protocol["source_sha256"]:
            raise ValueError("source changed after protocol freeze")
        run(args, protocol, report)
    except Exception as exc:
        report["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        (args.output / "failure-traceback.txt").write_text(traceback.format_exc())
    finally:
        report["limitations"] = ["Fresh recovery evidence; prior lost receipts are not recreated.",
            "CPU eager, short unpadded inputs; KV and activations remain in RAM.",
            "Process RSS includes startup and temporary tensors; it excludes uncharged OS cache.",
            "Hashes warm files; no physical SSD, cold-storage, GPU, chat or tool-quality claim."]
        report["artifacts"] = {p.name: {"bytes": p.stat().st_size, "sha256": support.sha256_file(p)} for p in args.output.iterdir() if p.is_file()}
        support.write_json(args.output / "receipt.json", report)
        print(json.dumps({"success": report["success"], "mode": args.mode, "stage": report["stage"], "error": report.get("error")}))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
