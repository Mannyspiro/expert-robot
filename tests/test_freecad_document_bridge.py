import json
import tempfile
import unittest
from pathlib import Path

from merlin.freecad_document_bridge import build_document_export_macro, register_freecad_document_artifact
from merlin.project_registry import MerlinRegistry
from merlin.knowledge_graph import MerlinKnowledgeGraph


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

    def test_imported_document_is_registered_and_linked_to_cad_workspace_graph(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            registry = MerlinRegistry(root / "registry")
            registry.register_project("merlin", "Merlin")
            graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
            payload = {
                "schema": "merlin-freecad-document-mesh/1",
                "document_name": "Assembly A",
                "units": "mm",
                "objects": [{
                    "ref": "Body", "name": "Body",
                    "mesh": {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                             "faces": [[0, 1, 2]]},
                    "assembly_children": [],
                }],
                "assemblies": [{"ref": "Assembly", "children": ["Body"]}],
            }
            result = register_freecad_document_artifact(
                registry=registry, graph=graph, project_id="merlin",
                logical_path="cad/assembly-a.json",
                content=json.dumps(payload).encode("utf-8"),
            )
            self.assertTrue(result["artifact_verified"])
            node = graph.get_node(result["cad_node_id"])
            self.assertEqual(node.node_type, "freecad_assembly")
            self.assertEqual(node.payload["objects"][0]["mesh"]["faces"], [[0, 1, 2]])
            self.assertEqual(graph.neighbors(result["cad_node_id"])[0]["relation"], "produces")

    def test_rejects_unsupported_document_format_and_unbounded_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "source must be"):
                build_document_export_macro(Path(temp) / "model.obj", Path(temp) / "out.json")
            with self.assertRaisesRegex(ValueError, "outside the supported bound"):
                build_document_export_macro(Path(temp) / "model.step", Path(temp) / "out.json",
                                            max_objects=100000)


if __name__ == "__main__":
    unittest.main()
