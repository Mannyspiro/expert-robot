import unittest

from merlin.insurance_intelligence import (
    AGENCY_SCOPE, JURISDICTIONS, InsurerProductEvidence, InsuranceEvidence,
    agency_scope_for, compare_insurer_products,
)


class InsuranceEvidenceTests(unittest.TestCase):
    def test_full_us_jurisdiction_coverage(self):
        self.assertEqual(len(JURISDICTIONS), 51)
        self.assertEqual(len(set(JURISDICTIONS)), 51)

    def test_preserves_existing_agency_scope(self):
        self.assertEqual(set(agency_scope_for("AZ")), {"personal_p_and_c", "commercial_p_and_c"})
        self.assertEqual(set(agency_scope_for("TX")), {"personal_p_and_c"})
        self.assertEqual(agency_scope_for("CA"), ("personal_p_and_c",))
        self.assertEqual(agency_scope_for("OR"), ())

    def test_evidence_rejects_unverified_or_bad_source_shapes(self):
        item = InsuranceEvidence(
            evidence_id="AZ-STAT-20-461", source_url="https://www.azleg.gov/ars/20/00461.htm",
            jurisdiction="AZ", product="commercial_general_liability", topic="claim handling",
            evidence_type="statute", finding_status="verified_fact",
            published_at="2026-01-01T00:00:00Z", retrieved_at="2026-11-06T00:00:00Z",
        )
        item.validate()
        bad = InsuranceEvidence(
            evidence_id="x", source_url="http://example.com", jurisdiction="AZ",
            product="auto", topic="test", evidence_type="statute",
            finding_status="verified_fact", published_at="2026-01-01T00:00:00Z",
            retrieved_at="2026-11-06T00:00:00Z",
        )
        with self.assertRaises(ValueError):
            bad.validate()

    def test_only_complete_comparable_profiles_are_ranked(self):
        complete = InsurerProductEvidence(
            legal_entity="Example Insurance Company", naic_company_code="12345",
            jurisdiction="AZ", product="homeowners", admitted_status="admitted",
            price_score=80, coverage_score=90, claims_service_score=85,
            complaint_score=88, financial_strength_score=90, availability_score=80,
            evidence_ids=("FORM-1", "COMPLAINT-1"),
        )
        incomplete = InsurerProductEvidence(
            legal_entity="Another Company", naic_company_code="54321",
            jurisdiction="AZ", product="homeowners", admitted_status="surplus_lines",
            price_score=95, coverage_score=90,
        )
        ranked = compare_insurer_products([incomplete, complete])
        self.assertEqual(ranked[0]["legal_entity"], "Example Insurance Company")
        self.assertTrue(ranked[0]["rankable"])
        self.assertFalse(ranked[1]["rankable"])
        self.assertIsNone(ranked[1]["weighted_score"])

    def test_invalid_score_rejected(self):
        profile = InsurerProductEvidence(
            legal_entity="Example", naic_company_code="1", jurisdiction="AZ",
            product="auto", admitted_status="admitted", price_score=101,
        )
        with self.assertRaises(ValueError):
            compare_insurer_products([profile])


if __name__ == "__main__":
    unittest.main()
