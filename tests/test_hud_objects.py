import unittest

from merlin.hud_objects import render_descriptor
from merlin.knowledge_graph import GraphNode


class HudObjectRendererTests(unittest.TestCase):
    def node(self, node_type, payload):
        return GraphNode("node:1", node_type, "Engineering artifact", payload)

    def test_freecad_descriptor_preserves_assembly_geometry(self):
        payload = {"parts": [{"ref": "P1", "size_mm": [10, 20, 5],
                              "position_mm": [1, 2, 3]}]}
        view = render_descriptor(self.node("freecad_assembly", payload))
        self.assertEqual(view["workspace"], "freecad")
        self.assertEqual(view["cad"]["parts"][0]["ref"], "P1")
        self.assertTrue(view["capabilities"]["read_only"])

    def test_freecad_descriptor_preserves_imported_mesh_and_assembly_tree(self):
        payload = {
            "objects": [{
                "ref": "Body",
                "mesh": {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                         "faces": [[0, 1, 2]]},
                "assembly_children": ["Bolt", "Plate"],
            }],
            "assemblies": [{"ref": "Assembly", "children": ["Body"]}],
        }
        view = render_descriptor(self.node("freecad_assembly", payload))
        self.assertEqual(view["cad"]["objects"][0]["mesh"]["faces"], [[0, 1, 2]])
        self.assertEqual(view["cad"]["assemblies"][0]["children"], ["Body"])

    def test_electrical_descriptor_preserves_nets_and_components(self):
        payload = {"components": [{"ref": "R1"}],
                   "netlist": {"nets": [{"name": "GND", "endpoints": ["R1.1", "J1.2"]}]}}
        view = render_descriptor(self.node("electrical_net", payload))
        self.assertEqual(view["workspace"], "electrical")
        self.assertEqual(view["netlist"]["components"][0]["ref"], "R1")

    def test_simulation_descriptor_preserves_measured_series(self):
        payload = {"series": [{"name": "voltage", "points": [[0, 0], [1, 5]]}],
                   "units": {"x": "s", "y": "V"}}
        view = render_descriptor(self.node("simulation_result", payload))
        self.assertEqual(view["workspace"], "simulation")
        self.assertEqual(view["simulation"]["series"][0]["points"][1], [1, 5])
        self.assertTrue(view["capabilities"]["simulation_is_not_runtime"])


if __name__ == "__main__":
    unittest.main()
