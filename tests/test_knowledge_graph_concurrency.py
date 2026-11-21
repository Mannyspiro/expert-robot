"""Reproduce immutable graph check/insert races without a scheduler guess."""
from pathlib import Path
import tempfile
import threading
import unittest

from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph


class GraphConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.graph = MerlinKnowledgeGraph(Path(self.temp.name) / "graph.sqlite3")

    def concurrent(self, operation, values, select_prefix):
        original = self.graph._connect; barrier = threading.Barrier(2)
        results = []; errors = []
        class Cursor:
            def __init__(self, cursor): self.cursor = cursor
            def fetchone(self):
                value = self.cursor.fetchone()
                # Old SELECT-before-BEGIN code deterministically observes the
                # same absent row in both workers. Protected SELECTs cannot wait
                # on a barrier: the second writer is correctly serialized.
                barrier.wait(timeout=3)
                return value
        class Connection:
            def __init__(self, db): self.db = db
            def __enter__(self): self.db.__enter__(); return self
            def __exit__(self, *args): return self.db.__exit__(*args)
            def close(self): return self.db.close()
            def execute(self, sql, *args):
                cursor = self.db.execute(sql, *args)
                return Cursor(cursor) if sql.startswith(select_prefix) and not self.db.in_transaction else cursor
        self.graph._connect = lambda: Connection(original())
        def run(value):
            try: results.append(operation(value))
            except Exception as exc: errors.append(exc)
        threads = [threading.Thread(target=run, args=(value,)) for value in values]
        try:
            for thread in threads: thread.start()
            for thread in threads: thread.join(5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        finally:
            self.graph._connect = original
        return results, errors

    def test_identical_nodes_concurrently_return_one_immutable_identity(self):
        node = GraphNode("same-node", "artifact", "Fixture", {"value": 1})
        results, errors = self.concurrent(self.graph.add_node, (node, node), "SELECT node_type,label,payload_json")
        self.assertEqual(errors, []); self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.graph.export_snapshot()["nodes"]), 1)

    def test_conflicting_nodes_concurrently_preserve_the_first_payload(self):
        nodes = (GraphNode("same-node", "artifact", "Fixture", {"value": 1}),
                 GraphNode("same-node", "artifact", "Fixture", {"value": 2}))
        results, errors = self.concurrent(self.graph.add_node, nodes, "SELECT node_type,label,payload_json")
        self.assertEqual(len(results), 1); self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertIn(self.graph.get_node("same-node").payload, ({"value": 1}, {"value": 2}))

    def edges(self):
        self.graph.add_node(GraphNode("source", "artifact", "Source", {}))
        self.graph.add_node(GraphNode("target", "claim", "Target", {}))

    def test_identical_edges_concurrently_append_only_once(self):
        self.edges(); edge = GraphEdge("source", "tests", "target", {"evidence": "fixture"})
        results, errors = self.concurrent(self.graph.add_edge, (edge, edge), "SELECT payload_json FROM graph_edges")
        self.assertEqual(errors, []); self.assertEqual(len(results), 2)
        self.assertEqual(len(self.graph.export_snapshot()["edges"]), 1)

    def test_conflicting_edges_concurrently_do_not_overwrite_provenance(self):
        self.edges()
        edges = (GraphEdge("source", "tests", "target", {"evidence": "first"}),
                 GraphEdge("source", "tests", "target", {"evidence": "second"}))
        results, errors = self.concurrent(self.graph.add_edge, edges, "SELECT payload_json FROM graph_edges")
        self.assertEqual(len(results), 1); self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertEqual(len(self.graph.export_snapshot()["edges"]), 1)


if __name__ == "__main__": unittest.main()
