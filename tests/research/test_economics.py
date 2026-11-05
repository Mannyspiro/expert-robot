import unittest

from python.merlin.economics import (
    LocalDemandEvent, opportunity_frontier, score_promotional_pressure,
)


class PromotionalPressureTests(unittest.TestCase):
    def test_unknown_factors_are_not_scored_as_absent(self):
        result = score_promotional_pressure({})
        self.assertIsNone(result["score"])
        self.assertEqual(result["evidence_coverage"], 0.0)

    def test_known_positive_and_negative_factors_are_explained(self):
        result = score_promotional_pressure({
            "paid_referral_or_sponsorship": True,
            "undisclosed_financial_or_issuer_exposure": False,
        })
        self.assertEqual(result["score"], 57.14)
        self.assertEqual(result["evidence_coverage"], 0.35)
        self.assertEqual(result["factors"]["urgency_or_scarcity_tactics"], "unknown")
        self.assertFalse(result["calibrated_probability"])

    def test_unknown_signal_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown promotional signals"):
            score_promotional_pressure({"trust_me": True})

    def test_non_boolean_signal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "true, false, or None"):
            score_promotional_pressure({"paid_referral_or_sponsorship": "maybe"})


class LocalDemandEventTests(unittest.TestCase):
    def event(self, **changes):
        values = dict(
            event_id="pima-2026-001", jurisdiction="Pima County, AZ",
            source_url="https://www.pima.gov/example/agenda.pdf",
            source_sha256="a" * 64, meeting_date="2026-11-01",
            publication_date="2026-10-29", stage="proposal",
            project="Water infrastructure planning", proposed_amount=1000000.0,
        )
        values.update(changes)
        return LocalDemandEvent(**values)

    def test_proposal_is_not_promoted_to_approved_demand(self):
        event = self.event()
        event.validate()
        self.assertIn("not approved demand", event.evidence_label)

    def test_award_is_commitment_not_completed_delivery(self):
        event = self.event(stage="award")
        self.assertIn("verify amendments and actual outlays", event.evidence_label)

    def test_bad_source_hash_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "64-character"):
            self.event(source_sha256="bad").validate()

    def test_negative_amount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.event(proposed_amount=-1).validate()


class OpportunityFrontierTests(unittest.TestCase):
    def candidate(self, candidate_id, **overrides):
        values = dict(
            candidate_id=candidate_id, evidence_quality=0.8,
            valuation_dispersion=0.7, catalyst_strength=0.6,
            balance_sheet_resilience=0.8, liquidity=0.9,
            downside_severity=0.3, model_uncertainty=0.2,
            portfolio_correlation=0.2,
        )
        values.update(overrides)
        return values

    def test_pareto_frontier_does_not_force_single_alpha_score(self):
        strong = self.candidate("A", evidence_quality=0.9)
        weak = self.candidate("B", evidence_quality=0.7)
        result = opportunity_frontier([weak, strong])
        self.assertEqual([x["candidate_id"] for x in result["frontier"]], ["A"])
        self.assertEqual([x["candidate_id"] for x in result["dominated"]], ["B"])
        self.assertEqual(result["method"], "pareto_frontier")

    def test_tradeoffs_remain_on_frontier(self):
        evidence = self.candidate("A", evidence_quality=0.95, liquidity=0.5)
        liquidity = self.candidate("B", evidence_quality=0.6, liquidity=0.99)
        result = opportunity_frontier([evidence, liquidity])
        self.assertEqual(len(result["frontier"]), 2)

    def test_missing_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing liquidity"):
            opportunity_frontier([self.candidate("A", liquidity=None) | {"liquidity": None}])

    def test_duplicate_candidate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            opportunity_frontier([self.candidate("A"), self.candidate("A")])


if __name__ == "__main__":
    unittest.main()
