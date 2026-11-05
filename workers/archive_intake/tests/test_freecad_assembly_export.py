import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_adapter import GeometryContractError, build_assembly_graph
from cad_assembly_graph import resolve_assembly


IDENTITY = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


class FakeShape:
    def isNull(self):
        return False


class FreeCADAssemblyExportTests(unittest.TestCase):
    def setUp(self):
        self.part = SimpleNamespace(
            Name="Housing", Label="Housing", TypeId="App::Part",
            Shape=FakeShape(), Group=[],
        )
        self.bracket = SimpleNamespace(
            Name="Bracket", Label="Bracket", TypeId="PartDesign::Feature",
            Shape=FakeShape(), Group=[],
        )
        self.part.Group = [self.bracket]
        self.document = SimpleNamespace(Objects=[self.part, self.bracket])

    def test_exports_hierarchy_with_explicit_parent_relative_frames(self):
        calls = []
        def placement(obj, parent):
            calls.append((obj.Name, parent.Name if parent else None))
            return IDENTITY
        graph = build_assembly_graph(
            self.document,
            assembly_id="fixture-assembly",
            assembly_artifact_sha256="a" * 64,
            artifact_sha256_for_object=lambda obj: "b" * 64,
            parent_from_component_for_object=placement,
            length_unit="mm",
            angle_unit="deg",
        )
        resolved = resolve_assembly(graph)
        by_id = {item["component_id"]: item for item in resolved["components"]}
        self.assertEqual(by_id["Housing"]["parent_component_id"], "assembly-root")
        self.assertEqual(by_id["Bracket"]["parent_component_id"], "Housing")
        self.assertEqual(calls, [("Bracket", "Housing"), ("Housing", None)])

    def test_requires_artifact_receipt_for_each_component(self):
        with self.assertRaises(GeometryContractError):
            build_assembly_graph(
                self.document,
                assembly_id="fixture-assembly",
                assembly_artifact_sha256="a" * 64,
                artifact_sha256_for_object=lambda obj: "not-a-digest",
                parent_from_component_for_object=lambda obj, parent: IDENTITY,
                length_unit="mm",
                angle_unit="deg",
            )

    def test_rejects_multiple_parents(self):
        second = SimpleNamespace(
            Name="Frame", Label="Frame", TypeId="App::Part",
            Shape=FakeShape(), Group=[self.bracket],
        )
        self.document.Objects.append(second)
        self.part.Group = [self.bracket]
        with self.assertRaises(GeometryContractError):
            build_assembly_graph(
                self.document,
                assembly_id="fixture-assembly",
                assembly_artifact_sha256="a" * 64,
                artifact_sha256_for_object=lambda obj: "b" * 64,
                parent_from_component_for_object=lambda obj, parent: IDENTITY,
                length_unit="mm",
                angle_unit="deg",
            )


if __name__ == "__main__":
    unittest.main()
