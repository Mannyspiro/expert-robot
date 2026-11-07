import unittest

from python.merlin.capability_registry import capability_snapshot, validate_graph


class CapabilityRegistryTests(unittest.TestCase):
    def test_legacy_capabilities_are_normalized_to_three_states(self):
        rows = [
            {"id": "geometry", "status": "AVAILABLE", "evidence": "unit-tested"},
            {"id": "council", "status": "QUALIFICATION_GATED"},
            {"id": "provider", "status": "CONFIGURED_AT_RUNTIME"},
            {"id": "outbox", "status": "AVAILABLE_WITH_OUTBOX"},
            {"id": "media", "status": "NOT_CONFIGURED"},
        ]
        snapshot = capability_snapshot(rows, outbox_configured=False)
        states = {item["id"]: item["state"] for item in snapshot["capabilities"]}
        self.assertEqual(states, {
            "geometry": "configured", "council": "unqualified",
            "provider": "unqualified", "outbox": "unavailable",
            "media": "unavailable",
        })
        self.assertEqual(set(snapshot["states"]), {"configured", "unavailable", "unqualified"})
        legacy_status = {item["id"]: item["status"] for item in snapshot["capabilities"]}
        self.assertEqual(legacy_status, {
            "geometry": "AVAILABLE", "council": "QUALIFICATION_GATED",
            "provider": "QUALIFICATION_GATED", "outbox": "UNAVAILABLE",
            "media": "UNAVAILABLE",
        })
        self.assertEqual(len(snapshot["registry_sha256"]), 64)

    def test_runtime_provider_status_is_not_promoted_without_qualification(self):
        rows = [
            {"id": "model.remote_openai_compatible", "status": "CONFIGURED_AT_RUNTIME"},
            {"id": "model.nouscoder", "status": "NOT_QUALIFIED"},
            {"id": "voice.kokoro", "status": "OPTIONAL_LOCAL_SERVICE"},
        ]
        runtime = {"providers": {
            "cloud": {"status": "UNAVAILABLE"},
            "local": {"status": "UNAVAILABLE"},
            "speech_output": {"status": "UNAVAILABLE"},
        }}
        states = {x["id"]: x["state"] for x in capability_snapshot(rows, runtime)["capabilities"]}
        self.assertEqual(states["model.remote_openai_compatible"], "unavailable")
        self.assertEqual(states["model.nouscoder"], "unqualified")
        self.assertEqual(states["voice.kokoro"], "unavailable")

    def test_valid_graph_returns_stable_topological_order_and_digest(self):
        result = validate_graph({
            "nodes": [{"id": "foundations"}, {"id": "algebra"}, {"id": "geometry"}],
            "edges": [
                {"source": "foundations", "target": "algebra", "relation": "prerequisite"},
                {"source": "algebra", "target": "geometry", "relation": "requires"},
                {"source": "foundations", "target": "geometry", "relation": "related"},
            ],
        })
        self.assertTrue(result["valid"])
        self.assertEqual(result["topological_order"], ["foundations", "algebra", "geometry"])
        self.assertEqual(len(result["graph_sha256"]), 64)

    def test_graph_rejects_duplicate_ids_dangling_edges_and_cycles(self):
        duplicate = validate_graph({"nodes": [{"id": "a"}, {"id": "a"}], "edges": []})
        self.assertFalse(duplicate["valid"])
        self.assertIn("duplicate_node_id", {e["code"] for e in duplicate["errors"]})

        dangling = validate_graph({"nodes": [{"id": "a"}],
                                   "edges": [{"source": "a", "target": "missing"}]})
        self.assertIn("dangling_edge", {e["code"] for e in dangling["errors"]})

        cycle = validate_graph({"nodes": [{"id": "a"}, {"id": "b"}],
                                "edges": [
                                    {"source": "a", "target": "b", "relation": "requires"},
                                    {"source": "b", "target": "a", "relation": "requires"},
                                ]})
        self.assertIn("dependency_cycle", {e["code"] for e in cycle["errors"]})

    def test_graph_rejects_unhashable_edge_endpoints_without_crashing(self):
        result = validate_graph({
            "nodes": [{"id": "a"}],
            "edges": [{"source": ["a"], "target": {"id": "a"}, "relation": "requires"}],
        })
        self.assertFalse(result["valid"])
        self.assertIn("dangling_edge", {e["code"] for e in result["errors"]})

    def test_graph_size_limits_are_enforced(self):
        with self.assertRaisesRegex(ValueError, "size limits"):
            validate_graph({"nodes": [{"id": "a"}, {"id": "b"}], "edges": []},
                           max_nodes=1)


if __name__ == "__main__":
    unittest.main()
