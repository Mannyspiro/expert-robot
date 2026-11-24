#!/usr/bin/env python3
"""Reconstructed CPU direct-safetensors offload loader for one pinned checkpoint.

No remote model code lookup, full resident bootstrap or .dat weight copy. This
is a new recovery implementation and must be paired with fresh acceptance.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct

import parallax_cpu_probe as support

CHECKPOINT_LOCK_SHA256 = "bc21d1390c2c68001aa4c1ad2e2a72441b4a82125bdc0d2ffde8f98ef801deb5"
WEIGHT_NAME = "model-00001-of-00001.safetensors"
WEIGHT_SHA256 = "2049f3dec8156649f1a3e2deed4decbe649cf0d7a8a9f9273453cbfa13aed2cf"
WEIGHT_BYTES = 1309592289


def file_stamps(checkpoint: Path) -> dict:
    lock = json.loads((checkpoint.parent / "checkpoint-lock.json").read_text())
    result = {}
    for entry in lock["files"]:
        path = checkpoint / Path(entry["path"]).name
        info = path.stat()
        result[path.name] = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
    return result


def verify_fixed_checkpoint(checkpoint: Path) -> dict:
    checkpoint = Path(checkpoint)
    canonical = checkpoint.parent.resolve(strict=True) / "checkpoint"
    if checkpoint.is_symlink() or checkpoint.resolve(strict=True) != canonical:
        raise ValueError("checkpoint must be the canonical nonsymlink checkpoint directory")
    rows = support.verify_payloads(checkpoint.parent, "checkpoint-lock.json", CHECKPOINT_LOCK_SHA256)
    return {"files": rows, "stamps": file_stamps(checkpoint)}


def read_header(path: Path) -> dict:
    with path.open("rb") as source:
        raw = source.read(8)
        if len(raw) != 8:
            raise ValueError("truncated safetensors length")
        length = struct.unpack("<Q", raw)[0]
        if not 0 < length <= 1024**2:
            raise ValueError("unbounded safetensors header")
        payload = source.read(length)
        if len(payload) != length:
            raise ValueError("truncated safetensors header")
    header = json.loads(payload)
    header.pop("__metadata__", None)
    if len(header) != 366:
        raise ValueError("unexpected source tensor count")
    intervals = []
    for name, value in header.items():
        shape, offsets = value["shape"], value["data_offsets"]
        if value["dtype"] != "BF16" or not shape or any(type(x) is not int or x < 1 for x in shape):
            raise ValueError("unexpected checkpoint tensor dtype/shape")
        if len(offsets) != 2 or any(type(x) is not int for x in offsets):
            raise ValueError("invalid tensor offsets")
        start, end = offsets
        if start < 0 or end - start != math.prod(shape) * 2:
            raise ValueError("tensor byte range differs from shape")
        intervals.append((start, end))
    position = 0
    for start, end in sorted(intervals):
        if start != position:
            raise ValueError("overlapping or gapped source tensor ranges")
        position = end
    if 8 + length + position != path.stat().st_size or path.stat().st_size != WEIGHT_BYTES:
        raise ValueError("source layout does not cover exact checkpoint payload")
    return header


def meta_inventory(model) -> dict:
    value = support.assert_meta(model)
    value["parameter_bytes_if_fp32"] = sum(p.numel() * 4 for _, p in model.named_parameters(remove_duplicate=False))
    return value


def check_unchanged(checkpoint: Path, provenance: dict) -> None:
    if file_stamps(checkpoint) != provenance["source_stamps"]:
        raise ValueError("source files changed during inference")
    verify_fixed_checkpoint(checkpoint)


def load_direct(checkpoint: Path, index_dir: Path):
    verified = verify_fixed_checkpoint(checkpoint)
    weight = (checkpoint / WEIGHT_NAME).resolve(strict=True)
    header = read_header(weight)
    import torch
    from accelerate import disk_offload, init_empty_weights
    Config, Model = support.import_author(checkpoint)
    config = Config.from_pretrained(checkpoint, local_files_only=True)
    expected = {"hidden_size": 1024, "num_hidden_layers": 28, "num_attention_heads": 16,
                "num_key_value_heads": 8, "head_dim": 128, "vocab_size": 151936,
                "attn_type": "parallax", "tie_word_embeddings": True}
    if any(getattr(config, key) != value for key, value in expected.items()):
        raise ValueError("checkpoint architecture differs from pinned Parallax")
    config._attn_implementation = "eager"
    with init_empty_weights(include_buffers=False):
        model = Model(config)
    model.eval()
    paths = dict(model.named_parameters(remove_duplicate=False))
    if len(paths) != 367 or any(p.device.type != "meta" or p.dtype != torch.float32 for p in paths.values()):
        raise ValueError("model did not initialize as the expected empty FP32 parameter graph")
    index, used = {}, set()
    for name, param in paths.items():
        source_name = "model.embed_tokens.weight" if name == "lm_head.weight" else name
        if source_name not in header or list(param.shape) != header[source_name]["shape"]:
            raise ValueError("source tensor does not match every parameter path")
        used.add(source_name)
        index[name] = {"safetensors_file": str(weight), "weight_name": source_name, "dtype": "float32"}
    if used != set(header):
        raise ValueError("checkpoint contains unused learned tensors")
    for layer in range(28):
        for suffix, shape in (("r_proj.weight", [2048, 1024]), ("r_norm.weight", [128])):
            name = f"model.layers.{layer}.self_attn.{suffix}"
            if header[name]["shape"] != shape or name not in index:
                raise ValueError("learned R tensor was dropped or reshaped")
    del paths
    raw = json.dumps(index, sort_keys=True, separators=(",", ":")) + "\n"
    if len(raw.encode()) > 256 * 1024:
        raise ValueError("offload index exceeds bound")
    index_dir.mkdir(mode=0o700)
    index_path = index_dir / "index.json"
    with index_path.open("x") as stream:
        stream.write(raw)
    index_hash = support.sha256_file(index_path)
    disk_offload(model, offload_dir=index_dir, execution_device=torch.device("cpu"), offload_buffers=False)
    if sorted(p.name for p in index_dir.iterdir()) != ["index.json"]:
        raise ValueError("direct mode unexpectedly materialized weight copies")
    inventory = meta_inventory(model)
    if file_stamps(checkpoint) != verified["stamps"]:
        raise ValueError("checkpoint changed while constructing direct loader")
    return model, {"model_id": "YifeiZuo/Parallax-0.6B", "revision": "0cf73e2d49ea1a09a9ef85178b73ad68e019ae36",
                   "weight_sha256": WEIGHT_SHA256, "weight_bytes": WEIGHT_BYTES,
                   "source_stamps": verified["stamps"], "index_sha256": index_hash,
                   "index_bytes": index_path.stat().st_size, "index_entries": len(index),
                   "learned_r_parameter_paths": 56, "tied_lm_head_source": "model.embed_tokens.weight",
                   "initialization": "init_empty_weights(include_buffers=False)",
                   "copied_weight_bytes": 0, "post_load_inventory": inventory}
