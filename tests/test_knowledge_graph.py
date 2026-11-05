import pytest

from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph


def test_graph_roundtrip_and_deterministic_snapshot(tmp_path):
    graph = MerlinKnowledgeGraph(tmp_path / "graph.sqlite3")
    graph.add_node(GraphNode("claim:one", "claim", "A testable claim", {"formula": "x=x"},
                             "hypothesis", "https://example.org/source"))
    graph.add_node(GraphNode("source:one", "source", "Reference source", {"kind": "paper"},
                             "literature"))
    graph.add_edge(GraphEdge("source:one", "supports", "claim:one", {"scope": "background"}))
    assert graph.get_node("claim:one").payload == {"formula": "x=x"}
    assert graph.neighbors("claim:one", "in")[0]["relation"] == "supports"
    first = graph.export_snapshot()
    assert first["snapshot_sha256"] == graph.export_snapshot()["snapshot_sha256"]
    assert "do not establish truth" in first["epistemic_notice"]


def test_graph_rejects_unknown_types_relations_and_dangling_edges(tmp_path):
    graph = MerlinKnowledgeGraph(tmp_path / "graph.sqlite3")
    with pytest.raises(ValueError):
        graph.add_node(GraphNode("x", "magic", "Unknown", {}))
    graph.add_node(GraphNode("claim:x", "claim", "Claim", {}))
    with pytest.raises(ValueError):
        graph.add_edge(GraphEdge("claim:x", "invented", "claim:x", {}))
    with pytest.raises(Exception):
        graph.add_edge(GraphEdge("claim:x", "supports", "missing:node", {}))


def test_graph_direction_validation(tmp_path):
    graph = MerlinKnowledgeGraph(tmp_path / "graph.sqlite3")
    with pytest.raises(ValueError):
        graph.neighbors("node:x", "sideways")


def test_edge_identity_is_immutable_and_idempotent(tmp_path):
    graph = MerlinKnowledgeGraph(tmp_path / "graph.sqlite3")
    graph.add_node(GraphNode("claim:a", "claim", "A", {}))
    graph.add_node(GraphNode("claim:b", "claim", "B", {}))
    edge = GraphEdge("claim:a", "supports", "claim:b", {"scope": "test"})
    graph.add_edge(edge)
    graph.add_edge(edge)
    with pytest.raises(ValueError, match="different payload"):
        graph.add_edge(GraphEdge("claim:a", "supports", "claim:b", {"scope": "changed"}))
