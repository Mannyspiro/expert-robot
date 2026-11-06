import unittest

from merlin.legal_intelligence import (
    Doctrine, LegalCase, LegalClaim, LegalJurisdiction, LegalProvision,
    LegalSource, ResearchDossier, US_JURISDICTIONS, claim_set_digest,
    validate_graph_references,
)


class LegalIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.source = LegalSource(
            source_id="az-constitution", title="Arizona Constitution",
            source_type="constitution", jurisdiction_id="US-AZ",
            canonical_url="https://www.azleg.gov/const/ArizonaConstitution.pdf",
            retrieved_at="2026-11-06T12:00:00Z",
            effective_from="1912-02-14", version_label="current-research-snapshot",
            sha256="a" * 64, authority_status="binding", permitted_use="public_link_only",
        )

    def test_jurisdiction_universe_covers_50_states_and_dc(self):
        self.assertEqual(len(US_JURISDICTIONS), 51)
        self.assertIn("AZ", US_JURISDICTIONS)
        self.assertIn("DC", US_JURISDICTIONS)

    def test_source_requires_https_timezone_and_validity_window(self):
        self.source.validate()
        with self.assertRaises(ValueError):
            LegalSource("bad", "Bad", "statute", "US-AZ", "http://example.org",
                        "2026-11-06T12:00:00Z").validate()
        with self.assertRaises(ValueError):
            LegalSource("bad-date", "Bad", "statute", "US-AZ", "https://example.org",
                        "2026-11-06", effective_from="2027-01-01",
                        effective_to="2026-01-01").validate()

    def test_provision_must_reference_known_source(self):
        provision = LegalProvision("az-art-2-sec-1", "missing", "Art. 2 §1", "Text")
        errors = validate_graph_references(sources=[self.source], provisions=[provision])
        self.assertTrue(any("unknown_source:missing" in error for error in errors))

    def test_claim_must_track_temporal_scope_and_references(self):
        claim = LegalClaim("claim-1", "A proposition", "US-AZ", "2026-11-06",
                           source_ids=("missing",), status="source_supported")
        errors = validate_graph_references(sources=[self.source], claims=[claim])
        self.assertTrue(any("unknown_source:missing" in error for error in errors))

    def test_verified_claim_requires_counterauthority_review_record(self):
        claim = LegalClaim("claim-2", "A proposition", "US-AZ", "2026-11-06",
                           status="independently_verified")
        with self.assertRaises(ValueError):
            claim.validate()

    def test_claim_digest_is_stable_and_order_independent(self):
        one = LegalClaim("a", "Rule A", "US-AZ", "2026-11-06",
                         source_ids=("s2", "s1"), status="source_supported")
        two = LegalClaim("b", "Rule B", "US-CA", "2026-11-06",
                         case_ids=("c1",), status="source_supported")
        self.assertEqual(claim_set_digest([one, two]), claim_set_digest([two, one]))

    def test_dossier_requires_known_subjects_and_jurisdictions(self):
        dossier = ResearchDossier(
            "How does negligence differ?", ("US-AZ", "US-CA"),
            "2026-11-06", ("torts", "civil_procedure"),
        )
        dossier.validate()
        with self.assertRaises(ValueError):
            ResearchDossier("Question", ("US-AZ",), "2026-11-06", ("invented",)).validate()

    def test_case_validates_date_and_precedential_status(self):
        case = LegalCase(
            "case-1", "Example v Example", "Arizona Supreme Court", "US-AZ",
            "2025-05-01", "000 Ariz. 1", "appeal from judgment",
            "The court held ...", authority_status="binding",
        )
        case.validate()
        bad = LegalCase(
            "case-2", "Bad v Bad", "Court", "US-AZ", "not-a-date",
            "citation", "posture", "holding", authority_status="binding",
        )
        with self.assertRaises(ValueError):
            bad.validate()

    def test_doctrine_requires_summary_and_identity(self):
        Doctrine("negligence", "Negligence", "torts", "US-AZ", "Duty, breach, causation and harm").validate()
        with self.assertRaises(ValueError):
            Doctrine("x", "X", "torts", "US-AZ", "").validate()

    def test_graph_validator_checks_case_treatment_sources(self):
        case = LegalCase(
            "case-1", "Example", "Court", "US-AZ", "2025-05-01",
            "citation", "appeal", "holding",
            subsequent_treatment_source_ids=("missing-treatment",),
        )
        errors = validate_graph_references(sources=[self.source], cases=[case])
        self.assertTrue(any("unknown_treatment_source" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
