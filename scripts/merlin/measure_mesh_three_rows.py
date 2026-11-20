"""Three-row known-profile inversion on the frozen synthetic mesh benchmark."""
import json
import math
from measure_mesh_localization import estimate_center, measure_arm, move_template
from measure_mesh_interpolation import REPO, field, load_protocol, near_uniform_mesh, read_mesh


def fit(source):
    rows = []
    for y in (.25, .5, .75):
        residuals = [(source(x, y) - .1 * math.sin(2*math.pi*y), x) for x in (.25, .5, .75)]
        (a, x), (b, z) = sorted(residuals, reverse=True)[:2]
        if b <= 0:
            raise ValueError("two positive residuals required")
        rows.append((x+z)/2 + .08**2 * math.log(a/b)/(2*(x-z)))
    return sum(rows)/3, 2*(rows[2]-rows[0])


def measure():
    samples = load_protocol()["samples"]
    verts, faces, _ = read_mesh(REPO/"docs/evidence/mesh-interpolation-native-v1.msh2")
    uniform = near_uniform_mesh(len(verts))
    mirrored = ([(1-x, y) for x, y in uniform[0]], uniform[1])
    cases = []
    for mid in (.43, .57):
        for slope in (-.45, .45):
            def source(x, y):
                return field(x, y, mid+slope*(y-.5))
            center, gradient = fit(source)
            warped = [move_template([(x,y)], center+gradient*(y-.5))[0] for x,y in verts]
            xs = [i/8 for i in range(9)]
            peak = estimate_center(xs, [source(x,.5) for x in xs], .1)
            single = uniform if peak is None else (move_template(verts,peak),faces)
            meshes = dict(three_row=(warped,faces), single=single, uniform=uniform, mirrored=mirrored)
            errors = {k:measure_arm(mesh,samples,source)["rmse"] for k,mesh in meshes.items()}
            cases.append(dict(mid=mid,slope=slope,estimated_mid=center,estimated_slope=gradient,
                              rmse=errors,passed=all(errors["three_row"] < errors[k]
                                                   for k in ("single","uniform","mirrored"))))
    return cases


if __name__ == "__main__":
    print(json.dumps(measure(),indent=2))
