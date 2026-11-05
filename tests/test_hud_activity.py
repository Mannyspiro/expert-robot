import unittest

from merlin.hud_activity import HudActivityProjector, PHASES


def event(event_id, kind, payload=None, *, source="runtime", run_id="run-1", refs=()):
    return {
        "event_id": event_id, "source": source, "kind": kind,
        "run_id": run_id, "task_id": "task-1", "payload": payload or {},
        "evidence_refs": list(refs), "timestamp": "2026-11-04T12:00:00Z",
    }


class HudActivityTests(unittest.TestCase):
    def test_projects_real_stage_agent_resources_and_evidence(self):
        hud = HudActivityProjector()
        hud.ingest_many([
            event("e1", "task.started", {"summary": "Research request accepted"}),
            event("e2", "research.stage", {"stage": "experiment"}),
            event("e3", "agent.status", {"agent_id": "agent-math", "role": "mathematician",
                                         "status": "running", "activity": "evaluating model"}),
            event("e4", "resource.sample", {"cpu_cores_reserved": 2, "memory_bytes_reserved": 4096}),
            event("e5", "proof.checked", {"status": "pending"}, refs=("artifact:proof-candidate",)),
        ])
        view = hud.snapshot()
        self.assertEqual(view["phase"], "formalization")
        self.assertEqual(view["agents"][0]["agent_id"], "agent-math")
        self.assertEqual(view["resources"]["cpu_cores_reserved"], 2)
        self.assertEqual(view["evidence_refs"], ["artifact:proof-candidate"])
        self.assertTrue(view["visualization_policy"]["private_reasoning_is_not_exposed"])

    def test_duplicate_event_is_idempotent(self):
        hud = HudActivityProjector()
        item = event("same", "task.started")
        self.assertTrue(hud.ingest(item))
        self.assertFalse(hud.ingest(item))
        self.assertEqual(hud.snapshot()["event_count"], 1)

    def test_run_filter_and_bounded_history(self):
        hud = HudActivityProjector(max_events=2)
        hud.ingest(event("a", "task.started", run_id="one"))
        hud.ingest(event("b", "task.progress", run_id="two"))
        hud.ingest(event("c", "task.completed", run_id="two"))
        self.assertEqual(hud.snapshot(run_id="one")["event_count"], 0)
        self.assertEqual(hud.snapshot(run_id="two")["event_count"], 2)
        self.assertEqual(hud.snapshot()["event_count"], 2)

    def test_invalid_event_rejected(self):
        hud = HudActivityProjector()
        with self.assertRaises(ValueError):
            hud.ingest(event("bad", "not-a-real-event"))
        self.assertEqual(hud.snapshot()["event_count"], 0)


if __name__ == "__main__":
    unittest.main()
