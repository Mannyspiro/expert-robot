import unittest

from merlin.research_lifecycle import ResearchLifecycle, StageEvidence


class ResearchLifecycleIndependentReceiptTests(unittest.TestCase):
    def _evidence(self, stage, status):
        return StageEvidence(stage, "a" * 64, ("source-1",), "owner/repo@" + "b" * 40,
                             "test-tool", "1.0", status)

    def test_verified_label_without_receipt_verifier_cannot_complete(self):
        lifecycle = ResearchLifecycle("hypothesis-1")
        for stage, status in (("literature_evidence", "recorded"), ("experiment", "completed"),
                              ("counterexample_search", "completed"), ("formalization", "compiled")):
            lifecycle = lifecycle.advance(self._evidence(stage, status))
        result = lifecycle.advance(self._evidence("independent_verification", "verified"))
        self.assertEqual(result.terminal_status, "verification_blocked")

    def test_receipt_verifier_must_accept_exact_evidence(self):
        lifecycle = ResearchLifecycle("hypothesis-1")
        for stage, status in (("literature_evidence", "recorded"), ("experiment", "completed"),
                              ("counterexample_search", "completed"), ("formalization", "compiled")):
            lifecycle = lifecycle.advance(self._evidence(stage, status))
        evidence = self._evidence("independent_verification", "verified")
        blocked = lifecycle.advance(evidence, independent_receipt_verifier=lambda item: False)
        self.assertEqual(blocked.terminal_status, "verification_blocked")
        accepted = lifecycle.advance(evidence, independent_receipt_verifier=lambda item: item == evidence)
        self.assertEqual(accepted.terminal_status, "independently_verified")


if __name__ == "__main__":
    unittest.main()
