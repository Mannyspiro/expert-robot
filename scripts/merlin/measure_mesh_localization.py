"""Replay the preregistered coarse-observation mesh selection experiment."""
from functools import partial
import json
import math
from pathlib import Path

from measure_mesh_interpolation import (
    REPO, digest, evaluate, field, load_protocol, near_uniform_mesh, read_mesh,
)


PROTOCOL_HASH = "ba626d3bc035ae819635ec6bdf2cf8ac4e764a64d26c8b0933f6c490d6026d21"


def estimate_center(xs, values, threshold):
    """Return an interior pilot coordinate, or None to select the uniform control."""
    if len(xs) != len(values) or len(xs) < 3 or not all(map(math.isfinite, values)):
        raise ValueError("finite observation required at every pilot coordinate")
    peak = max(values)
    if peak - min(values) < threshold or values.count(peak) != 1:
        return None
    index = values.index(peak)
    return xs[index] if 0 < index < len(xs) - 1 else None


def move_template(vertices, center):
    if not 0 < center < 1:
        raise ValueError("interior center required")
    return [(2*x*center if x <= 0.5 else 1 - 2*(1-x)*(1-center), y)
            for x, y in vertices]


def measure_arm(mesh, samples, source):
    vertices, triangles = mesh
    measured = {tuple(p): source(*p) for p in vertices}
    truth = {tuple(p): source(*p) for p in samples}
    if len(truth) != len(samples) or len(measured) != len(vertices):
        raise ValueError("measurement coordinates must be unique within each stage")
    # The evaluator visits shared triangle vertices repeatedly. Reuse their measurements.
    lookup = {**measured, **truth}
    result = evaluate(vertices, triangles, samples, field_fn=lambda x, y: lookup[x, y])
    return {"rmse": result["metrics"]["rmse"], "validation": result["validation"],
            "affine_max_error": result["metrics"]["affine_control_max_absolute_error"],
            "uncovered": result["metrics"]["uncovered_samples"],
            "vertex_queries": len(measured), "scoring_queries": len(truth)}


def measure():
    evidence = REPO / "docs/evidence"
    raw = (evidence / "mesh-localization-protocol-v1.json").read_bytes()
    if digest(raw) != PROTOCOL_HASH:
        raise ValueError("localization protocol changed")
    spec = json.loads(raw)
    parent = (evidence / "mesh-displacement-20261118.json").read_bytes()
    if digest(parent) != spec["parent_receipt_sha256"]:
        raise ValueError("displacement receipt changed")
    prior = json.loads(parent)
    scoring = load_protocol()
    vertices, faces, mesh_hash = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    if mesh_hash != prior["mesh_file_sha256"] or scoring["sample_sha256"] != prior["sample_sha256"]:
        raise ValueError("template or scoring points changed")
    uniform = near_uniform_mesh(len(vertices))
    cases = {}
    for center in [*spec["ridge_centers_m"], None]:
        source = (partial(field, center=center) if center is not None
                  else lambda x, y: 0.1 * math.sin(2 * math.pi * y))
        xs = spec["pilot_x_m"]
        values = [source(x, spec["pilot_y_m"]) for x in xs]
        estimate = estimate_center(xs, values, spec["contrast_threshold"])
        adapted = uniform if estimate is None else (move_template(vertices, estimate), faces)
        meshes = {"adapted": adapted, "uniform": uniform, "fixed_template": (vertices, faces)}
        arms = {name: measure_arm(mesh, scoring["samples"], source) for name, mesh in meshes.items()}
        ratio = arms["adapted"]["rmse"] / arms["uniform"]["rmse"]
        passed = ratio < 1 if center is not None else estimate is None and ratio == 1
        cases[str(center) if center is not None else "y_only"] = {
            "pilot_values": values, "shared_pilot_queries": len(values), "estimated_center_m": estimate,
            "adapted_over_uniform_rmse": ratio, "passed": passed, "arms": arms}
    return {"schema": "merlin-mesh-localization/1", "protocol_sha256": PROTOCOL_HASH,
            "script_sha256": digest(Path(__file__).read_bytes()),
            "evaluator_sha256": digest(Path(__file__).with_name("measure_mesh_interpolation.py").read_bytes()),
            "mesh_sha256": mesh_hash, "sample_sha256": scoring["sample_sha256"], "cases": cases,
            "advance": all(case["passed"] for case in cases.values())}


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True, indent=2, allow_nan=False))
