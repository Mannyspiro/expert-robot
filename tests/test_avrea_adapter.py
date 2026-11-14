import hashlib
import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.project_registry import MerlinRegistry
from merlin.avrea_adapter import AvreaAdapter


class AvreaAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = MerlinRegistry(root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.outbox = MerlinEventOutbox(root / "outbox.sqlite3")
        self.job = {"schema":"merlin-research-task/2","task_id":"t1",
                    "approval_ref":"approval:1","lease_ref":"lease:1",
                    "resource_budget":{"cpu_cores":1,"memory_bytes":1024},
                    "promotion_authority":False,"artifact_refs":[]}

    def tearDown(self):
        self.temp.cleanup()

    def adapter(self, approval=True, lease=True):
        return AvreaAdapter(
            dispatch_transport=lambda payload: {"runner_id":"avrea-runner-1",
                                                  "job_id":"job-1","status":"accepted"},
            collect_transport=lambda job_id: {"runner_id":"avrea-runner-1","job_id":job_id,
                                                "status":"completed",
                                                "artifacts":[{"name":"result.json","content":b'{"ok":true}'}]},
            approval_validator=lambda ref, payload: approval and ref=="approval:1",
            lease_validator=lambda ref, budget: lease and ref=="lease:1",
            registry=self.registry,outbox=self.outbox,
        )

    def test_dispatch_requires_approval_and_mcfc_lease(self):
        receipt = self.adapter().dispatch(self.job)
        self.assertEqual(receipt["status"],"accepted")
        self.assertGreaterEqual(self.outbox.counts()["pending"],3)
        with self.assertRaises(PermissionError):
            self.adapter(approval=False).dispatch(self.job)
        with self.assertRaises(PermissionError):
            self.adapter(lease=False).dispatch(self.job)

    def test_result_collection_registers_and_verifies_artifacts(self):
        adapter = self.adapter()
        adapter.dispatch(self.job)
        result = adapter.collect("job-1",project_id="merlin")
        self.assertEqual(result["artifacts"][0]["name"],"result.json")
        self.assertEqual(result["artifacts"][0]["artifact_ref"]["schema"],
                         "merlin-artifact-ref/1")
        self.assertEqual(result["artifacts"][0]["artifact_ref"]["version"], 1)
        self.assertEqual(result["artifacts"][0]["artifact_ref"]["sha256"],
                         result["artifacts"][0]["sha256"])
        self.assertTrue(self.registry.verify_artifact(result["artifacts"][0]["sha256"]))
        result_event_id = "evt_" + hashlib.sha256("avrea-result:job-1".encode()).hexdigest()
        result_event = self.outbox.get(result_event_id)
        self.assertIsNotNone(result_event)
        self.assertEqual(result_event["topic"], "merlin.avrea.result.collected")
        self.assertEqual(result_event["payload"]["artifacts"][0]["sha256"],
                         result["artifacts"][0]["sha256"])
        # Telemetry events are also persisted; the idempotent result event remains unique.
        before = self.outbox.counts()["pending"]
        adapter.collect("job-1", project_id="merlin")
        self.assertEqual(self.outbox.counts()["pending"], before)
        self.assertEqual(self.outbox.get(result_event_id)["payload"], result)

    def test_dispatch_pins_and_resolves_input_artifact_versions(self):
        digest = self.registry.put_artifact("merlin", "input.json", b"input")
        ref = self.registry.artifact_ref("merlin", "input.json")
        job = {**self.job, "artifact_refs": [ref]}
        receipt = self.adapter().dispatch(job)
        self.assertEqual(receipt["artifact_refs"], [ref])
        self.assertEqual(receipt["schema"], "merlin-avrea-dispatch-receipt/1")
        self.assertEqual(ref["sha256"], digest)

    def test_dispatch_rejects_malformed_or_unresolvable_artifact_reference(self):
        malformed = {**self.job, "artifact_refs": [{"schema": "bad"}]}
        with self.assertRaises(ValueError):
            self.adapter().dispatch(malformed)
        missing = {**self.job, "artifact_refs": [{
            "schema": "merlin-artifact-ref/1", "project_id": "merlin",
            "logical_path": "missing.json", "version": 1, "sha256": "d" * 64,
        }]}
        with self.assertRaises(KeyError):
            self.adapter().dispatch(missing)

    def test_missing_transport_fails_closed(self):
        adapter = AvreaAdapter(dispatch_transport=None,collect_transport=None,
            approval_validator=lambda *_:True,lease_validator=lambda *_:True,
            registry=self.registry,outbox=self.outbox)
        with self.assertRaises(RuntimeError):
            adapter.dispatch(self.job)

    def test_dispatch_transports_exact_registry_input_bytes_with_reference(self):
        digest = self.registry.put_artifact("merlin", "input.json", b'{"input":7}')
        ref = self.registry.artifact_ref("merlin", "input.json")
        captured = []
        adapter = AvreaAdapter(
            dispatch_transport=lambda payload: captured.append(payload) or {
                "runner_id": "avrea-runner-1", "job_id": "job-input", "status": "accepted"
            },
            collect_transport=None,
            approval_validator=lambda *_: True,
            lease_validator=lambda *_: True,
            registry=self.registry, outbox=self.outbox,
        )
        adapter.dispatch({**self.job, "task_id": "input-task", "artifact_refs": [ref]})
        transported = captured[0]["artifact_inputs"][0]
        import base64
        self.assertEqual(transported["artifact_ref"], ref)
        self.assertEqual(base64.b64decode(transported["content_base64"]), b'{"input":7}')
        self.assertEqual(transported["artifact_ref"]["sha256"], digest)


if __name__ == "__main__":
    unittest.main()
