"""Compare measured and assumed row backgrounds at the original probe budget."""
import hashlib
import json
import math
import random

from measure_mesh_interpolation import REPO, load_protocol, near_uniform_mesh, read_mesh
from measure_mesh_localization import measure_arm, move_template
from measure_mesh_three_rows import fit


def select_mesh(pilots, vertices, faces, uniform, estimate_background):
    minima = {y: min(v for (px, py), v in pilots.items() if py == y)
              for y in (.25, .5, .75)}

    def reading(x, y):
        if estimate_background:
            # The shared inversion subtracts the nominal sine term internally.
            return pilots[x, y] - minima[y] + .1 * math.sin(2*math.pi*y)
        return pilots[x, y]

    try:
        mid, slope = fit(reading)
        warped = [move_template([(x,y)], mid+slope*(y-.5))[0] for x,y in vertices]
        return (warped, faces), None
    except ValueError as error:
        return uniform, str(error)


def measure():
    evidence = REPO / "docs/evidence"
    spec = (evidence / "mesh-row-background-protocol.txt").read_bytes()
    prior = json.loads((evidence / "mesh-robustness-results.json").read_bytes())
    vertices, faces, mesh_hash = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    uniform = near_uniform_mesh(len(vertices))
    mirrored = ([(1-x,y) for x,y in uniform[0]], uniform[1])
    protocol = load_protocol()
    if mesh_hash != prior["mesh_sha256"] or protocol["sample_sha256"] != prior["sample_sha256"]:
        raise ValueError("original inputs changed")
    cases = []
    for fresh in (False, True):
        for mid in ((.46,.54) if fresh else (.43,.57)):
            for slope in ((-.56,.56) if fresh else (-.45,.45)):
                def source(x,y):
                    background = (.17 if fresh else .12)*math.sin(2*math.pi*y)
                    return math.exp(-((x-(mid+slope*(y-.5)))/.08)**2)+background+(.03 if fresh else 0)
                rng = random.Random(311)
                pilots = {(x,y):source(x,y)+(rng.uniform(-.001,.001) if fresh else 0)
                          for y in (.25,.5,.75) for x in (.25,.5,.75)}
                if not fresh:
                    parent = next(c for c in prior["cases"] if c["mid"] == mid and c["slope"] == slope
                                  and c["perturbation"] == "background")
                    if any(pilots[x,y] != v for x,y,v in parent["pilots"]):
                        raise ValueError("prior pilot replay failed")
                meshes = {"uniform":uniform,"mirrored":mirrored}
                fallback = {}
                for name in ("fixed","estimated"):
                    meshes[name], fallback[name] = select_mesh(pilots,vertices,faces,uniform,name=="estimated")
                rmse = {name:measure_arm(mesh, protocol["samples"],source)["rmse"]
                        for name,mesh in meshes.items()}
                if not fresh and rmse["fixed"] != parent["arms"]["adapted"]["rmse"]:
                    raise ValueError("prior RMSE replay failed")
                passed = rmse["estimated"] < min(rmse["uniform"],rmse["mirrored"])
                cases.append(dict(fresh=fresh,mid=mid,slope=slope,rmse=rmse,fallback=fallback,
                                  pilots=[[x,y,v] for (x,y),v in pilots.items()],
                                  passed=passed and (fresh or rmse["estimated"] < rmse["fixed"])))
    return dict(protocol_sha256=hashlib.sha256(spec).hexdigest(),mesh_sha256=mesh_hash,
                sample_sha256=protocol["sample_sha256"],cases=cases,advance=all(c["passed"] for c in cases))


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2, allow_nan=False))
