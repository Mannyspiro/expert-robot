"""Frozen synthetic assumption-mismatch experiment with explicit fallback."""
from datetime import datetime, timezone
import hashlib
import json
import math
import platform
import random

from measure_mesh_interpolation import REPO, load_protocol, near_uniform_mesh, read_mesh
from measure_mesh_localization import measure_arm, move_template
from measure_mesh_three_rows import fit


def measure():
    protocol_path = REPO / "docs/evidence/mesh-robustness-protocol-v1.json"
    raw = protocol_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != "b2a91850196ebd1b89de8ee682fe92e208a52d3886873fdbb36f5f592f2eb012":
        raise ValueError("frozen robustness protocol changed")
    spec = json.loads(raw)
    vertices, faces, mesh_hash = read_mesh(REPO / "docs/evidence/mesh-interpolation-native-v1.msh2")
    samples = load_protocol()
    uniform = near_uniform_mesh(len(vertices))
    mirrored = ([(1-x,y) for x,y in uniform[0]], uniform[1])
    results = []
    for mid in spec["centers"]:
        for slope in spec["slopes"]:
            for perturbation in spec["perturbations"]:
                def source(x, y):
                    center = mid + slope*(y-.5)
                    return (math.exp(-((x-center)/perturbation["width"])**2)
                            + perturbation["background"]*math.sin(2*math.pi*y))

                rng = random.Random(spec["noise_seed"])
                queries = []
                def pilot(x,y):
                    value = source(x,y) + rng.uniform(-perturbation["noise"],perturbation["noise"])
                    queries.append([x,y,value])
                    return value

                reason = None
                center = gradient = None
                try:
                    center, gradient = fit(pilot)
                    warped = [move_template([(x,y)],center+gradient*(y-.5))[0] for x,y in vertices]
                    adapted = (warped,faces)
                except ValueError as error:
                    reason = str(error)
                    adapted = uniform
                # A failed early inversion still consumes the full declared pilot budget.
                for y in (.25,.5,.75):
                    for x in (.25,.5,.75):
                        if not any(q[:2] == [x,y] for q in queries):
                            pilot(x,y)
                arms = {name:measure_arm(mesh,samples["samples"],source)
                        for name,mesh in (("adapted",adapted),("uniform",uniform),("mirrored",mirrored))}
                ratios = {name:arms["adapted"]["rmse"]/arms[name]["rmse"]
                          for name in ("uniform","mirrored")}
                results.append(dict(mid=mid,slope=slope,perturbation=perturbation["id"],
                                    estimated_center=center,estimated_slope=gradient,
                                    fallback_reason=reason,pilots=queries,arms=arms,ratios=ratios,
                                    passed=all(r < 1 for r in ratios.values())))
    return dict(schema="merlin-mesh-robustness-result/1",cases=results,
                advance=all(c["passed"] for c in results),
                protocol_sha256=hashlib.sha256(raw).hexdigest(),
                mesh_sha256=mesh_hash,sample_sha256=samples["sample_sha256"],
                source_sha256={p:hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in (
                    "scripts/merlin/measure_mesh_robustness.py",
                    "scripts/merlin/measure_mesh_three_rows.py",
                    "scripts/merlin/measure_mesh_localization.py",
                    "scripts/merlin/measure_mesh_interpolation.py")},
                python=platform.python_version())


if __name__ == "__main__":
    print(json.dumps(measure(),sort_keys=True,indent=2,allow_nan=False))
