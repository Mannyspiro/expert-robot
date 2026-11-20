"""Test the nine-probe selector when a ridge is broad, overlapping or absent."""
import hashlib
import json
import math
import random

from measure_mesh_interpolation import REPO, load_protocol, near_uniform_mesh, read_mesh
from measure_mesh_localization import measure_arm
from measure_mesh_row_background import row_contrast, select_mesh


def signal(kind, x, y):
    if kind == "flat":
        return 0.03
    background = 0.03 + 0.17 * math.sin(2 * math.pi * y)
    dx = x - (0.47 + 0.4 * (y - 0.5))
    if kind == "broad":
        return background + math.exp(-(dx / 0.22)**2)
    if kind == "overlap":
        return background + math.exp(-((dx + 0.09) / 0.12)**2) + 0.8 * math.exp(-((dx - 0.09) / 0.12)**2)
    return background


def measure():
    evidence = REPO / "docs/evidence"
    raw = (evidence / "mesh-background-controls-protocol.json").read_bytes()
    spec = json.loads(raw)
    samples = load_protocol()
    vertices, faces, mesh_hash = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    uniform = near_uniform_mesh(len(vertices))
    mirrored = ([(1-x,y) for x,y in uniform[0]], uniform[1])
    cases = []
    for kind in ("flat", "noise", "broad", "overlap"):
        def source(x, y):
            return signal(kind, x, y)

        comparisons = [measure_arm(mesh, samples["samples"], source)["rmse"] for mesh in (uniform, mirrored)]
        for seed in ([None] if kind == "flat" else spec["seeds"]):
            bound = spec["noise_bound"]
            rng = random.Random(seed)
            pilots = {(x,y): source(x,y) + (0 if seed is None else rng.uniform(-bound,bound))
                      for y in (.25,.5,.75) for x in (.25,.5,.75)}
            mesh, reason = select_mesh(pilots, vertices, faces, uniform, True)
            old_error = measure_arm(mesh, samples["samples"], source)["rmse"]
            contrast = row_contrast(pilots)
            guarded, guarded_reason = select_mesh(pilots, vertices, faces, uniform, True, noise_bound=bound)
            fallback = guarded_reason is not None
            error = measure_arm(guarded, samples["samples"], source)["rmse"]
            null = kind in ("flat", "noise")
            cases.append(dict(kind=kind, seed=seed, max_row_range=contrast,
                              original_fallback=reason, guarded_fallback=fallback,
                              original_rmse=old_error, guarded_rmse=error, uniform_rmse=comparisons,
                              passed=fallback if null else error < min(comparisons)))
    return dict(protocol_sha256=hashlib.sha256(raw).hexdigest(),mesh_sha256=mesh_hash,
                sample_sha256=samples["sample_sha256"],cases=cases,advance=all(c["passed"] for c in cases))


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, allow_nan=False))
