"""Evidence-first research utilities for Merlin.

This module deliberately generates testable candidates, not discoveries.
It is dependency-free and fails closed when evidence or analogy invariants are missing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Iterable


class EvidenceClass(str, Enum):
    AI_PROPOSAL = "AI_PROPOSAL"
    HYPOTHESIS_ONLY = "HYPOTHESIS_ONLY"
    RECONSTRUCTED_CONTEXT = "RECONSTRUCTED_CONTEXT"
    OBSERVED_DOCUMENT = "OBSERVED_DOCUMENT"
    ENGINEERING_VERIFIED = "ENGINEERING_VERIFIED"
    CERTIFIED_NUMERICAL = "CERTIFIED_NUMERICAL"
    PROVED = "PROVED"


_EVIDENCE_RANK = {item.value: i for i, item in enumerate(EvidenceClass)}
_REQUIRED_ARTIFACT = {
    EvidenceClass.ENGINEERING_VERIFIED.value: "test_log",
    EvidenceClass.CERTIFIED_NUMERICAL.value: "certificate",
    EvidenceClass.PROVED.value: "formal_receipt",
}


@dataclass(frozen=True)
class Claim:
    id: str
    statement: str
    evidence_class: str = EvidenceClass.AI_PROPOSAL.value
    method: str = "retrieved"
    sources: tuple[str, ...] = ()
    artifacts: tuple[dict[str, str], ...] = ()

    def validate(self) -> None:
        if self.evidence_class not in _EVIDENCE_RANK:
            raise ValueError("unknown evidence class")
        if not self.id.strip() or not self.statement.strip() or len(self.statement) > 2000:
            raise ValueError("claim requires a bounded id and statement")
        required = _REQUIRED_ARTIFACT.get(self.evidence_class)
        if required and not any(a.get("kind") == required and a.get("sha256") for a in self.artifacts):
            raise ValueError(f"{self.evidence_class} requires a hashed {required} artifact")


class EvidenceLedger:
    """Append-only in-memory claim ledger; promotions require hashed receipts."""

    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}

    def add(self, claim: Claim) -> None:
        claim.validate()
        previous = self._claims.get(claim.id)
        if previous and _EVIDENCE_RANK[claim.evidence_class] < _EVIDENCE_RANK[previous.evidence_class]:
            raise ValueError("claim downgrade rejected")
        self._claims[claim.id] = claim

    def promote(self, claim_id: str, evidence_class: str, artifact: dict[str, str]) -> Claim:
        if claim_id not in self._claims:
            raise KeyError(claim_id)
        current = self._claims[claim_id]
        if evidence_class not in _EVIDENCE_RANK or _EVIDENCE_RANK[evidence_class] <= _EVIDENCE_RANK[current.evidence_class]:
            raise ValueError("promotion must increase evidence class")
        promoted = Claim(
            id=current.id, statement=current.statement, evidence_class=evidence_class,
            method=current.method, sources=current.sources, artifacts=current.artifacts + (artifact,),
        )
        promoted.validate()
        self._claims[claim_id] = promoted
        return promoted

    def all(self) -> list[Claim]:
        return sorted(self._claims.values(), key=lambda c: (-_EVIDENCE_RANK[c.evidence_class], c.id))


@dataclass(frozen=True)
class Idea:
    title: str
    mechanism: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    observable: str
    falsifier: str
    novelty: float = 0.5
    feasibility: float = 0.5
    evidence_fit: float = 0.5
    testability: float = 0.5
    resource_cost: float = 0.5
    source_domains: tuple[str, ...] = ()

    def validate(self) -> None:
        required = (self.title, self.mechanism, self.observable, self.falsifier)
        if any(not isinstance(v, str) or not v.strip() for v in required):
            raise ValueError("idea lacks a mechanism, observable, or falsifier")
        if not self.assumptions or not self.constraints:
            raise ValueError("idea must state assumptions and constraints")
        for value in (self.novelty, self.feasibility, self.evidence_fit, self.testability, self.resource_cost):
            if not 0 <= value <= 1:
                raise ValueError("idea scores must be within [0,1]")
        if len(self.title) > 180 or len(self.mechanism) > 1200:
            raise ValueError("idea exceeds bounded length")


def rank_ideas(ideas: Iterable[Idea], limit: int = 8) -> dict[str, Any]:
    """Reject incomplete candidates, then rank by transparent weighted criteria."""
    if type(limit) is not int or not 1 <= limit <= 30:
        raise ValueError("limit must be an integer in [1,30]")
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()
    for idea in ideas:
        try:
            idea.validate()
        except (ValueError, TypeError) as exc:
            rejected.append({"title": getattr(idea, "title", "(invalid)"), "reason": str(exc)})
            continue
        key = re.sub(r"\W+", " ", idea.title.lower()).strip()
        if key in seen:
            rejected.append({"title": idea.title, "reason": "duplicate candidate"})
            continue
        seen.add(key)
        score = (
            0.15 * idea.novelty
            + 0.25 * idea.feasibility
            + 0.20 * idea.evidence_fit
            + 0.30 * idea.testability
            + 0.10 * (1.0 - idea.resource_cost)
        )
        accepted.append({
            **asdict(idea),
            "score": round(score, 6),
            "evidence_class": EvidenceClass.HYPOTHESIS_ONLY.value,
            "status": "RESEARCH_CANDIDATE",
        })
    accepted.sort(key=lambda row: (-row["score"], row["title"].lower()))
    for index, row in enumerate(accepted, 1):
        row["rank"] = index
    payload: dict[str, Any] = {
        "schema": "merlin-ideonomy/1",
        "ranking_weights": {
            "novelty": 0.15, "feasibility": 0.25, "evidence_fit": 0.20,
            "testability": 0.30, "resource_efficiency": 0.10,
        },
        "accepted": accepted[:limit],
        "rejected": rejected,
        "note": "Candidate generation is not evidence of alien knowledge or scientific discovery.",
    }
    payload["sha256"] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


@dataclass(frozen=True)
class AnalogyMap:
    source_problem: str
    target_problem: str
    entity_mapping: dict[str, str]
    operation_mapping: dict[str, str]
    required_invariants: tuple[str, ...]
    preserved_invariants: tuple[str, ...]
    source_boundary_conditions: tuple[str, ...]
    target_boundary_conditions: tuple[str, ...]
    known_failure_modes: tuple[str, ...] = ()


def validate_analogy(mapping: AnalogyMap) -> dict[str, Any]:
    """A reframe is accepted only when every declared invariant and boundary maps."""
    missing = sorted(set(mapping.required_invariants) - set(mapping.preserved_invariants))
    unmapped_entities = sorted(k for k, v in mapping.entity_mapping.items() if not v.strip())
    unmapped_operations = sorted(k for k, v in mapping.operation_mapping.items() if not v.strip())
    boundary_mismatch = not mapping.source_boundary_conditions or not mapping.target_boundary_conditions
    reasons: list[str] = []
    if not mapping.source_problem.strip() or not mapping.target_problem.strip():
        reasons.append("source and target problems must be named")
    if not mapping.entity_mapping:
        reasons.append("entity mapping is empty")
    if not mapping.operation_mapping:
        reasons.append("operation mapping is empty")
    if missing:
        reasons.append("unpreserved invariants: " + ", ".join(missing))
    if unmapped_entities:
        reasons.append("unmapped entities: " + ", ".join(unmapped_entities))
    if unmapped_operations:
        reasons.append("unmapped operations: " + ", ".join(unmapped_operations))
    if boundary_mismatch:
        reasons.append("both source and target boundary conditions must be explicit")
    if not mapping.known_failure_modes:
        reasons.append("failure modes have not been enumerated")
    return {
        "schema": "merlin-analogy-check/1",
        "accepted": not reasons,
        "reasons": reasons,
        "preserved_invariants": sorted(set(mapping.required_invariants) & set(mapping.preserved_invariants)),
        "failure_modes": list(mapping.known_failure_modes),
        "rule": "Solve the simpler target only after the mapping passes; translate back and test against the original problem.",
    }


@dataclass(frozen=True)
class PromotionPacket:
    tests_passed: bool
    independent_review: bool
    held_out_qualification: bool
    rollback_ready: bool
    authority_unchanged: bool
    human_approval: bool
    compute_budget_respected: bool


def qualify_rsi_candidate(packet: PromotionPacket) -> dict[str, Any]:
    checks = asdict(packet)
    failed = [name for name, passed in checks.items() if passed is not True]
    return {
        "schema": "merlin-rsi-gate/1",
        "eligible_for_human_promotion_review": not failed,
        "status": "PASS" if not failed else "BLOCKED",
        "failed_gates": failed,
        "authority_expansion": False,
        "automatic_promotion": False,
    }
