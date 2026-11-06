"""Traceable partner evidence ingestion, ranking, RFP clauses, proposal claims and learning.

This module deliberately does not scrape interactive DIFI/NAIC pages or infer
license status. It accepts dated observations captured from official public
records and preserves the exact source URL and record identifier.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from hashlib import sha256
import re
from typing import Iterable


def _https(url: str) -> None:
    if not url.startswith("https://") or len(url) <= 8:
        raise ValueError("source must be an absolute HTTPS URL")


def _date(value: str) -> None:
    date.fromisoformat(value)


@dataclass(frozen=True)
class LicenseObservation:
    subject_id: str
    subject_type: str  # entity | individual
    legal_name: str
    license_number: str
    license_type: str
    lines_of_authority: tuple[str, ...]
    status: str  # active | inactive | expired | suspended | unknown
    observed_on: str
    effective_on: str | None
    source_url: str
    source_record_id: str
    source_system: str = "Arizona DIFI / NAIC State Based Systems"
    raw_record_sha256: str | None = None

    def __post_init__(self):
        if self.subject_type not in {"entity", "individual"}:
            raise ValueError("subject_type must be entity or individual")
        if self.status not in {"active", "inactive", "expired", "suspended", "unknown"}:
            raise ValueError("invalid license status")
        if not all((self.subject_id, self.legal_name, self.license_number,
                    self.license_type, self.source_record_id)):
            raise ValueError("license identity and source record fields are required")
        _date(self.observed_on)
        if self.effective_on:
            _date(self.effective_on)
        _https(self.source_url)
        if self.raw_record_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.raw_record_sha256):
            raise ValueError("raw_record_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class PublicContractEvidence:
    evidence_id: str
    partner_id: str
    evidence_kind: str  # award | cooperative_contract | performance_reference
    buyer: str
    contract_number: str
    title: str
    status: str
    start_date: str | None
    end_date: str | None
    observed_on: str
    source_url: str
    source_record_id: str
    supplier_legal_name: str
    scope_summary: str = ""
    performance_verified: bool = False

    def __post_init__(self):
        if self.evidence_kind not in {"award", "cooperative_contract", "performance_reference"}:
            raise ValueError("unsupported contract evidence kind")
        for d in (self.start_date, self.end_date, self.observed_on):
            if d:
                _date(d)
        _https(self.source_url)
        if not all((self.evidence_id, self.partner_id, self.buyer,
                    self.contract_number, self.source_record_id, self.supplier_legal_name)):
            raise ValueError("contract identity and provenance are required")


def ingest_difi_normalized_csv(
    csv_text: str, observed_on: str, source_url: str,
) -> tuple[LicenseObservation, ...]:
    """Import a user/agent-exported DIFI/SBS public lookup CSV.

    The CSV must be normalized to the explicit field names below. This is
    intentionally not a guessed scraper for the interactive SBS website.
    """
    _date(observed_on)
    _https(source_url)
    required = {
        "subject_id", "subject_type", "legal_name", "license_number",
        "license_type", "lines_of_authority", "status", "source_record_id",
    }
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("DIFI export missing required normalized columns")
    rows = []
    for row in reader:
        lines = tuple(x.strip() for x in (row.get("lines_of_authority") or "").split(";") if x.strip())
        rows.append(LicenseObservation(
            subject_id=row["subject_id"].strip(),
            subject_type=row["subject_type"].strip().lower(),
            legal_name=row["legal_name"].strip(),
            license_number=row["license_number"].strip(),
            license_type=row["license_type"].strip(),
            lines_of_authority=lines,
            status=row["status"].strip().lower(),
            observed_on=observed_on,
            effective_on=(row.get("effective_on") or "").strip() or None,
            source_url=source_url,
            source_record_id=row["source_record_id"].strip(),
            raw_record_sha256=sha256(",".join(row.get(k, "") or "" for k in reader.fieldnames).encode("utf-8")).hexdigest(),
        ))
    return tuple(rows)


def ingest_public_contract_records(records: Iterable[dict]) -> tuple[PublicContractEvidence, ...]:
    """Convert normalized official award/co-op records to graph evidence."""
    return tuple(PublicContractEvidence(**record) for record in records)


RELATIONSHIP_TYPES = {
    "competitor", "capability_benchmark", "potential_prime",
    "potential_subcontractor", "referral_source",
}


@dataclass(frozen=True)
class PartnerSignal:
    partner_id: str
    legal_name: str
    relationship: str
    evidence_ids: tuple[str, ...] = ()
    capability_tags: tuple[str, ...] = ()
    observed_on: str = ""

    def __post_init__(self):
        if self.relationship not in RELATIONSHIP_TYPES:
            raise ValueError("unsupported relationship type")
        if not self.partner_id or not self.legal_name:
            raise ValueError("partner identity required")
        if self.observed_on:
            _date(self.observed_on)


@dataclass(frozen=True)
class PartnerRank:
    partner_id: str
    relationship: str
    score: float
    rationale: tuple[str, ...]
    qualification_state: str


def rank_partners(
    partners: Iterable[PartnerSignal],
    contracts: Iterable[PublicContractEvidence],
    licenses: Iterable[LicenseObservation],
) -> tuple[PartnerRank, ...]:
    """Rank within relationship cohorts; never compare a competitor as a bidder."""
    contract_rows = tuple(contracts)
    license_rows = tuple(licenses)
    results = []
    for p in partners:
        rationale = [f"relationship cohort: {p.relationship}"]
        relevant_contracts = [c for c in contract_rows if c.partner_id == p.partner_id]
        relevant_licenses = [l for l in license_rows if l.subject_id == p.partner_id]
        verified_awards = [c for c in relevant_contracts if c.evidence_kind == "award"]
        coop = [c for c in relevant_contracts if c.evidence_kind == "cooperative_contract"]
        active = [l for l in relevant_licenses if l.status == "active"]
        score = 0.0
        if verified_awards:
            score += min(35.0, 15.0 * len(verified_awards))
            rationale.append(f"{len(verified_awards)} public award record(s) linked")
        if coop:
            score += min(20.0, 10.0 * len(coop))
            rationale.append(f"{len(coop)} cooperative contract record(s) linked")
        if active:
            score += min(25.0, 8.0 * len(active))
            rationale.append(f"{len(active)} active official license observation(s)")
        if not relevant_contracts:
            rationale.append("no linked public contract record")
        if not relevant_licenses:
            rationale.append("no linked official license observation")
        if p.relationship in {"competitor", "capability_benchmark"}:
            state = "benchmark_only"
        else:
            state = "unqualified_pending_evidence"
        # Performance-reference scoring requires an explicit verified flag.
        verified_refs = [c for c in relevant_contracts
                         if c.evidence_kind == "performance_reference" and c.performance_verified]
        if verified_refs:
            score += min(20.0, 10.0 * len(verified_refs))
            rationale.append(f"{len(verified_refs)} verified performance reference(s)")
        results.append(PartnerRank(p.partner_id, p.relationship, score,
                                   tuple(rationale), state))
    return tuple(sorted(results, key=lambda x: (x.relationship, -x.score, x.partner_id)))


@dataclass(frozen=True)
class RfpClause:
    solicitation_id: str
    clause_id: str
    heading: str
    text: str
    source_url: str
    document_sha256: str
    document_name: str
    observed_on: str
    is_addendum: bool = False

    def __post_init__(self):
        _https(self.source_url)
        _date(self.observed_on)
        if not re.fullmatch(r"[0-9a-f]{64}", self.document_sha256):
            raise ValueError("document_sha256 must be lowercase SHA-256")
        if not all((self.solicitation_id, self.clause_id, self.text, self.document_name)):
            raise ValueError("clause and document identity required")


def ingest_rfp_text(
    solicitation_id: str, document_name: str, source_url: str,
    extracted_text: str, observed_on: str, is_addendum: bool = False,
) -> tuple[RfpClause, ...]:
    """Split already-extracted official text into clause-linked evidence.

    PDF/DOCX extraction is an upstream adapter. The source bytes should be
    hashed before extraction; this function hashes the exact extracted text
    as an additional reproducibility identifier.
    """
    _https(source_url)
    _date(observed_on)
    digest = sha256(extracted_text.encode("utf-8")).hexdigest()
    lines = extracted_text.splitlines()
    clauses = []
    current_id, heading, body = "document-intro", document_name, []
    def flush():
        if body and "\\n".join(body).strip():
            clauses.append(RfpClause(
                solicitation_id, current_id, heading, "\\n".join(body).strip(),
                source_url, digest, document_name, observed_on, is_addendum,
            ))
    for line in lines:
        s = line.strip()
        m = re.match(r"^(?:section\\s+)?([0-9]+(?:\\.[0-9]+)*|[A-Z]\\.?[0-9]+)\\s+(.+)$", s, re.I)
        if m:
            flush()
            current_id, heading, body = m.group(1), m.group(2), [s]
        elif s:
            body.append(s)
    flush()
    return tuple(clauses)


@dataclass(frozen=True)
class ProposalClaim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]
    claim_kind: str = "capability"  # capability | past_performance | license | pricing | compliance


@dataclass(frozen=True)
class ClaimDecision:
    claim_id: str
    state: str
    reasons: tuple[str, ...]


class ProposalEvidenceVault:
    """Claims are blocked unless each has at least one registered source artifact."""
    def __init__(self):
        self._sources: dict[str, tuple[str, str, str]] = {}
        self._claims: dict[str, ProposalClaim] = {}

    def add_source(self, evidence_id: str, source_url: str, source_sha256: str,
                   source_type: str) -> None:
        _https(source_url)
        if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
            raise ValueError("source_sha256 must be lowercase SHA-256")
        if not evidence_id or not source_type:
            raise ValueError("source identity and type required")
        self._sources[evidence_id] = (source_url, source_sha256, source_type)

    def add_claim(self, claim: ProposalClaim) -> ClaimDecision:
        if not claim.claim_id or not claim.text.strip():
            raise ValueError("claim identity and text required")
        self._claims[claim.claim_id] = claim
        missing = [eid for eid in claim.evidence_ids if eid not in self._sources]
        if not claim.evidence_ids:
            return ClaimDecision(claim.claim_id, "blocked", ("claim has no source evidence",))
        if missing:
            return ClaimDecision(claim.claim_id, "blocked",
                                 ("unregistered evidence ids: " + ", ".join(missing),))
        return ClaimDecision(claim.claim_id, "human_review_required",
                             ("source provenance attached; claim accuracy and proposal approval require human review",))

    def source_map(self, claim_id: str) -> tuple[tuple[str, str, str, str], ...]:
        claim = self._claims[claim_id]
        return tuple((eid, *self._sources[eid]) for eid in claim.evidence_ids if eid in self._sources)


@dataclass(frozen=True)
class LearningObservation:
    source_id: str
    source_correct: bool | None
    qualification_outcome: str | None
    partner_performance: float | None
    proposal_outcome: str | None
    private_data_included: bool = False


def aggregate_learning(observations: Iterable[LearningObservation]) -> dict:
    """Aggregate only non-private outcomes; never persist raw applicant/person data."""
    rows = [o for o in observations if not o.private_data_included]
    source_rows = [o.source_correct for o in rows if o.source_correct is not None]
    return {
        "observations_count": len(rows),
        "source_accuracy": (sum(source_rows) / len(source_rows)) if source_rows else None,
        "qualification_outcomes": _counts(o.qualification_outcome for o in rows),
        "proposal_outcomes": _counts(o.proposal_outcome for o in rows),
        "mean_partner_performance": (
            sum(o.partner_performance for o in rows if o.partner_performance is not None)
            / len([o for o in rows if o.partner_performance is not None])
            if any(o.partner_performance is not None for o in rows) else None
        ),
        "authority_change": "none",
        "human_approval_required": True,
        "private_rows_excluded": sum(1 for o in observations if o.private_data_included),
    }


def _counts(values: Iterable[str | None]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        if value is not None:
            result[value] = result.get(value, 0) + 1
    return result
