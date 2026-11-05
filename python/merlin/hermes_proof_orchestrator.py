"""Fail-closed boundary between Hermes claims and the Lean dispatcher.

All production Lean submissions must pass through dispatch_eligible_claim.
The dispatcher receives the exact source bytes that were hashed and recorded.
A Lean compile result is not an independent proof verification or promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Mapping

from merlin.hermes_claim_routing import Route, route_claim


@dataclass(frozen=True)
class DispatchReceipt:
    schema: str
    claim_id: str
    route: str
    reason_codes: tuple[str, ...]
    repository: str
    commit_sha: str
    source_sha256: str | None
    tool_version: str | None
    compilation_status: str
    verification_status: str
    promotion_authority: bool = False


def dispatch_eligible_claim(
    claim: Any,
    *,
    repository: str,
    commit_sha: str,
    lean_tool_version: str,
    lean_dispatcher: Callable[..., Mapping[str, Any]],
    artifact_recorder: Callable[..., Mapping[str, Any]],
) -> DispatchReceipt:
    """Validate, record exact bytes, then dispatch; all non-eligible routes stop."""
    if not isinstance(repository, str) or not repository.strip() or "/" not in repository:
        raise ValueError("repository must be owner/name")
    if not isinstance(commit_sha, str) or len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
        raise ValueError("commit_sha must be a lowercase 40-character Git SHA")
    if not isinstance(lean_tool_version, str) or not lean_tool_version.strip():
        raise ValueError("Lean tool version is required")
    if not callable(lean_dispatcher) or not callable(artifact_recorder):
        raise ValueError("Lean dispatcher and canonical artifact recorder are required")

    route, reasons = route_claim(claim) if isinstance(claim, Mapping) else (Route.REJECT, ("not_a_mapping",))
    claim_id = claim.get("claim_id", "") if isinstance(claim, Mapping) else ""
    if route is not Route.LEAN_COMPILE:
        return DispatchReceipt(
            "merlin-hermes-proof-dispatch/1", str(claim_id), route.value,
            tuple(reasons), repository, commit_sha, None, lean_tool_version,
            "not_dispatched", "not_verified", False,
        )

    # Route policy has approved the claim; validate bytes again at the boundary.
    source = claim["lean_source"]
    if not isinstance(source, str) or not source.strip():
        return DispatchReceipt(
            "merlin-hermes-proof-dispatch/1", str(claim_id), Route.REJECT.value,
            ("invalid_lean_source_at_dispatch_boundary",), repository, commit_sha,
            None, lean_tool_version, "not_dispatched", "not_verified", False,
        )
    source_bytes = source.encode("utf-8")
    digest = hashlib.sha256(source_bytes).hexdigest()
    recorded = artifact_recorder(
        claim_id=str(claim_id), repository=repository, commit_sha=commit_sha,
        artifact_bytes=source_bytes, artifact_sha256=digest,
        artifact_kind="lean_source", tool_name="lean",
        tool_version=lean_tool_version,
    )
    if not isinstance(recorded, Mapping) or recorded.get("artifact_sha256") != digest or recorded.get("registry_verified") is not True:
        raise RuntimeError("canonical registry did not return an exact-digest verified source receipt")

    result = lean_dispatcher(
        claim_id=str(claim_id), source=source, source_sha256=digest,
        repository=repository, commit_sha=commit_sha,
        tool_version=lean_tool_version,
    )
    if not isinstance(result, Mapping):
        raise TypeError("Lean dispatcher must return a result object")
    status = result.get("compilation_status")
    if status not in {"compiled", "compile_failed", "timed_out", "tool_error"}:
        raise ValueError("Lean dispatcher returned an unknown compilation status")
    return DispatchReceipt(
        "merlin-hermes-proof-dispatch/1", str(claim_id), Route.LEAN_COMPILE.value,
        tuple(reasons), repository, commit_sha, digest, lean_tool_version,
        status, "pending_independent_cace_verification", False,
    )


__all__ = ["DispatchReceipt", "dispatch_eligible_claim"]
