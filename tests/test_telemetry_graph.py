import unittest
from merlin.telemetry_graph import build_telemetry_graph

class TelemetryGraphTests(unittest.TestCase):
    def test_multiscale_run_task_event_evidence_graph(self):
        graph = build_telemetry_graph([{
            "event_id":"e1","run_id":"r1","task_id":"t1","kind":"verification.completed",
            "source":"verifier","timestamp":"2026-11-03T10:00:00Z",
            "evidence_refs":["sha256:proof"]
        }])
        kinds = {node["kind"] for node in graph["nodes"]}
        self.assertEqual(kinds, {"run","task","event","evidence"})
        self.assertTrue(graph["source_separation_preserved"])
        self.assertEqual(len(graph["edges"]), 3)

if __name__ == "__main__":
    unittest.main()
