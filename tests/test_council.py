import unittest

from merlin.council import (
    CouncilMap, Position, build_deliberation_packets, close_council,
    record_position, self_map,
)


class CouncilTests(unittest.TestCase):
    def test_personas_have_distinct_deliberation_packets(self):
        packets = build_deliberation_packets("Should we add hybrid routing?", verbosity="lively")
        self.assertGreaterEqual(len(packets), 5)
        self.assertEqual(len({p["persona"]["temperament"] for p in packets}), len(packets))
        self.assertTrue(all("Do not invent sources" in p["instructions"] for p in packets))

    def test_self_map_tracks_changed_position(self):
        council = CouncilMap("Should we switch strategies?")
        record_position(council, Position("skeptic", "against", .8), 1)
        record_position(council, Position(
            "skeptic", "conditional support", .7,
            changed_mind_from="against",
            change_reason="Paired benchmark showed repeatable quality-preserving gains.",
        ), 2)
        mapped = self_map(council)
        self.assertEqual(mapped["skeptic"]["current_position"]["stance"], "conditional support")
        self.assertEqual(len(mapped["skeptic"]["position_history"]), 2)

    def test_council_cannot_authorize_promotion(self):
        council = close_council(
            CouncilMap("Question"), "pilot only", ["Evidence is promising."], ["More trials needed."]
        )
        self.assertFalse(council.promotion_authorized)

    def test_stance_change_requires_reason(self):
        council = CouncilMap("Question")
        record_position(council, Position("builder", "yes", .6), 1)
        with self.assertRaises(ValueError):
            record_position(council, Position("builder", "no", .7), 2)


if __name__ == "__main__":
    unittest.main()
