import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from cad_assembly_graph import AssemblyGraphError, resolve_assembly, transform_point


IDENTITY = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def translated(x=0, y=0, z=0):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


class CadAssemblyGraphTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "assembly_version": "1.0",
            "assembly_id": "pump-module",
            "units": {"length": "mm", "angle": "deg"},
            "components": [
                {"component_id": "root", "parent_component_id": None,
                 "artifact_sha256": "a" * 64, "parent_from_component": IDENTITY},
                {"component_id": "housing", "parent_component_id": "root",
                 "artifact_sha256": "b" * 64, "parent_from_component": translated(10, 0, 0)},
                {"component_id": "rotor", "parent_component_id": "housing",
                 "artifact_sha256": "c" * 64, "parent_from_component": translated(0, 5, 0)},
            ],
        }

    def test_resolves_nested_component_frames(self):
        result = resolve_assembly(self.document)
        rotor = next(c for c in result["components"] if c["component_id"] == "rotor")
        self.assertEqual(transform_point(rotor["root_from_component"], [1, 2, 3]),
                         [11.0, 7.0, 3.0])
        self.assertEqual(result["component_count"], 3)
        self.assertEqual(len(result["assembly_sha256"]), 64)

    def test_component_order_does_not_change_digest(self):
        first = resolve_assembly(self.document)
        reversed_doc = {**self.document, "components": list(reversed(self.document["components"]))}
        second = resolve_assembly(reversed_doc)
        self.assertEqual(first["assembly_sha256"], second["assembly_sha256"])

    def test_duplicate_component_rejected(self):
        self.document["components"].append(dict(self.document["components"][1]))
        with self.assertRaises(AssemblyGraphError):
            resolve_assembly(self.document)

    def test_unknown_parent_rejected(self):
        self.document["components"][2]["parent_component_id"] = "missing"
        with self.assertRaises(AssemblyGraphError):
            resolve_assembly(self.document)

    def test_cycle_rejected(self):
        self.document["components"][1]["parent_component_id"] = "rotor"
        self.document["components"][2]["parent_component_id"] = "housing"
        with self.assertRaises(AssemblyGraphError):
            resolve_assembly(self.document)

    def test_multiple_roots_rejected(self):
        self.document["components"][2]["parent_component_id"] = None
        with self.assertRaises(AssemblyGraphError):
            resolve_assembly(self.document)

    def test_nonfinite_transform_rejected(self):
        self.document["components"][1]["parent_from_component"][0][3] = float("nan")
        with self.assertRaises(AssemblyGraphError):
            resolve_assembly(self.document)


if __name__ == "__main__":
    unittest.main()
