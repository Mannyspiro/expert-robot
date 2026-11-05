import tempfile
import unittest
from pathlib import Path

from merlin.engineering_ir import EngineeringProject, Part, Pin
from merlin.engineering_project_store import EngineeringProjectStore
from merlin.knowledge_graph import GraphNode, MerlinKnowledgeGraph
from merlin.observatory_integrity import verify_database
from merlin.proof_observatory import ProofObservatory, canonical_json, sha256_text
from merlin.observatory_graph_bridge import (
    link_observatory_to_graph,
    register_engineering_revision_views,
    register_representation_graph_views,
)
from merlin.representation_graph import Frame, RepresentationGraph, identity, matrix


def make_receipt():
    payload = {
        "schema": "merlin-cross-domain-benchmark-receipt-v1",
        "source_commit": "a" * 40,
        "all_passed": True,
        "domains": {"geometry": {"passed": True, "checks": {"frame_identity": True}}},
    }
    return {**payload, "receipt_sha256": sha256_text(canonical_json(payload))}


def make_dag():
    payload = {
        "schema": "merlin-theorem-dependency-dag-v1",
        "registry_sha256": "c" * 64,
        "node_count": 1,
        "edge_count": 0,
        "nodes": [{
            "id": "MathAI.Geometry.frame_identity",
            "source": "MathAI/Geometry.lean",
            "source_sha256": "d" * 64,
            "domain": "geometry",
            "status": "candidate",
            "tags": [],
            "dependencies": [],
            "registry_statement_sha256": "e" * 64,
            "lean_surface_declaration": {
                "surface_statement_sha256": "f" * 64,
            },
            "lean_surface_parse_status": "parsed",
            "formal_qualification_required": True,
        }],
        "edges": [],
        "topological_order_dependencies_first": ["MathAI.Geometry.frame_identity"],
        "surface_hash_semantics": "surface syntax only",
    }
    return {**payload, "dag_sha256": sha256_text(canonical_json(payload))}


class ObservatoryGraphBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.project_store = EngineeringProjectStore(root / "engineering.sqlite3")
        self.graph = MerlinKnowledgeGraph(root / "knowledge.sqlite3")
        self.observatory = ProofObservatory(root / "observatory.sqlite3")
        self.project = EngineeringProject(
            name="bridge-fixture",
            units="mm",
            parts=(Part(
                "U1", "controller", (Pin("1", "GND"), Pin("2", "VCC")),
                size_mm=(12.0, 8.0, 2.0),
            ),),
            nets=(),
            metadata={"fixture": "bridge-test"},
        )
        self.project_store.save("robot-controller", self.project)
        self.views = register_engineering_revision_views(
            self.graph, self.project_store, "robot-controller", 1,
        )

    def tearDown(self):
        self.observatory.close()
        self.tmp.cleanup()

    def test_registers_real_engineering_parts_and_frame_views(self):
        self.assertEqual(self.views["revision"], 1)
        part_id = self.views["part_object_views"]["U1"]
        part_node = self.graph.get_node(part_id)
        self.assertEqual(part_node.node_type, "object_view")
        self.assertEqual(part_node.payload["engineering_revision_sha256"], self.views["revision_sha256"])

        representation = RepresentationGraph([
            Frame("canonical", identity(2)),
            Frame("sheared", matrix([[1, 1], [0, 1]])),
        ])
        frames = register_representation_graph_views(
            self.graph, representation,
            project_id="robot-controller", revision=1,
            revision_sha256=self.views["revision_sha256"],
            project_node_id=self.views["project_node_id"],
        )
        self.assertEqual(set(frames), {"canonical", "sheared"})
        self.assertEqual(
            self.graph.get_node(frames["sheared"]).payload["object_kind"],
            "coordinate_frame",
        )

    def test_links_benchmark_to_actual_revision_bound_graph_objects(self):
        part_id = self.views["part_object_views"]["U1"]
        result = link_observatory_to_graph(
            self.graph, self.project_store, self.observatory,
            make_receipt(), make_dag(),
            project_id="robot-controller", revision=1,
            object_view_ids_by_domain={"geometry": [part_id]},
        )
        self.assertEqual(result["observatory_link_count"], 1)
        self.assertEqual(result["knowledge_graph_edge_count"], 1)
        edges = self.graph.neighbors(part_id, direction="out")
        self.assertTrue(any(
            edge["relation"] == "tests"
            and edge["target_id"] == "MathAI.Geometry.frame_identity"
            for edge in edges
        ))
        report = verify_database(self.observatory.path, make_dag())
        self.assertTrue(report["ok"], report["errors"])

    def test_rejects_object_view_from_a_different_engineering_revision(self):
        old_part_id = self.views["part_object_views"]["U1"]
        changed = EngineeringProject(
            name="bridge-fixture",
            units="mm",
            parts=(Part(
                "U1", "controller", (Pin("1", "GND"), Pin("2", "VCC")),
                size_mm=(14.0, 8.0, 2.0),
            ),),
            nets=(),
            metadata={"fixture": "bridge-test"},
        )
        self.project_store.save("robot-controller", changed)
        register_engineering_revision_views(
            self.graph, self.project_store, "robot-controller", 2,
        )
        with self.assertRaisesRegex(ValueError, "exact Engineering IR revision"):
            link_observatory_to_graph(
                self.graph, self.project_store, self.observatory,
                make_receipt(), make_dag(),
                project_id="robot-controller", revision=2,
                object_view_ids_by_domain={"geometry": [old_part_id]},
            )

    def test_rejects_a_project_node_with_a_mismatched_identity(self):
        node_id = self.views["project_node_id"]
        node = self.graph.get_node(node_id)
        self.graph.add_node(GraphNode(
            node_id=node_id,
            node_type="project",
            label=node.label,
            payload={
                **node.payload,
                "engineering_project_id": "different-project",
            },
            evidence_class=node.evidence_class,
        ))
        part_id = self.views["part_object_views"]["U1"]
        with self.assertRaisesRegex(ValueError, "exact Engineering IR revision"):
            link_observatory_to_graph(
                self.graph, self.project_store, self.observatory,
                make_receipt(), make_dag(),
                project_id="robot-controller", revision=1,
                object_view_ids_by_domain={"geometry": [part_id]},
            )

    def test_rejects_string_instead_of_object_view_id_collection(self):
        part_id = self.views["part_object_views"]["U1"]
        with self.assertRaisesRegex(TypeError, "iterable of IDs"):
            link_observatory_to_graph(
                self.graph, self.project_store, self.observatory,
                make_receipt(), make_dag(),
                project_id="robot-controller", revision=1,
                object_view_ids_by_domain={"geometry": part_id},
            )

    def test_invalid_dag_does_not_leave_a_benchmark_receipt_behind(self):
        broken = make_dag()
        broken["nodes"][0]["dependencies"] = ["missing"]
        dag_payload = {key: value for key, value in broken.items() if key != "dag_sha256"}
        broken["dag_sha256"] = sha256_text(canonical_json(dag_payload))
        part_id = self.views["part_object_views"]["U1"]
        with self.assertRaisesRegex(ValueError, "DAG failed integrity checks"):
            link_observatory_to_graph(
                self.graph, self.project_store, self.observatory,
                make_receipt(), broken,
                project_id="robot-controller", revision=1,
                object_view_ids_by_domain={"geometry": [part_id]},
            )
        report = verify_database(self.observatory.path)
        self.assertEqual(report["counts"]["benchmark_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
