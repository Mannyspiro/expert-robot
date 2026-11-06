"""Insurance knowledge and product-comparison primitives for Merlin.

Offline-first and evidence-led. This module does not quote, bind, cancel,
underwrite, adjust claims, or provide legal advice. A carrier score is emitted
only from explicit, comparable evidence supplied by an authorized caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import urlsplit


JURISDICTIONS = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
)

# Preserve the user's previously defined agency scope. These are research
# eligibility boundaries, not a representation of current producer appointments.
AGENCY_SCOPE = {
    "AZ": frozenset({"personal_p_and_c", "commercial_p_and_c"}),
    "CA": frozenset({"personal_p_and_c"}),
    "FL": frozenset({"personal_p_and_c"}),
    "GA": frozenset({"personal_p_and_c"}),
    "NY": frozenset({"personal_p_and_c"}),
    "TX": frozenset({"personal_p_and_c"}),
}


PERSONAL_PRODUCTS = (
    "private_passenger_auto", "homeowners", "renters", "condominium",
    "landlord_dwelling_fire", "manufactured_home", "personal_umbrella",
    "flood_nfip", "private_flood", "earthquake", "scheduled_personal_property",
    "motorcycle", "recreational_vehicle", "watercraft", "personal_cyber",
    "identity_fraud", "pet", "travel", "title",
)

COMMERCIAL_PRODUCTS = (
    "businessowners_policy", "commercial_package", "commercial_property",
    "commercial_general_liability", "commercial_auto", "workers_compensation",
    "employers_liability", "commercial_umbrella_excess", "professional_eo",
    "directors_officers", "employment_practices_liability", "cyber",
    "crime_fidelity", "inland_marine", "builders_risk", "equipment_breakdown",
    "business_interruption", "contingent_business_interruption", "cargo",
    "ocean_marine", "pollution_environmental", "product_liability",
    "liquor_liability", "garagekeepers", "dealers_open_lot", "surety_bonds",
    "fiduciary_liability", "event_cancellation", "aviation", "farm_ranch",
)

POLICY_REVIEW_ISSUES = (
    "actual_cash_value_vs_replacement_cost",
    "roof_payment_schedule_and_cosmetic_damage",
    "water_backup_vs_surface_flood",
    "earth_movement_and_earthquake",
    "ordinance_or_law_and_code_upgrade",
    "matching_and_pair_or_set_limits",
    "mold_fungi_rot_and_continuous_seepage",
    "vacancy_unoccupancy_and_unprotected_property",
    "wear_tear_maintenance_and_prior_damage",
    "business_personal_property_off_premises",
    "business_income_waiting_period_and_period_of_restoration",
    "dependent_property_and_contingent_business_interruption",
    "coinsurance_and_margin_clause",
    "valuation_agreed_value_stated_value_and_functional_replacement",
    "deductible_percentage_wind_hail_named_storm",
    "sublimits_aggregates_and_erosion",
    "defense_inside_or_outside_limits",
    "claims_made_retroactive_date_and_extended_reporting",
    "consent_to_settle_and_hammer_clause",
    "additional_insured_primary_noncontributory_and_waiver",
    "employee_exclusion_and_independent_contractor_classification",
    "audit_premium_payroll_sales_and_subcontractor_cost",
    "cyber_war_systemic_event_and_social_engineering_exclusions",
    "pollution_silica_asbestos_and_microbe_exclusions",
    "auto_symbol_schedule_driver_and_garaging_restrictions",
    "underinsurance_inflation_guard_and_reconstruction_cost",
    "notice_of_loss_proof_of_loss_and_cooperation_conditions",
    "appraisal_arbitration_suit_limitation_and_choice_of_law",
    "cancellation_nonrenewal_and_midterm_restrictions",
)

CONDUCT_PATTERNS = (
    "coverage_or_exclusion_misrepresentation",
    "unreasonable_claim_delay",
    "inadequate_investigation",
    "unsupported_low_estimate_or_scope",
    "failure_to_explain_partial_denial",
    "inconsistent_comparable_claim_treatment",
    "unreasonable_document_requests",
    "unfair_cancellation_or_nonrenewal",
    "premium_or_refund_error",
    "misleading_discount_or_bundle_presentation",
    "undisclosed_compensation_or_conflict",
    "unfair_claim_vendor_or_network_pressure",
    "unfair_underwriting_or_rating",
    "unreasonable_rescission_or_reformation",
    "failure_to_pay undisputed_amounts",
)

# International comparison is descriptive; local custom is not a substitute
# for local law, product wording, or a licensed local professional.
INTERNATIONAL_SYSTEMS = (
    "Lloyds_market_subscription_and_delegated_authority",
    "mutual_and_cooperative_insurance",
    "takaful_sharia_compliant_risk_sharing",
    "microinsurance_and_informal_risk_pools",
    "state_social_insurance_and_public_private_layers",
    "parametric_and_index_based_cover",
    "catastrophe_pools_and_national_reinsurance_facilities",
    "civil_law_vs_common_law_contract_interpretation",
    "cross_border_motor_green_card_and_frontier_systems",
    "cultural_attitudes_to_household_risk_family_and_community_support",
)


@dataclass(frozen=True)
class InsuranceEvidence:
    evidence_id: str
    source_url: str
    jurisdiction: str
    product: str
    topic: str
    evidence_type: str
    finding_status: str
    published_at: str
    retrieved_at: str
    source_hash: str = ""

    def validate(self) -> None:
        if not self.evidence_id.strip() or not self.topic.strip():
            raise ValueError("evidence_id and topic are required")
        if self.jurisdiction not in JURISDICTIONS:
            raise ValueError("jurisdiction must be a US state or DC code")
        parsed = urlsplit(self.source_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("source_url must be HTTPS")
        allowed_types = {
            "statute", "regulation", "regulator_bulletin", "policy_form",
            "endorsement", "court_decision", "market_conduct_report",
            "complaint_aggregate", "financial_filing", "actuarial_study",
            "academic_research", "carrier_marketing", "consumer_testimony",
        }
        if self.evidence_type not in allowed_types:
            raise ValueError("unsupported evidence_type")
        allowed_statuses = {
            "verified_fact", "documented_practice", "allegation",
            "contractual_design", "industry_pattern", "disputed",
            "historical_context", "not_yet_verified",
        }
        if self.finding_status not in allowed_statuses:
            raise ValueError("unsupported finding_status")
        for name, value in (("published_at", self.published_at), ("retrieved_at", self.retrieved_at)):
            try:
                parsed_time = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"{name} must be ISO-8601") from exc
            if parsed_time.tzinfo is None:
                raise ValueError(f"{name} must include a timezone")


@dataclass(frozen=True)
class InsurerProductEvidence:
    legal_entity: str
    naic_company_code: str
    jurisdiction: str
    product: str
    admitted_status: str
    price_score: float | None = None
    coverage_score: float | None = None
    claims_service_score: float | None = None
    complaint_score: float | None = None
    financial_strength_score: float | None = None
    availability_score: float | None = None
    evidence_ids: tuple[str, ...] = ()


DEFAULT_WEIGHTS = {
    "price_score": 0.15,
    "coverage_score": 0.25,
    "claims_service_score": 0.20,
    "complaint_score": 0.15,
    "financial_strength_score": 0.15,
    "availability_score": 0.10,
}


def compare_insurer_products(
    profiles: list[InsurerProductEvidence],
    *,
    weights: Mapping[str, float] = DEFAULT_WEIGHTS,
) -> list[dict[str, object]]:
    """Rank comparable evidence; incomplete profiles remain explicitly unranked.

    All component scores use 0-100 where higher is better. Complaint score must
    be normalized so fewer/better complaints yield a higher score. Never infer
    a quote, policy form, or financial rating that was not supplied.
    """
    if not weights or any(key not in DEFAULT_WEIGHTS for key in weights):
        raise ValueError("weights must use supported score dimensions")
    if any(value < 0 for value in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("weights must be non-negative and sum to more than zero")
    total_weight = sum(weights.values())
    results = []
    for profile in profiles:
        if profile.jurisdiction not in JURISDICTIONS:
            raise ValueError("profile jurisdiction must be a US state or DC code")
        scores = {}
        for key in weights:
            value = getattr(profile, key)
            if value is not None:
                if isinstance(value, bool) or not 0 <= value <= 100:
                    raise ValueError(f"{key} must be between 0 and 100")
                scores[key] = float(value)
        present_weight = sum(weights[key] for key in scores)
        completeness = present_weight / total_weight
        comparable = bool(scores) and abs(present_weight - total_weight) < 1e-9
        weighted = (
            sum(scores[key] * weights[key] for key in scores) / present_weight
            if present_weight else None
        )
        results.append({
            "legal_entity": profile.legal_entity,
            "naic_company_code": profile.naic_company_code,
            "jurisdiction": profile.jurisdiction,
            "product": profile.product,
            "admitted_status": profile.admitted_status,
            "weighted_score": round(weighted, 2) if comparable and weighted is not None else None,
            "evidence_completeness": round(completeness, 4),
            "rankable": comparable,
            "missing_dimensions": [key for key in weights if key not in scores],
            "evidence_ids": list(profile.evidence_ids),
            "interpretation": (
                "comparable research score; not a purchase recommendation"
                if comparable else "insufficient comparable evidence; do not rank"
            ),
        })
    return sorted(
        results,
        key=lambda row: (
            row["rankable"],
            row["weighted_score"] if row["weighted_score"] is not None else -1,
            row["evidence_completeness"],
        ),
        reverse=True,
    )


def agency_scope_for(jurisdiction: str) -> tuple[str, ...]:
    """Return previously stated intended research scope, not live license status."""
    if jurisdiction not in JURISDICTIONS:
        raise ValueError("unknown US jurisdiction")
    return tuple(sorted(AGENCY_SCOPE.get(jurisdiction, frozenset())))


__all__ = [
    "AGENCY_SCOPE", "COMMERCIAL_PRODUCTS", "CONDUCT_PATTERNS",
    "DEFAULT_WEIGHTS", "INTERNATIONAL_SYSTEMS", "InsurerProductEvidence",
    "InsuranceEvidence", "JURISDICTIONS", "PERSONAL_PRODUCTS",
    "POLICY_REVIEW_ISSUES", "agency_scope_for", "compare_insurer_products",
]
