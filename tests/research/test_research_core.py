import unittest

from python.merlin.research import (
    AnalogyMap, Claim, EvidenceClass, EvidenceLedger, Idea, PromotionPacket,
    qualify_rsi_candidate, rank_ideas, validate_analogy,
)


class EvidenceLedgerTests(unittest.TestCase):
    def test_claim_cannot_be_proved_without_formal_receipt(self):
        ledger = EvidenceLedger()
        ledger.add(Claim("c1", "A hypothesis", EvidenceClass.HYPOTHESIS_ONLY.value))
        with self.assertRaisesRegex(ValueError, "formal_receipt"):
            ledger.promote("c1", EvidenceClass.PROVED.value, {"kind": "test_log", "sha256": "abc"})

    def test_verified_claim_requires_hashed_test_log(self):
        with self.assertRaisesRegex(ValueError, "hashed test_log"):
            Claim("c2", "Tested", EvidenceClass.ENGINEERING_VERIFIED.value).validate()

    def test_valid_promotion_needs_artifact_hash(self):
        ledger = EvidenceLedger()
        ledger.add(Claim("c3", "Tested", EvidenceClass.HYPOTHESIS_ONLY.value))
        promoted = ledger.promote("c3", EvidenceClass.ENGINEERING_VERIFIED.value, {"kind": "test_log", "sha256": "abc"})
        self.assertEqual(promoted.evidence_class, EvidenceClass.ENGINEERING_VERIFIED.value)


class IdeonomyTests(unittest.TestCase):
    def test_idea_with_mechanism_and_falsifier_is_ranked(self):
        idea = Idea(
            title="Graph-preserving CAD simplification",
            mechanism="Collapse degree-two vertices while preserving incidence.",
            assumptions=("The mesh is a 2-manifold.",),
            constraints=("Boundary vertices are fixed.",),
            observable="Hausdorff distance and Euler characteristic.",
            falsifier="Any topology mismatch or distance above tolerance.",
            feasibility=0.9, testability=0.95, evidence_fit=0.8,
        )
        result = rank_ideas([idea])
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["accepted"][0]["rank"], 1)

    def test_idea_without_falsifier_is_rejected(self):
        idea = Idea("Alien energy", "Use unknown energy", ("unknown",), ("none",), "energy", "")
        result = rank_ideas([idea])
        self.assertEqual(result["accepted"], [])
        self.assertEqual(len(result["rejected"]), 1)

    def test_duplicate_ideas_are_rejected(self):
        idea = Idea("A", "Mechanism", ("assumption",), ("constraint",), "measure", "disprove")
        result = rank_ideas([idea, idea])
        self.assertEqual(len(result["accepted"]), 1)
        self.assertEqual(result["rejected"][0]["reason"], "duplicate candidate")


class AnalogyTests(unittest.TestCase):
    def mapping(self):
        return AnalogyMap(
            source_problem="repair a mesh",
            target_problem="repair a graph",
            entity_mapping={"vertex": "node", "edge": "edge"},
            operation_mapping={"collapse": "contract"},
            required_invariants=("connectivity", "boundary"),
            preserved_invariants=("connectivity", "boundary"),
            source_boundary_conditions=("fixed boundary vertices",),
            target_boundary_conditions=("fixed boundary nodes",),
            known_failure_modes=("non-manifold input",),
        )

    def test_valid_analogy_passes(self):
        self.assertTrue(validate_analogy(self.mapping())["accepted"])

    def test_analogy_missing_invariant_fails(self):
        mapping = self.mapping()
        bad = AnalogyMap(**{**mapping.__dict__, "preserved_invariants": ("connectivity",)})
        result = validate_analogy(bad)
        self.assertFalse(result["accepted"])
        self.assertTrue(any("unpreserved invariants" in reason for reason in result["reasons"]))


class RsiGateTests(unittest.TestCase):
    def test_all_gates_required(self):
        packet = PromotionPacket(True, True, True, True, True, True, True)
        self.assertEqual(qualify_rsi_candidate(packet)["status"], "PASS")

    def test_authority_expansion_blocks_promotion(self):
        packet = PromotionPacket(True, True, True, True, False, True, True)
        result = qualify_rsi_candidate(packet)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("authority_unchanged", result["failed_gates"])
        self.assertFalse(result["automatic_promotion"])


if __name__ == "__main__":
    unittest.main()
