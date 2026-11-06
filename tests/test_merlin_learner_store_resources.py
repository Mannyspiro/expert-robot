import gc
import tempfile
import unittest
import warnings
from pathlib import Path

from python.merlin.learner_model import LearnerStore


class LearnerSQLiteLifecycleTests(unittest.TestCase):
    def test_store_operations_close_every_sqlite_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "learner.sqlite3"
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", ResourceWarning)
                store = LearnerStore(database)
                store.record_attempt({
                    "attempt_id": "attempt-1",
                    "learner_id": "learner-1",
                    "idea_id": "idea-1",
                    "problem_id": "problem-1",
                    "dimension": "recognition",
                    "score": 1.0,
                    "session_id": "session-1",
                    "response": {"answer": "correct"},
                })
                store.estimate("learner-1", "idea-1", "recognition")
                store.attempts("learner-1")
                gc.collect()

            leaked = [
                str(item.message) for item in captured
                if "unclosed database" in str(item.message).lower()
            ]
            self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
