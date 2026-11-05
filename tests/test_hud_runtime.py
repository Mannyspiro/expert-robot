import json
import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.hud_runtime import build_hud_runtime, mount_hud_runtime
from merlin.knowledge_graph import GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


class HudRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(root / "graph.sqlite3")
        self.outbox = MerlinEventOutbox(root / "outbox.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def request(self, app, path, query=""):
        response = {}
        def start(status, headers):
            response["status"] = status
            response["headers"] = dict(headers)
        body = b"".join(app({"PATH_INFO": path, "QUERY_STRING": query,
                             "REQUEST_METHOD": "GET"}, start))
        response["body"] = json.loads(body)
        return response

    def test_runtime_injects_canonical_graph_and_typed_workspace(self):
        self.graph.add_node(GraphNode(
            "equation:polar", "equation_atlas", "Polar form",
            {"latex": "z = re^{i theta}", "coordinate_system": "polar"},
        ))
        runtime = build_hud_runtime(
            registry=self.registry, graph=self.graph, outbox=self.outbox,
        )
        graph = self.request(runtime.application, "/api/hud/graph")
        self.assertEqual(graph["status"], "200 OK")
        self.assertEqual(graph["body"]["nodes"][0]["node_id"], "equation:polar")
        node = self.request(runtime.application, "/api/hud/node", "node_id=equation%3Apolar")
        self.assertEqual(node["status"], "200 OK")
        self.assertEqual(node["body"]["workspace"]["workspace"], "equation")
        self.assertEqual(node["body"]["workspace"]["representation"]["latex"], "z = re^{i theta}")

    def test_project_and_outbox_queries_use_canonical_stores(self):
        self.registry.put_artifact("merlin", "notes/summary.txt", b"verified note")
        runtime = build_hud_runtime(
            registry=self.registry, graph=self.graph, outbox=self.outbox,
        )
        projects = self.request(runtime.application, "/api/hud/projects")
        self.assertEqual(projects["status"], "200 OK")
        self.assertEqual(projects["body"]["items"][0]["project_id"], "merlin")
        self.assertEqual(projects["body"]["items"][0]["artifact_count"], 1)
        project = self.request(runtime.application, "/api/hud/project",
                               "project_id=merlin")
        self.assertEqual(project["status"], "200 OK")
        self.assertEqual(project["body"]["project"]["artifacts"][0]["logical_path"],
                         "notes/summary.txt")
        self.assertTrue(project["body"]["project"]["artifacts"][0]["verified"])
        outbox = self.request(runtime.application, "/api/hud/outbox")
        self.assertEqual(outbox["status"], "200 OK")
        self.assertIn("pending", outbox["body"]["counts"])

    def test_activity_get_does_not_acknowledge_outbox_events(self):
        self.outbox.enqueue(
            "test-telemetry", "merlin.telemetry.task.progress",
            {"event_id": "e1", "schema": "merlin-telemetry/1",
             "source": "hermes", "kind": "task.progress",
             "timestamp": "2026-11-04T12:00:00+00:00", "run_id": "r1",
             "task_id": "t1", "payload": {}, "evidence_refs": [],
             "model_id": None, "duration_ms": None, "cpu_percent": None,
             "memory_bytes": None},
        )
        runtime = build_hud_runtime(
            registry=self.registry, graph=self.graph, outbox=self.outbox,
        )
        before = self.outbox.counts()["pending"]
        response = self.request(runtime.application, "/api/hud/activity")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(self.outbox.counts()["pending"], before)

    def test_mounted_dashboard_serves_read_only_browser_view(self):
        runtime = build_hud_runtime(
            registry=self.registry, graph=self.graph, outbox=self.outbox,
        )
        def host(environ, start_response):
            start_response("200 OK", [("Content-Type", "text/plain")])
            return [b"host"]
        mounted = mount_hud_runtime(host, runtime)
        response = {}
        def start(status, headers):
            response["status"] = status
            response["headers"] = dict(headers)
        body = b"".join(mounted(
            {"PATH_INFO": "/dashboard", "REQUEST_METHOD": "GET"}, start
        )).decode("utf-8")
        self.assertEqual(response["status"], "200 OK")
        self.assertIn("Merlin Research HUD", body)
        self.assertIn("/api/hud/node?node_id=", body)

    def test_mount_preserves_host_routes(self):
        runtime = build_hud_runtime(
            registry=self.registry, graph=self.graph, outbox=self.outbox,
        )
        def host(environ, start_response):
            start_response("200 OK", [("Content-Type", "application/json")])
            return [b'{"host":true}']
        mounted = mount_hud_runtime(host, runtime)
        self.assertEqual(self.request(mounted, "/health")["body"], {"host": True})
        self.assertEqual(self.request(mounted, "/api/hud/graph")["status"], "200 OK")


if __name__ == "__main__":
    unittest.main()
