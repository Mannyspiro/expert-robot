"""Evidence-gated partner qualification for procurement opportunities.

Directory listings and self-assertions are discovery signals, never proof of
licensing, appointments, public-sector performance, or teaming consent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

VALID_RELATIONSHIPS = {
    "capability_benchmark", "potential_competitor", "potential_prime",
    "potential_subcontractor", "referral_source", "unqualified",
}
VALID_STATUSES = {"verified", "not_met", "unknown", "conflicting", "not_applicable"}
VALID_SOURCE_KINDS = {
    "official_registry", "contracting_authority", "client_reference",
    "partner_written", "partner_claim", "directory",
}
REQUIRED_EVIDENCE = (
    "entity_license", "individual_license", "lines_of_authority",
    "appointments", "public_sector_references", "teaming_permission",
    "conflict_review",
)
TRUSTED_SOURCES = {
    "entity_license": {"official_registry"},
    "individual_license": {"official_registry"},
    "lines_of_authority": {"official_registry"},
    "appointments": {"official_registry", "carrier_confirmation"},
    "public_sector_references": {"contracting_authority", "client_reference"},
    "teaming_permission": {"partner_written"},
    "conflict_review": {"contracting_authority", "partner_written"},
}


@dataclass(frozen=True)
class PartnerEvidence:
    evidence_type: str
    status: str
    source_url: str
    source_kind: str
    observed_on: str
    subject: str = ""

    def __post_init__(self) -> None:
        if self.evidence_type not in REQUIRED_EVIDENCE:
            raise ValueError("unsupported partner evidence_type")
        if self.status not in VALID_STATUSES:
            raise ValueError("unsupported partner evidence status")
        if self.source_kind not in VALID_SOURCE_KINDS:
            raise ValueError("unsupported partner evidence source_kind")
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTPS URL")
        date.fromisoformat(self.observed_on)


@dataclass(frozen=True)
class PartnerCandidate:
    partner_id: str
    legal_name: str
    relationship: str
    evidence: tuple[PartnerEvidence, ...] = ()

    def __post_init__(self) -> None:
        if not self.partner_id.strip() or not self.legal_name.strip():
            raise ValueError("partner_id and legal_name are required")
        if self.relationship not in VALID_RELATIONSHIPS:
            raise ValueError("unsupported partner relationship")
        kinds = [x.evidence_type for x in self.evidence]
        if len(kinds) != len(set(kinds)):
            raise ValueError("partner evidence types must be unique")


@dataclass(frozen=True)
class PartnerQualification:
    decision: str
    verified_evidence: tuple[str, ...]
    unresolved_evidence: tuple[str, ...]
    failed_evidence: tuple[str, ...]
    reasons: tuple[str, ...]


def evaluate_partner(candidate: PartnerCandidate) -> PartnerQualification:
    """Qualify evidence only; final partner selection always needs human review."""
    if candidate.relationship in {"capability_benchmark", "potential_competitor", "unqualified"}:
        return PartnerQualification(
            "benchmark_or_competitor_only", (), REQUIRED_EVIDENCE, (),
            ("relationship classification does not authorize partner selection",),
        )

    by_type = {x.evidence_type: x for x in candidate.evidence}
    verified: list[str] = []
    unresolved: list[str] = []
    failed: list[str] = []
    for requirement in REQUIRED_EVIDENCE:
        item = by_type.get(requirement)
        if item is None or item.status in {"unknown", "conflicting"}:
            unresolved.append(requirement)
        elif item.status == "not_met":
            failed.append(requirement)
        elif item.status == "not_applicable":
            # A mandatory qualification gate cannot be waived by this status.
            unresolved.append(requirement)
        elif item.source_kind not in TRUSTED_SOURCES[requirement]:
            unresolved.append(requirement)
        else:
            verified.append(requirement)

    if failed:
        decision = "exclude_pending_reassessment"
    elif unresolved:
        decision = "hold_for_evidence"
    else:
        decision = "qualified_for_human_review"
    reasons = []
    if failed:
        reasons.append("one or more mandatory partner qualifications are explicitly not met")
    if unresolved:
        reasons.append("mandatory partner evidence is missing, conflicting, or not authoritative")
    if decision == "qualified_for_human_review":
        reasons.append("evidence gates are satisfied; human selection and conflict approval remain required")
    return PartnerQualification(
        decision, tuple(verified), tuple(unresolved), tuple(failed), tuple(reasons)
    )
