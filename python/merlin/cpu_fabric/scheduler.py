"""Bounded thread-pool scheduler benchmark with output verification."""
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

def _work(item):
    value = item + 1
    for i in range(1, 120):
        value = (value * 1664525 + i + 1013904223) & 0xffffffff
    return value

def run_scheduler_benchmark(tasks=4096, workers=8):
    if not 1 <= tasks <= 100000 or not 1 <= workers <= 64:
        raise ValueError("tasks/workers outside configured bounds")
    t = perf_counter(); serial = [_work(i) for i in range(tasks)]; serial_s = perf_counter()-t
    t = perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parallel = list(pool.map(_work, range(tasks), chunksize=32))
    parallel_s = perf_counter()-t
    if serial != parallel:
        raise AssertionError("parallel execution changed results")
    return {"tasks":tasks,"workers":workers,"serial_seconds":serial_s,
            "parallel_seconds":parallel_s,"speedup":serial_s/parallel_s if parallel_s else None,
            "verified_equal":True}
