import unittest
from merlin.titan_protocol_model import (
    build_protocol_model, build_titan_protocol_bundle, canonical_json_bytes,
    generate_structural_test_vectors, validate_envelope_structure, verify_bundle,
)

class TitanProtocolModelTests(unittest.TestCase):
    def test_model_keeps_experimental_concepts_outside_production_boundary(self):
        model = build_protocol_model("ML-KEM-768")
        self.assertEqual(model["production_boundary"]["suite"]["aead"], "AES-256-GCM-SIV")
        self.assertIn("rotors", model["experimental_boundary"]["excluded_concepts"])
        self.assertFalse(model["production_boundary"]["cryptographic_operations_implemented"])

    def test_state_machine_fails_closed(self):
        transitions = build_protocol_model()["state_machine"]["transitions"]
        self.assertIn("rejected", transitions["initialized"])
        self.assertEqual(transitions["accepted"], [])
        self.assertEqual(transitions["rejected"], [])

    def test_structural_vectors_are_reproducible_and_pass(self):
        first, second = generate_structural_test_vectors(), generate_structural_test_vectors()
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(len(first["vectors"]), 5)
        for vector in first["vectors"]:
            self.assertEqual(not validate_envelope_structure(vector["input"]),
                             vector["expected"]["structurally_valid"])
            self.assertFalse(vector["cryptographic_known_answer"])

    def test_bundle_hashes_and_independent_recomputation(self):
        bundle = build_titan_protocol_bundle()
        result = verify_bundle(bundle)
        self.assertEqual(result["vector_count"], 5)
        self.assertEqual(result["vectors_passed"], 5)
        self.assertFalse(result["cryptographic_security_verified"])
        tampered = dict(bundle, model_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify_bundle(tampered)
        tampered_bytes = dict(bundle, model_bytes_b64="eA==")
        with self.assertRaisesRegex(ValueError, "embedded bytes"):
            verify_bundle(tampered_bytes)

    def test_rotor_data_is_rejected_from_production_envelope(self):
        valid = generate_structural_test_vectors()["vectors"][0]["input"]
        contaminated = dict(valid, rotor_state={"step": 4})
        self.assertTrue(any("experimental research fields" in e
                            for e in validate_envelope_structure(contaminated)))

    def test_unknown_kem_rejected(self):
        with self.assertRaises(ValueError):
            build_protocol_model("MERLIN-CUSTOM-KEM")

if __name__ == "__main__":
    unittest.main()
