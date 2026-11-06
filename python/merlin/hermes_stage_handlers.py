"""Stage-scoped Hermes handler registration and canonical evidence recording.

This module deliberately requires concrete domain executors to be injected.
It does not substitute a fake numerical solver, proof searcher or research agent.
Each executor returns immutable artifact bytes; this layer stores and verifies
those bytes, links them to the canonical hypothesis graph, and returns refs.
"""
from __future__ import annotations

from dataclasses import asdict
import re
from typing import Any, Callable, Mapping

from .research_evidence import ResearchEvidenceRecorder
from .hermes_proof_orchestrator import dispatch_eligible_claim

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
    "electrical_analysis": {
        "evidence_kind": "experiment",
        "tool": "ngspice",
        "label": "electrical analysis",
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
    artifact_verifier: Callable[..., Mapping[str, Any]] | None,
    repository: str,
    commit_sha: str,
    requester_id: str,
    electrical_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]] | None = None,
    theorem_verifier: Callable[..., Mapping[str, Any]] | None = None,
    lean_dispatcher: Callable[..., Mapping[str, Any]] | None = None,
    lean_tool_version: str | None = None,
) -> dict[str, Callable[[Mapping[str, Any], Any], Mapping[str, Any]]]:
    """Build stage handlers that record artifacts and optionally obtain CACE receipts.

    Research, numerical and proof-search executors are mandatory. If the CACE
    verifier is not configured, artifacts are still recorded and returned with
    verification_status=blocked_missing_credentials. This is never verification
    and cannot authorize promotion. Electrical analysis is registered when its
    ngspice executor is supplied.
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
    if electrical_executor is not None:
        executors["electrical_analysis"] = electrical_executor
    if any(not callable(executor) for executor in executors.values()):
        raise ValueError("all registered stage executors must be callable")
    if artifact_verifier is not None and not callable(artifact_verifier):
        raise ValueError("artifact_verifier must be callable or None")
    if lean_dispatcher is not None and not callable(lean_dispatcher):
        raise ValueError("lean_dispatcher must be callable or None")
    if lean_dispatcher is not None and (
        not isinstance(lean_tool_version, str) or not lean_tool_version.strip()
    ):
        raise ValueError("lean_tool_version is required when a Lean dispatcher is configured")
    if not isinstance(repository, str) or "/" not in repository:
        raise ValueError("repository must be owner/name")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
    if not isinstance(requester_id, str) or not requester_id.strip():
        raise ValueError("requester_id is required")

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
            if artifact_verifier is None:
                # Missing verifier credentials must not block independent research
                # and artifact capture, but must never be reported as verified.
                cace_result = {
                    "schema": "merlin-cace-verification-result/1",
                    "verification_status": "blocked_missing_credentials",
                    "reason_code": "cace_verifier_not_configured",
                    "artifact_sha256": digest,
                    "promotion_authority": False,
                }
            else:
                context.emit_progress(_contract["label"] + " artifact stored; requesting independent CACE verification")
                cace_result = artifact_verifier(
                    project_id=project_id,
                    repository=repository,
                    commit_sha=commit_sha,
                    artifact_sha256=digest,
                    artifact_kind=_stage,
                    artifact_schema=str(output["metadata"].get("artifact_schema") or output["media_type"]),
                    requester_id=requester_id,
                    logical_path=logical_path,
                )
                if not isinstance(cace_result, Mapping):
                    raise TypeError("CACE artifact verifier must return a receipt result")
                cace_result = dict(cace_result)
                if cace_result.get("artifact_sha256") != digest:
                    raise ValueError("CACE result does not bind the submitted artifact digest")
            theorem_receipts = []
            lean_dispatch_receipts = []
            theorem_claims = output["metadata"].get("theorem_claims", [])
            if theorem_claims and _stage != "proof_search":
                raise ValueError("theorem_claims are only accepted from the proof_search stage")
            if not isinstance(theorem_claims, list):
                raise TypeError("theorem_claims metadata must be a list")

            for claim in theorem_claims:
                if not isinstance(claim, Mapping):
                    raise TypeError("each theorem claim must be an object")
                claim_id = claim.get("claim_id", "")
                if lean_dispatcher is None:
                    lean_receipt = {
                        "schema": "merlin-hermes-proof-dispatch/1",
                        "claim_id": str(claim_id),
                        "route": "not_dispatched",
                        "reason_codes": ["lean_dispatcher_not_configured"],
                        "repository": repository,
                        "commit_sha": commit_sha,
                        "source_sha256": None,
                        "tool_version": lean_tool_version,
                        "compilation_status": "not_dispatched",
                        "verification_status": "blocked_missing_lean_dispatcher",
                        "promotion_authority": False,
                    }
                else:
                    safe_task = _safe_segment(context.task_id)
                    safe_claim = _safe_segment(str(claim_id))

                    def record_lean_source(
                        *, claim_id: str, artifact_bytes: bytes,
                        artifact_sha256: str, **_unused: Any,
                    ) -> Mapping[str, Any]:
                        source_path = (
                            "proof-sources/" + safe_task + "/" + safe_claim + ".lean"
                        )
                        source_record = evidence_recorder.record(
                            project_id=project_id,
                            hypothesis_id=context.hypothesis_id,
                            logical_path=source_path,
                            content=artifact_bytes,
                            evidence_kind="proof",
                            description="Exact Lean source recorded before Hermes dispatch: " + claim_id,
                        )
                        return {
                            "artifact_sha256": source_record["artifact_sha256"],
                            "registry_verified": source_record["artifact_verified"],
                        }

                    dispatch = dispatch_eligible_claim(
                        claim,
                        repository=repository,
                        commit_sha=commit_sha,
                        lean_tool_version=lean_tool_version,
                        lean_dispatcher=lean_dispatcher,
                        artifact_recorder=record_lean_source,
                    )
                    lean_receipt = asdict(dispatch)

                # A research executor's claimed compilation_status is never trusted.
                # Only the exact-input dispatcher result can establish compilation.
                if lean_receipt["compilation_status"] == "compiled":
                    if theorem_verifier is None:
                        lean_receipt["verification_status"] = "pending_independent_cace_verification"
                    else:
                        theorem = claim.get("formal_statement")
                        if not isinstance(theorem, str) or not theorem.strip():
                            raise ValueError("compiled theorem claim is missing its exact formal statement")
                        source_digest = lean_receipt.get("source_sha256")
                        if not isinstance(source_digest, str) or len(source_digest) != 64:
                            raise ValueError("compiled theorem claim is missing its exact Lean source digest")
                        theorem_result = theorem_verifier(
                            project_id=project_id,
                            repository=repository,
                            commit_sha=commit_sha,
                            artifact_sha256=source_digest,
                            theorem=theorem,
                            requester_id=requester_id,
                            logical_path=(
                                "proof-sources/" + _safe_segment(context.task_id) + "/"
                                + _safe_segment(str(claim_id)) + ".lean"
                            ),
                        )
                        if not isinstance(theorem_result, Mapping):
                            raise TypeError("CACE theorem verifier must return a receipt result")
                        theorem_result = dict(theorem_result)
                        if theorem_result.get("artifact_sha256") != source_digest:
                            raise ValueError("CACE theorem receipt is not bound to the exact stored Lean source")
                        theorem_receipts.append(theorem_result)
                        lean_receipt["verification_status"] = str(
                            theorem_result.get("verification_status", "unknown")
                        )
                elif lean_receipt["verification_status"] == "pending_independent_cace_verification":
                    lean_receipt["verification_status"] = "blocked_missing_lean_dispatcher"
                lean_dispatch_receipts.append(lean_receipt)

            result_metadata = dict(output["metadata"])
            result_metadata["lean_dispatch_receipts"] = lean_dispatch_receipts
            if theorem_claims and artifact_verifier is None and theorem_verifier is None:
                cace_result["theorem_verification_status"] = "blocked_missing_credentials"
            receipt_digest = cace_result.get("receipt_artifact_sha256")
            evidence_refs = ["sha256:" + digest]
            if isinstance(receipt_digest, str) and len(receipt_digest) == 64:
                evidence_refs.append("sha256:" + receipt_digest)
            for lean_receipt in lean_dispatch_receipts:
                source_digest = lean_receipt.get("source_sha256")
                if isinstance(source_digest, str) and len(source_digest) == 64:
                    evidence_refs.append("sha256:" + source_digest)
            for theorem_receipt in theorem_receipts:
                theorem_receipt_digest = theorem_receipt.get("receipt_artifact_sha256")
                if isinstance(theorem_receipt_digest, str) and len(theorem_receipt_digest) == 64:
                    evidence_refs.append("sha256:" + theorem_receipt_digest)
            evidence_refs = list(dict.fromkeys(evidence_refs))
            context.emit_tool_event(
                "agent.tool.completed", _contract["tool"],
                {"stage": _stage, "task_id": context.task_id,
                 "artifact_sha256": digest, "registry_verified": True,
                 "cace_status": cace_result.get("verification_status")},
            )
            if cace_result.get("verification_status") == "blocked_missing_credentials":
                context.emit_progress(_contract["label"] + " artifact recorded; independent CACE verification is blocked because credentials are not configured")
            else:
                context.emit_progress(_contract["label"] + " artifact and CACE receipt recorded")
            return {
                "schema": "merlin-hermes-stage-result/1",
                "stage": _stage,
                "summary": output["summary"],
                "metadata": result_metadata,
                "artifact": {
                    "project_id": project_id,
                    "logical_path": logical_path,
                    "sha256": digest,
                    "media_type": output["media_type"],
                    "size_bytes": len(output["artifact_bytes"]),
                    "registry_verified": True,
                },
                "graph_edge": recorded["graph_edge"],
                "cace_verification": cace_result,
                "cace_theorem_receipts": theorem_receipts,
                "evidence_refs": evidence_refs,
                "hypothesis_status_unchanged": recorded["hypothesis_status_unchanged"],
                "promotion_authority": False,
            }

        handlers[stage] = handler
    return handlers


def build_merlin_hermes_handlers(
    *,
    evidence_recorder: ResearchEvidenceRecorder,
    project_id: str,
    research_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    proof_search_executor: Callable[[Mapping[str, Any], Any], Mapping[str, Any]],
    artifact_verifier: Callable[..., Mapping[str, Any]] | None = None,
    repository: str,
    commit_sha: str,
    requester_id: str,
    include_ngspice: bool = True,
    lean_dispatcher: Callable[..., Mapping[str, Any]] | None = None,
    lean_tool_version: str | None = None,
    theorem_verifier: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Callable[[Mapping[str, Any], Any], Mapping[str, Any]]]:
    """Register built-in numerical/electrical engines plus real injected research/proof engines."""
    from merlin.linear_simulation import linear_ode_task_executor
    from merlin.ngspice_engine import ngspice_task_executor

    return build_hermes_stage_handlers(
        evidence_recorder=evidence_recorder,
        project_id=project_id,
        research_executor=research_executor,
        numerical_experiment_executor=linear_ode_task_executor,
        proof_search_executor=proof_search_executor,
        electrical_executor=ngspice_task_executor if include_ngspice else None,
        artifact_verifier=artifact_verifier,
        repository=repository,
        commit_sha=commit_sha,
        requester_id=requester_id,
        theorem_verifier=theorem_verifier,
        lean_dispatcher=lean_dispatcher,
        lean_tool_version=lean_tool_version,
    )


__all__ = ["build_hermes_stage_handlers", "build_merlin_hermes_handlers"]
