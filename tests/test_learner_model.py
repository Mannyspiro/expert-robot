import tempfile
import unittest
from pathlib import Path

from merlin.learner_model import LearnerStore, LearnerEventConflict, select_next_lesson


class LearnerModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=LearnerStore(Path(self.tmp.name)/"learner.sqlite")
    def tearDown(self): self.tmp.cleanup()

    def event(self,attempt,session,score=1.0,dimension="conceptual_explanation",**extra):
        return {"learner_id":"learner-test","attempt_id":attempt,"idea_id":"rotation",
          "problem_id":attempt,"problem_version":"1","dimension":dimension,"score":score,
          "session_id":session,"response":{"work":"shown"},"rubric_version":"r1",**extra}

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

    def test_invalid_score_rejected(self):
        with self.assertRaises(ValueError):
            self.store.record_attempt(self.event("a1","s1",score=1.5))


if __name__=="__main__": unittest.main()
