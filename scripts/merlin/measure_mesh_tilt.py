"""Check what a single pilot transect can distinguish about ridge orientation."""
import json
from pathlib import Path

from measure_mesh_interpolation import REPO, digest, field, load_protocol, near_uniform_mesh, read_mesh
from measure_mesh_localization import estimate_center, measure_arm, move_template


def measure():
    evidence = REPO / "docs/evidence"
    raw = (evidence / "mesh-tilt-protocol-v1.json").read_bytes()
    if digest(raw) != "a10d1dd804ff60186303a39d5a42aeeb4d4db60964eb5f71bacfdf662bb207d8":
        raise ValueError("tilt protocol changed")
    spec = json.loads(raw)
    parent_raw = (evidence / "mesh-localization-protocol-v1.json").read_bytes()
    if digest(parent_raw) != spec["parent_protocol_sha256"]:
        raise ValueError("parent protocol changed")
    pilot = json.loads(parent_raw)
    original = json.loads((evidence / "mesh-localization-20261118.json").read_bytes())
    sample = load_protocol()
    vertices, faces, mesh_hash = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    if sample["sample_sha256"] != original["sample_sha256"] or mesh_hash != original["mesh_sha256"]:
        raise ValueError("template or scoring points changed")
    uniform = near_uniform_mesh(len(vertices))
    mid = spec["center_at_midline_m"]
    reference = original["cases"][str(mid)]
    cases = []
    for slope in spec["slopes_dx_dy"]:
        def source(x, y):
            return field(x, y, center=mid + slope * (y - 0.5))

        xs = pilot["pilot_x_m"]
        values = [source(x, pilot["pilot_y_m"]) for x in xs]
        estimate = estimate_center(xs, values, pilot["contrast_threshold"])
        adapted = uniform if estimate is None else (move_template(vertices, estimate), faces)
        arms = {name: measure_arm(mesh, sample["samples"], source)
                for name, mesh in (("adapted", adapted), ("uniform", uniform))}
        if (values != reference["pilot_values"] or arms["adapted"]["validation"]["mesh_sha256"]
                != reference["arms"]["adapted"]["validation"]["mesh_sha256"]):
            raise ValueError("identical-transect prediction failed")
        ratio = arms["adapted"]["rmse"] / arms["uniform"]["rmse"]
        if slope == 0 and abs(ratio - reference["adapted_over_uniform_rmse"]) > 1e-12:
            raise ValueError("upright case replay failed")
        cases.append({"slope_dx_dy": slope, "pilot_values": values, "estimated_center_m": estimate,
                      "adapted_over_uniform_rmse": ratio, "arms": arms})
    return {"schema": "merlin-mesh-tilt/1", "protocol_sha256": digest(raw),
            "script_sha256": digest(Path(__file__).read_bytes()), "mesh_sha256": mesh_hash,
            "sample_sha256": sample["sample_sha256"], "cases": cases,
            "tilt_transfer_passed": all(c["adapted_over_uniform_rmse"] < 1 for c in cases if c["slope_dx_dy"])}


if __name__ == "__main__":
    print(json.dumps(measure(), sort_keys=True, indent=2, allow_nan=False))
