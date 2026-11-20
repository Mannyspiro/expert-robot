"""Measure whether a nine-probe profile check avoids harmful mesh movement."""
import hashlib
import itertools
import json
import math
import random

from measure_mesh_interpolation import REPO, load_protocol, near_uniform_mesh, read_mesh
from measure_mesh_localization import measure_arm
from measure_mesh_row_background import select_mesh

COORDS = (.25, .5, .75)
# Each template contains the three expected readings before adding a row offset.
TEMPLATES = [tuple(math.exp(-((x-i/1000)/.08)**2) for x in COORDS) for i in range(1001)]


def profile_error(pilots):
    worst = 0.0
    for y in COORDS:
        best = math.inf
        for template in TEMPLATES:
            differences = [pilots[x,y]-value for x,value in zip(COORDS,template)]
            best = min(best, max(differences)-min(differences))
        worst = max(worst, best)
    return worst


def measure():
    evidence = REPO / "docs/evidence"
    raw = (evidence / "mesh-profile-gate-protocol.json").read_bytes()
    spec = json.loads(raw)
    protocol = load_protocol()
    vertices, faces, mesh_hash = read_mesh(evidence / "mesh-interpolation-native-v1.msh2")
    uniform = near_uniform_mesh(len(vertices))
    mirrored = ([(1-x,y) for x,y in uniform[0]], uniform[1])
    results = []
    for mid, slope, family in itertools.product(spec["centers"],spec["slopes"],spec["families"]):
        def source(x,y):
            dx = x-mid-slope*(y-.5)
            background = .03+.17*math.sin(2*math.pi*y)
            if family == "overlap":
                return background+math.exp(-((dx+.09)/.12)**2)+.8*math.exp(-((dx-.09)/.12)**2)
            width = .08 if family == "narrow" else .22
            return background+math.exp(-(dx/width)**2)

        def score(mesh):
            return measure_arm(mesh,protocol["samples"],source)["rmse"]

        baseline, mirror = score(uniform), score(mirrored)
        for seed in spec["seeds"]:
            rng = random.Random(seed)
            bound = spec["noise_bound"]
            pilots = {(x,y):source(x,y)+rng.uniform(-bound,bound) for y in COORDS for x in COORDS}
            mesh, fallback = select_mesh(pilots,vertices,faces,uniform,True,noise_bound=bound)
            candidate = score(mesh)
            error = profile_error(pilots)
            moved = error <= .013 and fallback is None
            selected = candidate if moved else baseline
            results.append(dict(center=mid,slope=slope,family=family,seed=seed,profile_error=error,
                                moved=moved,fallback=fallback,uniform=baseline,mirrored=mirror,
                                candidate=candidate,selected=selected,harmful=selected>baseline,
                                missed=not moved and candidate<baseline))
    available = sum(c["candidate"] < c["uniform"] for c in results)
    missed = sum(c["missed"] for c in results)
    harmful = sum(c["harmful"] for c in results)
    return dict(cases=results,available=available,missed=missed,harmful=harmful,
                advance=available>0 and not harmful and (available-missed)/available>=.75,
                mesh_sha256=mesh_hash,sample_sha256=protocol["sample_sha256"],
                protocol_sha256=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    print(json.dumps(measure(),indent=2,allow_nan=False))
