"""Typed, evidence-first legal research primitives for Merlin.

This is an offline domain model, not a legal opinion engine. A source citation,
matching quotation, or successful validation does not establish that a legal
proposition is correct. Promotion to verified knowledge requires an
independent, authenticated review bound to the exact claim-set digest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from urllib.parse import urlsplit
import hashlib
import json


US_JURISDICTIONS = frozenset({
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VT", "VA", "WA", "WV", "WI", "WY", "DC",
})
LEGAL_SOURCE_TYPES = frozenset({
    "constitution", "statute", "regulation", "court_opinion", "court_rule",
    "agency_order", "agency_guidance", "treaty", "tribal_code",
    "legislative_history", "restatement", "treatise", "law_review",
    "legal_encyclopedia", "empirical_study", "historical_document",
})
AUTHORITY_STATUSES = frozenset({
    "binding", "persuasive", "nonbinding", "vacated", "overruled",
    "superseded", "repealed", "historical", "unknown",
})
CLAIM_STATUSES = frozenset({
    "research_lead", "source_supported", "contested", "inconclusive",
    "rejected", "independently_verified",
})
LEGAL_FIELDS = {
    "legal_foundations": ("sources_of_law", "jurisdiction", "precedent", "interpretation", "legal_theory"),
    "constitutional": ("federalism", "separation_of_powers", "individual_rights", "judicial_review", "remedies"),
    "jurisprudence": ("natural_law", "legal_positivism", "legal_realism", "interpretivism", "critical_theories"),
    "contracts": ("formation", "interpretation", "performance", "breach", "remedies", "commercial_contracts"),
    "property": ("ownership", "estates", "land_use", "transfers", "mortgages", "landlord_tenant"),
    "torts": ("negligence", "causation", "strict_liability", "intentional_torts", "damages", "defenses"),
    "criminal_law": ("offense_elements", "culpability", "defenses", "sentencing", "criminal_responsibility"),
    "civil_procedure": ("jurisdiction", "pleadings", "discovery", "motions", "trial", "appeal", "preclusion"),
    "criminal_procedure": ("search_seizure", "interrogation", "due_process", "suppression", "trial_rights"),
    "evidence": ("relevance", "hearsay", "privilege", "authentication", "experts", "burdens"),
    "administrative": ("agency_authority", "rulemaking", "adjudication", "judicial_review", "delegation"),
    "business": ("entities", "fiduciary_duties", "securities", "bankruptcy", "secured_transactions", "governance"),
    "employment": ("wages", "discrimination", "workplace_safety", "labor_relations", "benefits"),
    "family_estates": ("marriage", "dissolution", "custody", "support", "trusts", "estates"),
    "tax": ("individual", "corporate", "partnership", "estate_gift", "international", "state_local"),
    "intellectual_property": ("patents", "copyright", "trademarks", "trade_secrets", "licensing"),
    "environmental": ("pollution", "water", "public_lands", "zoning", "permitting", "natural_resources"),
    "insurance": ("coverage", "underwriting", "claims", "bad_faith", "regulation", "reinsurance", "solvency"),
    "health_bioethics": ("healthcare_regulation", "privacy", "consent", "liability", "biotechnology"),
    "international": ("treaties", "customary_law", "state_responsibility", "jurisdiction", "international_courts"),
    "comparative": ("common_law", "civil_law", "mixed_systems", "customary_law", "religious_law"),
    "remedies_disputes": ("damages", "injunctions", "restitution", "arbitration", "mediation", "enforcement"),
    "professional_responsibility": ("confidentiality", "conflicts", "competence", "candor", "client_funds"),
    "legal_history": ("legal_institutions", "historical_doctrine", "codification", "constitutional_development"),
}


def _aware_iso(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LegalJurisdiction:
    jurisdiction_id: str
    name: str
    system_family: str
    parent_id: str | None = None
    jurisdiction_type: str = "national"

    def validate(self) -> None:
        if not self.jurisdiction_id.strip() or not self.name.strip():
            raise ValueError("jurisdiction id and name are required")
        if self.system_family not in {"common_law", "civil_law", "mixed", "customary", "religious", "supranational", "other"}:
            raise ValueError("unsupported legal system family")


@dataclass(frozen=True)
class LegalSource:
    source_id: str
    title: str
    source_type: str
    jurisdiction_id: str
    canonical_url: str
    retrieved_at: str
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    version_label: str = ""
    sha256: str = ""
    authority_status: str = "unknown"
    court_level: str | None = None
    citation: str | None = None
    permitted_use: str = "review_required"

    def validate(self) -> None:
        if not self.source_id.strip() or not self.title.strip() or not self.jurisdiction_id.strip():
            raise ValueError("source id, title and jurisdiction are required")
        if self.source_type not in LEGAL_SOURCE_TYPES:
            raise ValueError("unsupported legal source type")
        parsed = urlsplit(self.canonical_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("canonical_url must be HTTPS without embedded credentials")
        _aware_iso(self.retrieved_at, "retrieved_at")
        if self.published_at:
            _aware_iso(self.published_at, "published_at")
        for label, value in (("effective_from", self.effective_from), ("effective_to", self.effective_to)):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError as exc:
                    raise ValueError(f"{label} must be YYYY-MM-DD") from exc
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot precede effective_from")
        if self.authority_status not in AUTHORITY_STATUSES:
            raise ValueError("unsupported authority status")
        if self.sha256 and (len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256)):
            raise ValueError("sha256 must be a lowercase 64-character hex digest")
        if self.permitted_use not in {"public_link_only", "retain_allowed", "licensed", "review_required", "restricted"}:
            raise ValueError("unsupported permitted_use")


@dataclass(frozen=True)
class LegalProvision:
    provision_id: str
    source_id: str
    locator: str
    text: str
    effective_from: str | None = None
    effective_to: str | None = None

    def validate(self) -> None:
        if not all(v.strip() for v in (self.provision_id, self.source_id, self.locator, self.text)):
            raise ValueError("provision id, source, locator and text are required")
        for name, value in (("effective_from", self.effective_from), ("effective_to", self.effective_to)):
            if value:
                date.fromisoformat(value)
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("provision effective_to precedes effective_from")


@dataclass(frozen=True)
class Doctrine:
    doctrine_id: str
    name: str
    field: str
    jurisdiction_id: str
    summary: str
    elements: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all(v.strip() for v in (self.doctrine_id, self.name, self.field, self.jurisdiction_id, self.summary)):
            raise ValueError("doctrine identity, field, jurisdiction and summary are required")


@dataclass(frozen=True)
class LegalCase:
    case_id: str
    name: str
    court: str
    jurisdiction_id: str
    decision_date: str
    citation: str
    procedural_posture: str
    holding: str
    authority_status: str = "unknown"
    majority_author: str | None = None
    separate_opinions: tuple[str, ...] = ()
    subsequent_treatment_source_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all(v.strip() for v in (self.case_id, self.name, self.court, self.jurisdiction_id, self.citation, self.procedural_posture, self.holding)):
            raise ValueError("case identity, court, citation, posture and holding are required")
        date.fromisoformat(self.decision_date)
        if self.authority_status not in AUTHORITY_STATUSES:
            raise ValueError("unsupported case authority status")


@dataclass(frozen=True)
class LegalClaim:
    claim_id: str
    proposition: str
    jurisdiction_id: str
    as_of_date: str
    source_ids: tuple[str, ...] = ()
    provision_ids: tuple[str, ...] = ()
    case_ids: tuple[str, ...] = ()
    counterauthority_ids: tuple[str, ...] = ()
    status: str = "research_lead"
    confidence: float | None = None

    def validate(self) -> None:
        if not all(v.strip() for v in (self.claim_id, self.proposition, self.jurisdiction_id)):
            raise ValueError("claim identity, proposition and jurisdiction are required")
        date.fromisoformat(self.as_of_date)
        if self.status not in CLAIM_STATUSES:
            raise ValueError("unsupported claim status")
        if self.confidence is not None and (isinstance(self.confidence, bool) or not 0 <= self.confidence <= 1):
            raise ValueError("confidence must be between 0 and 1")
        if self.status == "independently_verified" and not self.counterauthority_ids:
            raise ValueError("independent verification requires an explicit counterauthority review record")


@dataclass(frozen=True)
class ResearchDossier:
    question: str
    jurisdiction_ids: tuple[str, ...]
    as_of_date: str
    fields: tuple[str, ...]
    required_sections: tuple[str, ...] = (
        "definition_and_purpose", "history", "elements_and_tests", "exceptions",
        "primary_authority", "secondary_scholarship", "jurisdictional_comparison",
        "application", "current_status", "uncertainty_register",
    )

    def validate(self) -> None:
        if not self.question.strip() or not self.jurisdiction_ids:
            raise ValueError("research question and at least one jurisdiction are required")
        date.fromisoformat(self.as_of_date)
        unknown = set(self.fields) - set(LEGAL_FIELDS)
        if unknown:
            raise ValueError("unknown legal fields: " + ", ".join(sorted(unknown)))
        if not self.required_sections:
            raise ValueError("dossier must have required research sections")


def claim_set_digest(claims: Iterable[LegalClaim]) -> str:
    """Stable digest over claims; it is an identity commitment, not a signature."""
    rows = []
    for claim in claims:
        claim.validate()
        rows.append({
            "claim_id": claim.claim_id, "proposition": claim.proposition,
            "jurisdiction_id": claim.jurisdiction_id, "as_of_date": claim.as_of_date,
            "source_ids": sorted(claim.source_ids), "provision_ids": sorted(claim.provision_ids),
            "case_ids": sorted(claim.case_ids), "counterauthority_ids": sorted(claim.counterauthority_ids),
        })
    canonical = json.dumps(sorted(rows, key=lambda row: row["claim_id"]), sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def validate_graph_references(*, sources: Iterable[LegalSource] = (),
                              provisions: Iterable[LegalProvision] = (),
                              cases: Iterable[LegalCase] = (),
                              claims: Iterable[LegalClaim] = (),
                              doctrines: Iterable[Doctrine] = ()) -> list[str]:
    """Validate graph referential integrity without asserting semantic truth."""
    source_rows, provision_rows = tuple(sources), tuple(provisions)
    case_rows, claim_rows, doctrine_rows = tuple(cases), tuple(claims), tuple(doctrines)
    source_ids = {x.source_id for x in source_rows}
    provision_ids = {x.provision_id for x in provision_rows}
    case_ids = {x.case_id for x in case_rows}
    errors: list[str] = []
    for source in source_rows:
        try: source.validate()
        except ValueError as exc: errors.append(f"source:{source.source_id}:{exc}")
    for provision in provision_rows:
        try: provision.validate()
        except ValueError as exc: errors.append(f"provision:{provision.provision_id}:{exc}")
        if provision.source_id not in source_ids:
            errors.append(f"provision:{provision.provision_id}:unknown_source:{provision.source_id}")
    for case in case_rows:
        try: case.validate()
        except ValueError as exc: errors.append(f"case:{case.case_id}:{exc}")
        unknown = set(case.subsequent_treatment_source_ids) - source_ids
        errors.extend(f"case:{case.case_id}:unknown_treatment_source:{item}" for item in sorted(unknown))
    for claim in claim_rows:
        try: claim.validate()
        except ValueError as exc: errors.append(f"claim:{claim.claim_id}:{exc}")
        for kind, refs, known in (
            ("source", claim.source_ids, source_ids),
            ("provision", claim.provision_ids, provision_ids),
            ("case", claim.case_ids, case_ids),
            ("counterauthority", claim.counterauthority_ids, case_ids | source_ids),
        ):
            errors.extend(f"claim:{claim.claim_id}:unknown_{kind}:{item}" for item in sorted(set(refs) - known))
    for doctrine in doctrine_rows:
        try: doctrine.validate()
        except ValueError as exc: errors.append(f"doctrine:{doctrine.doctrine_id}:{exc}")
    return errors


__all__ = [
    "AUTHORITY_STATUSES", "CLAIM_STATUSES", "LEGAL_FIELDS", "LEGAL_SOURCE_TYPES",
    "US_JURISDICTIONS", "Doctrine", "LegalCase", "LegalClaim", "LegalJurisdiction",
    "LegalProvision", "LegalSource", "ResearchDossier", "claim_set_digest",
    "sha256_text", "validate_graph_references",
]
