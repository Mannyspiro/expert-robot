import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "python"))
from merlin_tool_reframing import propose


class ToolReframingTests(unittest.TestCase):
    def test_dependency_contract(self):
        p = propose("dependency cycle in plan graph")
        self.assertEqual(p.family, "graph")
        self.assertIn("cycle", p.falsifier)

    def test_simplex_contract(self):
        p = propose("simplex barycentric reconstruction")
        self.assertEqual(p.family, "linear algebra")
        self.assertIn("sum to one", p.invariant)

    def test_restart_contract(self):
        self.assertEqual(propose("checkpoint restart").family, "state machine")

    def test_ambiguity_fails_closed(self):
        for problem in ("", "invent something", "simplex and checkpoint"):
            with self.assertRaises(ValueError):
                propose(problem)


if __name__ == "__main__":
    unittest.main()
