"""Replay the original mesh benchmark, then move the feature on both fixed meshes."""
from functools import partial
import json
import math
from pathlib import Path

from measure_mesh_interpolation import REPO, digest, evaluate, field, load_protocol, near_uniform_mesh, read_mesh


def measure():
    evidence = REPO / "docs/evidence"
    specification = (evidence / "mesh-displacement-protocol-v1.json").read_bytes()
    plan = json.loads(specification)
    previous = (evidence / "mesh-interpolation-20261118.json").read_bytes()
    if digest(previous) != plan["parent_receipt_sha256"]:
        raise ValueError("original receipt mismatch")
    prior = json.loads(previous)
    protocol = load_protocol()
    vertices, faces, mesh_sha = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    if mesh_sha != prior["input_mesh_file_sha256"] or protocol["sample_sha256"] != prior["sample_sha256"]:
        raise ValueError("mesh or sample identity changed")
    meshes = {"candidate": (vertices, faces), "equal_vertex_comparator": near_uniform_mesh(len(vertices))}
    results = {}
    for case in ("baseline", "primary", "mirror"):
        center = plan[case + "_center_m"]
        metrics = {}
        for arm, mesh in meshes.items():
            report = evaluate(*mesh, protocol["samples"], field_fn=partial(field, center=center))
            if report["validation"]["mesh_sha256"] != prior[arm]["validation"]["mesh_sha256"]:
                raise ValueError("triangulation changed")
            metrics[arm] = report["metrics"]
            if case == "baseline" and not math.isclose(metrics[arm]["rmse"], prior[arm]["metrics"]["rmse"],
                                                       rel_tol=1e-12, abs_tol=0):
                raise ValueError("original RMSE replay failed")
        ratio = metrics["candidate"]["rmse"] / metrics["equal_vertex_comparator"]["rmse"]
        results[case] = {"center_m": center, "metrics": metrics, "rmse_ratio": ratio}
    return {"schema": "merlin-mesh-displacement/1", "protocol_sha256": digest(specification),
            "script_sha256": digest(Path(__file__).read_bytes()),
            "evaluator_sha256": digest((Path(__file__).parent / "measure_mesh_interpolation.py").read_bytes()),
            "sample_sha256": protocol["sample_sha256"], "mesh_file_sha256": mesh_sha,
            "vertices_per_mesh": len(vertices), "results": results}


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, sort_keys=True))
