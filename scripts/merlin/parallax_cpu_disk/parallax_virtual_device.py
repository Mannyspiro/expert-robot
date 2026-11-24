#!/usr/bin/env python3
"""Bounded logical execution for the CPU Parallax profile.

The logical device schedules real PyTorch CPU operations. It does not implement
CUDA, create GPU hardware, or limit whole-process RAM. Weight-row staging is
accounted separately by parallax_virtual_memory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import threading

MAX_QUERY_TOKENS = 64
MAX_CONTEXT_TOKENS = 80
MAX_FORWARD_CALLS = 16
MAX_LOGITS_BYTES = 40 * 1024**2
MAX_TORCH_THREADS = 2
MAX_VOCABULARY = 151936


@dataclass(frozen=True)
class ExecutionLimits:
    max_query_tokens: int = MAX_QUERY_TOKENS
    max_context_tokens: int = MAX_CONTEXT_TOKENS
    max_forward_calls: int = MAX_FORWARD_CALLS
    max_logits_bytes: int = MAX_LOGITS_BYTES
    max_torch_threads: int = MAX_TORCH_THREADS

    def __post_init__(self):
        caps = (MAX_QUERY_TOKENS, MAX_CONTEXT_TOKENS, MAX_FORWARD_CALLS,
                MAX_LOGITS_BYTES, MAX_TORCH_THREADS)
        for (name, value), cap in zip(asdict(self).items(), caps):
            if type(value) is not int or not 1 <= value <= cap:
                raise ValueError(f"{name} must be an integer in 1..{cap}")
        if self.max_query_tokens > self.max_context_tokens:
            raise ValueError("query bound cannot exceed context bound")


class BackendUnavailable(RuntimeError):
    """An explicitly requested backend cannot execute this qualified profile."""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def capabilities():
    """Only selected runtime capabilities; no host inventory or driver changes."""
    import torch
    built = bool(torch.backends.cuda.is_built())
    # Calling is_available is deliberate: a CUDA build alone is not a device.
    available = bool(torch.cuda.is_available()) if built else False
    return {"torch_version": str(torch.__version__), "cuda_built": built,
            "cuda_available": available, "cuda_profile_qualified": False,
            "cpu_software_supported": True}


def select_backend(requested="cpu", *, limits=None):
    if requested not in ("cpu", "cuda"):
        raise ValueError("backend must be explicitly cpu or cuda")
    selected_limits = ExecutionLimits() if limits is None else limits
    if not isinstance(selected_limits, ExecutionLimits):
        raise TypeError("limits must be ExecutionLimits")
    found = capabilities()
    if requested == "cuda":
        if not found["cuda_built"] or not found["cuda_available"]:
            raise BackendUnavailable("CUDA is unavailable: this request requires a CUDA runtime and a real GPU; no fallback was performed")
        raise BackendUnavailable("CUDA profile is unqualified: this Parallax row-paging implementation is CPU-only; no fallback was performed")
    import torch
    torch.set_num_threads(selected_limits.max_torch_threads)
    return LogicalAccelerator(selected_limits, found)


class LogicalAccelerator:
    """One bounded, nonconcurrent CPU execution session.

    Admission errors leave the session reusable. A model or result error poisons
    it because the cache may already have changed. Returned-logit accounting is
    a per-forward bound, not a bound on outputs a caller retains afterwards.
    """

    def __init__(self, limits, found):
        self.limits, self._capabilities = limits, dict(found)
        self._mutex = threading.Lock()
        self._calls = self._completed = self._failures = self._rejections = 0
        self._poisoned = self._active = False
        self._maximum_logits_bytes = self._maximum_logits_storage_bytes = 0
        self._last_model_inventory = None

    def descriptor(self):
        return {"logical_device": "merlin:software:0", "backend": "pytorch_cpu",
                "actual_device": "cpu", "hardware_acceleration": False,
                "operation": "unpadded_batch_one_fp32_causal_lm_forward",
                "cuda_emulation": False, "capabilities": dict(self._capabilities),
                "limits": asdict(self.limits),
                "scope": "Admission limits and returned-logit bytes per call; no whole-process RAM, GPU memory, or speedup guarantee."}

    def snapshot(self):
        return {**self.descriptor(), "forward_calls": self._calls,
                "completed_calls": self._completed, "failed_calls": self._failures,
                "rejected_calls": self._rejections, "in_flight": self._active,
                "poisoned": self._poisoned,
                "maximum_returned_logits_bytes": self._maximum_logits_bytes,
                "maximum_returned_logits_storage_bytes": self._maximum_logits_storage_bytes,
                "last_model_inventory": self._last_model_inventory}

    def _cache_length(self, cache):
        import torch
        if cache is None:
            return 0
        layers = getattr(cache, "layers", None)
        _require(isinstance(layers, (list, tuple)) and len(layers) <= 28,
                 "cache must expose at most 28 CPU layers")
        length = int(cache.get_seq_length())
        _require(0 <= length <= self.limits.max_context_tokens, "cache exceeds context bound")
        for layer in layers:
            for value in (getattr(layer, "keys", None), getattr(layer, "values", None)):
                if value is None:
                    continue
                _require(isinstance(value, torch.Tensor) and value.device.type == "cpu"
                         and value.dtype == torch.float32, "borrowed cache must be CPU FP32")
                if value.numel():
                    _require(value.ndim == 4 and value.shape[0] == 1
                             and value.shape[-2] == length and value.shape[1] <= 8
                             and value.shape[-1] <= 128, "cache tensor exceeds the supported shape")
                    _require(bool(torch.isfinite(value).all()), "cache must be finite")
        return length

    def _model_inventory(self, model):
        import torch
        inventory = {"cpu_parameter_paths": 0, "meta_parameter_paths": 0, "cpu_buffers": 0}
        for _, value in model.named_parameters(remove_duplicate=False):
            _require(value.device.type in ("cpu", "meta") and value.dtype == torch.float32,
                     "borrowed model parameters must be FP32 CPU or verified-offload meta")
            inventory[value.device.type + "_parameter_paths"] += 1
        for value in model.buffers():
            _require(value.device.type == "cpu", "borrowed model buffers must be CPU")
            inventory["cpu_buffers"] += 1
        return inventory

    def _admit(self, model, input_ids, attention_mask, cache, use_cache, return_dict):
        import torch
        _require(not self._poisoned, "logical execution session is poisoned after an execution failure")
        _require(self._calls < self.limits.max_forward_calls, "forward call budget exhausted")
        _require(torch.get_num_threads() <= self.limits.max_torch_threads, "Torch thread count exceeds execution limit")
        _require(use_cache is True and return_dict is True, "only cached return-dict inference is supported")
        _require(isinstance(input_ids, torch.Tensor) and input_ids.device.type == "cpu"
                 and input_ids.dtype == torch.int64 and input_ids.ndim == 2
                 and input_ids.shape[0] == 1, "input IDs must be batch-one CPU int64")
        query = input_ids.shape[1]
        _require(1 <= query <= self.limits.max_query_tokens, "query exceeds token bound")
        vocabulary = getattr(model.config, "vocab_size", None)
        _require(type(vocabulary) is int and 1 <= vocabulary <= MAX_VOCABULARY,
                 "model vocabulary exceeds supported profile")
        _require(bool(((input_ids >= 0) & (input_ids < vocabulary)).all()), "input ID is outside vocabulary")
        total = self._cache_length(cache) + query
        _require(total <= self.limits.max_context_tokens, "request exceeds context token bound")
        _require(isinstance(attention_mask, torch.Tensor) and attention_mask.device.type == "cpu"
                 and attention_mask.dtype in (torch.int64, torch.bool)
                 and tuple(attention_mask.shape) == (1, total)
                 and bool((attention_mask == 1).all()), "attention mask must describe the complete unpadded CPU prefix")
        _require(query * vocabulary * 4 <= self.limits.max_logits_bytes, "predicted logits exceed byte bound")
        self._last_model_inventory = self._model_inventory(model)
        return query, vocabulary, total

    def forward(self, model, *, input_ids, attention_mask, past_key_values=None,
                use_cache=True, return_dict=True):
        import torch
        if not self._mutex.acquire(blocking=False):
            self._rejections += 1
            raise ValueError("logical execution permits only one forward at a time")
        executed = False
        try:
            query, vocabulary, total = self._admit(model, input_ids, attention_mask,
                                                   past_key_values, use_cache, return_dict)
            self._calls += 1
            self._active = executed = True
            with torch.inference_mode():
                result = model(input_ids=input_ids, attention_mask=attention_mask,
                               past_key_values=past_key_values, use_cache=True, return_dict=True)
                logits = getattr(result, "logits", None)
                _require(isinstance(logits, torch.Tensor) and logits.device.type == "cpu"
                         and logits.dtype == torch.float32, "returned logits must be CPU FP32")
                actual_bytes = logits.numel() * logits.element_size()
                storage_bytes = logits.untyped_storage().nbytes()
                _require(actual_bytes <= self.limits.max_logits_bytes
                         and storage_bytes <= self.limits.max_logits_bytes,
                         "actual returned logits or backing storage exceed byte bound")
                _require(tuple(logits.shape) == (1, query, vocabulary), "returned logits shape differs from admitted request")
                _require(bool(torch.isfinite(logits).all()), "returned logits must be finite")
                _require(self._cache_length(getattr(result, "past_key_values", None)) == total,
                         "returned cache does not cover admitted prefix")
                self._last_model_inventory = self._model_inventory(model)
            self._maximum_logits_bytes = max(self._maximum_logits_bytes, actual_bytes)
            self._maximum_logits_storage_bytes = max(self._maximum_logits_storage_bytes, storage_bytes)
            self._completed += 1
            return result
        except Exception:
            if executed:
                self._failures += 1
                self._poisoned = True
            else:
                self._rejections += 1
            raise
        finally:
            self._active = False
            self._mutex.release()
