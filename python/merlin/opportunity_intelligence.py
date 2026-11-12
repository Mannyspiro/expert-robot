"""Evidence-aware matching for grants, scholarships, and public contracts.

This module is deliberately offline: discovery connectors must provide sourced
records; this layer normalizes, screens, and ranks them without claiming that a
listing is open or that an applicant is eligible when evidence is missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlparse


VALID_TYPES = {
    "government_contract", "subcontract", "grant", "scholarship",
    "fellowship", "prize", "training_stipend", "artist_opportunity",
}
VALID_STATUSES = {"open", "upcoming", "rolling", "closed", "unknown"}
VALID_CONFIDENCE = {"official", "verified_secondary", "unverified"}
VALID_APPLICANT_TYPES = {"individual", "for_profit_business", "nonprofit",
                         "club", "school", "fiscal_sponsor", "public_entity"}


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    title: str
    opportunity_type: str
    applicant_types: tuple[str, ...]
    source_url: str
    source_name: str
    source_confidence: str = "unverified"
    status: str = "unknown"
    deadline: str | None = None
    jurisdictions: tuple[str, ...] = ()
    eligible_fields: tuple[str, ...] = ()
    required_credentials: tuple[str, ...] = ()
    identity_criteria: tuple[str, ...] = ()
    age_min: int | None = None
    age_max: int | None = None
    enrollment_required: bool = False
    organization_required: bool = False
    requires_fiscal_sponsor: bool = False
    license_jurisdictions: tuple[str, ...] = ()
    award_min: int | None = None
    award_max: int | None = None
    notes: str = ""
    last_verified: str | None = None

    def __post_init__(self) -> None:
        if self.opportunity_type not in VALID_TYPES:
            raise ValueError("unsupported opportunity_type")
        if self.status not in VALID_STATUSES:
            raise ValueError("unsupported status")
        if self.source_confidence not in VALID_CONFIDENCE:
            raise ValueError("unsupported source_confidence")
        if not self.applicant_types or any(x not in VALID_APPLICANT_TYPES for x in self.applicant_types):
            raise ValueError("applicant_types must contain supported applicant types")
        parsed = urlparse(self.source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an absolute HTTPS URL")
        if self.deadline:
            date.fromisoformat(self.deadline)
        if self.last_verified:
            date.fromisoformat(self.last_verified)
        if self.age_min is not None and self.age_min < 0:
            raise ValueError("age_min cannot be negative")
        if self.age_max is not None and self.age_max < 0:
            raise ValueError("age_max cannot be negative")
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min cannot exceed age_max")
        if self.award_min is not None and self.award_max is not None and self.award_min > self.award_max:
            raise ValueError("award_min cannot exceed award_max")


@dataclass(frozen=True)
class ApplicantProfile:
    applicant_type: str
    jurisdictions: tuple[str, ...] = ()
    age: int | None = None
    enrolled: bool | None = None
    fields: tuple[str, ...] = ()
    credentials: tuple[str, ...] = ()
    licenses: tuple[str, ...] = ()
    has_fiscal_sponsor: bool | None = None
    # Identity attributes are opt-in matching inputs; never infer or log them.
    identity_attributes: tuple[str, ...] = ()
    priorities: tuple[str, ...] = ()
    # Explicitly known unmet requirements; absence from credentials/licenses means unknown.
    unmet_credentials: tuple[str, ...] = ()
    unmet_licenses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.applicant_type not in VALID_APPLICANT_TYPES:
            raise ValueError("unsupported applicant_type")
        if self.age is not None and self.age < 0:
            raise ValueError("age cannot be negative")


@dataclass(frozen=True)
class MatchResult:
    opportunity_id: str
    eligibility: str
    score: int
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    verification_required: tuple[str, ...]


def evaluate_opportunity(
    opportunity: Opportunity,
    applicant: ApplicantProfile,
    as_of: date | None = None,
) -> MatchResult:
    """Return eligible / conditional / ineligible without inventing missing facts."""
    today = as_of or date.today()
    blockers: list[str] = []
    reasons: list[str] = []
    verify: list[str] = []

    if applicant.applicant_type not in opportunity.applicant_types:
        blockers.append("applicant type is not accepted")
    if opportunity.organization_required and applicant.applicant_type == "individual":
        blockers.append("an eligible organization is required")
    if opportunity.requires_fiscal_sponsor:
        if applicant.has_fiscal_sponsor is None:
            verify.append("fiscal sponsor status not verified")
        elif not applicant.has_fiscal_sponsor:
            blockers.append("eligible fiscal sponsor or qualifying organization required")
    if opportunity.jurisdictions:
        if not applicant.jurisdictions:
            verify.append("applicant jurisdiction not verified")
        elif not set(applicant.jurisdictions).intersection(opportunity.jurisdictions):
            blockers.append("applicant jurisdiction does not match listed eligibility")
    if opportunity.age_min is not None:
        if applicant.age is None:
            verify.append("minimum age not verified")
        elif applicant.age < opportunity.age_min:
            blockers.append("applicant is below minimum age")
    if opportunity.age_max is not None:
        if applicant.age is None:
            verify.append("maximum age not verified")
        elif applicant.age > opportunity.age_max:
            blockers.append("applicant exceeds maximum age")
    if opportunity.enrollment_required:
        if applicant.enrolled is None:
            verify.append("student enrollment status not verified")
        elif not applicant.enrolled:
            blockers.append("current or planned enrollment is required")
    missing_credentials = set(opportunity.required_credentials) - set(applicant.credentials)
    if missing_credentials:
        verify.extend("credential not confirmed: " + x for x in sorted(missing_credentials - set(applicant.unmet_credentials)))
    if applicant.unmet_credentials:
        blockers.extend("required credential not held: " + x for x in sorted(set(opportunity.required_credentials).intersection(applicant.unmet_credentials)))
    missing_licenses = set(opportunity.license_jurisdictions) - set(applicant.licenses)
    if missing_licenses:
        known_unmet = missing_licenses.intersection(applicant.unmet_licenses)
        unknown = missing_licenses - known_unmet
        if known_unmet:
            blockers.append("required insurance or professional license not held: " + ", ".join(sorted(known_unmet)))
        if unknown:
            verify.append("required insurance or professional license not verified: " + ", ".join(sorted(unknown)))
    if opportunity.eligible_fields and applicant.fields:
        if not set(opportunity.eligible_fields).intersection(applicant.fields):
            blockers.append("field of study or project does not match")
    elif opportunity.eligible_fields:
        verify.append("field of study or project fit needs confirmation")

    # Identity is only compared against explicit criteria when user opted in.
    if opportunity.identity_criteria:
        if not applicant.identity_attributes:
            verify.append("identity-based eligibility not evaluated")
        elif not set(opportunity.identity_criteria).issubset(applicant.identity_attributes):
            blockers.append("explicit identity eligibility criterion not met")

    if opportunity.status == "closed":
        blockers.append("application window is closed")
    elif opportunity.status == "unknown":
        verify.append("current application status must be verified")
    elif opportunity.status == "upcoming":
        reasons.append("upcoming cycle; track opening date")
    elif opportunity.status == "rolling":
        reasons.append("rolling application; verify funds remain available")
    if opportunity.deadline and opportunity.deadline < today.isoformat():
        blockers.append("listed deadline has passed")
    if opportunity.source_confidence == "unverified":
        verify.append("confirm listing against the official program or solicitation")
    elif opportunity.source_confidence == "verified_secondary":
        verify.append("confirm details on the awarding agency's official page")
    if not opportunity.last_verified:
        verify.append("source has no recorded verification date")

    if blockers:
        eligibility = "ineligible"
    elif verify:
        eligibility = "conditional"
    else:
        eligibility = "eligible"

    score = 50
    score += 20 if eligibility == "eligible" else 5 if eligibility == "conditional" else -40
    score += 10 if opportunity.source_confidence == "official" else 0
    score += 10 if opportunity.status in {"open", "rolling"} else 0
    if opportunity.eligible_fields and set(opportunity.eligible_fields).intersection(applicant.fields):
        score += 10
    if set(opportunity.eligible_fields).intersection(applicant.priorities):
        score += 10
    score = max(0, min(100, score))
    return MatchResult(opportunity.opportunity_id, eligibility, score,
                       tuple(reasons), tuple(blockers), tuple(dict.fromkeys(verify)))


def rank_opportunities(
    opportunities: Iterable[Opportunity],
    applicant: ApplicantProfile,
    as_of: date | None = None,
) -> list[tuple[Opportunity, MatchResult]]:
    """Rank by eligibility, evidence quality, then fit score; stable by title."""
    rows = [(item, evaluate_opportunity(item, applicant, as_of)) for item in opportunities]
    order = {"eligible": 0, "conditional": 1, "ineligible": 2}
    return sorted(rows, key=lambda row: (order[row[1].eligibility], -row[1].score,
                                         row[0].title.casefold()))


def opportunity_to_dict(item: Opportunity) -> dict[str, Any]:
    """Serialize a record without adding claims or deriving eligibility."""
    return {
        "opportunity_id": item.opportunity_id,
        "title": item.title,
        "opportunity_type": item.opportunity_type,
        "applicant_types": list(item.applicant_types),
        "source_url": item.source_url,
        "source_name": item.source_name,
        "source_confidence": item.source_confidence,
        "status": item.status,
        "deadline": item.deadline,
        "jurisdictions": list(item.jurisdictions),
        "eligible_fields": list(item.eligible_fields),
        "required_credentials": list(item.required_credentials),
        "identity_criteria": list(item.identity_criteria),
        "age_min": item.age_min,
        "age_max": item.age_max,
        "enrollment_required": item.enrollment_required,
        "organization_required": item.organization_required,
        "requires_fiscal_sponsor": item.requires_fiscal_sponsor,
        "license_jurisdictions": list(item.license_jurisdictions),
        "award_min": item.award_min,
        "award_max": item.award_max,
        "notes": item.notes,
        "last_verified": item.last_verified,
    }
