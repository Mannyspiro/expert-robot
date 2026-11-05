import unittest
from merlin.titan_crypto_lab import TitanProfile, build_research_matrix, default_scenarios, simulate_lifecycle, validate_profile

class TitanCryptoResearchTests(unittest.TestCase):
    def test_reviewed_profile_is_accepted(self):
        self.assertEqual(validate_profile(TitanProfile(kem="ML-KEM-768")), [])
    def test_unreviewed_profile_is_rejected(self):
        errors=validate_profile(TitanProfile(aead="CUSTOM-ROTOR-CIPHER",context_binding=False))
        self.assertGreaterEqual(len(errors),2)
    def test_lifecycle_fails_closed(self):
        results=[simulate_lifecycle(TitanProfile(kem="ML-KEM-768"),s) for s in default_scenarios()]
        self.assertEqual(results[0]["terminal_state"],"verified")
        self.assertTrue(all(r["terminal_state"]=="rejected" for r in results[1:]))
        self.assertTrue(all(r["cryptographic_operations_performed"] is False for r in results))
    def test_matrix_scope(self):
        report=build_research_matrix()
        self.assertEqual(report["schema"],"titan-cryptographic-research-matrix/1")
        self.assertEqual(len(report["research_tracks"]),4)
        self.assertIn("No custom cipher promotion",report["promotion_rule"])

if __name__=="__main__": unittest.main()
