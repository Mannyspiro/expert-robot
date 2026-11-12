"""Repeatable, non-promoting memory/latency qualification for module loaders.

RSS sampling is best-effort and platform-dependent. This harness emits evidence;
it never changes manifest approval or promotion state.
"""
from __future__ import annotations

from statistics import median
from threading import Event, Thread
from time import perf_counter, sleep
from typing import Any
import os


def _rss_bytes() -> int | None:
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as stream:
            pages = int(stream.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError, AttributeError):
        return None


def measure_peak_rss(operation, sample_interval_ms: float = 5.0) -> dict[str, Any]:
    """Run operation while sampling this process's RSS; return timing and samples."""
    if sample_interval_ms <= 0:
        raise ValueError("sample_interval_ms must be positive")
    before = _rss_bytes()
    peak = [before]
    stop = Event()

    def sample() -> None:
        while not stop.is_set():
            current = _rss_bytes()
            if current is not None and (peak[0] is None or current > peak[0]):
                peak[0] = current
            stop.wait(sample_interval_ms / 1000.0)

    sampler = Thread(target=sample, name="merlin-rss-sampler", daemon=True)
    sampler.start()
    started = perf_counter()
    error = None
    try:
        result = operation()
    except Exception as exc:
        result = None
        error = type(exc).__name__
        raise
    finally:
        duration_ms = max(0.0, (perf_counter() - started) * 1000)
        stop.set()
        sampler.join(timeout=max(0.1, sample_interval_ms / 1000.0 * 4))
        after = _rss_bytes()
        if after is not None and (peak[0] is None or after > peak[0]):
            peak[0] = after
    return {
        "duration_ms": duration_ms, "rss_before_bytes": before,
        "rss_peak_sampled_bytes": peak[0], "rss_after_bytes": after,
        "rss_peak_delta_bytes": (peak[0] - before)
            if peak[0] is not None and before is not None else None,
        "rss_retained_delta_bytes": (after - before)
            if after is not None and before is not None else None,
        "rss_sampling": "linux_proc_statm" if after is not None else "unavailable",
        "error_type": error,
    }


def run_loader_qualification(manager, module_id: str, *, trials: int = 5,
                             rss_ceiling_bytes: int | None = None,
                             sample_interval_ms: float = 5.0) -> dict[str, Any]:
    """Measure repeated cold/warm activation and unload; qualification is advisory."""
    if isinstance(trials, bool) or not isinstance(trials, int) or trials < 2:
        raise ValueError("trials must be an integer >= 2")
    if rss_ceiling_bytes is not None and (
        isinstance(rss_ceiling_bytes, bool) or not isinstance(rss_ceiling_bytes, int)
        or rss_ceiling_bytes <= 0
    ):
        raise ValueError("rss_ceiling_bytes must be a positive integer")
    if module_id not in manager.catalog:
        raise ValueError("module_id is not registered")
    rows = []
    for index in range(trials):
        manager.deactivate(module_id)
        cold = measure_peak_rss(lambda: manager.activate(module_id), sample_interval_ms)
        warm = measure_peak_rss(lambda: manager.activate(module_id), sample_interval_ms)
        unload = measure_peak_rss(lambda: manager.deactivate(module_id), sample_interval_ms)
        rows.append({"trial": index + 1, "cold_load": cold,
                     "warm_activation": warm, "unload": unload,
                     "resident_bytes_after_unload": manager.resident_bytes,
                     "resident_after_unload": module_id in manager.resident_ids()})
    cold_peaks = [r["cold_load"]["rss_peak_delta_bytes"] for r in rows
                  if r["cold_load"]["rss_peak_delta_bytes"] is not None]
    rss_available = len(cold_peaks) == trials
    ceiling_pass = (rss_ceiling_bytes is not None and rss_available
                    and all(value <= rss_ceiling_bytes for value in cold_peaks))
    unload_pass = all(not r["resident_after_unload"] for r in rows)
    return {
        "schema": "merlin-loader-qualification/1",
        "module_id": module_id, "trials": rows,
        "summary": {
            "trial_count": trials,
            "cold_load_median_ms": median(r["cold_load"]["duration_ms"] for r in rows),
            "warm_activation_median_ms": median(r["warm_activation"]["duration_ms"] for r in rows),
            "unload_median_ms": median(r["unload"]["duration_ms"] for r in rows),
            "cold_peak_rss_delta_max_bytes": max(cold_peaks) if cold_peaks else None,
            "rss_measurements_available": rss_available,
            "rss_ceiling_bytes": rss_ceiling_bytes,
            "rss_ceiling_pass": ceiling_pass,
            "unload_accounting_pass": unload_pass,
        },
        "qualified": False,
        "qualification_status": "evidence_only_requires_independent_review",
        "promotion_authorized": False,
        "limitations": [
            "RSS peak is sampled and may miss short-lived allocations",
            "RSS is process-wide and includes unrelated allocations",
            "current catalog reads the full artifact into memory before loader invocation",
            "warm activation measures resident lookup, not a second physical model load",
            "no independent reviewer or held-out workload is represented",
        ],
    }
