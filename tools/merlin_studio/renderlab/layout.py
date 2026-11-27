"""Enumerate measured CPU worker sizes and simulated production layouts."""

import argparse
from itertools import product
import json
from pathlib import Path
from statistics import median


def evaluate(samples, cpus, ram_mib, reserve):
    groups = {}
    for item in samples:
        groups.setdefault(item["threads"], []).append(item)
    scenes = sorted({i["scene"] for rows in groups.values() for i in rows})
    maximum_count = max(len(rows) for rows in groups.values())
    baseline = {scene: {r.get("pixel_sha256") for r in groups[1] if r["scene"] == scene} for scene in scenes}
    if any(None in hashes or len(hashes) != 1 for hashes in baseline.values()):
        raise ValueError("The single-thread baseline needs one repeatable pixel hash per scene")
    candidates = []
    for threads, rows in sorted(groups.items()):
        if len(rows) != maximum_count or any("error" in item for item in rows):
            continue
        if any({r["pixel_sha256"] for r in rows if r["scene"] == scene} != baseline[scene] for scene in scenes):
            continue
        candidates.append({"threads":threads, "median_seconds_by_scene": {
                                scene:median(r["seconds"] for r in rows if r["scene"] == scene) for scene in scenes},
                           "seconds_per_frame":sum(median(r["seconds"] for r in rows if r["scene"] == scene)
                                                   for scene in scenes)/len(scenes),
                           "peak_rss_mib":max(r["rss_mib"] for r in rows)})
    simulations = []
    rejected = 0
    for row, workers in product(candidates, range(1, cpus + 1)):
        memory = row["peak_rss_mib"] * workers
        if row["threads"] * workers > cpus - reserve or memory > ram_mib:
            rejected += 1
            continue
        simulations.append(dict(threads_per_worker=row["threads"], workers=workers,
                                estimated_memory_mib=round(memory, 2),
                                optimistic_frames_per_minute=round(60 * workers / row["seconds_per_frame"], 2)))
    simulations.sort(key=lambda r: (-r["optimistic_frames_per_minute"], r["workers"]))
    return dict(evidence_class="isolated samples with simulated packing; no shared-resource penalty",
                cpus=cpus, reserved_threads=reserve, memory_budget_mib=ram_mib,
                measured_single_worker=candidates, factor_points=len(candidates)*cpus,
                rejected=rejected, feasible=simulations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--ram-mib", type=int, required=True)
    parser.add_argument("--reserve", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.cpus <= 256 or not 0 <= args.reserve < args.cpus or args.ram_mib < 1:
        parser.error("Set a positive hardware budget with fewer reserved threads than total threads")
    samples = [json.loads(line) for line in args.samples.read_text().splitlines() if line]
    print(json.dumps(evaluate(samples, args.cpus, args.ram_mib, args.reserve), indent=2))


if __name__ == "__main__":
    main()
