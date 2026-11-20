import unittest
from unittest.mock import patch
from dot_ai_os.bridge import canonical
from dot_ai_os.research_tools import reviewed_virtual_circuit_demo, research_contract, mathematical_lenses_demo


class ResearchToolIntegrationTests(unittest.TestCase):
    def test_existing_virtual_tool_retains_original_fields_and_requires_protocol(self):
        result = reviewed_virtual_circuit_demo({})
        self.assertEqual(result["selected_for_followup"], "lower_power")
        self.assertEqual(result["epistemic_status"], "simulated")
        self.assertFalse(result["research_protocol"]["confirmatory_discovery"])
        self.assertEqual(result["research_protocol"]["experiment_class"], "known_fixture_reproduction")
        self.assertLess(len(canonical(result)), 48000)

    def test_failed_or_missing_protocol_cannot_call_success_a_repair(self):
        with patch("dot_ai_os.research_tools.research_episode_demo", return_value={"qualification": True}):
            with self.assertRaises(ValueError): reviewed_virtual_circuit_demo({})

    def test_no_unreviewed_caller_commands_or_private_sources(self):
        with self.assertRaises(ValueError): reviewed_virtual_circuit_demo({"path": "/any/input"})
        with self.assertRaises(ValueError): reviewed_virtual_circuit_demo({"operation": "execute"})

    def test_fixed_contract_and_math_lenses_have_no_authority(self):
        for call in (research_contract, mathematical_lenses_demo):
            value = call({})
            self.assertFalse(value["qualification"])
            self.assertFalse(value["promotion_authority"])


if __name__ == "__main__": unittest.main()
