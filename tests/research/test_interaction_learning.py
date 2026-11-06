import tempfile
import unittest
from pathlib import Path

from python.merlin.interaction_learning import (
    InteractionLearningStore, analyze_interactions,
)


class InteractionLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = InteractionLearningStore(Path(self.temp.name) / "merlin.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_feedback_is_categorical_and_idempotent(self):
        event = {
            "event_id": "feedback-001", "session_id": "session-001",
            "domain": "research", "task_type": "literature_review",
            "outcome": "partial", "friction_code": "incomplete_answer",
            "correction_type": "scope", "satisfaction": 2,
            "raw_prompt": "private prompt text must never be stored",
        }
        first = self.store.record_feedback(event)
        second = self.store.record_feedback(event)
        self.assertTrue(first["accepted"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        summary = self.store.feedback_summary()
        self.assertEqual(summary["count"], 1)
        self.assertNotIn("raw_prompt", str(summary))
        self.assertNotIn("private prompt text", str(summary))

    def test_preferences_default_to_metadata_only_and_no_personalization(self):
        preferences = self.store.preferences()
        self.assertTrue(preferences["aggregate_telemetry"])
        self.assertTrue(preferences["explicit_feedback_learning"])
        self.assertFalse(preferences["personalization"])
        self.assertFalse(preferences["raw_conversation_retention"])
        self.assertFalse(preferences["automatic_self_modification"])

    def test_can_disable_feedback_learning(self):
        self.store.set_preferences({"explicit_feedback_learning": False})
        with self.assertRaises(PermissionError):
            self.store.record_feedback({
                "session_id": "session-1", "task_type": "chat",
                "outcome": "success",
            })

    def test_preference_api_rejects_unknown_or_non_boolean_values(self):
        for change in ({"raw_conversation_retention": True}, {"personalization": "yes"}):
            with self.assertRaises(ValueError):
                self.store.set_preferences(change)

    def test_feedback_event_id_cannot_be_reused_with_different_content(self):
        event = {"event_id": "feedback-002", "session_id": "session-2",
                 "task_type": "chat", "outcome": "success"}
        self.store.record_feedback(event)
        with self.assertRaises(ValueError):
            self.store.record_feedback({**event, "outcome": "failure"})

    def test_retention_purge_removes_expired_feedback(self):
        self.store.record_feedback({
            "event_id": "old-feedback", "session_id": "session-3",
            "task_type": "chat", "outcome": "success", "created_at": 10,
        })
        self.assertEqual(self.store.purge_feedback_before(11), 1)
        self.assertEqual(self.store.feedback_summary()["count"], 0)

    def test_aggregate_analysis_proposes_only_after_minimum_sample(self):
        events = []
        for i in range(5):
            events.append({
                "source": "runtime", "kind": "task.completed",
                "task_id": "/api/slow", "duration_ms": 2000 + i,
                "payload": {"component": "http_api", "status_code": 200},
            })
        proposal = analyze_interactions(events, [], min_samples=5)
        self.assertEqual(len(proposal["proposals"]), 1)
        self.assertEqual(proposal["proposals"][0]["type"], "performance")
        self.assertFalse(proposal["automatic_code_or_policy_changes"])
        self.assertFalse(proposal["promotion_authorized"])

    def test_aggregate_analysis_identifies_repeated_task_failure_and_correction(self):
        feedback = [{
            "domain": "mathematics", "task_type": "proof_explanation",
            "outcome": "failure" if i < 3 else "success",
            "friction_code": "incomplete_answer" if i < 3 else None,
            "correction_type": "reasoning" if i < 3 else None,
            "satisfaction": 2 if i < 3 else 4,
        } for i in range(5)]
        result = analyze_interactions([], feedback, min_samples=5)
        self.assertEqual(result["feedback"]["task_metrics"][0]["samples"], 5)
        self.assertEqual(len(result["proposals"]), 1)
        self.assertEqual(result["proposals"][0]["type"], "task_quality")
        self.assertEqual(result["proposals"][0]["correction_counts"]["reasoning"], 3)

    def test_below_minimum_sample_size_does_not_trigger_proposal(self):
        feedback = [{
            "domain": "research", "task_type": "summary", "outcome": "failure",
            "friction_code": "incomplete_answer", "correction_type": "scope",
            "satisfaction": 1,
        } for _ in range(4)]
        result = analyze_interactions([], feedback, min_samples=5)
        self.assertEqual(result["proposals"], [])


if __name__ == "__main__":
    unittest.main()
