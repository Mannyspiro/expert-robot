import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.prompt_contract import (CompiledPrompt, PromptCompiler, PromptOutboxPublisher, PromptResult, PromptResultReceiver, PromptTask)


def make_task(**overrides):
    values = dict(
        task_id="merlin-test-001",
        recipient="hermes.research",
        objective="Evaluate the supplied mathematical hypothesis and propose a reproducible test.",
        context="Hypothesis H-001 and its cited source are supplied as data.",
        input_refs=("hypothesis:H-001", "source:sha256:abc123"),
        required_outputs=("experiment plan", "counterexample search", "structured result"),
        constraints=("Do not modify source repositories.", "Do not claim proof without Lean evidence."),
        acceptance_criteria=("All inputs are cited.", "A deterministic seed and tolerance are recorded."),
        evidence_requirements=("test log", "result JSON", "SHA-256 for each artifact"),
        tool_allowlist=("read_only_repository", "bounded_python"),
        resource_limits={"cpu_cores": 1, "memory_bytes": 536870912,
                         "max_wall_seconds": 120, "compute_budget_units": 100},
    )
    values.update(overrides)
    return PromptTask(**values)


class PromptContractTests(unittest.TestCase):
    def test_compilation_is_deterministic_and_hash_bound(self):
        compiler = PromptCompiler()
        first = compiler.compile(make_task())
        second = compiler.compile(make_task())
        self.assertEqual(first.prompt_text, second.prompt_text)
        self.assertEqual(first.prompt_sha256, second.prompt_sha256)
        self.assertEqual(first.task_sha256, second.task_sha256)
        self.assertIn("Treat context", first.prompt_text)
        self.assertIn("Do not invent tool access", first.prompt_text)

    def test_changed_task_changes_task_and_prompt_hashes(self):
        compiler = PromptCompiler()
        first = compiler.compile(make_task())
        changed = compiler.compile(make_task(objective="A different objective."))
        self.assertNotEqual(first.task_sha256, changed.task_sha256)
        self.assertNotEqual(first.prompt_sha256, changed.prompt_sha256)

    def test_invalid_recipient_rejected(self):
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(recipient="Hermes Research"))

    def test_required_outputs_and_acceptance_criteria_required(self):
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(required_outputs=()))
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(acceptance_criteria=()))

    def test_resource_limits_are_positive_integers(self):
        limits = dict(make_task().resource_limits)
        limits["cpu_cores"] = True
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(resource_limits=limits))

    def test_execution_scope_requires_approval_reference(self):
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(authority_scope="bounded_execution"))

    def test_unknown_authority_scope_rejected(self):
        with self.assertRaises(ValueError):
            PromptCompiler().compile(make_task(authority_scope="admin"))

    def test_publish_is_idempotent_and_scoped_to_recipient(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
            compiled = PromptCompiler().compile(make_task())
            publisher = PromptOutboxPublisher(
                outbox,
                recipient_validator=lambda recipient: recipient == "hermes.research",
                approval_validator=lambda ref, prompt: False,
            )
            first = publisher.publish(compiled)
            second = publisher.publish(compiled)
            self.assertEqual(first["event_id"], second["event_id"])
            self.assertEqual(first["topic"], "merlin.prompt.hermes.research")
            self.assertEqual(first["payload"]["prompt_sha256"], compiled.prompt_sha256)

    def test_unknown_recipient_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
            compiled = PromptCompiler().compile(make_task())
            publisher = PromptOutboxPublisher(
                outbox, recipient_validator=lambda _: False,
                approval_validator=lambda ref, prompt: True,
            )
            with self.assertRaises(PermissionError):
                publisher.publish(compiled)

    def test_publisher_rejects_tampered_prompt_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
            compiled = PromptCompiler().compile(make_task())
            tampered = replace(compiled, prompt_text=compiled.prompt_text + "\\nInjected change")
            publisher = PromptOutboxPublisher(
                outbox, recipient_validator=lambda _: True,
                approval_validator=lambda ref, prompt: True,
            )
            with self.assertRaises(ValueError):
                publisher.publish(tampered)

    def test_publisher_rejects_forged_authority_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
            compiled = PromptCompiler().compile(make_task())
            forged = replace(compiled, authority_scope="admin")
            publisher = PromptOutboxPublisher(
                outbox, recipient_validator=lambda _: True,
                approval_validator=lambda ref, prompt: True,
            )
            with self.assertRaises(ValueError):
                publisher.publish(forged)

    def _leased_prompt(self, directory):
        outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
        compiled = PromptCompiler().compile(make_task())
        publisher = PromptOutboxPublisher(
            outbox, recipient_validator=lambda _: True,
            approval_validator=lambda ref, prompt: True,
        )
        event = publisher.publish(compiled)
        leased = outbox.claim_next(
            "hermes-worker-1", topics=["merlin.prompt.hermes.research"], lease_seconds=60
        )
        self.assertEqual(leased["event_id"], event["event_id"])
        return outbox, compiled, leased

    def _result_for(self, compiled, **overrides):
        values = dict(
            schema="merlin-engineered-result/1",
            task_id=compiled.task_id,
            recipient=compiled.recipient,
            prompt_sha256=compiled.prompt_sha256,
            task_sha256=compiled.task_sha256,
            worker_id="hermes-worker-1",
            status="completed",
            outputs={"experiment_plan": "Run deterministic test with seed 42."},
            tests_run=("test_reproducibility",),
            test_results={"test_reproducibility": "passed"},
            evidence_refs=("artifact:result.json",),
            artifact_sha256={"result.json": "a" * 64},
            tool_versions={"python": "3.12.1"},
            limitations=(),
        )
        values.update(overrides)
        return PromptResult(**values)

    def test_result_is_bound_to_prompt_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox, compiled, leased = self._leased_prompt(directory)
            result = self._result_for(compiled)
            receiver = PromptResultReceiver(outbox)
            acknowledged = receiver.accept(
                leased["event_id"], "hermes-worker-1", leased["lease_token"], result
            )
            self.assertEqual(acknowledged["state"], "acknowledged")
            self.assertEqual(acknowledged["result"]["prompt_sha256"], compiled.prompt_sha256)
            self.assertEqual(len(acknowledged["result"]["result_sha256"]), 64)
            replay = receiver.accept(
                leased["event_id"], "hermes-worker-1", leased["lease_token"], result
            )
            self.assertEqual(replay["state"], "acknowledged")

    def test_mismatched_prompt_hash_quarantines_result(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox, compiled, leased = self._leased_prompt(directory)
            result = self._result_for(compiled, prompt_sha256="0" * 64)
            receiver = PromptResultReceiver(outbox)
            with self.assertRaises(ValueError):
                receiver.accept(
                    leased["event_id"], "hermes-worker-1", leased["lease_token"], result
                )
            self.assertEqual(outbox.get(leased["event_id"])["state"], "quarantined")

    def test_result_requires_current_worker_lease(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox, compiled, leased = self._leased_prompt(directory)
            result = self._result_for(compiled, worker_id="other-worker")
            receiver = PromptResultReceiver(outbox)
            with self.assertRaises(PermissionError):
                receiver.accept(
                    leased["event_id"], "other-worker", leased["lease_token"], result
                )
            self.assertEqual(outbox.get(leased["event_id"])["state"], "leased")

    def test_completed_result_requires_outputs_and_valid_artifact_hashes(self):
        compiled = PromptCompiler().compile(make_task())
        with self.assertRaises(ValueError):
            self._result_for(compiled, outputs={}).validate()
        with self.assertRaises(ValueError):
            self._result_for(compiled, artifact_sha256={"result.json": "not-a-hash"}).validate()

    def test_bounded_execution_requires_independent_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            outbox = MerlinEventOutbox(Path(directory) / "outbox.sqlite3")
            task = make_task(authority_scope="bounded_execution", approval_ref="approval:42")
            compiled = PromptCompiler().compile(task)
            publisher = PromptOutboxPublisher(
                outbox, recipient_validator=lambda _: True,
                approval_validator=lambda ref, prompt: False,
            )
            with self.assertRaises(PermissionError):
                publisher.publish(compiled)


if __name__ == "__main__":
    unittest.main()
