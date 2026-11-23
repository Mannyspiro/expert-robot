"""Tests for Merlin's deterministic prerequisite graph tool."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from merlin_dependency_math import dependency_order


class DependencyMathTests(unittest.TestCase):
    def test_order_is_stable_and_respects_prerequisites(self):
        graph = {"release": ("tests", "build"), "tests": ("build",), "build": (), "docs": ()}
        result = dependency_order(graph)
        self.assertEqual(result, dependency_order(dict(reversed(list(graph.items())))))
        self.assertLess(result.index("build"), result.index("tests"))
        self.assertLess(result.index("tests"), result.index("release"))

    def test_empty_and_independent_graphs(self):
        self.assertEqual(dependency_order({}), ())
        self.assertEqual(dependency_order({"b": (), "a": ()}), ("a", "b"))

    def test_missing_duplicate_and_cycle_rejected(self):
        for graph in ({"a": ("missing",)}, {"a": ("a",)},
                      {"a": ("b",), "b": ("a",)}, {"a": ("b", "b"), "b": ()}):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                dependency_order(graph)

    def test_type_and_bound_rejected(self):
        for graph, bound in (({"a": ()}, True), ({"a": ()}, 0), ({"a": ()}, 10001)):
            with self.assertRaises(ValueError):
                dependency_order(graph, limit=bound)
        for graph in ({"a": "b"}, {"a": (None,)}, {"": ()}, {"a": ("a", "a")}):
            with self.assertRaises(ValueError):
                dependency_order(graph)
        with self.assertRaises(ValueError):
            dependency_order({"a": (), "b": ()}, limit=1)


if __name__ == "__main__":
    unittest.main()
