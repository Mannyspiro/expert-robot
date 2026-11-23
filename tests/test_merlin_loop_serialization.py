"""Versioned scheduler serialization checks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from merlin_loop_coordinator import Loop, LoopCoordinator

class SerializationTests(unittest.TestCase):
    def test_round_trip_and_interrupted_review(self):
        c = LoopCoordinator(max_depth=2)
        c.add(Loop("first", "research"))
        c.start("first")
        restored = LoopCoordinator.from_json(c.to_json())
        self.assertEqual(restored.max_depth, 2)
        self.assertEqual(restored.loops["first"].state, "blocked")

    def test_corrupt_schema_rejected(self):
        with self.assertRaises(ValueError):
            LoopCoordinator.from_json('{"schema":2,"max_depth":3,"loops":{}}')

if __name__ == "__main__":
    unittest.main()
