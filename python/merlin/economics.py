"""Evidence primitives for Merlin's economics and markets research.

This module is deliberately read-only: it scores source signals and research
candidates; it does not produce personalized investment advice or submit orders.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Any


PROMOTION_WEIGHTS = {
    "paid_referral_or_sponsorship": 20,
    "undisclosed_financial_or_issuer_exposure": 15,
    "urgency_or_scarcity_tactics": 15,
    "guaranteed_or_implausibly_certain_returns": 15,
    "unverifiable_performance_or_testimonials": 10,
    "selective_or_nonreproducible_backtests": 10,
    "no_independent_corroboration": 10,
    "repeated_calls_to_transact_or_upgrade": 5,
}

DEMAND_STAGES = {
    "proposal", "discussion", "authorization", "appropriation",
    "solicitation", "award", "obligation", "invoice", "delivery",
    "cancelled", "amended",
}

POSITIVE_OPPORTUNITY_DIMENSIONS = (
    "evidence_quality", "valuation_dispersion", "catalyst_strength",
    "balance_sheet_resilience", "liquidity",
)
RISK_OPPORTUNITY_DIMENSIONS = (
    "downside_severity", "model_uncertainty", "portfolio_correlation",
)


def score_promotional_pressure(
    signals: Mapping[str, bool | None],
) -> dict[str, Any]:
    """Return an explainable incentive-risk indicator with unknown coverage.

    True means evidence of the tactic/conflict was observed; False means it
    was checked and not observed; None or missing means unknown. Unknowns are
    excluded from the denominator and separately reduce coverage.
    """
    unknown_keys = set(signals) - set(PROMOTION_WEIGHTS)
    if unknown_keys:
        raise ValueError(f"unknown promotional signals: {sorted(unknown_keys)}")
    known_weight = 0
    observed_weight = 0
    factors: dict[str, str] = {}
    for key, weight in PROMOTION_WEIGHTS.items():
        value = signals.get(key)
        if value is not None and type(value) is not bool:
            raise ValueError(f"{key} must be true, false, or None")
        if value is None:
            factors[key] = "unknown"
            continue
        known_weight += weight
        if value:
            observed_weight += weight
            factors[key] = "observed"
        else:
            factors[key] = "not_observed"
    score = round(100 * observed_weight / known_weight, 2) if known_weight else None
    return {
        "score": score,
        "scale": "0-100 observed promotional-pressure indicator",
        "known_weight": known_weight,
        "evidence_coverage": round(known_weight / 100, 4),
        "observed_weight": observed_weight,
        "factors": factors,
        "interpretation": (
            "incentive and persuasion-risk signal; not a finding of fraud, dishonesty, or intent"
        ),
        "calibrated_probability": False,
    }


@dataclass(frozen=True)
class LocalDemandEvent:
    event_id: str
    jurisdiction: str
    source_url: str
    source_sha256: str
    meeting_date: str
    publication_date: str
    stage: str
    project: str
    location: str = ""
    industry_hypothesis: str = ""
    proposed_amount: float | None = None
    authorized_amount: float | None = None
    funding_source: str = ""
    status_note: str = ""

    def validate(self) -> None:
        required = (self.event_id, self.jurisdiction, self.source_url,
                    self.source_sha256, self.meeting_date, self.publication_date,
                    self.project)
        if any(not isinstance(value, str) or not value.strip() for value in required):
            raise ValueError("local demand event requires identity, provenance, dates, and project")
        if self.stage not in DEMAND_STAGES:
            raise ValueError("unsupported public-record event stage")
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256.lower()):
            raise ValueError("source_sha256 must be a 64-character hexadecimal digest")
        for amount in (self.proposed_amount, self.authorized_amount):
            if amount is not None and (not math.isfinite(amount) or amount < 0):
                raise ValueError("event amounts must be finite and non-negative")

    @property
    def evidence_label(self) -> str:
        if self.stage in {"proposal", "discussion"}:
            return "early public-sector pipeline signal; not approved demand"
        if self.stage in {"authorization", "appropriation", "solicitation", "award", "obligation"}:
            return "public-sector commitment-stage signal; verify amendments and actual outlays"
        if self.stage in {"invoice", "delivery"}:
            return "reported execution-stage evidence; verify payment and completion"
        return "status-change event; do not count as incremental demand without reconciliation"


def opportunity_dominates(a: Mapping[str, float], b: Mapping[str, float]) -> bool:
    """True when a is no worse than b on all dimensions and better on one."""
    dimensions = POSITIVE_OPPORTUNITY_DIMENSIONS + RISK_OPPORTUNITY_DIMENSIONS
    for key in dimensions:
        av, bv = a[key], b[key]
        if not (math.isfinite(av) and math.isfinite(bv) and 0 <= av <= 1 and 0 <= bv <= 1):
            raise ValueError(f"{key} must be finite and within [0,1]")
    no_worse = all(a[k] >= b[k] for k in POSITIVE_OPPORTUNITY_DIMENSIONS)
    no_worse = no_worse and all(a[k] <= b[k] for k in RISK_OPPORTUNITY_DIMENSIONS)
    strictly_better = any(a[k] > b[k] for k in POSITIVE_OPPORTUNITY_DIMENSIONS)
    strictly_better = strictly_better or any(a[k] < b[k] for k in RISK_OPPORTUNITY_DIMENSIONS)
    return no_worse and strictly_better


def opportunity_frontier(candidates: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return Pareto frontier and dominated candidates without inventing alpha."""
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip() or candidate_id in seen:
            raise ValueError("each candidate needs a unique non-empty candidate_id")
        seen.add(candidate_id)
        row = dict(candidate)
        for key in POSITIVE_OPPORTUNITY_DIMENSIONS + RISK_OPPORTUNITY_DIMENSIONS:
            if key not in row:
                raise ValueError(f"candidate {candidate_id} is missing {key}")
        normalized.append(row)
    frontier: list[dict[str, Any]] = []
    dominated: list[dict[str, Any]] = []
    for candidate in normalized:
        if any(
            other["candidate_id"] != candidate["candidate_id"]
            and opportunity_dominates(other, candidate)
            for other in normalized
        ):
            dominated.append(candidate)
        else:
            frontier.append(candidate)
    frontier.sort(key=lambda row: row["candidate_id"])
    dominated.sort(key=lambda row: row["candidate_id"])
    return {
        "method": "pareto_frontier",
        "frontier": frontier,
        "dominated": dominated,
        "note": "research triage only; not an expected-return forecast, suitability assessment, or trade instruction",
    }
