"""Evidence-aware readiness gates for public procurement pursuits.

A readiness result is a triage decision, not legal advice or permission to bid.
Unknown evidence remains conditional; explicit failed requirements block pursuit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


VALID_GATES = {
    "app_registration_complete",
    "sam_registration_active",
    "agency_entity_license_verified",
    "producer_appointments_verified",
    "lines_of_authority_verified",
    "professional_liability_verified",
    "cyber_coverage_verified",
    "public_sector_references_verified",
    "delivery_capacity_verified",
    "required_certifications_verified",
}


@dataclass(frozen=True)
class ProcurementRequirements:
    """Only mark gates required by the specific solicitation and pursuit route."""
    gates: tuple[str, ...]

    def __post_init__(self) -> None:
        unknown = set(self.gates) - VALID_GATES
        if unknown:
            raise ValueError("unsupported procurement gates: " + ", ".join(sorted(unknown)))
        if len(set(self.gates)) != len(self.gates):
            raise ValueError("procurement gates must be unique")


@dataclass(frozen=True)
class ProcurementEvidence:
    """True = verified, False = explicitly not satisfied, None = unknown."""
    app_registration_complete: bool | None = None
    sam_registration_active: bool | None = None
    agency_entity_license_verified: bool | None = None
    producer_appointments_verified: bool | None = None
    lines_of_authority_verified: bool | None = None
    professional_liability_verified: bool | None = None
    cyber_coverage_verified: bool | None = None
    public_sector_references_verified: bool | None = None
    delivery_capacity_verified: bool | None = None
    required_certifications_verified: bool | None = None


@dataclass(frozen=True)
class ProcurementReadinessResult:
    decision: str
    verified_gates: tuple[str, ...]
    unresolved_gates: tuple[str, ...]
    failed_gates: tuple[str, ...]
    reasons: tuple[str, ...]


def evaluate_procurement_readiness(
    requirements: ProcurementRequirements,
    evidence: ProcurementEvidence,
) -> ProcurementReadinessResult:
    """Return proceed_to_human_review, hold_for_evidence, or no_bid."""
    verified: list[str] = []
    unresolved: list[str] = []
    failed: list[str] = []
    for gate in requirements.gates:
        value = getattr(evidence, gate)
        if value is True:
            verified.append(gate)
        elif value is False:
            failed.append(gate)
        else:
            unresolved.append(gate)

    if failed:
        decision = "no_bid"
    elif unresolved:
        decision = "hold_for_evidence"
    else:
        decision = "proceed_to_human_review"

    reasons = []
    if failed:
        reasons.append("one or more mandatory solicitation requirements are explicitly unmet")
    if unresolved:
        reasons.append("mandatory evidence is missing or has not been independently verified")
    if decision == "proceed_to_human_review":
        reasons.append("all configured gates are verified; human bid/no-bid approval is still required")
    return ProcurementReadinessResult(
        decision, tuple(verified), tuple(unresolved), tuple(failed), tuple(reasons)
    )
