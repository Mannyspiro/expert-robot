import tempfile
import unittest
from pathlib import Path

from merlin.freecad_document_bridge import build_document_export_macro


class FreeCADDocumentBridgeTests(unittest.TestCase):
    def test_macro_imports_document_and_exports_bounded_assembly_mesh(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "assembly.FCStd"
            target = Path(temp) / "assembly.json"
            macro = build_document_export_macro(source, target)
            self.assertIn("App.openDocument(SOURCE)", macro)
            self.assertIn("Import.insert(SOURCE, DOC.Name)", macro)
            self.assertIn('"vertices": mesh_vertices', macro)
            self.assertIn('"faces": mesh_faces', macro)
            self.assertIn('"assemblies":', macro)
            self.assertIn("MAX_VERTICES", macro)
            self.assertIn("MAX_FACES", macro)

    def test_rejects_unsupported_document_format_and_unbounded_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "source must be"):
                build_document_export_macro(Path(temp) / "model.obj", Path(temp) / "out.json")
            with self.assertRaisesRegex(ValueError, "outside the supported bound"):
                build_document_export_macro(Path(temp) / "model.step", Path(temp) / "out.json",
                                            max_objects=100000)


if __name__ == "__main__":
    unittest.main()
