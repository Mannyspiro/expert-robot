import gc
import tempfile
import unittest
import warnings
from pathlib import Path

from python.merlin.learner_model import LearnerStore


class LearnerStoreResourceTests(unittest.TestCase):
    def test_all_store_operations_close_sqlite_connections(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "learner.sqlite3"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                store = LearnerStore(database)
                result = store.record_attempt({
                    "attempt_id": "attempt-1",
                    "learner_id": "learner-1",
                    "idea_id": "idea-1",
                    "problem_id": "problem-1",
                    "problem_version": "1",
                    "dimension": "recognition",
                    "score": 1.0,
                    "session_id": "session-1",
                    "response": {"answer_kind": "multiple_choice"},
                })
                self.assertEqual(result["state"], "recorded")
                estimate = store.estimate("learner-1", "idea-1", "recognition")
                self.assertEqual(estimate.observations, 1)
                self.assertEqual(len(store.attempts("learner-1", "idea-1")), 1)
                del store
                gc.collect()
            leaks = [item for item in caught if issubclass(item.category, ResourceWarning)]
            self.assertEqual(leaks, [])

            reopened = LearnerStore(database)
            self.assertEqual(len(reopened.attempts("learner-1", "idea-1")), 1)


if __name__ == "__main__":
    unittest.main()
