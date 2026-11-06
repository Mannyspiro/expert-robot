import hashlib
import unittest

from merlin.partner_evidence_pipeline import (
    LicenseObservation, PublicContractEvidence, PartnerSignal, rank_partners,
    ingest_rfp_text, ProposalClaim, ProposalEvidenceVault,
    LearningObservation, aggregate_learning, ingest_difi_normalized_csv,
)


class PartnerEvidencePipelineTests(unittest.TestCase):
    def test_difi_observation_requires_dated_official_record(self):
        row = LicenseObservation(
            "entity-1", "entity", "Example Benefits LLC", "12345",
            "insurance_producer_entity", ("property", "casualty"), "active",
            "2026-11-05", "2026-01-01", "https://difi.az.gov/license-search",
            "SBS-12345",
        )
        self.assertEqual(row.status, "active")
        with self.assertRaises(ValueError):
            LicenseObservation(
                "x", "entity", "X LLC", "1", "producer", (), "active",
                "not-a-date", None, "https://example.gov", "record",
            )

    def test_difi_normalized_export_imports_entity_and_individual_observations(self):
        source = "\n".join([
            "subject_id,subject_type,legal_name,license_number,license_type,",
            "lines_of_authority,status,source_record_id,effective_on",
            "e1,entity,Example LLC,123,producer_entity,property;casualty,active,SBS-E1,2026-01-01",
            "i1,individual,Jane Producer,456,producer,property;casualty,active,SBS-I1,2026-01-01",
        ])
        rows = ingest_difi_normalized_csv(
            source, "2026-11-05", "https://difi.az.gov/license-search"
        )
        self.assertEqual([x.subject_type for x in rows], ["entity", "individual"])
        self.assertEqual(rows[0].lines_of_authority, ("property", "casualty"))
        self.assertTrue(rows[0].raw_record_sha256)

    def test_contract_award_and_coop_are_linked_as_distinct_evidence(self):
        award = PublicContractEvidence(
            "award-1", "partner-1", "award", "City", "RFP-1", "Broker services",
            "awarded", "2025-01-01", "2026-01-01", "2026-11-05",
            "https://city.gov/contracts/1", "award-1", "Example LLC",
        )
        coop = PublicContractEvidence(
            "coop-1", "partner-1", "cooperative_contract", "State", "CTR-1",
            "Co-op broker services", "active", "2025-01-01", "2027-01-01",
            "2026-11-05", "https://spo.az.gov/contracts", "CTR-1", "Example LLC",
        )
        ranks = rank_partners(
            [PartnerSignal("partner-1", "Example LLC", "potential_subcontractor")],
            [award, coop], [],
        )
        self.assertEqual(ranks[0].relationship, "potential_subcontractor")
        self.assertGreater(ranks[0].score, 0)
        self.assertEqual(ranks[0].qualification_state, "unqualified_pending_evidence")

    def test_competitor_and_benchmark_cohorts_stay_distinct(self):
        rows = rank_partners(
            [PartnerSignal("c", "Competitor LLC", "competitor"),
             PartnerSignal("b", "Benchmark LLC", "capability_benchmark"),
             PartnerSignal("p", "Prime LLC", "potential_prime")], [], [],
        )
        by_id = {x.partner_id: x for x in rows}
        self.assertEqual(by_id["c"].qualification_state, "benchmark_only")
        self.assertEqual(by_id["b"].qualification_state, "benchmark_only")
        self.assertEqual(by_id["p"].qualification_state, "unqualified_pending_evidence")

    def test_rfp_text_is_split_into_clause_linked_document_evidence(self):
        clauses = ingest_rfp_text(
            "RFP-26", "official-rfp.txt", "https://city.gov/rfp",
            "1 Scope\\nProvide benefits consulting.\\n2.1 Licensing\\nShow required licenses.",
            "2026-11-05",
        )
        self.assertEqual(len(clauses), 2)
        self.assertEqual(clauses[1].clause_id, "2.1")
        self.assertEqual(len(clauses[0].document_sha256), 64)

    def test_proposal_vault_blocks_unsupported_claim_and_maps_sources(self):
        vault = ProposalEvidenceVault()
        blocked = vault.add_claim(ProposalClaim("claim-1", "We have public-sector experience.", ()))
        self.assertEqual(blocked.state, "blocked")
        digest = hashlib.sha256(b"official contract").hexdigest()
        vault.add_source("award-1", "https://city.gov/award", digest, "contract_award")
        accepted = vault.add_claim(ProposalClaim(
            "claim-2", "A public contract award is recorded.", ("award-1",), "past_performance"
        ))
        self.assertEqual(accepted.state, "human_review_required")
        self.assertEqual(vault.source_map("claim-2")[0][0], "award-1")

    def test_learning_loop_excludes_private_rows_and_never_expands_authority(self):
        rows = [
            LearningObservation("s1", True, "qualified", 0.8, "shortlisted"),
            LearningObservation("s2", False, "hold", None, "not_selected", True),
        ]
        result = aggregate_learning(rows)
        self.assertEqual(result["observations_count"], 1)
        self.assertEqual(result["source_accuracy"], 1.0)
        self.assertEqual(result["private_rows_excluded"], 1)
        self.assertEqual(result["authority_change"], "none")
        self.assertTrue(result["human_approval_required"])


if __name__ == "__main__":
    unittest.main()
