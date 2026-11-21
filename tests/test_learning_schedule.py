import unittest
from datetime import datetime, timezone, timedelta, timedelta

from merlin.learning_schedule import (
    RetrievalState, SQLiteRetrievalScheduler, initial_retrieval_state, schedule_retrieval,
)


class RetrievalScheduleTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)

    def test_initial_review_due_next_day(self):
        state = initial_retrieval_state("parrondo.state_dependence", self.now)
        self.assertEqual(state.due_at, self.now + timedelta(days=1))

    def test_successful_reviews_expand_intervals(self):
        state = initial_retrieval_state("parrondo.state_dependence", self.now)
        first = schedule_retrieval(state, quality=4, reviewed_at=state.due_at)
        second = schedule_retrieval(first.state, quality=5, reviewed_at=first.state.due_at)
        third = schedule_retrieval(second.state, quality=5, reviewed_at=second.state.due_at)
        self.assertEqual(first.state.interval_days, 1)
        self.assertEqual(second.state.interval_days, 3)
        self.assertGreater(third.state.interval_days, second.state.interval_days)

    def test_failed_recall_shortens_interval_and_changes_representation(self):
        state = initial_retrieval_state("parrondo.state_dependence", self.now)
        result = schedule_retrieval(state, quality=1, reviewed_at=state.due_at)
        self.assertEqual(result.state.interval_days, 1)
        self.assertEqual(result.state.repetitions, 0)
        self.assertEqual(result.state.lapses, 1)
        self.assertEqual(result.next_representation, "manipulative")

    def test_speed_is_not_an_input(self):
        state = initial_retrieval_state("parrondo.state_dependence", self.now)
        result = schedule_retrieval(state, quality=5, reviewed_at=state.due_at)
        self.assertEqual(result.quality, 5)

    def test_naive_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            initial_retrieval_state("x", datetime(2026, 11, 11))

    def test_persistent_scheduler_survives_reconstruction(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            database = str(Path(tmp) / "learner.sqlite")
            scheduler = SQLiteRetrievalScheduler(database)
            first = scheduler.review("learner-1", "parrondo.state", quality=5, reviewed_at=self.now)
            self.assertEqual(first.state.interval_days, 1)
            restored = SQLiteRetrievalScheduler(database)
            state = restored.get("learner-1", "parrondo.state")
            self.assertIsNotNone(state)
            self.assertEqual(state.repetitions, 1)
            self.assertEqual(state.due_at, self.now + timedelta(days=1))

    def test_due_retrievals_are_selected_by_utc_time(self):
        import tempfile
        from pathlib import Path
        from datetime import timedelta
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = SQLiteRetrievalScheduler(str(Path(tmp) / "learner.sqlite"))
            scheduler.review("learner-1", "parrondo.state", quality=5, reviewed_at=self.now)
            due = scheduler.due("learner-1", as_of=self.now + timedelta(days=1))
            self.assertEqual([state.concept_id for state in due], ["parrondo.state"])

    def test_failed_persistent_recall_increments_lapses(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = SQLiteRetrievalScheduler(str(Path(tmp) / "learner.sqlite"))
            scheduler.review("learner-1", "parrondo.state", quality=2, reviewed_at=self.now)
            state = scheduler.get("learner-1", "parrondo.state")
            self.assertEqual(state.lapses, 1)
            self.assertEqual(state.repetitions, 0)
            self.assertEqual(state.representation_index, 1)


if __name__ == "__main__":
    unittest.main()
