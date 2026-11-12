import unittest

from merlin.partner_qualification import (
    PartnerCandidate, PartnerEvidence, evaluate_partner,
)


def evidence(evidence_type, source_kind, status="verified"):
    return PartnerEvidence(
        evidence_type=evidence_type,
        status=status,
        source_url="https://example.gov/record",
        source_kind=source_kind,
        observed_on="2026-11-05",
    )


class PartnerQualificationTests(unittest.TestCase):
    def complete_candidate(self):
        items = (
            evidence("entity_license", "official_registry"),
            evidence("individual_license", "official_registry"),
            evidence("lines_of_authority", "official_registry"),
            evidence("appointments", "official_registry"),
            evidence("public_sector_references", "contracting_authority"),
            evidence("teaming_permission", "partner_written"),
            evidence("conflict_review", "contracting_authority"),
        )
        return PartnerCandidate("p-1", "Example Benefits LLC", "potential_subcontractor", items)

    def test_complete_authoritative_evidence_still_requires_human_review(self):
        result = evaluate_partner(self.complete_candidate())
        self.assertEqual(result.decision, "qualified_for_human_review")
        self.assertEqual(len(result.verified_evidence), 7)
        self.assertTrue(any("human selection" in reason for reason in result.reasons))

    def test_carrier_confirmation_can_verify_appointments(self):
        candidate = self.complete_candidate()
        items = tuple(
            evidence(x.evidence_type,
                     "carrier_confirmation" if x.evidence_type == "appointments" else x.source_kind)
            for x in candidate.evidence
        )
        result = evaluate_partner(PartnerCandidate(
            candidate.partner_id, candidate.legal_name, candidate.relationship, items,
        ))
        self.assertEqual(result.decision, "qualified_for_human_review")
        self.assertIn("appointments", result.verified_evidence)

    def test_directory_listing_cannot_verify_license(self):
        candidate = PartnerCandidate(
            "p-2", "Directory Benefits LLC", "potential_subcontractor",
            (evidence("entity_license", "directory"),),
        )
        result = evaluate_partner(candidate)
        self.assertEqual(result.decision, "hold_for_evidence")
        self.assertIn("entity_license", result.unresolved_evidence)

    def test_missing_teaming_permission_holds_candidate(self):
        candidate = self.complete_candidate()
        result = evaluate_partner(PartnerCandidate(
            candidate.partner_id, candidate.legal_name, candidate.relationship,
            tuple(x for x in candidate.evidence if x.evidence_type != "teaming_permission"),
        ))
        self.assertEqual(result.decision, "hold_for_evidence")
        self.assertIn("teaming_permission", result.unresolved_evidence)

    def test_explicit_failed_mandatory_gate_excludes_candidate(self):
        candidate = self.complete_candidate()
        items = tuple(
            evidence(x.evidence_type, x.source_kind,
                     "not_met" if x.evidence_type == "appointments" else "verified")
            for x in candidate.evidence
        )
        result = evaluate_partner(PartnerCandidate(
            candidate.partner_id, candidate.legal_name, candidate.relationship, items,
        ))
        self.assertEqual(result.decision, "exclude_pending_reassessment")
        self.assertEqual(result.failed_evidence, ("appointments",))

    def test_competitor_is_not_misclassified_as_partner(self):
        result = evaluate_partner(PartnerCandidate(
            "p-3", "Public Sector Benchmark", "potential_competitor",
        ))
        self.assertEqual(result.decision, "benchmark_or_competitor_only")

    def test_invalid_url_and_duplicate_evidence_are_rejected(self):
        with self.assertRaises(ValueError):
            PartnerEvidence("entity_license", "verified", "http://example.gov",
                            "official_registry", "2026-11-05")
        item = evidence("entity_license", "official_registry")
        with self.assertRaises(ValueError):
            PartnerCandidate("p-4", "Duplicate LLC", "potential_prime", (item, item))


if __name__ == "__main__":
    unittest.main()
