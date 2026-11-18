import unittest
from merlin.scientific_loop import ConditionalFact, Prediction, assess_clue_hypotheses
from test_scientific_loop import ScientificLoopTests


class ClueInquiryTests(unittest.TestCase):
    def test_observation_can_contradict_specialist_explanation(self):
        observation = ScientificLoopTests().observation()
        fact = ConditionalFact("cache", "Repeated reads may use cache", ("experiment:cache",),
                               ("working set fits",))
        hypotheses = {"fast": [Prediction("latency_ms", 50, 1, "ms")],
                      "slow": [Prediction("latency_ms", 92, 3, "ms")]}
        result = assess_clue_hypotheses([observation], hypotheses, specialist_facts=[fact],
                                       scope="one synthetic benchmark", next_test="disable cache")
        self.assertEqual(result["hypotheses"]["fast"][0]["overall"], "contradicted")
        self.assertEqual(result["hypotheses"]["slow"][0]["overall"], "consistent_with_prediction")
        self.assertFalse(result["promotion_authority"])
        with self.assertRaises(ValueError):
            assess_clue_hypotheses([observation, observation], hypotheses, specialist_facts=[fact],
                                  scope="one benchmark", next_test="disable cache")
        with self.assertRaises(ValueError):
            ConditionalFact("unsupported", "claim", (), ("condition",)).validate()
