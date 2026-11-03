import unittest
from merlin.telemetry import normalize_event, telemetry_view

class TelemetryTests(unittest.TestCase):
    def test_normalizes_source_labeled_event(self):
        event = normalize_event({"source":"runtime","kind":"task.progress","run_id":"r1",
            "task_id":"t1","payload":{"step":2},"cpu_percent":12.5,
            "memory_bytes":1024,"evidence_refs":["sha256:abc"]})
        self.assertEqual(event["schema"], "merlin-telemetry/1")
        self.assertEqual(event["source"], "runtime")
        self.assertEqual(event["memory_bytes"], 1024)

    def test_rejects_source_confusion_and_bad_metrics(self):
        with self.assertRaises(ValueError):
            normalize_event({"source":"simulation_and_runtime","kind":"task.progress","run_id":"r"})
        with self.assertRaises(ValueError):
            normalize_event({"source":"runtime","kind":"resource.sample","run_id":"r","cpu_percent":120})

    def test_view_keeps_sources_separate(self):
        events = [normalize_event({"source":s,"kind":"task.progress","run_id":"r"})
                  for s in ("simulation","runtime")]
        view = telemetry_view(events)
        self.assertEqual(view["source_counts"]["simulation"], 1)
        self.assertEqual(view["source_counts"]["runtime"], 1)
        self.assertTrue(view["simulation_is_not_runtime"])

if __name__ == "__main__":
    unittest.main()
