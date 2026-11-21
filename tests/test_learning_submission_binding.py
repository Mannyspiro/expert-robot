"""A course revision between lab precheck and submission must not retarget work."""
import tempfile
import unittest
from pathlib import Path

from merlin.learning_platform import Actor, LearningConflictError, LearningPlatform


class SubmissionBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LearningPlatform(Path(self.temp.name) / 'learning.sqlite3')
        self.teacher = Actor('tenant', 'faculty', 'instructor')
        self.reviewer = Actor('tenant', 'reviewer', 'reviewer')
        self.student = Actor('tenant', 'student', 'learner')
        course = self.store.create_course(self.teacher, 'pinned-lab', 'Pinned lab')
        manifest = course['manifest']
        manifest['objectives'] = [{'id': 'objective', 'title': 'Interpret evidence'}]
        manifest['lessons'] = [{'id': 'lesson', 'title': 'Lab', 'objective_id': 'objective',
                                'body': 'Version one.', 'exercise': {'task_id': 'lab'}}]
        manifest['assessments'] = [{'id': 'assessment', 'title': 'Review',
                                   'objective_id': 'objective', 'human_review_required': True,
                                   'rubric': [{'dimension': 'interpretation', 'points': 1}]}]
        self.store.update_manifest(self.teacher, course['course_id'], manifest)
        self.course_id = course['course_id']
        self._publish()
        self.store.enroll(self.student, self.course_id)
        self.original = self.store.get_course(self.student, self.course_id)
        self.pin = {'expected_version': self.original['version'],
                    'expected_manifest_sha256': self.original['manifest_sha256']}

    def _publish(self):
        draft = self.store.get_course(self.teacher, self.course_id)
        self.store.review_course(self.reviewer, self.course_id, draft['version'], 'approved')
        self.store.publish_course(self.teacher, self.course_id)

    def _submit(self, submission='submission', **pin):
        return self.store.submit_assessment(self.student, self.course_id, submission,
                                            'lesson', 'lab', 'Observed result', **pin)

    def _revise(self):
        draft = self.store.create_revision(self.teacher, self.course_id)
        manifest = draft['manifest']
        manifest['lessons'][0]['body'] = 'Different version two.'
        self.store.update_manifest(self.teacher, self.course_id, manifest)
        self._publish()
        self.store.enroll(self.student, self.course_id)

    def test_matching_pin_appends_pending_work_without_mastery(self):
        result = self._submit(**self.pin)
        self.assertEqual(result['version'], self.original['version'])
        self.assertEqual(result['status'], 'pending_review')
        self.assertFalse(result['mastery_updated'])
        self.assertFalse(result['proof_qualified'])

    def test_revision_after_external_precheck_blocks_new_submission(self):
        self._revise()
        with self.assertRaises(LearningConflictError):
            self._submit(**self.pin)
        with self.store._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM learning_submissions').fetchone()[0], 0)

    def test_exact_original_replay_survives_revision_but_different_pin_fails(self):
        self._submit(**self.pin)
        self._revise()
        self.assertTrue(self._submit(**self.pin)['duplicate'])
        current = self.store.get_course(self.student, self.course_id)
        with self.assertRaises(LearningConflictError):
            self._submit(expected_version=current['version'],
                         expected_manifest_sha256=current['manifest_sha256'])

    def test_same_version_wrong_manifest_never_inserts(self):
        with self.assertRaises(LearningConflictError):
            self._submit(expected_version=self.original['version'],
                         expected_manifest_sha256='0' * 64)

    def test_partial_or_malformed_pins_are_rejected(self):
        for pin in ({'expected_version': 1}, {'expected_manifest_sha256': 'a' * 64},
                    {'expected_version': True, 'expected_manifest_sha256': 'a' * 64},
                    {'expected_version': 1, 'expected_manifest_sha256': 'malformed'}):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                self._submit(**pin)


if __name__ == '__main__':
    unittest.main()
