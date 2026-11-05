import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.prompt_engineering import (
    PromptCompiler, PromptDispatchCoordinator, PromptRequest,
)


def request(prompt_id="prompt-001", target="hermes"):
    return PromptRequest(
        prompt_id=prompt_id,
        objective="Investigate a bounded spectral identity",
        target_system=target,
        task_type="symbolic_research",
        context="A candidate identity is recorded in the hypothesis ledger.",
        inputs={"hypothesis_id": "H-1", "seed": 42},
        instructions=(
            "Restate the claim and identify its assumptions.",
            "Derive a symbolic check and provide reproducible evidence.",
            "Separate verified results from conjectures.",
        ),
        output_contract={
            "type": "object",
            "required": ["status", "assumptions", "artifact_sha256"],
        },
        constraints=("No network access unless separately authorized.", "Do not alter canonical artifacts."),
        success_criteria=("All assumptions are explicit.", "Output conforms to the declared object contract."),
        resource_budget={"cpu_cores": 1, "memory_bytes": 1048576, "max_wall_seconds": 30},
        source_refs=("hypothesis:H-1",),
    )


class PromptEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / "outbox.sqlite3")
        self.compiler = PromptCompiler()

    def tearDown(self):
        self.temp.cleanup()

    def coordinator(self, approval=True, lease=True, targets=None):
        return PromptDispatchCoordinator(
            self.outbox,
            allowed_targets=targets or {"hermes", "lean", "cace"},
            approval_validator=lambda ref, prompt: approval and ref == "approval:1",
            lease_validator=lambda ref, budget: lease and ref == "lease:1",
        )

    def test_compilation_is_deterministic_and_digest_bound(self):
        compiled = self.compiler.compile(request())
        again = self.compiler.compile(request())
        self.assertEqual(compiled.prompt_text, again.prompt_text)
        self.assertEqual(compiled.prompt_sha256, again.prompt_sha256)
        expected = hashlib.sha256(json.dumps(
            {"manifest": dict(compiled.manifest), "prompt_text": compiled.prompt_text},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode()).hexdigest()
        self.assertEqual(compiled.prompt_sha256, expected)
        self.assertFalse(compiled.promotion_authority)

    def test_invalid_or_authority_expanding_request_rejected(self):
        with self.assertRaises(ValueError):
            self.compiler.compile(PromptRequest(**{**request().__dict__, "authority": "admin"}))
        with self.assertRaises(ValueError):
            self.compiler.compile(PromptRequest(**{**request().__dict__, "instructions": ()}))

    def test_dispatch_requires_approval_and_active_lease(self):
        prompt = self.compiler.compile(request())
        with self.assertRaises(PermissionError):
            self.coordinator(approval=False).publish(
                prompt, approval_ref="approval:1", lease_ref="lease:1",
                resource_budget=dict(request().resource_budget),
            )
        with self.assertRaises(PermissionError):
            self.coordinator(lease=False).publish(
                prompt, approval_ref="approval:1", lease_ref="lease:1",
                resource_budget=dict(request().resource_budget),
            )

    def test_target_allowlist_blocks_unregistered_subsystem(self):
        prompt = self.compiler.compile(request(target="unknown-agent"))
        with self.assertRaises(PermissionError):
            self.coordinator().publish(
                prompt, approval_ref="approval:1", lease_ref="lease:1",
                resource_budget=dict(request().resource_budget),
            )

    def test_publish_is_durable_idempotent_and_non_promoting(self):
        prompt = self.compiler.compile(request())
        coordinator = self.coordinator()
        kwargs = dict(
            approval_ref="approval:1", lease_ref="lease:1",
            resource_budget=dict(request().resource_budget), channel="self",
        )
        first = coordinator.publish(prompt, **kwargs)
        second = coordinator.publish(prompt, **kwargs)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["payload"]["channel"], "self")
        self.assertEqual(first["payload"]["prompt_sha256"], prompt.prompt_sha256)
        self.assertFalse(first["payload"]["promotion_authority"])
        self.assertEqual(self.outbox.counts()["pending"], 1)

    def test_prompt_id_reuse_with_different_content_is_not_silently_accepted(self):
        coordinator = self.coordinator()
        budget = dict(request().resource_budget)
        first = self.compiler.compile(request())
        second_request = PromptRequest(**{**request().__dict__, "objective": "Different objective"})
        second = self.compiler.compile(second_request)
        first_event = coordinator.publish(first, approval_ref="approval:1", lease_ref="lease:1", resource_budget=budget)
        # Different digest is a new immutable prompt version, never an overwrite.
        second_event = coordinator.publish(second, approval_ref="approval:1", lease_ref="lease:1", resource_budget=budget)
        self.assertNotEqual(first.prompt_sha256, second.prompt_sha256)
        self.assertNotEqual(first_event["event_id"], second_event["event_id"])
        self.assertEqual(self.outbox.counts()["pending"], 2)

