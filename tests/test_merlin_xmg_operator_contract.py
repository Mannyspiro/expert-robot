"""Tests for XMG typed operator-contract composition."""
import unittest

from merlin.equation_atlas.operators import load_contract, validate_pipeline


class XMGOperatorContractTests(unittest.TestCase):
    def test_contract_is_explicitly_proposed_not_runtime_claim(self):
        contract = load_contract()
        self.assertEqual(contract["contract_id"], "merlin-xmg-operator-contract/0.1")
        self.assertEqual(contract["status"], "PROPOSED_CONTRACT_NOT_RUNTIME_CAPABILITY")
        self.assertGreaterEqual(len(contract["operators"]), 7)

    def test_valid_pipeline_composes_by_exact_frame_type(self):
        steps = [
            {"operator": "reaction", "input_frame": "ScalarField", "output_frame": "ScalarField"},
            {"operator": "diffusion", "input_frame": "ScalarField", "output_frame": "ScalarField"},
        ]
        self.assertEqual(validate_pipeline(steps), [])

    def test_rejects_frame_mismatch_between_operators(self):
        steps = [
            {"operator": "reaction", "input_frame": "ScalarField", "output_frame": "ScalarField"},
            {"operator": "jump_process", "input_frame": "ReactionState", "output_frame": "ProbabilityMass"},
        ]
        errors = validate_pipeline(steps)
        self.assertTrue(any("frame mismatch" in error for error in errors))

    def test_rejects_invalid_operator_input_and_output_frames(self):
        steps = [
            {"operator": "diffusion", "input_frame": "GraphState", "output_frame": "ProbabilityMass"},
        ]
        errors = validate_pipeline(steps)
        self.assertEqual(len(errors), 2)

    def test_rejects_unknown_operator(self):
        self.assertTrue(validate_pipeline([
            {"operator": "magic", "input_frame": "ScalarField", "output_frame": "ScalarField"}
        ]))


if __name__ == "__main__":
    unittest.main()
