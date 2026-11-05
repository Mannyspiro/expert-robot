import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freecad_adapter import FreeCADBackend, FreeCADUnavailable, _placement_matrix


class FreeCADAdapterContractTests(unittest.TestCase):
    def test_requires_explicit_runtime_modules(self):
        with self.assertRaises(FreeCADUnavailable):
            FreeCADBackend(
                app=None, importer=object(), part=object(),
                mesh_part=object(), mesh=object(), backend_version="test-build",
            )

    def test_requires_exact_version_label(self):
        importer = SimpleNamespace(insert=lambda *_: None)
        modules = dict(
            app=object(), importer=importer, part=object(),
            mesh_part=object(), mesh=object(),
        )
        with self.assertRaises(FreeCADUnavailable):
            FreeCADBackend(**modules, backend_version=" ")

    def test_normalizes_freecad_placement_matrix(self):
        values = [
            1, 0, 0, 10,
            0, 1, 0, 20,
            0, 0, 1, 30,
            0, 0, 0, 1,
        ]
        placement = SimpleNamespace(toMatrix=lambda: SimpleNamespace(A=values))
        self.assertEqual(_placement_matrix(placement), [
            [1.0, 0.0, 0.0, 10.0],
            [0.0, 1.0, 0.0, 20.0],
            [0.0, 0.0, 1.0, 30.0],
            [0.0, 0.0, 0.0, 1.0],
        ])


if __name__ == "__main__":
    unittest.main()
