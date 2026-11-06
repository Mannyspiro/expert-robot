"""Production composition root for the approval-gated Merlin Hermes worker."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .cace_runtime import cace_verification_adapter_from_environment
from .event_outbox import MerlinEventOutbox
from .hermes_service import HermesWorkerService
from .hermes_stage_handlers import build_merlin_hermes_handlers
from .hermes_worker import HermesWorker
from .hypothesis_ledger import HypothesisLedger
from .knowledge_graph import MerlinKnowledgeGraph
from .project_registry import MerlinRegistry
from .research_evidence import ResearchEvidenceRecorder


@dataclass
class MerlinHermesRuntime:
    root: Path
    registry: MerlinRegistry
    ledger: HypothesisLedger
    graph: MerlinKnowledgeGraph
    outbox: MerlinEventOutbox
    evidence_recorder: ResearchEvidenceRecorder
    cace_adapter: Any | None
    worker: HermesWorker
    service: HermesWorkerService

    def start(self) -> bool:
        return self.service.start()

    def stop(self, timeout_seconds: float = 10.0) -> bool:
        return self.service.stop(timeout_seconds=timeout_seconds)

    def health(self) -> dict[str, Any]:
        return {
            "schema": "merlin-hermes-runtime-health/1",
            "worker": self.service.health(),
            "cace_verification": (
                "configured" if self.cace_adapter is not None else "unavailable"
            ),
            "promotion_authority": False,
        }


def build_merlin_hermes_runtime(
    *,
    root: str | Path,
    project_id: str,
    project_name: str,
    repository: str,
    commit_sha: str,
    requester_id: str,
    research_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    proof_search_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    approval_validator: Callable[[str, Mapping[str, Any]], bool],
    lease_validator: Callable[[str, Mapping[str, int]], bool],
    worker_id: str = "hermes-worker",
    lean_dispatcher: Callable[..., Mapping[str, Any]] | None = None,
    lean_tool_version: str | None = None,
    include_ngspice: bool = True,
    cace_opener: Any | None = None,
    lease_seconds: float = 120,
    max_attempts: int = 4,
) -> MerlinHermesRuntime:
    """Build stores, evidence recorder, CACE adapter, stage handlers and worker.

    All authority-bearing dependencies are mandatory injections. There are no
    permissive approval/lease defaults, local CACE test doubles or fake stage
    executors. Without complete CACE URL/token/pinned signer configuration,
    artifacts can be recorded but CACE verification remains unavailable.
    """
    if not isinstance(root, (str, Path)) or not str(root).strip():
        raise ValueError("runtime root is required")
    for value, label in (
        (project_id, "project_id"), (project_name, "project_name"),
        (requester_id, "requester_id"),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(label + " is required")
    if not isinstance(repository, str) or "/" not in repository:
        raise ValueError("repository must be owner/name")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40 or any(
        char not in "0123456789abcdef" for char in commit_sha
    ):
        raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
    if not callable(approval_validator) or not callable(lease_validator):
        raise ValueError("production approval and MCFC lease validators are required")
    if not callable(research_executor) or not callable(proof_search_executor):
        raise ValueError("real research and proof-search executors are required")
    if lean_dispatcher is not None and not isinstance(lean_tool_version, str):
        raise ValueError("lean_tool_version is required when a Lean dispatcher is configured")

    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    registry = MerlinRegistry(root_path / "registry")
    registry.register_project(project_id, project_name)
    ledger = HypothesisLedger(root_path / "hypotheses.sqlite3")
    graph = MerlinKnowledgeGraph(root_path / "knowledge-graph.sqlite3")
    outbox = MerlinEventOutbox(root_path / "outbox.sqlite3")
    recorder = ResearchEvidenceRecorder(registry, ledger, graph)
    cace_adapter = cace_verification_adapter_from_environment(
        registry=registry, outbox=outbox, graph=graph, opener=cace_opener,
    )

    handlers = build_merlin_hermes_handlers(
        evidence_recorder=recorder,
        project_id=project_id,
        research_executor=research_executor,
        proof_search_executor=proof_search_executor,
        artifact_verifier=(
            cace_adapter.verify_artifact if cace_adapter is not None else None
        ),
        repository=repository,
        commit_sha=commit_sha,
        requester_id=requester_id,
        include_ngspice=include_ngspice,
        lean_dispatcher=lean_dispatcher,
        lean_tool_version=lean_tool_version,
        theorem_verifier=cace_adapter.verify if cace_adapter is not None else None,
    )
    worker = HermesWorker(
        outbox,
        handlers=handlers,
        approval_validator=approval_validator,
        lease_validator=lease_validator,
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        max_attempts=max_attempts,
    )
    service = HermesWorkerService(worker)
    return MerlinHermesRuntime(
        root=root_path,
        registry=registry,
        ledger=ledger,
        graph=graph,
        outbox=outbox,
        evidence_recorder=recorder,
        cace_adapter=cace_adapter,
        worker=worker,
        service=service,
    )


__all__ = ["MerlinHermesRuntime", "build_merlin_hermes_runtime"]
