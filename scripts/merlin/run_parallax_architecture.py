"""Evaluate a hypothetical Parallax package and exact Merlin tensor replay."""
import argparse
import json
from pathlib import Path
from random import Random
from statistics import median
from time import perf_counter_ns

from merlin.studio_tensor_backend import execute_jobs
from merlin.studio_tensor_prepared import prepare_jobs
from merlin.studio_tensor_tile import Boundary, ONE, ZERO, pair_from

REPLAYS = 8
TRIALS = 9
DEV_SEED = 8021
EVAL_SEEDS = (17701, 17729)
LAYOUTS = ("grouped", "deduplicated", "padded")


def hardware_screen():
    """Steady-state thermal and roofline bounds, all device inputs assumed."""
    result = []
    for name, conductivity in (("copper", 390), ("diamond", 1400),
                               ("hypothetical-normal-transport", 100_000),
                               ("zero-bulk-resistance-limit", None)):
        bulk = 0.0005 / (conductivity * 0.0001) if conductivity else 0
        thermal_w = 45 / (0.60 + 0.12 + bulk)
        for lanes in (16, 64):
            for memory_gbs in (32, 128):
                for intensity in (0.5, 4):
                    # 1 GHz, one contraction primitive per lane and cycle.
                    # 12 W idle, 0.8 nJ per useful contraction primitive.
                    limits = {"lanes": lanes, "memory": memory_gbs * intensity,
                              "thermal": (thermal_w - 12) / 0.8}
                    limiter = min(limits, key=limits.get)
                    result.append({"spreader": name, "through_plane_w_m_k": conductivity,
                                   "lanes": lanes, "memory_gb_s": memory_gbs,
                                   "ops_per_byte": intensity, "power_cap_w": thermal_w,
                                   "bound_gop_s": limits[limiter], "limiter": limiter})
    assert len(result) == 32
    return result


def jobs_for(seed, repeated):
    rng = Random(seed)
    jobs = []
    for i in range(32 if repeated else 512):
        chain = tuple(pair_from([[rng.randint(-2, 2) for _ in range(2)] for _ in range(2)])
                      for _ in range(rng.randint(1, 8)))
        boundary = Boundary("open", (ONE, ZERO), (ZERO, ONE)) if i % 2 else Boundary("loop")
        jobs.append((chain, boundary))
    if repeated:
        jobs = jobs * 16
        rng.shuffle(jobs)
    # A narrowing fault must survive a later zero matrix in every layout.
    large = pair_from([[32767, 0], [0, 32767]])
    zero = pair_from([[0, 0], [0, 0]])
    jobs[-1] = ((large, large, zero), Boundary("loop"))
    return tuple(jobs)


def benchmark(jobs, layouts):
    expected = execute_jobs(jobs, backend="reference")
    assert expected[-1] is None
    times = {name: [] for name in layouts}
    for trial in range(TRIALS):
        for name in layouts[trial % len(layouts):] + layouts[:trial % len(layouts)]:
            start = perf_counter_ns()
            prepared = prepare_jobs(jobs, layout=name)
            prep_ms = (perf_counter_ns() - start) / 1e6
            start = perf_counter_ns()
            outputs = [prepared.execute() for _ in range(REPLAYS)]
            elapsed_ms = (perf_counter_ns() - start) / 1e6
            assert all(output == expected for output in outputs)
            times[name].append((prep_ms + elapsed_ms) / REPLAYS)
    return {name: median(samples) for name, samples in times.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    # Warm imports before timings.
    prepare_jobs(jobs_for(1, True)).execute()
    development = {kind: benchmark(jobs_for(DEV_SEED, kind == "repeated"), LAYOUTS)
                   for kind in ("repeated", "diverse")}
    policy = {kind: min(times, key=times.get) for kind, times in development.items()}
    (out / "Frozen-Selection.json").write_text(json.dumps(policy, indent=2) + "\n")
    held_out = {}
    for kind, candidate in policy.items():
        layouts = tuple(dict.fromkeys(("grouped", candidate)))
        held_out[kind] = [benchmark(jobs_for(seed, kind == "repeated"), layouts)
                          for seed in EVAL_SEEDS]
    accepted = {kind: candidate != "grouped" and all(
        row["grouped"] / row[candidate] >= 1.10 for row in held_out[kind])
        for kind, candidate in policy.items()}
    report = {"hardware": hardware_screen(), "ms_per_replay_including_preparation": {
              "development": development, "held_out": held_out},
              "replays": REPLAYS, "trials": TRIALS, "held_out_seeds": EVAL_SEEDS,
              "selected": policy, "accepted_local": accepted}
    (out / "Results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
