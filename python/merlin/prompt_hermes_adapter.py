"""Bridge deterministic engineered prompts into the existing Hermes worker queue.

This module translates a compiled PromptTask into the existing
merlin-research-task/1 envelope. It does not execute handlers or grant
hypothesis-promotion authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from merlin.event_outbox import MerlinEventOutbox
from merlin.prompt_contract import CompiledPrompt, PromptCompiler, PromptTask

HERMES_RECIPIENT_STAGES = {
    "hermes.research": "research",
    "hermes.numerical_experiment": "numerical_experiment",
    "hermes.proof_search": "proof_search",
    "hermes.electrical_analysis": "electrical_analysis",
}


@dataclass(frozen=True)
class HermesPromptBinding:
    hypothesis_id: str
    stage: str
    lease_ref: str

    def validate(self) -> None:
        for name, value in (
            ("hypothesis_id", self.hypothesis_id),
            ("stage", self.stage),
            ("lease_ref", self.lease_ref),
        ):
            if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                raise ValueError(f"{name} must be a non-empty bounded string")


class PromptHermesDispatcher:
    """Compile, admit and enqueue one prompt as a bounded Hermes research task."""

    def __init__(
        self,
        outbox: MerlinEventOutbox,
        *,
        recipient_validator: Callable[[str], bool],
        approval_validator: Callable[[str, CompiledPrompt], bool],
        lease_validator: Callable[[str, Mapping[str, int]], bool],
        compiler: PromptCompiler | None = None,
    ):
        if not isinstance(outbox, MerlinEventOutbox):
            raise ValueError("outbox must be a MerlinEventOutbox")
        if not all(callable(fn) for fn in (recipient_validator, approval_validator, lease_validator)):
            raise ValueError("recipient, approval and MCFC lease validators are required")
        self.outbox = outbox
        self.recipient_validator = recipient_validator
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.compiler = compiler or PromptCompiler()

    def dispatch(self, task: PromptTask, binding: HermesPromptBinding) -> dict[str, Any]:
        if not isinstance(task, PromptTask):
            raise TypeError("task must be a PromptTask")
        if not isinstance(binding, HermesPromptBinding):
            raise TypeError("binding must be a HermesPromptBinding")
        binding.validate()
        compiled = self.compiler.compile(task)
        if len(task.objective) > 2000:
            raise ValueError("Hermes task objective must not exceed the worker envelope limit of 2000 characters")
        expected_stage = HERMES_RECIPIENT_STAGES.get(task.recipient)
        if expected_stage is None or expected_stage != binding.stage:
            raise ValueError("recipient does not map to the declared Hermes stage")
        if task.authority_scope != "bounded_execution" or not task.approval_ref:
            raise PermissionError("Hermes dispatch requires bounded_execution and explicit approval")
        if not self.recipient_validator(task.recipient):
            raise PermissionError("Hermes recipient is not registered and enabled")
        if not self.approval_validator(task.approval_ref, compiled):
            raise PermissionError("operator approval is not valid for this compiled prompt")
        if not self.lease_validator(binding.lease_ref, task.resource_limits):
            raise PermissionError("MCFC resource lease is not valid for this task")

        payload = {
            "schema": "merlin-research-task/1",
            "task_id": task.task_id,
            "hypothesis_id": binding.hypothesis_id,
            "objective": task.objective,
            "stage": binding.stage,
            "resource_budget": dict(task.resource_limits),
            "approval_ref": task.approval_ref,
            "lease_ref": binding.lease_ref,
            "evidence_refs": list(task.input_refs),
            "experiment_spec": {
                "engineered_prompt": compiled.to_payload(),
                "required_outputs": list(task.required_outputs),
                "constraints": list(task.constraints),
                "acceptance_criteria": list(task.acceptance_criteria),
                "evidence_requirements": list(task.evidence_requirements),
                "tool_allowlist": list(task.tool_allowlist),
            },
            "authority": "bounded_execution_only",
            "promotion_authority": False,
        }
        key = f"engineered-hermes-prompt:{task.task_id}:{compiled.prompt_sha256}"
        event = self.outbox.enqueue(
            idempotency_key=key,
            topic="merlin.hermes.task",
            payload=payload,
        )
        return {
            "event": event,
            "compiled_prompt": compiled.to_payload(),
            "dispatch_status": "queued",
            "promotion_authority": False,
        }


def validate_hermes_prompt_receipt(
    receipt: Mapping[str, Any], compiled_prompt: CompiledPrompt
) -> dict[str, Any]:
    """Check that an acknowledged Hermes result retains the exact prompt binding.

    This is correlation validation, not CACE verification, a Lean proof, or
    evidence that a handler ran correctly.
    """
    if not isinstance(receipt, Mapping) or receipt.get("schema") != "merlin-hermes-task-result/1":
        raise ValueError("unsupported Hermes result receipt")
    if not isinstance(compiled_prompt, CompiledPrompt):
        raise TypeError("compiled_prompt must be a CompiledPrompt")
    compiled_prompt.validate()
    if receipt.get("task_id") != compiled_prompt.task_id:
        raise ValueError("Hermes receipt task_id does not match prompt")
    if receipt.get("promotion_authority") is not False:
        raise PermissionError("Hermes receipt cannot carry promotion authority")
    result = receipt.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("Hermes receipt must contain a result object")
    for field, expected in (
        ("prompt_sha256", compiled_prompt.prompt_sha256),
        ("task_sha256", compiled_prompt.task_sha256),
        ("source_repository", compiled_prompt.source_repository),
        ("source_commit_sha", compiled_prompt.source_commit_sha),
    ):
        if result.get(field) != expected:
            raise ValueError(f"Hermes result {field} does not match compiled prompt")
    return {
        "correlation_status": "matched",
        "task_id": compiled_prompt.task_id,
        "prompt_sha256": compiled_prompt.prompt_sha256,
        "task_sha256": compiled_prompt.task_sha256,
        "source_repository": compiled_prompt.source_repository,
        "source_commit_sha": compiled_prompt.source_commit_sha,
        "promotion_authority": False,
        "cace_verified": False,
        "mathematical_proof": False,
    }


__all__ = [
    "HermesPromptBinding",
    "PromptHermesDispatcher",
    "validate_hermes_prompt_receipt",
    "HERMES_RECIPIENT_STAGES",
]
