"""Deterministic quality gates for Merlin research claims and task outcomes."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Iterable
from urllib.parse import urlsplit


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    url: str
    captured_at: str
    content: bytes
    declared_sha256: str

    def errors(self) -> list[str]:
        result = []
        parts = urlsplit(self.url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            result.append("source URL must be HTTPS without embedded credentials")
        if not self.source_id.strip():
            result.append("source_id is required")
        try:
            stamp = datetime.fromisoformat(self.captured_at.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                result.append("captured_at must include timezone")
        except (TypeError, ValueError):
            result.append("captured_at must be ISO-8601")
        if sha256_bytes(self.content) != self.declared_sha256:
            result.append("source snapshot digest mismatch")
        return result


@dataclass(frozen=True)
class ClaimEvidence:
    source_id: str
    excerpt: str


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    text: str
    evidence: tuple[ClaimEvidence, ...] = ()


@dataclass(frozen=True)
class IndependentReview:
    reviewer_id: str
    subject_agent_id: str
    subject_digest: str
    verdict: str


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    content: bytes
    declared_sha256: str


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    description: str
    satisfied: bool
    evidence_artifact_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestResult:
    test_id: str
    status: str
    log_artifact_id: str


def verify_claims(claims: Iterable[ResearchClaim], sources: Iterable[SourceSnapshot],
                  *, producing_agent_id: str,
                  independent_review: IndependentReview | None = None) -> dict[str, object]:
    claims, sources = tuple(claims), tuple(sources)
    source_map = {source.source_id: source for source in sources}
    source_errors = {key: source.errors() for key, source in source_map.items()}
    rows = []
    for claim in claims:
        errors = []
        if not claim.claim_id.strip() or not claim.text.strip():
            errors.append("claim id and text are required")
        if not claim.evidence:
            errors.append("claim has no source evidence")
        checked = 0
        for evidence in claim.evidence:
            source = source_map.get(evidence.source_id)
            if source is None:
                errors.append("unknown source: " + evidence.source_id)
            elif source_errors[evidence.source_id]:
                errors.extend(source_errors[evidence.source_id])
            elif not evidence.excerpt.strip() or evidence.excerpt not in source.content.decode("utf-8", errors="replace"):
                errors.append("quoted excerpt is not present verbatim in source snapshot")
            else:
                checked += 1
        rows.append({"claim_id": claim.claim_id, "text": claim.text,
                     "status": "traceable" if checked and not errors else "unsubstantiated",
                     "verified_source_spans": checked, "errors": errors,
                     "semantic_truth": "not_established_by_provenance_check"})
    canonical = "\n".join(sorted(
        row["claim_id"] + "|" + row["text"] + "|" +
        "|".join(e.source_id + ":" + e.excerpt for e in claim.evidence)
        for row, claim in zip(rows, claims)
    ))
    subject_digest = sha256_bytes(canonical.encode())
    review_status = "not_reviewed"
    if independent_review:
        if independent_review.reviewer_id == producing_agent_id or independent_review.reviewer_id == independent_review.subject_agent_id:
            review_status = "invalid_self_review"
        elif independent_review.subject_agent_id != producing_agent_id:
            review_status = "review_subject_mismatch"
        elif independent_review.subject_digest != subject_digest:
            review_status = "review_digest_mismatch"
        elif independent_review.verdict not in {"supported", "rejected", "inconclusive"}:
            review_status = "invalid_verdict"
        else:
            review_status = independent_review.verdict
    return {
        "schema": "merlin-claim-verification/1",
        "producing_agent_id": producing_agent_id,
        "claim_count": len(rows),
        "traceable_claim_count": sum(r["status"] == "traceable" for r in rows),
        "unsubstantiated_claim_count": sum(r["status"] != "traceable" for r in rows),
        "claims": rows, "subject_digest": subject_digest,
        "independent_semantic_review": review_status,
        "truth_gate_passed": bool(rows) and all(r["status"] == "traceable" for r in rows) and review_status == "supported",
        "note": "Traceability does not prove semantic entailment; independent review must bind this exact claim set."
    }


def verify_work(*, task_id: str, producing_agent_id: str,
                artifacts: Iterable[Artifact], criteria: Iterable[AcceptanceCriterion],
                tests: Iterable[TestResult]) -> dict[str, object]:
    artifact_map = {a.artifact_id: a for a in artifacts}
    errors = {key: (["artifact digest mismatch"] if sha256_bytes(a.content) != a.declared_sha256 else [])
              for key, a in artifact_map.items()}
    criterion_rows = []
    for criterion in criteria:
        missing = [key for key in criterion.evidence_artifact_ids
                   if key not in artifact_map or errors.get(key)]
        criterion_rows.append({"criterion_id": criterion.criterion_id,
                               "description": criterion.description,
                               "satisfied": criterion.satisfied and bool(criterion.evidence_artifact_ids) and not missing,
                               "missing_or_invalid_artifacts": missing})
    test_rows = []
    for test in tests:
        log = artifact_map.get(test.log_artifact_id)
        valid_log = bool(log and not errors.get(test.log_artifact_id) and log.content)
        test_rows.append({"test_id": test.test_id, "status": test.status,
                          "log_artifact_id": test.log_artifact_id,
                          "log_present_and_valid": valid_log,
                          "passed": test.status == "passed" and valid_log})
    criteria_ok = bool(criterion_rows) and all(r["satisfied"] for r in criterion_rows)
    tests_ok = bool(test_rows) and all(r["passed"] for r in test_rows)
    integrity_ok = all(not v for v in errors.values())
    return {"schema": "merlin-work-verification/1", "task_id": task_id,
            "producing_agent_id": producing_agent_id, "artifact_count": len(artifact_map),
            "artifact_errors": errors, "acceptance_criteria": criterion_rows, "tests": test_rows,
            "artifact_integrity_passed": integrity_ok,
            "acceptance_criteria_passed": criteria_ok, "tests_passed_with_logs": tests_ok,
            "useful_work_gate_passed": bool(task_id.strip()) and integrity_ok and criteria_ok and tests_ok,
            "promotion_authority": False}


__all__ = ["AcceptanceCriterion", "Artifact", "ClaimEvidence", "IndependentReview",
           "ResearchClaim", "SourceSnapshot", "TestResult", "sha256_bytes",
           "verify_claims", "verify_work"]
