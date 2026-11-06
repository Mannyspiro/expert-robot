import unittest
from datetime import date

from merlin.opportunity_intelligence import (
    ApplicantProfile, Opportunity, evaluate_opportunity, rank_opportunities,
)


class OpportunityIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.applicant = ApplicantProfile(
            applicant_type="individual",
            jurisdictions=("Arizona", "Tucson"),
            age=30,
            enrolled=True,
            fields=("technology", "computer_science"),
            credentials=("Harvard CS50", "Google coursework", "Bloomberg Terminal certification"),
            identity_attributes=("woman", "Latina", "trans"),
            priorities=("technology", "community"),
        )

    def make_opportunity(self, **kwargs):
        base = dict(
            opportunity_id="scholarship-1",
            title="Technology Scholarship",
            opportunity_type="scholarship",
            applicant_types=("individual",),
            source_url="https://example.org/program",
            source_name="Program owner",
            source_confidence="official",
            status="open",
            deadline="2026-12-31",
            jurisdictions=("Arizona",),
            eligible_fields=("technology",),
            enrollment_required=True,
            last_verified="2026-11-05",
        )
        base.update(kwargs)
        return Opportunity(**base)

    def test_eligible_when_all_required_facts_are_verified(self):
        result = evaluate_opportunity(self.make_opportunity(), self.applicant,
                                      date(2026, 11, 5))
        self.assertEqual(result.eligibility, "eligible")
        self.assertGreaterEqual(result.score, 80)

    def test_individual_cannot_claim_organization_only_grant(self):
        item = self.make_opportunity(
            opportunity_type="grant",
            applicant_types=("nonprofit",),
            organization_required=True,
        )
        result = evaluate_opportunity(item, self.applicant, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "ineligible")
        self.assertTrue(any("applicant type" in x for x in result.blockers))

    def test_missing_student_status_is_conditional_not_invented(self):
        profile = ApplicantProfile(applicant_type="individual", jurisdictions=("Arizona",),
                                   enrolled=None, fields=("technology",))
        result = evaluate_opportunity(self.make_opportunity(), profile, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "conditional")
        self.assertIn("student enrollment status not verified", result.verification_required)

    def test_passed_deadline_blocks(self):
        result = evaluate_opportunity(self.make_opportunity(deadline="2026-10-01"),
                                      self.applicant, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "ineligible")
        self.assertIn("listed deadline has passed", result.blockers)

    def test_identity_criteria_are_explicit_and_opt_in(self):
        item = self.make_opportunity(identity_criteria=("Latina", "trans"))
        no_identity = ApplicantProfile(applicant_type="individual", jurisdictions=("Arizona",),
                                       enrolled=True, fields=("technology",))
        result = evaluate_opportunity(item, no_identity, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "conditional")
        self.assertIn("identity-based eligibility not evaluated", result.verification_required)

    def test_all_explicit_identity_criteria_must_match(self):
        item = self.make_opportunity(identity_criteria=("Latina", "trans"))
        partial = ApplicantProfile(applicant_type="individual", jurisdictions=("Arizona",),
                                   enrolled=True, fields=("technology",),
                                   identity_attributes=("Latina",))
        result = evaluate_opportunity(item, partial, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "ineligible")

    def test_fiscal_sponsor_is_a_verifiable_requirement(self):
        item = self.make_opportunity(opportunity_type="grant",
                                     requires_fiscal_sponsor=True)
        unknown = ApplicantProfile(applicant_type="individual", jurisdictions=("Arizona",),
                                   enrolled=True, fields=("technology",))
        result = evaluate_opportunity(item, unknown, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "conditional")
        sponsored = ApplicantProfile(applicant_type="individual", jurisdictions=("Arizona",),
                                     enrolled=True, fields=("technology",),
                                     has_fiscal_sponsor=True)
        result = evaluate_opportunity(item, sponsored, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "eligible")

    def test_unverified_source_never_becomes_eligible(self):
        result = evaluate_opportunity(
            self.make_opportunity(source_confidence="unverified", last_verified=None),
            self.applicant, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "conditional")
        self.assertTrue(result.verification_required)

    def test_insurance_license_scope_is_a_hard_gate(self):
        item = self.make_opportunity(
            opportunity_type="government_contract",
            applicant_types=("for_profit_business",),
            license_jurisdictions=("Arizona", "California"),
        )
        profile = ApplicantProfile(applicant_type="for_profit_business",
                                   licenses=("Arizona",),
                                   unmet_licenses=("California",))
        result = evaluate_opportunity(item, profile, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "ineligible")
        self.assertTrue(any("license" in x for x in result.blockers))

    def test_missing_license_is_conditional_not_assumed_absent(self):
        item = self.make_opportunity(
            opportunity_type="government_contract",
            applicant_types=("for_profit_business",),
            license_jurisdictions=("Arizona", "California"),
        )
        profile = ApplicantProfile(applicant_type="for_profit_business",
                                   licenses=("Arizona",))
        result = evaluate_opportunity(item, profile, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "conditional")
        self.assertTrue(any("California" in x for x in result.verification_required))

    def test_explicitly_unheld_license_blocks(self):
        item = self.make_opportunity(
            opportunity_type="government_contract",
            applicant_types=("for_profit_business",),
            license_jurisdictions=("California",),
        )
        profile = ApplicantProfile(applicant_type="for_profit_business",
                                   unmet_licenses=("California",))
        result = evaluate_opportunity(item, profile, date(2026, 11, 5))
        self.assertEqual(result.eligibility, "ineligible")
        self.assertTrue(any("not held" in x for x in result.blockers))

    def test_invalid_applicant_type_rejected(self):
        with self.assertRaises(ValueError):
            ApplicantProfile(applicant_type="unknown")

    def test_ranking_puts_eligible_before_conditional_and_closed(self):
        good = self.make_opportunity(opportunity_id="a", title="A")
        uncertain = self.make_opportunity(opportunity_id="b", title="B",
                                          source_confidence="unverified")
        closed = self.make_opportunity(opportunity_id="c", title="C", status="closed")
        ranked = rank_opportunities((closed, uncertain, good), self.applicant,
                                    date(2026, 11, 5))
        self.assertEqual([row[0].opportunity_id for row in ranked], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
