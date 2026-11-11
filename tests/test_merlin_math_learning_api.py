from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from merlin.math_learning_api import MathLearningService


class MathLearningServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "learner.sqlite3"
        self.service = MathLearningService(self.db, learner_id="test-learner")

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_starts_zero_first_and_has_no_mastery_credit(self):
        result = self.service.snapshot("mathematician")
        self.assertEqual(result["schema"], "merlin-math-lesson-session/1")
        self.assertEqual(result["progress"]["stage_index"], 0)
        self.assertEqual(result["progress"]["current_stage"]["mode"], "concrete")
        self.assertFalse(result["assessment"]["mastery_awarded"])
        self.assertEqual(result["assessment"]["attempt_count"], 0)

    def test_stage_completion_persists_and_advances_exactly_one_stage(self):
        first = self.service.snapshot("mathematics_programmer")
        stage_id = first["progress"]["current_stage"]["id"]
        result = self.service.complete_stage("mathematics_programmer", stage_id)
        self.assertEqual(result["progress"]["stage_index"], 1)
        self.assertEqual(result["progress"]["completed_stage_ids"], [stage_id])
        reopened = MathLearningService(self.db, learner_id="test-learner")
        self.assertEqual(reopened.snapshot("mathematics_programmer")["progress"], result["progress"])
        self.assertFalse(result["assessment"]["mastery_awarded"])
        self.assertEqual(result["assessment"]["attempt_count"], 0)

    def test_cannot_skip_stage_or_replay_completed_stage(self):
        with self.assertRaisesRegex(ValueError, "expected current stage"):
            self.service.complete_stage("mathematician", "introduce-notation")
        first = self.service.snapshot("mathematician")["progress"]["current_stage"]["id"]
        self.service.complete_stage("mathematician", first)
        with self.assertRaisesRegex(ValueError, "expected current stage"):
            self.service.complete_stage("mathematician", first)

    def test_unknown_path_and_client_supplied_lesson_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "canonical mathematics"):
            self.service.snapshot("invented_path")
        with self.assertRaises(TypeError):
            self.service.complete_stage({"lesson": "attacker-controlled"}, "stage")

    def test_learning_paths_have_distinct_canonical_lesson_ids(self):
        ids = {
            self.service.snapshot(path)["lesson"]["id"]
            for path in ("mathematician", "mathematics_programmer", "computational_hacker")
        }
        self.assertEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
