import tempfile
import unittest
from pathlib import Path

from merlin.event_outbox import MerlinEventOutbox
from merlin.learner_model import (
    LearnerStore, LearnerEventConflict, HermesLearningRouter, select_next_lesson, score_attempt_event,
    learner_subject_id,
)


class LearnerModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.store=LearnerStore(self.root/"learner.sqlite")
    def tearDown(self): self.tmp.cleanup()

    def event(self,attempt,session,score=1.0,dimension="conceptual_explanation",**extra):
        return {"learner_id":"learner-test","attempt_id":attempt,"idea_id":"rotation",
          "problem_id":attempt,"problem_version":"1","dimension":dimension,"score":score,
          "session_id":session,"response":{"work":"shown"},"rubric_version":"r1",**extra}

    def test_tenant_scoped_subject_ids_prevent_cross_tenant_learner_collisions(self):
        from_a = learner_subject_id("college-a", "student-1")
        from_b = learner_subject_id("college-b", "student-1")
        self.assertNotEqual(from_a, from_b)
        event = self.event("tenant-a-attempt", "s1")
        event["learner_id"] = from_a
        self.store.record_attempt(event)
        self.assertEqual(len(self.store.attempts(from_b)), 0)
        self.assertEqual(
            self.store.estimate(from_b, "rotation", "conceptual_explanation").state,
            "unobserved",
        )

    def test_tenant_scoped_learner_subject_is_stable_and_isolated(self):
        first = learner_subject_id("tenant-a", "learner-1")
        self.assertEqual(first, learner_subject_id("tenant-a", "learner-1"))
        self.assertNotEqual(first, learner_subject_id("tenant-b", "learner-1"))
        self.assertNotEqual(first, learner_subject_id("tenant-a", "learner-2"))
        self.assertNotIn("learner-1", first)
        with self.assertRaises(ValueError):
            learner_subject_id("", "learner-1")

    def test_append_and_idempotent_replay(self):
        e=self.event("a1","s1")
        self.assertEqual(self.store.record_attempt(e)["state"],"recorded")
        self.assertEqual(self.store.record_attempt(e)["state"],"duplicate")
        self.assertEqual(len(self.store.attempts("learner-test")),1)

    def test_conflicting_replay_rejected(self):
        self.store.record_attempt(self.event("a1","s1"))
        with self.assertRaises(LearnerEventConflict):
            self.store.record_attempt(self.event("a1","s1",score=0.2))

    def test_one_session_does_not_establish_mastery(self):
        self.store.record_attempt(self.event("a1","s1"))
        self.store.record_attempt(self.event("a2","s1"))
        self.assertNotEqual(self.store.estimate("learner-test","rotation",
          "conceptual_explanation").state,"provisionally_mastered")

    def test_two_sessions_can_provisionally_master_but_retention_requires_delay_and_transfer(self):
        self.store.record_attempt(self.event("a1","s1"))
        result=self.store.record_attempt(self.event("a2","s2"))
        self.assertEqual(result["estimate"]["state"],"provisionally_mastered")
        self.store.record_attempt(self.event("a3","s3",delayed=True,transfer=True))
        self.assertEqual(self.store.estimate("learner-test","rotation",
          "conceptual_explanation").state,"retained")

    def test_hermes_uses_prerequisite_and_gap_evidence(self):
        graph={"basics":{"prerequisites":[],"dimensions":["conceptual_explanation"]},
          "rotation":{"prerequisites":["basics"],"dimensions":["conceptual_explanation","representation_translation"]}}
        lessons=[{"lesson_id":"basics-intro","idea_id":"basics"},
          {"lesson_id":"rotation-four-forms","idea_id":"rotation"}]
        result=select_next_lesson("learner-test",self.store,graph,lessons)
        self.assertEqual(result["lesson_id"],"basics-intro")
        self.assertEqual(result["authority"],"recommendation_only")

    def test_rejects_boolean_and_nonfinite_scores(self):
        import math
        for score in (True, False, math.nan, math.inf, -math.inf):
            with self.subTest(score=score), self.assertRaises(ValueError):
                self.store.record_attempt(self.event("bad-score", "s1", score=score))

    def test_rejects_non_boolean_delay_and_transfer_flags(self):
        for field, value in (("delayed", "false"), ("transfer", 1)):
            event = self.event("bad-flag-" + field, "s1")
            event[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "must be booleans"):
                self.store.record_attempt(event)

    def test_rejects_boolean_or_nonfinite_submission_timestamp(self):
        import math
        for submitted_at in (True, math.nan, math.inf, 0, -1):
            event = self.event("bad-time-" + str(submitted_at), "s1")
            event["submitted_at"] = submitted_at
            with self.subTest(submitted_at=submitted_at), self.assertRaisesRegex(ValueError, "submitted_at"):
                self.store.record_attempt(event)

    def test_rejects_non_json_response_values(self):
        event = self.event("bad-response", "s1")
        event["response"] = {"answer": float("nan")}
        with self.assertRaisesRegex(ValueError, "finite JSON"):
            self.store.record_attempt(event)

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record_attempt(self.event("a1","s1",score=1.5))

    def test_hermes_consumes_and_acknowledges_learner_attempt(self):
        outbox=MerlinEventOutbox(self.root/"outbox.sqlite")
        e=self.event("a1","s1")
        e["problem_id"]="rotation-coordinate-90"
        e["response"]={"x":0,"y":1}
        outbox.enqueue("learning-attempt:a1","merlin.learning.attempt",e,now=1)
        graph={"MATH-REP-001":{"prerequisites":[],"dimensions":["procedure"]}}
        lessons=[{"lesson_id":"rotation-lesson","idea_id":"MATH-REP-001"}]
        router=HermesLearningRouter(outbox,self.store,graph,lessons)
        result=router.run_once()
        self.assertEqual(result["state"],"acknowledged")
        self.assertEqual(self.store.estimate("learner-test","MATH-REP-001",
          "procedure").observations,1)


    def test_server_scoring_ignores_client_score_and_idea_claims(self):
        event = {"learner_id":"learner-test","attempt_id":"scored-1",
          "problem_id":"rotation-coordinate-90","problem_version":"1","session_id":"s1",
          "score":1.0,"idea_id":"FAKE-ID","dimension":"proof_justification",
          "response":{"x":9,"y":9}}
        scored=score_attempt_event(event)
        self.assertEqual(scored["score"],0.0)
        self.assertEqual(scored["idea_id"],"MATH-REP-001")
        self.assertEqual(scored["dimension"],"procedure")
        self.assertEqual(scored["scoring_source"],"server_rubric")


    def test_profile_defaults_persist_and_normalize_preferences(self):
        default = self.store.get_profile("learner-test")
        self.assertAlmostEqual(sum(default["pathway_weights"].values()), 1.0)
        self.assertEqual(default["interests"], [])
        self.assertIsNone(default["max_minutes"])

        updated = self.store.update_profile("learner-test", {
            "pathway_weights": {
                "mathematician": 1.0,
                "mathematics_programmer": 0.0,
                "computational_hacker": 0.0,
            },
            "interests": ["Number Theory", "proof"],
            "pace": "gentle",
        })
        self.assertEqual(updated["pathway_weights"]["mathematician"], 1.0)
        self.assertEqual(updated["interests"], ["number_theory", "proof"])
        self.assertEqual(updated["max_minutes"], 20)
        self.assertEqual(self.store.get_profile("learner-test")["interests"], ["number_theory", "proof"])

    def test_profile_updates_merge_and_reject_invalid_values(self):
        self.store.update_profile("learner-test", {"interests": ["python"]})
        updated = self.store.update_profile("learner-test", {"pace": "standard"})
        self.assertEqual(updated["interests"], ["python"])
        self.assertEqual(updated["max_minutes"], 35)
        with self.assertRaisesRegex(ValueError, "at least one pathway"):
            self.store.update_profile("learner-test", {
                "pathway_weights": {
                    "mathematician": 0.0,
                    "mathematics_programmer": 0.0,
                    "computational_hacker": 0.0,
                }
            })
        with self.assertRaisesRegex(ValueError, "unsupported learner profile fields"):
            self.store.update_profile("learner-test", {"learner_id": "someone-else"})
        with self.assertRaisesRegex(ValueError, "interests must be a list"):
            self.store.update_profile("learner-test", {"interests": "python"})

    def test_next_lesson_respects_path_interest_and_time_preferences(self):
        graph = {
            "math-idea": {"prerequisites": [], "dimensions": ["conceptual_explanation"]},
            "code-idea": {"prerequisites": [], "dimensions": ["conceptual_explanation"]},
        }
        lessons = [
            {"lesson_id": "math-proof", "idea_id": "math-idea",
             "pathways": ["mathematician"], "interest_tags": ["proof", "history"],
             "estimated_minutes": 25, "learning_value": 0.8, "transfer_value": 0.9},
            {"lesson_id": "code-loop", "idea_id": "code-idea",
             "pathways": ["computational_hacker"], "interest_tags": ["python"],
             "estimated_minutes": 15, "learning_value": 0.9, "transfer_value": 0.8},
        ]
        math_result = select_next_lesson(
            "learner-test", self.store, graph, lessons,
            path_weights={"mathematician": 1.0}, interests=["proof"],
        )
        self.assertEqual(math_result["lesson_id"], "math-proof")
        self.assertIn("matches_learner_interests", math_result["reason_codes"])

        code_result = select_next_lesson(
            "learner-test", self.store, graph, lessons,
            path_weights={"computational_hacker": 1.0},
        )
        self.assertEqual(code_result["lesson_id"], "code-loop")

        blocked = select_next_lesson(
            "learner-test", self.store, graph, lessons,
            path_weights={"mathematician": 1.0}, max_minutes=10,
        )
        self.assertEqual(blocked["state"], "no_candidate")
        self.assertEqual(blocked["blocked_lessons"][0]["blocked_reason"], "exceeds_time_budget")


if __name__=="__main__": unittest.main()
