"""Frozen, equal-vertex P1 interpolation experiment on a synthetic unit square.

Run with PYTHONPATH=python. This reads an existing 2D Gmsh2.2 or Medit/BAMG mesh;
it does not launch a mesher, solve a PDE, tune the metric, or qualify geometry.
The fallback is explicitly a synthetic structured control, never a native run.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import platform
import time

from merlin.engineering.geometry import GeometrySpec, Point3D, validate_geometry


PROTOCOL_SHA256 = "b4d456bdd43e63373ca23b8ef3f94f3c60197a386c1a3718c22fa1779d3637f9"
NATIVE_SOURCE_COMMIT = "1563f71f224d59c8712e2181369ff93440957b0f"
REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "docs/evidence/mesh-interpolation-protocol-v1.json"
MAX_VERTICES = 10000
MAX_TRIANGLES = 20000
TOLERANCE = 1e-10


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_protocol():
    raw = PROTOCOL.read_bytes()
    if digest(raw) != PROTOCOL_SHA256:
        raise ValueError("the exact frozen mesh-interpolation protocol is required")
    result = json.loads(raw)
    if (result["sample_count"] != 4096 or len(result["samples"]) != 4096
            or digest(canonical(result["samples"])) != result["sample_sha256"]):
        raise ValueError("frozen sample identity mismatch")
    return result


def read_mesh(path):
    raw = Path(path).read_bytes()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("bounded ASCII mesh required")
    if raw.lstrip().startswith(b"$MeshFormat"):
        return read_gmsh22(raw)
    tokens = " ".join(line.split("#", 1)[0] for line in raw.decode("ascii").splitlines()).split()
    if len(tokens) > 500000:
        raise ValueError("mesh token budget exceeded")
    vertices, triangles = None, None
    dimension, index = None, 0
    optional_widths = {"Edges": 3, "Corners": 1, "RequiredVertices": 1, "RequiredEdges": 1}
    while index < len(tokens):
        keyword = tokens[index]
        index += 1
        if keyword == "End":
            if index != len(tokens):
                raise ValueError("unexpected content after mesh End")
            break
        if keyword in {"MeshVersionFormatted", "Dimension"}:
            value = int(tokens[index])
            index += 1
            if keyword == "Dimension":
                dimension = value
            elif value not in (1, 2):
                raise ValueError("unsupported ASCII mesh version")
            continue
        if keyword not in {"Vertices", "Triangles"} | set(optional_widths):
            raise ValueError("unsupported mesh section: " + keyword)
        count = int(tokens[index])
        index += 1
        limit = MAX_VERTICES if keyword == "Vertices" else 3 * MAX_TRIANGLES
        if count < 0 or count > limit:
            raise ValueError("mesh section budget exceeded")
        width = 3 if keyword == "Vertices" else 4 if keyword == "Triangles" else optional_widths[keyword]
        if index + count * width > len(tokens):
            raise ValueError("truncated mesh section")
        if keyword == "Vertices":
            if vertices is not None or dimension != 2:
                raise ValueError("one declared two-dimensional vertex section required")
            vertices = []
            for _ in range(count):
                vertices.append((float(tokens[index]), float(tokens[index + 1])))
                int(tokens[index + 2])
                index += 3
        elif keyword == "Triangles":
            if triangles is not None or count > MAX_TRIANGLES:
                raise ValueError("one bounded triangle section required")
            triangles = []
            for _ in range(count):
                triangles.append(tuple(int(tokens[index + offset]) - 1 for offset in range(3)))
                int(tokens[index + 3])
                index += 4
        else:
            for token in tokens[index:index + count * width]:
                int(token)
            index += count * width
    if dimension != 2 or vertices is None or triangles is None:
        raise ValueError("complete two-dimensional mesh required")
    return vertices, triangles, digest(raw)


def read_gmsh22(raw):
    """Read the native Gmsh2.2 ASCII export without altering coordinates."""
    lines = [line.strip() for line in raw.decode("ascii").splitlines() if line.strip()]
    if lines[:3] != ["$MeshFormat", "2.2 0 8", "$EndMeshFormat"]:
        raise ValueError("exact Gmsh2.2 ASCII format required")
    index = 3
    if lines[index] != "$Nodes":
        raise ValueError("Gmsh node section required")
    count = int(lines[index + 1])
    index += 2
    if not 4 <= count <= MAX_VERTICES:
        raise ValueError("bounded Gmsh vertex count required")
    vertices, ids = [], {}
    for _ in range(count):
        fields = lines[index].split()
        index += 1
        if len(fields) != 4:
            raise ValueError("Gmsh node requires id,x,y,z")
        node_id = int(fields[0])
        x, y, z = (float(value) for value in fields[1:])
        if node_id <= 0 or node_id in ids or not math.isfinite(z) or abs(z) > TOLERANCE:
            raise ValueError("unique planar Gmsh nodes required")
        ids[node_id] = len(vertices)
        vertices.append((x, y))
    if lines[index:index + 2] != ["$EndNodes", "$Elements"]:
        raise ValueError("Gmsh element section required")
    count = int(lines[index + 2])
    index += 3
    if not 2 <= count <= 3 * MAX_TRIANGLES:
        raise ValueError("bounded Gmsh element count required")
    triangles, element_ids = [], set()
    for _ in range(count):
        values = [int(value) for value in lines[index].split()]
        index += 1
        if len(values) < 3:
            raise ValueError("truncated Gmsh element")
        element_id, kind, tags = values[:3]
        width = {1: 2, 2: 3, 15: 1}.get(kind)
        if (element_id <= 0 or element_id in element_ids or width is None
                or not 0 <= tags <= 16 or len(values) != 3 + tags + width):
            raise ValueError("only bounded triangle/edge/point Gmsh elements are supported")
        element_ids.add(element_id)
        nodes = values[3 + tags:]
        if any(node not in ids for node in nodes):
            raise ValueError("Gmsh element references an unknown node")
        if kind == 2:
            triangles.append(tuple(ids[node] for node in nodes))
    if lines[index:] != ["$EndElements"] or len(triangles) > MAX_TRIANGLES:
        raise ValueError("complete triangle-only planar Gmsh export required")
    return vertices, triangles, digest(raw)


def near_uniform_mesh(count):
    """Exactly N points, almost equal row lengths, full square boundary."""
    if type(count) is not int or not 4 <= count <= MAX_VERTICES:
        raise ValueError("vertex count must be an integer between4 and10000")
    rows = max(2, round(math.sqrt(count)))
    low, remainder = divmod(count, rows)
    vertices, row_ids = [], []
    for row in range(rows):
        size = low + (1 if row < remainder else 0)
        if size < 2:
            raise ValueError("each row requires its two boundary endpoints")
        ids = []
        for col in range(size):
            ids.append(len(vertices))
            vertices.append((col / (size - 1), row / (rows - 1)))
        row_ids.append(ids)
    triangles = []
    for lower, upper in zip(row_ids, row_ids[1:]):
        i = j = 0
        while i + 1 < len(lower) or j + 1 < len(upper):
            next_lower = vertices[lower[i + 1]][0] if i + 1 < len(lower) else math.inf
            next_upper = vertices[upper[j + 1]][0] if j + 1 < len(upper) else math.inf
            if next_lower <= next_upper:
                triangles.append((lower[i], lower[i + 1], upper[j]))
                i += 1
            else:
                triangles.append((lower[i], upper[j + 1], upper[j]))
                j += 1
    return vertices, triangles


def validate_square_mesh(vertices, triangles):
    if not 4 <= len(vertices) <= MAX_VERTICES or not 2 <= len(triangles) <= MAX_TRIANGLES:
        raise ValueError("bounded nonempty planar mesh required")
    if (len(set(vertices)) != len(vertices)
            or any(not math.isfinite(value) or value < -TOLERANCE or value > 1 + TOLERANCE
                   for point in vertices for value in point)):
        raise ValueError("unique finite vertices within the unit square required")
    if any(len(face) != 3 or len(set(face)) != 3
           or any(type(v) is not int or not 0 <= v < len(vertices) for v in face) for face in triangles):
        raise ValueError("triangle connectivity references invalid vertices")
    spec = GeometrySpec("synthetic-square-interpolation", "m",
        tuple(Point3D(str(i), x, y, 0) for i, (x, y) in enumerate(vertices)),
        tuple(tuple(str(v) for v in face) for face in triangles), closed_solid=False)
    issues = validate_geometry(spec)
    if issues:
        raise ValueError("Merlin geometry validation: " + ",".join(i.code for i in issues))
    oriented, areas, flips = [], [], 0
    edges, used = defaultdict(list), set()
    for face in triangles:
        a, b, c = (vertices[v] for v in face)
        determinant = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if determinant == 0:
            raise ValueError("degenerate triangle")
        if determinant < 0:
            face = (face[0], face[2], face[1])
            flips += 1
        areas.append(abs(determinant) / 2)
        face_id = len(oriented)
        oriented.append(face)
        used.update(face)
        for v, w in zip(face, face[1:] + face[:1]):
            edges[tuple(sorted((v, w)))].append((face_id, v, w))
    if len(used) != len(vertices):
        raise ValueError("unused vertices would invalidate equal-N comparison")
    neighbors, boundary, side_intervals = defaultdict(set), [], defaultdict(list)
    for edge, entries in edges.items():
        if len(entries) == 2:
            left, right = entries
            if left[1:] != (right[2], right[1]):
                raise ValueError("folded/inconsistently embedded neighboring triangles")
            neighbors[left[0]].add(right[0])
            neighbors[right[0]].add(left[0])
        elif len(entries) == 1:
            boundary.append(edge)
            a, b = (vertices[v] for v in edge)
            found = False
            for axis in (0, 1):
                for endpoint in (0, 1):
                    if abs(a[axis] - endpoint) <= TOLERANCE and abs(b[axis] - endpoint) <= TOLERANCE:
                        side_intervals[(axis, endpoint)].append(tuple(sorted((a[1-axis], b[1-axis]))))
                        found = True
            if not found:
                raise ValueError("interior hole or incomplete square boundary")
        else:
            raise ValueError("non-manifold edge")
    for side in ((0, 0), (0, 1), (1, 0), (1, 1)):
        intervals = sorted(side_intervals[side])
        last = 0.0
        for start, end in intervals:
            if abs(start - last) > TOLERANCE or end - start <= 0:
                raise ValueError("square boundary has a gap or overlapping segment")
            last = end
        if abs(last - 1) > TOLERANCE:
            raise ValueError("square boundary does not cover full side")
    degree = defaultdict(int)
    for a, b in boundary:
        degree[a] += 1
        degree[b] += 1
    seen, queue = {0}, deque([0])
    while queue:
        for neighbor in neighbors[queue.popleft()]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    area = math.fsum(areas)
    if (any(value != 2 for value in degree.values()) or len(seen) != len(triangles)
            or len(vertices) - len(edges) + len(triangles) != 1
            or not math.isclose(area, 1, rel_tol=1e-8, abs_tol=1e-8)):
        raise ValueError("connected square disk topology/area coverage check failed")
    return oriented, {"vertex_count": len(vertices), "triangle_count": len(triangles),
        "geometry_issue_codes": [], "triangle_components": 1, "euler_characteristic": 1,
        "all_vertices_used": True, "all_four_boundary_sides_covered": True,
        "summed_triangle_area": area, "minimum_triangle_area": min(areas),
        "boundary_edge_count": len(boundary), "input_clockwise_faces_reoriented": flips,
        "mesh_sha256": digest(canonical({"vertices": vertices, "triangles": triangles})),
        "coverage_scope": "floating-point area, boundary, oriented adjacency, disk topology and held-out location checks; not formal proof"}


def field(x, y, center=.5):
    return math.exp(-((x - center) / .08) ** 2) + .1 * math.sin(2 * math.pi * y)


def affine(x, y):
    return 1 + 2 * x - 3 * y


def evaluate(vertices, triangles, samples, *, center=.5):
    triangles, validation = validate_square_mesh(vertices, triangles)
    bins, index, insertions = 32, defaultdict(list), 0
    records = []
    for face in triangles:
        a, b, c = (vertices[v] for v in face)
        det = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        records.append((a, b, c, det, tuple(field(*vertices[v], center=center) for v in face),
                        tuple(affine(*vertices[v]) for v in face)))
        ranges = []
        for axis in (0, 1):
            low = max(0, min(bins-1, int(min(vertices[v][axis] for v in face) * bins)))
            high = max(0, min(bins-1, int(max(vertices[v][axis] for v in face) * bins)))
            ranges.append(range(low, high + 1))
        for x in ranges[0]:
            for y in ranges[1]:
                index[x, y].append(len(records)-1)
                insertions += 1
                if insertions > 2000000:
                    raise ValueError("point-location index budget exceeded")
    errors, control_errors, checks = [], [], 0
    for x, y in samples:
        found = False
        for face_id in index[min(31, int(x * bins)), min(31, int(y * bins))]:
            checks += 1
            if checks > 10000000:
                raise ValueError("point-location work budget exceeded")
            a, b, c, det, values, controls = records[face_id]
            w1 = ((x-a[0]) * (c[1]-a[1]) - (y-a[1]) * (c[0]-a[0])) / det
            w2 = ((b[0]-a[0]) * (y-a[1]) - (b[1]-a[1]) * (x-a[0])) / det
            weights = (1-w1-w2, w1, w2)
            if min(weights) >= -1e-11:
                errors.append(abs(math.fsum(w * value for w, value in zip(weights, values)) - field(x, y, center=center)))
                control_errors.append(abs(math.fsum(w * value for w, value in zip(weights, controls)) - affine(x, y)))
                found = True
                break
        if not found:
            raise ValueError("held-out point is not covered by triangle connectivity")
    if max(control_errors) > 1e-10:
        raise ValueError("affine interpolation control failed")
    return {"validation": validation, "metrics": {
        "sample_count": len(samples), "rmse": math.sqrt(math.fsum(e*e for e in errors) / len(errors)),
        "mean_absolute_error": math.fsum(errors) / len(errors), "maximum_absolute_error": max(errors),
        "affine_control_max_absolute_error": max(control_errors), "uncovered_samples": 0},
        "point_location_triangle_tests": checks}


def measure(mesh_path=None, *, synthetic_vertices=289, native_receipt=None):
    protocol = load_protocol()
    if mesh_path is None:
        vertices, triangles = near_uniform_mesh(synthetic_vertices)
        input_sha = digest(canonical({"vertices": vertices, "triangles": triangles}))
        origin = "structured_synthetic_control_not_native"
    else:
        vertices, triangles, input_sha = read_mesh(mesh_path)
        origin = "provided_native_mesh_file; native tool execution is separately evidenced"
    comparator_vertices, comparator_triangles = near_uniform_mesh(len(vertices))
    start = time.perf_counter()
    candidate = evaluate(vertices, triangles, protocol["samples"])
    comparator = evaluate(comparator_vertices, comparator_triangles, protocol["samples"])
    ratio = candidate["metrics"]["rmse"] / comparator["metrics"]["rmse"]
    report = {"schema": "merlin-mesh-interpolation-measurement/1", "status": "passed",
        "protocol_sha256": PROTOCOL_SHA256, "sample_sha256": protocol["sample_sha256"],
        "field": protocol["field"], "field_output_unit": "1 (synthetic dimensionless scalar)",
        "candidate_origin": origin, "input_mesh_file_sha256": input_sha,
        "candidate": candidate, "equal_vertex_comparator": comparator,
        "candidate_to_uniform_rmse_ratio": ratio,
        "observed_result": "candidate_lower_rmse" if ratio < 1 else "candidate_higher_rmse" if ratio > 1 else "equal_rmse",
        "python": platform.python_version(), "elapsed_evaluation_seconds": time.perf_counter() - start,
        "source_sha256": {"benchmark": digest(Path(__file__).read_bytes()),
            "merlin_geometry_validator": digest((REPO/'python/merlin/engineering/geometry.py').read_bytes())},
        "qualification": False, "promotion_authority": False,
        "limits": ["Synthetic analytic field informed the fixed metric; only uniform evaluation locations are held out.",
            "One mesh/field/budget; no blind generalization, PDE-solver, physical or mesher-wide superiority claim.",
            "Equal total vertex count; boundary vertex counts and triangle shapes may differ.",
            "Floating-point connectivity/coverage validation is not a formal geometric proof."]}
    if native_receipt is not None:
        raw = Path(native_receipt).read_bytes()
        if len(raw) > 128000:
            raise ValueError("bounded native receipt required")
        receipt = json.loads(raw)
        name = receipt.get("output", {}).get("filename")
        if (mesh_path is None or receipt.get("schema") != "merlin-refine-native-build/1"
                or receipt.get("source", {}).get("commit") != NATIVE_SOURCE_COMMIT
                or receipt.get("execution", {}).get("exit_code") != 0
                or receipt.get("artifact_sha256", {}).get(name) != input_sha
                or receipt.get("output", {}).get("vertices_from_native_log") != len(vertices)
                or receipt.get("output", {}).get("triangles_from_native_log") != len(triangles)
                or receipt.get("qualification") is not False
                or receipt.get("promotion_authority") is not False):
            raise ValueError("native receipt does not bind the measured mesh/source/counts")
        report["native_run_receipt"] = {"sha256": digest(raw), "reported_metadata": receipt,
            "binding_verified": "mesh bytes/source/counts only; receipt authenticity is separately established"}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path)
    parser.add_argument("--native-receipt", type=Path)
    parser.add_argument("--synthetic-vertices", type=int, default=289)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(args.mesh, synthetic_vertices=args.synthetic_vertices, native_receipt=args.native_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "vertices": report["candidate"]["validation"]["vertex_count"],
        "rmse_ratio": report["candidate_to_uniform_rmse_ratio"], "result": report["observed_result"]}))


if __name__ == "__main__":
    main()
