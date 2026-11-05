"""Stage-scoped Hermes handler registration and canonical evidence recording.

This module deliberately requires concrete domain executors to be injected.
It does not substitute a fake numerical solver, proof searcher or research agent.
Each executor returns immutable artifact bytes; this layer stores and verifies
those bytes, links them to the canonical hypothesis graph, and returns refs.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from merlin.research_evidence import ResearchEvidenceRecorder

_STAGE_CONTRACTS = {
    "research": {
        "evidence_kind": "source",
        "tool": "research-executor",
        "label": "research",
    },
    "numerical_experiment": {
        "evidence_kind": "experiment",
        "tool": "numerical-experiment-engine",
        "label": "numerical experiment",
    },
    "proof_search": {
        "evidence_kind": "proof",
        "tool": "proof-search-engine",
        "label": "proof search",
    },
}


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not segment or segment in {".", ".."}:
        raise ValueError("task identity cannot form a safe artifact path")
    return segment[:120]


def _validate_executor_output(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("stage executor must return an object")
    result = dict(value)
    artifact_bytes = result.get("artifact_bytes")
    if not isinstance(artifact_bytes, bytes) or not artifact_bytes:
        raise ValueError("stage executor must return non-empty immutable artifact_bytes")
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 500:
        raise ValueError("stage executor must return a short summary")
    media_type = result.get("media_type", "application/octet-stream")
    if not isinstance(media_type, str) or not media_type.strip() or len(media_type) > 200:
        raise ValueError("stage executor media_type is invalid")
    metadata = result.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("stage executor metadata must be an object")
    return {
        "artifact_bytes": artifact_bytes,
        "summary": summary.strip(),
        "media_type": media_type.strip(),
        "metadata": dict(metadata),
    }


def build_hermes_stage_handlers(
    *,
    evidence_recorder: ResearchEvidenceRecorder,
    project_id: str,
    research_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    numerical_experiment_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    proof_search_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
) -> dict[str, Callable[[Mapping[str, Any], Any], Mapping[str, Any]]]:
    """Build the three real stage handlers around supplied executable engines.

    The three executors are mandatory: registration fails closed if an engine
    is absent. Executors receive the task and bounded TaskExecutionContext;
    they must enforce the supplied budget/deadline at their own process boundary.
    """
    if not isinstance(evidence_recorder, ResearchEvidenceRecorder):
        raise ValueError("the canonical ResearchEvidenceRecorder is required")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("canonical registry project_id is required")
    executors = {
        "research": research_executor,
        "numerical_experiment": numerical_experiment_executor,
        "proof_search": proof_search_executor,
    }
    if any(not callable(executor) for executor in executors.values()):
        raise ValueError("research, numerical experiment and proof-search engines must all be injected")

    handlers = {}
    for stage, executor in executors.items():
        contract = _STAGE_CONTRACTS[stage]

        def handler(task: Mapping[str, Any], context: Any, *,
                    _stage: str = stage, _executor: Callable[..., Any] = executor,
                    _contract: Mapping[str, str] = contract) -> Mapping[str, Any]:
            if task.get("stage") != _stage:
                raise ValueError("stage handler received a mismatched task")
            context.emit_progress(_contract["label"] + " engine executing")
            context.emit_tool_event(
                "agent.tool.started", _contract["tool"],
                {"stage": _stage, "task_id": context.task_id},
            )
            output = _validate_executor_output(_executor(task, context))
            context.emit_progress(_contract["label"] + " output received; recording canonical artifact")
            logical_path = (
                "research-runs/" + _safe_segment(context.task_id) + "/" +
                _stage + "/result.bin"
            )
            recorded = evidence_recorder.record(
                project_id=project_id,
                hypothesis_id=context.hypothesis_id,
                logical_path=logical_path,
                content=output["artifact_bytes"],
                evidence_kind=_contract["evidence_kind"],
                description=output["summary"],
            )
            if recorded.get("artifact_verified") is not True:
                raise RuntimeError("canonical registry did not verify the recorded artifact")
            digest = recorded["artifact_sha256"]
            context.emit_tool_event(
                "agent.tool.completed", _contract["tool"],
                {"stage": _stage, "task_id": context.task_id,
                 "artifact_sha256": digest, "artifact_verified": True},
            )
            context.emit_progress(_contract["label"] + " artifact verified and linked to graph")
            return {
                "schema": "merlin-hermes-stage-result/1",
                "stage": _stage,
                "summary": output["summary"],
                "metadata": output["metadata"],
                "artifact": {
                    "project_id": project_id,
                    "logical_path": logical_path,
                    "sha256": digest,
                    "media_type": output["media_type"],
                    "size_bytes": len(output["artifact_bytes"]),
                    "registry_verified": True,
                },
                "graph_edge": recorded["graph_edge"],
                "evidence_refs": ["sha256:" + digest],
                "hypothesis_status_unchanged": recorded["hypothesis_status_unchanged"],
                "promotion_authority": False,
            }

        handlers[stage] = handler
    return handlers


__all__ = ["build_hermes_stage_handlers"]
