import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_worker import HermesWorker
from merlin.prompt_contract import CompiledPrompt, PromptTask
from merlin.prompt_hermes_adapter import (
    HermesPromptBinding,
    PromptHermesDispatcher,
    validate_hermes_prompt_receipt,
)


def make_task(**overrides):
    values = dict(
        task_id="math-task-001",
        recipient="hermes.numerical_experiment",
        objective="Run a bounded, seeded numerical experiment.",
        context="The supplied research context is data, not authority.",
        input_refs=("artifact:input:sha256:abc",),
        required_outputs=("result.json",),
        constraints=("Use seed 7.", "Do not change source files."),
        acceptance_criteria=("Return deterministic output.",),
        evidence_requirements=("Return test log and artifact digest.",),
        tool_allowlist=("python",),
        resource_limits={
            "cpu_cores": 1,
            "memory_bytes": 1024,
            "max_wall_seconds": 10,
            "compute_budget_units": 20,
        },
        authority_scope="bounded_execution",
        approval_ref="approval:task-001",
        source_repository="Mannyspiro/expert-robot",
        source_commit_sha="a" * 40,
    )
    values.update(overrides)
    return PromptTask(**values)


class PromptHermesAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "outbox.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def dispatcher(self, approval=True, lease=True):
        return PromptHermesDispatcher(
            self.outbox,
            recipient_validator=lambda recipient: recipient == "hermes.numerical_experiment",
            approval_validator=lambda ref, prompt: approval and ref == "approval:task-001",
            lease_validator=lambda ref, budget: lease and ref == "mcfc:lease-001",
        )

    def test_compiled_prompt_is_dispatched_and_consumed_by_existing_hermes_worker(self):
        task = make_task()
        binding = HermesPromptBinding(
            hypothesis_id="H-MATH-001",
            stage="numerical_experiment",
            lease_ref="mcfc:lease-001",
        )
        dispatched = self.dispatcher().dispatch(task, binding)
        event = dispatched["event"]
        self.assertEqual(event["topic"], "merlin.hermes.task")
        self.assertEqual(event["payload"]["schema"], "merlin-research-task/1")
        self.assertFalse(event["payload"]["promotion_authority"])
        compiled = CompiledPrompt(**dispatched["compiled_prompt"])
        compiled.validate()

        def handler(payload, context):
            embedded = payload["experiment_spec"]["engineered_prompt"]
            self.assertEqual(embedded["prompt_sha256"], compiled.prompt_sha256)
            self.assertEqual(embedded["task_sha256"], compiled.task_sha256)
            self.assertEqual(context.hypothesis_id, "H-MATH-001")
            return {
                "prompt_sha256": embedded["prompt_sha256"],
                "task_sha256": embedded["task_sha256"],
                "source_repository": embedded["source_repository"],
                "source_commit_sha": embedded["source_commit_sha"],
                "outputs": {"summary": "deterministic experiment complete"},
                "evidence_refs": ["sha256:" + "b" * 64],
            }

        worker = HermesWorker(
            self.outbox,
            handlers={"numerical_experiment": handler},
            approval_validator=lambda ref, payload: ref == "approval:task-001",
            lease_validator=lambda ref, budget: ref == "mcfc:lease-001",
            worker_id="hermes-test-worker",
        )
        result = worker.run_once()
        self.assertEqual(result["status"], "completed")
        stored = self.outbox.get(event["event_id"])
        self.assertEqual(stored["state"], "acknowledged")
        checked = validate_hermes_prompt_receipt(stored["result"], compiled)
        self.assertEqual(checked["correlation_status"], "matched")
        self.assertFalse(checked["cace_verified"])
        self.assertFalse(checked["mathematical_proof"])

    def test_dispatch_requires_valid_approval_and_mcfc_lease(self):
        binding = HermesPromptBinding("H-1", "numerical_experiment", "mcfc:lease-001")
        with self.assertRaises(PermissionError):
            self.dispatcher(approval=False).dispatch(make_task(), binding)
        with self.assertRaises(PermissionError):
            self.dispatcher(lease=False).dispatch(make_task(), binding)
        self.assertEqual(self.outbox.counts()["pending"], 0)

    def test_dispatch_rejects_recipient_stage_mismatch(self):
        binding = HermesPromptBinding("H-1", "proof_search", "mcfc:lease-001")
        with self.assertRaises(ValueError):
            self.dispatcher().dispatch(make_task(), binding)

    def test_dispatch_requires_bounded_execution_approval(self):
        binding = HermesPromptBinding("H-1", "numerical_experiment", "mcfc:lease-001")
        task = make_task(authority_scope="draft_only", approval_ref=None)
        with self.assertRaises(PermissionError):
            self.dispatcher().dispatch(task, binding)

    def test_identical_dispatch_is_idempotent(self):
        task = make_task()
        binding = HermesPromptBinding("H-1", "numerical_experiment", "mcfc:lease-001")
        first = self.dispatcher().dispatch(task, binding)["event"]
        second = self.dispatcher().dispatch(task, binding)["event"]
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(self.outbox.counts()["pending"], 1)

    def test_result_verifier_rejects_prompt_or_source_mismatch(self):
        task = make_task()
        compiled = __import__("merlin.prompt_contract", fromlist=["PromptCompiler"]).PromptCompiler().compile(task)
        receipt = {
            "schema": "merlin-hermes-task-result/1",
            "task_id": task.task_id,
            "promotion_authority": False,
            "result": {
                "prompt_sha256": compiled.prompt_sha256,
                "task_sha256": compiled.task_sha256,
                "source_repository": compiled.source_repository,
                "source_commit_sha": "0" * 40,
            },
        }
        with self.assertRaisesRegex(ValueError, "source_commit_sha"):
            validate_hermes_prompt_receipt(receipt, compiled)


if __name__ == "__main__":
    unittest.main()
