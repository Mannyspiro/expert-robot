#!/usr/bin/env python3
"""Bounded CPU paging of the pinned Parallax embedding and output head.

This is an inference-only virtual tensor, not an OS RAM/swap limit. The same
logical BF16 matrix supplies selected embedding rows and FP32 output tiles.
Other learned modules and K/V attention use the unchanged verified disk loader.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
import threading
from types import MethodType

import parallax_direct_disk as direct

VOCABULARY_ROWS = 151936
HIDDEN_COLUMNS = 1024
MAX_POSITIONS = 64
MAX_TILE_ROWS = 8192
MAX_MANAGED_BYTES = 128 * 1024 * 1024
DEFAULT_MANAGED_BYTES = 32 * 1024 * 1024
DEFAULT_TILE_ROWS = 4096
TIED_SOURCE = "model.embed_tokens.weight"

SCOPE = "Live data storage for BF16 staging, converted FP32 tied-weight tiles, and temporary projection-result tiles."
EXCLUSIONS = [
    "Other model parameters and Accelerate's existing offload buffers",
    "Returned embeddings/full logits, hidden activations and K/V cache",
    "Source-header metadata, Python objects, allocator arenas, Torch/BLAS workspace and runtime libraries",
    "Operating-system page cache and memory owned by other processes",
]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _validate_dimensions_budget(managed_bytes, tile_rows, *, columns, max_positions):
    """Refuse impossible settings before the model or source is opened."""
    _require(type(managed_bytes) is int and 1 <= managed_bytes <= MAX_MANAGED_BYTES,
             "managed_bytes must be an integer in 1..134217728")
    _require(type(tile_rows) is int and 1 <= tile_rows <= MAX_TILE_ROWS,
             "tile_rows must be an integer in 1..8192")
    # Raw BF16 and converted FP32 coexist; the projection tile also coexists.
    required = tile_rows * (columns * 6 + max_positions * 4)
    _require(managed_bytes >= required,
             f"managed_bytes cannot hold the required tile buffers ({required} bytes)")
    return required


def validate_budget(managed_bytes, tile_rows):
    """Pure stdlib preflight for the fixed model and its full 64-position bound."""
    return _validate_dimensions_budget(managed_bytes, tile_rows,
                                       columns=HIDDEN_COLUMNS, max_positions=MAX_POSITIONS)


class _PagedRows:
    """Internal row store. Public model admission is only load_ram_managed()."""

    def __init__(self, path, *, rows, columns, data_offset, file_bytes, file_sha256,
                 managed_bytes, tile_rows, max_positions=MAX_POSITIONS):
        _require(sys.byteorder == "little", "only little-endian CPU storage is supported")
        _require(type(rows) is int and 1 <= rows <= VOCABULARY_ROWS
                 and type(columns) is int and 1 <= columns <= HIDDEN_COLUMNS,
                 "invalid logical tensor shape")
        _require(type(max_positions) is int and 1 <= max_positions <= MAX_POSITIONS,
                 "invalid position bound")
        self.required_bytes = _validate_dimensions_budget(managed_bytes, tile_rows,
                                                          columns=columns, max_positions=max_positions)
        _require(type(file_bytes) is int and 1 <= file_bytes <= direct.WEIGHT_BYTES
                 and type(data_offset) is int and data_offset >= 0
                 and data_offset + rows * columns * 2 <= file_bytes,
                 "logical tensor exceeds its source file")
        _require(isinstance(file_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", file_sha256),
                 "invalid complete source digest")
        self.path = Path(path)
        self.rows, self.columns, self.data_offset = rows, columns, data_offset
        self.managed_bytes, self.tile_rows, self.max_positions = managed_bytes, tile_rows, max_positions
        self.source_sha256 = file_sha256
        self._lock = threading.Lock()
        self._buffers = {}
        self._current = self._peak = 0
        self._component_peaks = {"bf16_staging": 0, "fp32_weights": 0, "projection_result": 0}
        self._stats = {"source_validation_bytes_read": 0, "weight_bytes_read": 0,
                       "weight_read_calls": 0, "embedding_calls": 0, "embedding_rows_read": 0,
                       "embedding_positions_served": 0, "projection_calls": 0, "projection_tiles": 0,
                       "tiles_loaded": 0, "tiles_released": 0}
        self._closed = True
        before = self.path.lstat()
        _require(stat.S_ISREG(before.st_mode) and before.st_size == file_bytes,
                 "weight source must be a regular nonsymlink file of the exact size")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(self.path, flags)
        try:
            current = os.fstat(fd)
            _require(stat.S_ISREG(current.st_mode) and _stamp(current) == _stamp(before),
                     "weight source changed while opening")
            self._source = os.fdopen(fd, "rb", buffering=0)
        except BaseException:
            os.close(fd)
            raise
        self._identity = _stamp(current)
        self._closed = False
        try:
            self._verify_complete_source(file_bytes, file_sha256)
        except BaseException:
            self._source.close()
            self._closed = True
            raise

    def _capture_live(self):
        values = {name: (len(value) if isinstance(value, bytearray)
                         else value.untyped_storage().nbytes())
                  for name, value in self._buffers.items()}
        self._current = sum(values.values())
        _require(self._current <= self.managed_bytes, "managed live storage exceeded its budget")
        self._peak = max(self._peak, self._current)
        for name, size in values.items():
            self._component_peaks[name] = max(self._component_peaks[name], size)

    def _verify_complete_source(self, expected_bytes, expected_digest):
        # Full source authentication is also streamed; it never maps the file.
        buffer = bytearray(min(64 * 1024, self.managed_bytes, expected_bytes))
        self._buffers["bf16_staging"] = buffer
        self._capture_live()
        view = memoryview(buffer)
        total, digest = 0, hashlib.sha256()
        try:
            while total < expected_bytes:
                count = self._source.readinto(view[:min(len(view), expected_bytes - total)])
                _require(count is not None and count > 0, "truncated complete weight source")
                digest.update(view[:count])
                total += count
            self._stats["source_validation_bytes_read"] = total
            _require(total == expected_bytes and digest.hexdigest() == expected_digest,
                     "complete weight source SHA-256 differs")
            self.check_source()
        finally:
            view = buffer = None
            self._buffers.clear()
            self._capture_live()

    def check_source(self):
        _require(not self._closed, "virtual tensor store is closed")
        _require(_stamp(os.fstat(self._source.fileno())) == self._identity
                 and _stamp(self.path.lstat()) == self._identity,
                 "weight source changed after complete verification")

    def _bind_verified_safetensors_matrix(self, tensor_name):
        """Derive the row offset from the same descriptor whose full hash passed."""
        with self._operation():
            self._source.seek(0)
            size_bytes = self._source.read(8)
            _require(len(size_bytes) == 8, "truncated source header length")
            length = struct.unpack("<Q", size_bytes)[0]
            _require(0 < length <= 1024 * 1024, "invalid bounded source header")
            raw = self._source.read(length)
            _require(len(raw) == length, "truncated source tensor metadata")
            header = json.loads(raw)
            entry = header[tensor_name]
            offsets = entry["data_offsets"]
            _require(entry["dtype"] == "BF16" and entry["shape"] == [self.rows, self.columns]
                     and isinstance(offsets, list) and len(offsets) == 2
                     and all(type(value) is int for value in offsets)
                     and 0 <= offsets[0] < offsets[1]
                     and offsets[1] - offsets[0] == self.rows * self.columns * 2
                     and 8 + length + offsets[1] <= self._identity[2],
                     "tied source tensor layout differs from the pinned model")
            self.data_offset = 8 + length + offsets[0]

    @contextmanager
    def _operation(self):
        if not self._lock.acquire(blocking=False):
            raise ValueError("one virtual tensor operation may execute at a time")
        try:
            self.check_source()
            _require(not self._buffers and self._current == 0, "a previous tile is still resident")
            yield
            self.check_source()
        finally:
            self._lock.release()

    def _input(self, value, *, embedding):
        import torch
        _require(not torch.is_grad_enabled(), "virtual tensor execution requires inference/no-grad mode")
        _require(isinstance(value, torch.Tensor) and value.device.type == "cpu"
                 and value.dtype == (torch.int64 if embedding else torch.float32),
                 "virtual tensor input has an unsupported device or dtype")
        _require(value.ndim == (2 if embedding else 3) and value.shape[0] == 1
                 and 1 <= value.shape[1] <= self.max_positions
                 and (embedding or value.shape[2] == self.columns)
                 and value.is_contiguous(), "virtual tensor input shape/layout exceeds its contract")

    def _consume(self, start, count, *, positions=None, hidden=None, output):
        """Keep every staged object local; no tile lease escapes the consumer."""
        import torch
        linear_positions = 0 if hidden is None else hidden.shape[0]
        needed = count * (self.columns * 6 + linear_positions * 4)
        _require(type(start) is int and type(count) is int and 0 <= start < self.rows
                 and 1 <= count <= self.tile_rows and start + count <= self.rows,
                 "tile row range is invalid")
        _require(needed <= self.managed_bytes and not self._buffers,
                 "tile buffers cannot be admitted")
        raw = source_view = weight = projected = view = None
        try:
            raw = bytearray(count * self.columns * 2)
            self._buffers["bf16_staging"] = raw
            self._capture_live()
            view = memoryview(raw)
            self._source.seek(self.data_offset + start * self.columns * 2)
            received = 0
            while received < len(raw):
                read = self._source.readinto(view[received:])
                _require(read is not None and read > 0, "truncated virtual tensor tile")
                received += read
                self._stats["weight_read_calls"] += 1
                self._stats["weight_bytes_read"] += read
            source_view = torch.frombuffer(raw, dtype=torch.bfloat16).reshape(count, self.columns)
            weight = source_view.to(dtype=torch.float32)
            self._buffers["fp32_weights"] = weight
            self._capture_live()
            self._stats["tiles_loaded"] += 1
            if hidden is None:
                for position in positions:
                    output[position].copy_(weight[0])
                self._stats["embedding_rows_read"] += 1
            else:
                projected = torch.nn.functional.linear(hidden, weight)
                self._buffers["projection_result"] = projected
                self._capture_live()
                output[:, start:start + count].copy_(projected)
                self._stats["projection_tiles"] += 1
        finally:
            # Drop local aliases before the dictionary's final owning references.
            # Inference-only execution prevents autograd from retaining a tile.
            if weight is not None:
                self._stats["tiles_released"] += 1
            view = raw = source_view = weight = projected = None
            self._buffers.clear()
            self._capture_live()

    def embedding(self, input_ids):
        import torch
        self._input(input_ids, embedding=True)
        ids = input_ids.reshape(-1).tolist()
        _require(all(0 <= token < self.rows for token in ids), "embedding token ID is outside the vocabulary")
        with self._operation():
            output = torch.empty((len(ids), self.columns), dtype=torch.float32, device="cpu")
            selected = {}
            for position, token in enumerate(ids):
                selected.setdefault(token, []).append(position)
            for token, positions in selected.items():
                self._consume(token, 1, positions=positions, output=output)
            self._stats["embedding_calls"] += 1
            self._stats["embedding_positions_served"] += len(ids)
            return output.reshape(1, len(ids), self.columns)

    def project(self, hidden_states):
        import torch
        self._input(hidden_states, embedding=False)
        with self._operation():
            positions = hidden_states.shape[1]
            output = torch.empty((positions, self.rows), dtype=torch.float32, device="cpu")
            hidden = hidden_states.reshape(positions, self.columns)
            for start in range(0, self.rows, self.tile_rows):
                self._consume(start, min(self.tile_rows, self.rows - start), hidden=hidden, output=output)
            self._stats["projection_calls"] += 1
            return output.reshape(1, positions, self.rows)

    def snapshot(self):
        return {"schema": "merlin-managed-parallax-tied-tensor/1", "scope": SCOPE,
                "exclusions": list(EXCLUSIONS), "execution_device": "cpu", "compute_dtype": "float32",
                "storage_dtype": "bfloat16", "logical_shape": [self.rows, self.columns],
                "logical_fp32_bytes": self.rows * self.columns * 4,
                "managed_budget_bytes": self.managed_bytes, "required_worst_tile_bytes": self.required_bytes,
                "managed_current_bytes": self._current, "managed_peak_bytes": self._peak,
                "component_peak_bytes": dict(self._component_peaks), "tile_rows": self.tile_rows,
                "max_positions_per_forward": self.max_positions, "persistent_weight_cache_bytes": 0,
                "source_sha256": self.source_sha256, "closed": self._closed, **self._stats}

    def close(self):
        if not self._lock.acquire(blocking=False):
            raise ValueError("cannot close an active virtual tensor operation")
        try:
            if not self._closed:
                self._source.close()
                self._closed = True
        finally:
            self._lock.release()

    def __enter__(self):
        self.check_source()
        return self

    def __exit__(self, *_):
        self.close()


def _remove_empty_hook(module):
    import torch
    from accelerate.hooks import AlignDevicesHook, remove_hook_from_module
    hook = getattr(module, "_hf_hook", None)
    _require(type(hook) is AlignDevicesHook and hook.offload is True
             and hook.original_devices == {"weight": torch.device("meta")}
             and module.weight.device.type == "meta" and module.weight.dtype == torch.float32,
             "only an unchanged empty-weight offload hook can be replaced")
    # In pinned Accelerate 1.16.0, detach_hook skips original meta devices.
    # Requiring the condition above prevents restoration of the full tensor.
    remove_hook_from_module(module)
    _require(module.weight.device.type == "meta" and not hasattr(module, "_hf_hook"),
             "hook removal materialized or retained a managed weight")


def load_ram_managed(checkpoint, index_dir, managed_bytes=DEFAULT_MANAGED_BYTES,
                     tile_rows=DEFAULT_TILE_ROWS):
    validate_budget(managed_bytes, tile_rows)
    import torch
    import accelerate
    import transformers
    _require(torch.__version__ == "2.9.1+cpu" and accelerate.__version__ == "1.16.0"
             and transformers.__version__ == "5.6.2", "virtual memory requires the pinned CPU runtime")
    checkpoint = Path(checkpoint)
    model, provenance = direct.load_direct(checkpoint, Path(index_dir))
    weight_path = checkpoint / direct.WEIGHT_NAME
    manager = _PagedRows(weight_path, rows=VOCABULARY_ROWS, columns=HIDDEN_COLUMNS,
                         data_offset=0,
                         file_bytes=direct.WEIGHT_BYTES, file_sha256=direct.WEIGHT_SHA256,
                         managed_bytes=managed_bytes, tile_rows=tile_rows)
    try:
        manager._bind_verified_safetensors_matrix(TIED_SOURCE)
        for module in (model.model.embed_tokens, model.lm_head):
            _require(list(module.weight.shape) == [VOCABULARY_ROWS, HIDDEN_COLUMNS],
                     "managed module shape differs from its tied source")
            _remove_empty_hook(module)

        def embed_forward(module, input_ids):
            _require(not module.training, "virtual memory supports inference only")
            return manager.embedding(input_ids)

        def head_forward(module, hidden_states):
            _require(not module.training, "virtual memory supports inference only")
            return manager.project(hidden_states)

        model.model.embed_tokens.forward = MethodType(embed_forward, model.model.embed_tokens)
        model.lm_head.forward = MethodType(head_forward, model.lm_head)
        direct.meta_inventory(model)
        manager.check_source()
        return model, {**provenance, "virtual_memory": manager.snapshot(),
                       "managed_parameter_paths": [TIED_SOURCE, "lm_head.weight"],
                       "learned_attention_and_cache_changed": False}, manager
    except BaseException:
        manager.close()
        raise
