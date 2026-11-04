import json
import tempfile
import unittest
from pathlib import Path

from merlin.theorem_dag import extract_theorem_dag


class TheoremDagTests(unittest.TestCase):
    def _fixture(self, root: Path, uses):
        formal = root / "formal"
        source = formal / "MathAI" / "Fixture.lean"
        source.parent.mkdir(parents=True)
        source.write_text(
            "namespace MathAI.Fixture\n"
            "theorem base (n : Nat) : n + 0 = n := by simp\n"
            "theorem derived (n : Nat) (h : n = n) : n + 0 = n := by simpa using base n\n"
            "end MathAI.Fixture\n",
            encoding="utf-8",
        )
        registry = formal / "theorem_registry.json"
        registry.write_text(json.dumps({
            "schema_version": 1,
            "theorems": [
                {"name": "MathAI.Fixture.base", "source": "MathAI/Fixture.lean",
                 "status": "candidate", "statement": "base", "domain": "algebra",
                 "tags": [], "uses": uses.get("base", [])},
                {"name": "MathAI.Fixture.derived", "source": "MathAI/Fixture.lean",
                 "status": "candidate", "statement": "derived", "domain": "algebra",
                 "tags": [], "uses": uses.get("derived", ["MathAI.Fixture.base"])},
            ],
        }), encoding="utf-8")
        return registry, formal

    def test_extracts_dependency_and_surface_hashes_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, formal = self._fixture(Path(tmp), {})
            first = extract_theorem_dag(registry, formal)
            second = extract_theorem_dag(registry, formal)
            self.assertEqual(first, second)
            self.assertEqual(first["node_count"], 2)
            self.assertEqual(first["edge_count"], 1)
            self.assertEqual(first["topological_order_dependencies_first"][0],
                             "MathAI.Fixture.base")
            derived = next(n for n in first["nodes"] if n["id"] == "MathAI.Fixture.derived")
            self.assertEqual(derived["lean_surface_parse_status"], "parsed")
            self.assertEqual(len(derived["lean_surface_declaration"]["surface_statement_sha256"]), 64)

    def test_rejects_missing_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, formal = self._fixture(Path(tmp), {"derived": ["MathAI.Missing"]})
            with self.assertRaises(ValueError):
                extract_theorem_dag(registry, formal)

    def test_rejects_dependency_cycles(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, formal = self._fixture(Path(tmp), {
                "base": ["MathAI.Fixture.derived"],
                "derived": ["MathAI.Fixture.base"],
            })
            with self.assertRaisesRegex(ValueError, "cycle"):
                extract_theorem_dag(registry, formal)


if __name__ == "__main__":
    unittest.main()
