import json
import unittest
from types import SimpleNamespace
from merlin.knowledge_graph import GraphNode

from merlin.hud_activity import HudActivityProjector
from merlin.hud_http import HudActivityWSGI


class HudActivityWSGITests(unittest.TestCase):
    def setUp(self):
        self.app = HudActivityWSGI(HudActivityProjector())

    def request(self, path="/api/hud/activity", method="GET"):
        result = {}
        def start_response(status, headers):
            result["status"] = status
            result["headers"] = dict(headers)
        body = b"".join(self.app({"PATH_INFO": path, "REQUEST_METHOD": method,
                                  "QUERY_STRING": ""}, start_response))
        result["body"] = json.loads(body)
        return result

    def test_get_returns_live_schema_and_no_store(self):
        response = self.request()
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["body"]["schema"], "merlin-hud-activity/1")
        self.assertEqual(response["headers"]["Cache-Control"], "no-store")

    def test_endpoint_is_get_only(self):
        self.assertEqual(self.request(method="POST")["status"], "405 Method Not Allowed")

    def test_dashboard_is_a_read_only_html_view(self):
        response = {}
        def start(status, headers):
            response["status"] = status
            response["headers"] = dict(headers)
        body = b"".join(self.app(
            {"PATH_INFO": "/dashboard", "REQUEST_METHOD": "GET"}, start
        )).decode("utf-8")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(response["headers"]["X-Frame-Options"], "DENY")
        self.assertIn('"/api/hud/activity"', body)
        self.assertIn('"/api/hud/graph"', body)
        self.assertIn('"/api/hud/projects"', body)
        self.assertNotIn('method:"POST"', body)

    def test_dashboard_rejects_mutating_methods(self):
        self.assertEqual(self.request(path="/dashboard", method="POST")["status"],
                         "405 Method Not Allowed")

    def test_unknown_path_is_not_found(self):
        self.assertEqual(self.request(path="/other")["status"], "404 Not Found")

    def test_graph_routes_require_injected_read_api(self):
        self.assertEqual(self.request(path="/api/hud/graph")["status"],
                         "503 Service Unavailable")

    def test_graph_snapshot_route_returns_canonical_snapshot(self):
        snapshot = {"schema_version": "1.0", "nodes": [], "edges": [],
                    "snapshot_sha256": "abc", "epistemic_notice": "not truth"}
        read_api = SimpleNamespace(graph=lambda: snapshot)
        app = HudActivityWSGI(HudActivityProjector(), read_api=read_api)
        response = {}
        def start(status, headers):
            response["status"] = status
        body = b"".join(app({"PATH_INFO": "/api/hud/graph", "REQUEST_METHOD": "GET"},
                            start))
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(json.loads(body), snapshot)

    def test_node_route_returns_node_and_typed_neighbors(self):
        node = GraphNode("claim:1", "claim", "Claim", {"text": "test"})
        graph = SimpleNamespace(
            get_node=lambda node_id: node if node_id == "claim:1" else None,
            neighbors=lambda node_id: [{"relation": "supports"}],
        )
        app = HudActivityWSGI(HudActivityProjector(),
                              read_api=SimpleNamespace(graph_store=graph))
        response = {}
        def start(status, headers):
            response["status"] = status
        body = b"".join(app({"PATH_INFO": "/api/hud/node",
                             "REQUEST_METHOD": "GET",
                             "QUERY_STRING": "node_id=claim%3A1"}, start))
        payload = json.loads(body)
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(payload["node"]["node_id"], "claim:1")
        self.assertEqual(payload["neighbors"][0]["relation"], "supports")


if __name__ == "__main__":
    unittest.main()
