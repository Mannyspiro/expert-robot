"""Enumerate model-compression and conditional-compute hypotheses.

This module generates experiment specifications only. It does not mutate models,
load arbitrary code, or promote candidates. Each candidate must be measured and
independently qualified before runtime use.
"""
from __future__ import annotations
from itertools import product

TRANSFORMS = {
    "weight_precision": ("fp16", "int8", "int4"),
    "rank_reduction": ("none", "low_rank_0.5", "low_rank_0.25"),
    "expert_routing": ("dense", "top1", "top2"),
    "activation_policy": ("all_layers", "early_exit", "adaptive_depth"),
    "module_policy": ("monolith", "shared_backbone_adapters", "specialist_modules"),
    "cache_policy": ("no_kv_cache", "bounded_kv_cache", "quantized_kv_cache"),
}

def enumerate_candidates(max_candidates: int = 48) -> list[dict]:
    """Return a deterministic, bounded, diverse set of candidate configurations."""
    if not 1 <= max_candidates <= 512:
        raise ValueError("max_candidates must be in [1, 512]")
    keys = tuple(TRANSFORMS)
    all_rows = product(*(TRANSFORMS[k] for k in keys))
    candidates = []
    seen = set()
    for row in all_rows:
        config = dict(zip(keys, row))
        # Avoid nonsensical combinations that add complexity without a clear test.
        if config["expert_routing"] != "dense" and config["module_policy"] == "monolith":
            continue
        if config["activation_policy"] == "early_exit" and config["module_policy"] == "monolith":
            continue
        signature = tuple(row)
        if signature in seen:
            continue
        seen.add(signature)
        candidates.append({
            "candidate_id": f"mc-{len(candidates)+1:04d}",
            "configuration": config,
            "hypothesis": (
                "Conditional specialist activation plus reduced precision may lower "
                "resident memory and per-request compute while preserving task quality."
            ),
            "required_measurements": [
                "peak_rss_bytes", "model_disk_bytes", "tokens_per_second",
                "time_to_first_token_ms", "task_quality", "fallback_rate",
                "activation_count", "numerical_or_task_correctness"
            ],
            "status": "proposed_not_tested",
        })
        if len(candidates) >= max_candidates:
            break
    return candidates

def rank_measured(results: list[dict]) -> list[dict]:
    """Rank only measured, qualified results; unknown metrics never receive a score."""
    eligible = []
    for item in results:
        required = ("peak_rss_bytes", "tokens_per_second", "task_quality",
                    "baseline_task_quality", "verified")
        if not all(k in item for k in required):
            continue
        if item["verified"] is not True or item["task_quality"] < item["baseline_task_quality"] * 0.98:
            continue
        if item["peak_rss_bytes"] <= 0 or item["tokens_per_second"] <= 0:
            continue
        # Quality-preserving throughput per resident GiB. This is a transparent
        # screening score, not a universal utility function.
        item = dict(item)
        item["screening_score"] = item["tokens_per_second"] / (item["peak_rss_bytes"] / (1024**3))
        eligible.append(item)
    return sorted(eligible, key=lambda x: x["screening_score"], reverse=True)
