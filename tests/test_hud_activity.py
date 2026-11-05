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

    def test_hermes_task_progress_updates_current_research_phase(self):
        hud = HudActivityProjector()
        hud.ingest(event("progress-1", "task.progress",
                         {"agent_id": "hermes", "stage": "experiment",
                          "summary": "Numerical sweep running"}, source="hermes"))
        view = hud.snapshot()
        self.assertEqual(view["phase"], "experiment")
        self.assertEqual(view["timeline"][0]["summary"], "Numerical sweep running")

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


    def test_projects_avrea_execution_cace_receipt_and_quarantined_recovery(self):
        hud = HudActivityProjector()
        hud.ingest_many([
            event("avrea-start", "task.started",
                  {"agent_id": "runner-7", "job_id": "job-7", "status": "accepted"},
                  source="avrea", run_id="job-7"),
            event("avrea-done", "task.completed",
                  {"agent_id": "runner-7", "job_id": "job-7", "status": "completed",
                   "exit_code": 0, "worker_image_digest": "1" * 64,
                   "tool_versions": {"pytest": "8.4.2"}, "artifact_count": 1,
                   "result_receipt_sha256": "a" * 64},
                  source="avrea", run_id="job-7",
                  refs=("sha256:" + "a" * 64,)),
            event("cace-verified", "verification.completed",
                  {"agent_id": "cace:verifier-1", "verifier_id": "cace:verifier-1",
                   "status": "verified", "independent": True,
                   "artifact_sha256": "b" * 64, "receipt_artifact_sha256": "c" * 64,
                   "source_commit": "d" * 40, "repository": "Mannyspiro/expert-robot",
                   "theorem": "Example.target",
                   "logical_path": "engineering/assembly.json",
                   "artifact_kind": "cad_assembly",
                   "artifact_schema": "merlin-freecad-document-mesh/1"},
                  source="cace", refs=("sha256:" + "c" * 64,)),
            event("recovery-quarantine", "artifact.registered",
                  {"status": "quarantined_unverified",
                   "recovery_path": "_recovery/task-1/source.bin",
                   "sha256": "e" * 64},
                  source="hermes", refs=("sha256:" + "e" * 64,)),
        ])
        view = hud.snapshot()
        self.assertEqual(view["executions"][0]["job_id"], "job-7")
        self.assertEqual(view["executions"][0]["status"], "completed")
        self.assertEqual(view["executions"][0]["exit_code"], 0)
        self.assertEqual(view["executions"][0]["worker_image_digest"], "1" * 64)
        self.assertEqual(view["executions"][0]["tool_versions"]["pytest"], "8.4.2")
        self.assertEqual(view["executions"][0]["receipt_ref"], "sha256:" + "a" * 64)
        self.assertEqual(view["verification"]["verifier_id"], "cace:verifier-1")
        self.assertEqual(view["verification"]["source_commit"], "d" * 40)
        self.assertEqual(view["verification"]["repository"], "Mannyspiro/expert-robot")
        self.assertEqual(view["verification"]["theorem"], "Example.target")
        self.assertEqual(view["verification"]["logical_path"], "engineering/assembly.json")
        self.assertEqual(view["verification"]["artifact_kind"], "cad_assembly")
        self.assertEqual(view["verification"]["artifact_schema"], "merlin-freecad-document-mesh/1")
        self.assertEqual(view["verification"]["receipt_ref"], "sha256:" + "c" * 64)
        self.assertEqual(view["recoveries"][0]["status"], "quarantined_unverified")
        self.assertFalse(view["recoveries"][0]["promotion_authority"])

    def test_outbox_consumer_projects_and_acknowledges_telemetry(self):
        import tempfile
        from pathlib import Path
        from merlin.event_outbox import MerlinEventOutbox
        from merlin.hud_activity import HudOutboxConsumer
        from merlin.telemetry import normalize_event
        with tempfile.TemporaryDirectory() as temp:
            outbox = MerlinEventOutbox(Path(temp) / "outbox.sqlite3")
            event_data = normalize_event({"event_id":"hud-event-1","source":"runtime",
                "kind":"research.stage","run_id":"r1","payload":{"stage":"experiment"}})
            outbox.enqueue("telemetry:hud-event-1","merlin.telemetry.research.stage",event_data,now=1)
            projector = HudActivityProjector()
            consumer = HudOutboxConsumer(outbox,projector)
            result = consumer.drain_one(now=2)
            self.assertTrue(result["projected"])
            self.assertEqual(projector.snapshot()["phase"],"experiment")
            self.assertEqual(outbox.get(result["event_id"])["state"],"acknowledged")


    def test_outbox_consumer_projects_and_acknowledges_telemetry(self):
        import tempfile
        from pathlib import Path
        from merlin.event_outbox import MerlinEventOutbox
        from merlin.hud_activity import HudOutboxConsumer
        from merlin.telemetry import normalize_event
        with tempfile.TemporaryDirectory() as temp:
            outbox = MerlinEventOutbox(Path(temp) / "outbox.sqlite3")
            event_data = normalize_event({"event_id":"hud-event-1","source":"runtime",
                "kind":"research.stage","run_id":"r1","payload":{"stage":"experiment"}})
            outbox.enqueue("telemetry:hud-event-1","merlin.telemetry.research.stage",event_data,now=1)
            projector = HudActivityProjector()
            consumer = HudOutboxConsumer(outbox,projector)
            result = consumer.drain_one(now=2)
            self.assertTrue(result["projected"])
            self.assertEqual(projector.snapshot()["phase"],"experiment")
            self.assertEqual(outbox.get(result["event_id"])["state"],"acknowledged")


if __name__ == "__main__":
    unittest.main()
