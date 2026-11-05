"""Explicit composition root for the engineered-prompt -> Hermes -> evidence loop.

All external authority checks, research/proof executors and CACE transport are
injected. This module does not start a process or invent a solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_stage_handlers import build_merlin_hermes_handlers
from merlin.hermes_worker import HermesWorker
from merlin.prompt_contract import PromptTask
from merlin.prompt_hermes_adapter import (
    HermesPromptBinding,
    PromptHermesDispatcher,
)
from merlin.prompt_contract import CompiledPrompt
from merlin.research_evidence import ResearchEvidenceRecorder


@dataclass
class MerlinHermesRuntime:
    """In-process runtime composed from canonical stores and qualified adapters."""

    outbox: MerlinEventOutbox
    worker: HermesWorker
    dispatcher: PromptHermesDispatcher
    stage_handlers: Mapping[str, Callable[..., Mapping[str, Any]]]

    def dispatch_prompt(self, task: PromptTask, binding: HermesPromptBinding) -> dict[str, Any]:
        return self.dispatcher.dispatch(task, binding)

    def run_once(self) -> dict[str, Any] | None:
        return self.worker.run_once()

    def run_forever(self, stop_event: Any, *, idle_seconds: float = 0.5) -> None:
        self.worker.run_forever(stop_event, idle_seconds=idle_seconds)

    def health(self) -> dict[str, Any]:
        counts = self.outbox.counts()
        return {
            "service": "merlin-hermes-runtime/1",
            "worker_id": self.worker.worker_id,
            "registered_stages": sorted(self.stage_handlers),
            "outbox_counts": counts,
            "status": "ready",
            "authority": "bounded_execution_only",
            "promotion_authority": False,
        }


def build_merlin_hermes_runtime(
    *,
    outbox: MerlinEventOutbox,
    evidence_recorder: ResearchEvidenceRecorder,
    project_id: str,
    research_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    proof_search_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    artifact_verifier: Callable[..., Mapping[str, Any]],
    repository: str,
    commit_sha: str,
    requester_id: str,
    recipient_validator: Callable[[str], bool],
    approval_validator: Callable[[str, Any], bool],
    lease_validator: Callable[[str, Mapping[str, int]], bool],
    worker_id: str = "hermes-worker",
    include_ngspice: bool = True,
    lease_seconds: float = 120,
    max_attempts: int = 4,
    retry_delay_seconds: float = 2,
) -> MerlinHermesRuntime:
    """Build one coherent runtime using the existing Hermes and evidence engines.

    Research and proof executors are mandatory and injected. Numerical execution
    uses Merlin's existing linear simulation executor; electrical analysis uses
    its existing ngspice executor when enabled. The artifact verifier must be
    an independent CACE verification transport/adapter, not registry hashing.
    """
    if not isinstance(outbox, MerlinEventOutbox):
        raise ValueError("canonical MerlinEventOutbox is required")
    if not isinstance(evidence_recorder, ResearchEvidenceRecorder):
        raise ValueError("canonical ResearchEvidenceRecorder is required")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("canonical project_id is required")
    if not callable(artifact_verifier):
        raise ValueError("independent CACE artifact verifier is required")
    if not callable(approval_validator) or not callable(lease_validator):
        raise ValueError("approval and MCFC lease validators are required")

    raw_handlers = build_merlin_hermes_handlers(
        evidence_recorder=evidence_recorder,
        project_id=project_id,
        research_executor=research_executor,
        proof_search_executor=proof_search_executor,
        artifact_verifier=artifact_verifier,
        repository=repository,
        commit_sha=commit_sha,
        requester_id=requester_id,
        include_ngspice=include_ngspice,
    )

    handlers: dict[str, Callable[..., Mapping[str, Any]]] = {}
    for stage, raw_handler in raw_handlers.items():
        def bound_handler(
            task: Mapping[str, Any],
            context: Any,
            *,
            _stage: str = stage,
            _handler: Callable[..., Mapping[str, Any]] = raw_handler,
        ) -> Mapping[str, Any]:
            if task.get("stage") != _stage:
                raise ValueError("runtime stage handler received mismatched stage")
            spec = task.get("experiment_spec")
            if not isinstance(spec, Mapping):
                raise ValueError("Hermes task is missing experiment_spec")
            prompt_payload = spec.get("engineered_prompt")
            if not isinstance(prompt_payload, Mapping):
                raise ValueError("Hermes task is missing its compiled engineered prompt")
            compiled = CompiledPrompt(**dict(prompt_payload))
            compiled.validate()
            if compiled.task_id != task.get("task_id"):
                raise ValueError("compiled prompt task ID does not match Hermes task")
            result = dict(_handler(task, context))
            result.update({
                "prompt_sha256": compiled.prompt_sha256,
                "task_sha256": compiled.task_sha256,
                "source_repository": compiled.source_repository,
                "source_commit_sha": compiled.source_commit_sha,
            })
            return result
        handlers[stage] = bound_handler

    worker = HermesWorker(
        outbox,
        handlers=handlers,
        approval_validator=approval_validator,
        lease_validator=lease_validator,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
    )
    dispatcher = PromptHermesDispatcher(
        outbox,
        recipient_validator=recipient_validator,
        approval_validator=approval_validator,
        lease_validator=lease_validator,
    )
    return MerlinHermesRuntime(
        outbox=outbox,
        worker=worker,
        dispatcher=dispatcher,
        stage_handlers=handlers,
    )


__all__ = ["MerlinHermesRuntime", "build_merlin_hermes_runtime"]
