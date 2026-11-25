"""Exact geometry, assignment and traffic checks for the abstract layout model."""
from dataclasses import replace
from itertools import combinations, product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin.parallax_layout import (FACES, Grid, LAYOUTS, assignment, axis_separated,
                                    comparison_report, kv_cache_bytes, layout_report,
                                    make_layout, manhattan, to_obj, to_openscad,
                                    validate_tiles, vertices, xyz_route)


class ParallaxLayoutTests(unittest.TestCase):
    def test_grid_bijection_and_bounds(self):
        for dims in ((1, 1, 1), (3, 2, 4), *LAYOUTS.values()):
            grid = Grid(*dims)
            cells = list(product(*(range(n) for n in dims)))
            self.assertEqual({grid.pack(p) for p in cells}, set(range(grid.volume)))
            for cell in cells:
                self.assertEqual(grid.unpack(grid.pack(cell)), cell)
            for invalid in (-1, grid.volume, True, 1.5):
                with self.assertRaises(ValueError):
                    grid.unpack(invalid)
            for axis in range(3):
                cell = [0, 0, 0]
                cell[axis] = dims[axis]
                with self.assertRaises(ValueError):
                    grid.pack(cell)
        for dims in ((0, 1, 1), (1, -1, 1), (1, 1, True), (1., 1, 1)):
            with self.assertRaises(ValueError):
                Grid(*dims)

    def test_assignment_is_identical_and_nonoverlapping(self):
        assignments = []
        for name in LAYOUTS:
            grid, tiles = make_layout(name)
            self.assertEqual([sum(t.role == r for t in tiles) for r in ("compute", "kv", "control")], [16, 8, 8])
            assignments.append([(t.address, t.role, t.index) for t in tiles])
            self.assertTrue(all(axis_separated(a, b) for a, b in combinations(tiles, 2)))
            self.assertFalse(axis_separated(tiles[0], tiles[0]))
            for tile in tiles:
                lo, hi = tile.bounds_eighths
                for i, bound in enumerate((grid.nx, grid.ny, grid.nz)):
                    self.assertTrue(0 <= lo[i] < hi[i] <= 8 * bound)
                    self.assertEqual(hi[i] - lo[i], 6)
        self.assertEqual(assignments[0], assignments[1])
        self.assertEqual(assignments[1], assignments[2])
        self.assertEqual([assignment(i) for i in range(4)], [("compute", 0), ("compute", 1), ("kv", 0), ("control", 0)])

    def test_mutated_coordinates_roles_addresses_are_rejected(self):
        grid, tiles = make_layout("stack")
        for invalid in (replace(tiles[0], cell=(4, 0, 0)), replace(tiles[0], cell=tiles[1].cell),
                        replace(tiles[0], role="kv"), replace(tiles[0], index=1), replace(tiles[0], index=False),
                        replace(tiles[0], address=1), replace(tiles[0], address=False)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_tiles(grid, (invalid, *tiles[1:]))
        with self.assertRaises(ValueError):
            validate_tiles(grid, tiles[:-1])

    def test_xyz_routes_are_legal_shortest_adjacent_paths(self):
        grid = Grid(4, 4, 2)
        a, b = (3, 0, 1), (0, 3, 0)
        route = xyz_route(grid, a, b)
        self.assertEqual((route[0], route[-1]), (a, b))
        self.assertEqual(len(route) - 1, 7)
        self.assertEqual(manhattan(a, b), 7)
        self.assertTrue(all(manhattan(x, y) == 1 for x, y in zip(route, route[1:])))
        for p in route:
            self.assertLess(grid.pack(p), grid.volume)
        self.assertEqual(xyz_route(grid, a, a), (a,))

    def test_kv_size_and_traffic_are_exact_and_do_not_improve_in_3d(self):
        self.assertEqual(kv_cache_bytes(), 469_762_048)
        self.assertEqual(kv_cache_bytes(context_length=1), 114_688)
        self.assertEqual(kv_cache_bytes(element_bytes=4), 939_524_096)
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                kv_cache_bytes(context_length=invalid)
        for name in LAYOUTS:
            report = layout_report(name)
            self.assertEqual(report["metrics"], {"logical_reads": 16, "total_hops": 24,
                             "maximum_hops": 2, "payload_read_bytes": 939_524_096,
                             "byte_hops": 1_409_286_144})
            self.assertEqual([t["hops"] for t in report["transfers"]], [2, 1] * 8)
            self.assertEqual({t["payload_bytes"] for t in report["transfers"]}, {58_720_256})
            for transfer in report["transfers"]:
                self.assertEqual(transfer["source_address"], 4 * (transfer["destination_address"] // 4) + 2)
                self.assertEqual(transfer["source_address"] % 4, 2)
            self.assertEqual(layout_report(name, 1)["metrics"]["byte_hops"] * 4096, report["metrics"]["byte_hops"])
        self.assertEqual(comparison_report()["checkpoint_shape"]["query_r_heads"], 16)

    def test_exported_meshes_are_closed_and_in_model_units(self):
        for name in LAYOUTS:
            obj = to_obj(name)
            points = [tuple(map(float, l.split()[1:])) for l in obj.splitlines() if l.startswith("v ")]
            faces = [tuple(int(v) - 1 for v in l.split()[1:]) for l in obj.splitlines() if l.startswith("f ")]
            self.assertEqual((len(points), len(faces)), (256, 192))
            edges = {}
            for face in faces:
                self.assertTrue(all(0 <= v < len(points) for v in face))
                for a, b in zip(face, (*face[1:], face[0])):
                    edges[tuple(sorted((a, b)))] = edges.get(tuple(sorted((a, b))), 0) + 1
            self.assertEqual(set(edges.values()), {2})
            _, tiles = make_layout(name)
            self.assertEqual(points[:8], list(vertices(tiles[0])))
            self.assertEqual(len(FACES), 6)
            self.assertIn("tile pitch", obj)
            self.assertIn("not mm", to_openscad(name))
            self.assertEqual(to_openscad(name).count("cube([0.75,0.75,0.75])"), 32)


if __name__ == "__main__":
    unittest.main()
