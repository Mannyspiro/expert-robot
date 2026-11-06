import unittest

from merlin.verifier import (
    AcceptanceCriterion, Artifact, ClaimEvidence, IndependentReview,
    ResearchClaim, SourceSnapshot, TestResult, sha256_bytes,
    verify_claims, verify_work,
)


class MerlinVerifierTests(unittest.TestCase):
    def setUp(self):
        self.body = b"Arizona statute section 20-461 describes specified unfair claim practices."
        self.source = SourceSnapshot("az-statute", "https://www.azleg.gov/ars/20/00461.htm",
            "2026-11-06T00:00:00Z", self.body, sha256_bytes(self.body))
        self.claim = ResearchClaim("claim-1", "Arizona law describes specified claim practices.",
            (ClaimEvidence("az-statute", "Arizona statute section 20-461 describes specified unfair claim practices."),))

    def test_traceability_is_not_semantic_proof(self):
        result = verify_claims([self.claim], [self.source], producing_agent_id="agent-a")
        self.assertEqual(result["traceable_claim_count"], 1)
        self.assertFalse(result["truth_gate_passed"])

    def test_tampered_source_bytes_fail(self):
        bad = SourceSnapshot("az-statute", self.source.url, self.source.captured_at,
                             b"tampered", self.source.declared_sha256)
        result = verify_claims([self.claim], [bad], producing_agent_id="agent-a")
        self.assertEqual(result["unsubstantiated_claim_count"], 1)

    def test_fabricated_excerpt_fails(self):
        claim = ResearchClaim("c2", "unsupported", (ClaimEvidence("az-statute", "invented quote"),))
        result = verify_claims([claim], [self.source], producing_agent_id="agent-a")
        self.assertEqual(result["claims"][0]["status"], "unsubstantiated")

    def test_missing_source_fails(self):
        claim = ResearchClaim("c3", "unsupported", (ClaimEvidence("missing", "quote"),))
        self.assertFalse(verify_claims([claim], [self.source], producing_agent_id="a")["truth_gate_passed"])

    def test_self_review_cannot_pass(self):
        first = verify_claims([self.claim], [self.source], producing_agent_id="agent-a")
        review = IndependentReview("agent-a", "agent-a", first["subject_digest"], "supported")
        result = verify_claims([self.claim], [self.source], producing_agent_id="agent-a", independent_review=review)
        self.assertEqual(result["independent_semantic_review"], "invalid_self_review")
        self.assertFalse(result["truth_gate_passed"])

    def test_independent_review_must_bind_exact_claim_digest(self):
        review = IndependentReview("reviewer-b", "agent-a", "0" * 64, "supported")
        result = verify_claims([self.claim], [self.source], producing_agent_id="agent-a", independent_review=review)
        self.assertEqual(result["independent_semantic_review"], "review_digest_mismatch")

    def test_independent_reviewer_without_authenticated_receipt_is_not_accepted(self):
        first = verify_claims([self.claim], [self.source], producing_agent_id="agent-a")
        review = IndependentReview("reviewer-b", "agent-a", first["subject_digest"], "supported")
        result = verify_claims([self.claim], [self.source], producing_agent_id="agent-a", independent_review=review)
        self.assertEqual(result["independent_semantic_review"], "review_not_authenticated")
        self.assertFalse(result["truth_gate_passed"])

    def test_work_requires_real_artifacts_acceptance_and_logs(self):
        log = Artifact("log", b"2 tests passed", sha256_bytes(b"2 tests passed"))
        output = Artifact("dossier", b"Arizona dossier", sha256_bytes(b"Arizona dossier"))
        result = verify_work(task_id="az-research", producing_agent_id="agent-a",
            artifacts=[log, output],
            criteria=[AcceptanceCriterion("c1", "Dossier exists", True, ("dossier",))],
            tests=[TestResult("unit", "passed", "log")])
        self.assertTrue(result["useful_work_gate_passed"])

    def test_missing_test_log_blocks_usefulness(self):
        output = Artifact("dossier", b"Arizona dossier", sha256_bytes(b"Arizona dossier"))
        result = verify_work(task_id="az-research", producing_agent_id="agent-a",
            artifacts=[output],
            criteria=[AcceptanceCriterion("c1", "Dossier exists", True, ("dossier",))],
            tests=[TestResult("unit", "passed", "missing")])
        self.assertFalse(result["useful_work_gate_passed"])

    def test_tampered_deliverable_blocks_usefulness(self):
        bad = Artifact("dossier", b"changed", "0" * 64)
        result = verify_work(task_id="az-research", producing_agent_id="agent-a",
            artifacts=[bad],
            criteria=[AcceptanceCriterion("c1", "Dossier exists", True, ("dossier",))],
            tests=[TestResult("unit", "passed", "dossier")])
        self.assertFalse(result["artifact_integrity_passed"])
        self.assertFalse(result["useful_work_gate_passed"])


if __name__ == "__main__":
    unittest.main()
