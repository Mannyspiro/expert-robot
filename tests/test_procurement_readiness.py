import unittest

from merlin.procurement_readiness import (
    ProcurementEvidence, ProcurementRequirements, evaluate_procurement_readiness,
)


class ProcurementReadinessTests(unittest.TestCase):
    def test_unknown_registration_holds_pursuit(self):
        requirements = ProcurementRequirements(("app_registration_complete",))
        result = evaluate_procurement_readiness(requirements, ProcurementEvidence())
        self.assertEqual(result.decision, "hold_for_evidence")
        self.assertEqual(result.unresolved_gates, ("app_registration_complete",))

    def test_explicitly_inactive_federal_registration_blocks_prime_bid(self):
        requirements = ProcurementRequirements(("sam_registration_active",))
        evidence = ProcurementEvidence(sam_registration_active=False)
        result = evaluate_procurement_readiness(requirements, evidence)
        self.assertEqual(result.decision, "no_bid")
        self.assertEqual(result.failed_gates, ("sam_registration_active",))

    def test_only_required_gates_are_evaluated(self):
        requirements = ProcurementRequirements((
            "agency_entity_license_verified",
            "producer_appointments_verified",
        ))
        evidence = ProcurementEvidence(
            agency_entity_license_verified=True,
            producer_appointments_verified=True,
            sam_registration_active=None,
        )
        result = evaluate_procurement_readiness(requirements, evidence)
        self.assertEqual(result.decision, "proceed_to_human_review")
        self.assertEqual(result.verified_gates, requirements.gates)

    def test_unknown_coverage_does_not_become_a_pass_or_failure(self):
        requirements = ProcurementRequirements((
            "professional_liability_verified", "cyber_coverage_verified",
        ))
        evidence = ProcurementEvidence(professional_liability_verified=True)
        result = evaluate_procurement_readiness(requirements, evidence)
        self.assertEqual(result.decision, "hold_for_evidence")
        self.assertEqual(result.unresolved_gates, ("cyber_coverage_verified",))

    def test_duplicate_or_unknown_gates_rejected(self):
        with self.assertRaises(ValueError):
            ProcurementRequirements(("sam_registration_active", "sam_registration_active"))
        with self.assertRaises(ValueError):
            ProcurementRequirements(("magic_certification",))

    def test_all_gates_pass_still_requires_human_review(self):
        requirements = ProcurementRequirements((
            "app_registration_complete", "agency_entity_license_verified",
            "delivery_capacity_verified",
        ))
        evidence = ProcurementEvidence(
            app_registration_complete=True,
            agency_entity_license_verified=True,
            delivery_capacity_verified=True,
        )
        result = evaluate_procurement_readiness(requirements, evidence)
        self.assertEqual(result.decision, "proceed_to_human_review")
        self.assertTrue(any("human" in reason for reason in result.reasons))


if __name__ == "__main__":
    unittest.main()
