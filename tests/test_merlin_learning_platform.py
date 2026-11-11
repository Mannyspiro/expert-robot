import tempfile
import unittest
from pathlib import Path

from python.merlin.learning_platform import (
    Actor, LearningConflictError, LearningPermissionError, LearningPlatform,
)


class LearningPlatformTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LearningPlatform(Path(self.tmp.name) / "learning.sqlite3")
        self.teacher = Actor("college-a", "faculty-1", "instructor")
        self.learner = Actor("college-a", "student-1", "learner")
        self.admin = Actor("college-a", "admin-1", "tenant_admin")
        self.reviewer = Actor("college-a", "reviewer-1", "reviewer")

    def tearDown(self):
        self.tmp.cleanup()

    def _publish(self, course):
        self.store.review_course(self.reviewer, course["course_id"], course["version"],
                                 "approved", "Independent content and assessment review.")
        return self.store.publish_course(self.teacher, course["course_id"])

    def _course(self):
        course = self.store.create_course(
            self.teacher, "intro-to-mathematics", "Introduction to Mathematics",
            "A foundational course.",
        )
        manifest = course["manifest"]
        manifest["modules"] = [{"id": "module-1", "title": "Representations"}]
        manifest["objectives"] = [
            {"id": "OBJ-1", "title": "Explain coordinates", "description": "Translate between forms.",
             "prerequisites": []},
            {"id": "OBJ-2", "title": "Rotate a point", "description": "Apply a rotation.",
             "prerequisites": ["OBJ-1"]},
        ]
        manifest["lessons"] = [
            {"id": "lesson-1", "title": "Coordinate foundations", "objective_id": "OBJ-1",
             "body": "Coordinates locate points in a reference frame."},
            {"id": "lesson-2", "title": "Quarter-turn rotation", "objective_id": "OBJ-2",
             "body": "A positive quarter turn maps (x,y) to (-y,x)."},
        ]
        manifest["assessments"] = [
            {"id": "assessment-1", "title": "Rotation check", "objective_id": "OBJ-2",
             "high_stakes": False, "human_review_required": False},
        ]
        manifest["resources"] = [
            {"id": "resource-1", "title": "Open notes", "source_uri": "https://example.org/notes",
             "license": "CC-BY-4.0", "creator": "Course faculty", "language": "en",
             "accessibility": {"transcript": True}},
        ]
        return self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_course_catalog_is_role_scoped_and_tenant_scoped(self):
        course = self._course()
        instructor_list = self.store.list_courses(self.teacher)
        self.assertEqual(instructor_list["count"], 1)
        self.assertEqual(instructor_list["courses"][0]["status"], "draft")
        self.assertEqual(self.store.list_courses(self.reviewer)["count"], 1)
        self.assertEqual(self.store.list_courses(self.learner)["count"], 0)

        self._publish(course)
        learner_catalog = self.store.list_courses(self.learner)
        self.assertEqual(learner_catalog["count"], 1)
        self.assertIsNone(learner_catalog["courses"][0]["enrollment_status"])
        self.store.enroll(self.learner, course["course_id"])
        enrolled_catalog = self.store.list_courses(self.learner)
        self.assertEqual(enrolled_catalog["courses"][0]["enrollment_status"], "active")

        other_teacher = Actor("college-a", "faculty-2", "instructor")
        self.assertEqual(self.store.list_courses(other_teacher)["count"], 0)
        other_tenant = Actor("college-b", "admin-b", "tenant_admin")
        self.assertEqual(self.store.list_courses(other_tenant)["count"], 0)
        self.assertEqual(self.store.list_courses(self.admin)["count"], 1)

    def test_publish_enroll_and_learner_scope(self):
        course = self._course()
        self.assertEqual(course["status"], "draft")
        published = self._publish(course)
        self.assertEqual(published["status"], "published")
        enrollment = self.store.enroll(self.learner, course["course_id"])
        self.assertEqual(enrollment["status"], "active")
        view = self.store.get_course(self.learner, course["course_id"])
        self.assertEqual(view["manifest"]["objectives"][1]["prerequisites"], ["OBJ-1"])
        with self.assertRaises(LearningPermissionError):
            self.store.get_course(Actor("college-a", "other-student", "learner"),
                                  course["course_id"])

    def test_publication_requires_independent_review(self):
        course = self._course()
        with self.assertRaisesRegex(LearningConflictError, "independent reviewer"):
            self.store.publish_course(self.teacher, course["course_id"])
        with self.assertRaises(LearningPermissionError):
            self.store.review_course(self.teacher, course["course_id"], course["version"],
                                     "approved", "author cannot self-review")
        self.store.review_course(self.reviewer, course["course_id"], course["version"],
                                 "approved", "independent review")
        published = self.store.publish_course(self.teacher, course["course_id"])
        self.assertEqual(published["status"], "published")

    def test_published_version_is_immutable_and_revision_is_new_version(self):
        course = self._course()
        self._publish(course)
        with self.assertRaises(LearningConflictError):
            self.store.update_manifest(self.teacher, course["course_id"], course["manifest"])
        revision = self.store.create_revision(self.teacher, course["course_id"])
        self.assertEqual(revision["version"], 2)
        self.assertEqual(revision["status"], "draft")
        self.assertEqual(self.store.get_course(self.teacher, course["course_id"], 1)["status"],
                         "published")

    def test_tenant_isolation_and_owner_permissions(self):
        course = self._course()
        other_tenant = Actor("college-b", "admin-b", "tenant_admin")
        with self.assertRaises(KeyError):
            self.store.get_course(other_tenant, course["course_id"])
        other_teacher = Actor("college-a", "faculty-2", "instructor")
        with self.assertRaises(LearningPermissionError):
            self.store.update_manifest(other_teacher, course["course_id"], course["manifest"])

    def test_high_stakes_assessment_requires_human_review(self):
        course = self.store.create_course(self.teacher, "ethics-101", "Ethics 101")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "ETH-1", "title": "Evaluate an argument"}]
        manifest["assessments"] = [
            {"id": "final", "title": "Final examination", "objective_id": "ETH-1",
             "high_stakes": True, "human_review_required": False},
        ]
        with self.assertRaisesRegex(ValueError, "human review"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_objective_graph_rejects_unknown_prerequisite_and_bad_lesson_link(self):
        course = self.store.create_course(self.teacher, "graph-101", "Graph 101")
        manifest = course["manifest"]
        manifest["objectives"] = [
            {"id": "A", "title": "A", "prerequisites": ["MISSING"]},
        ]
        with self.assertRaisesRegex(ValueError, "unknown objective"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)
        manifest["objectives"] = [{"id": "A", "title": "A", "prerequisites": []}]
        manifest["lessons"] = [{"id": "L", "title": "Lesson", "objective_id": "MISSING"}]
        with self.assertRaisesRegex(ValueError, "known objective"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_objective_graph_rejects_cycles_and_duplicate_prerequisites(self):
        course = self.store.create_course(self.teacher, "cycle-101", "Cycle 101")
        manifest = course["manifest"]
        manifest["objectives"] = [
            {"id": "A", "title": "A", "prerequisites": ["B"]},
            {"id": "B", "title": "B", "prerequisites": ["A"]},
        ]
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)
        manifest["objectives"][0]["prerequisites"] = ["B", "B"]
        with self.assertRaisesRegex(ValueError, "unique"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_duplicate_lesson_and_assessment_ids_are_rejected(self):
        course = self.store.create_course(self.teacher, "duplicate-ids", "Duplicate IDs")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "A", "title": "A"}]
        manifest["lessons"] = [
            {"id": "L", "title": "Lesson one", "objective_id": "A"},
            {"id": "L", "title": "Lesson two", "objective_id": "A"},
        ]
        with self.assertRaisesRegex(ValueError, "lesson IDs must be unique"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)
        manifest["lessons"] = []
        manifest["assessments"] = [
            {"id": "Q", "title": "Quiz one", "objective_id": "A"},
            {"id": "Q", "title": "Quiz two", "objective_id": "A"},
        ]
        with self.assertRaisesRegex(ValueError, "assessment IDs must be unique"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_resources_require_https_and_boolean_review_flags(self):
        course = self.store.create_course(self.teacher, "resource-policy", "Resource Policy")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "A", "title": "A"}]
        manifest["resources"] = [
            {"id": "R", "title": "Resource", "source_uri": "http://example.org",
             "license": "CC-BY-4.0", "creator": "Author"}
        ]
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)
        manifest["resources"] = []
        manifest["assessments"] = [
            {"id": "Q", "title": "Quiz", "objective_id": "A",
             "high_stakes": "false", "human_review_required": False}
        ]
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_resource_requires_rights_and_provenance_metadata(self):
        course = self.store.create_course(self.teacher, "media-101", "Media 101")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "M", "title": "Media literacy"}]
        manifest["resources"] = [
            {"id": "R", "title": "Unattributed video", "source_uri": "https://example.org/v",
             "license": "", "creator": ""},
        ]
        with self.assertRaises(ValueError):
            self.store.update_manifest(self.teacher, course["course_id"], manifest)

    def test_audit_is_append_only_metadata_and_role_gated(self):
        course = self._course()
        self._publish(course)
        events = self.store.audit_events(self.admin)
        self.assertGreaterEqual(len(events), 3)
        self.assertTrue(all("payload_sha256" in event for event in events))
        with self.assertRaises(LearningPermissionError):
            self.store.audit_events(self.learner)

    def test_slug_validation_and_duplicate_detection(self):
        with self.assertRaises(ValueError):
            self.store.create_course(self.teacher, "../course", "Invalid")
        self.store.create_course(self.teacher, "valid-course", "Valid")
        with self.assertRaises(Exception):
            self.store.create_course(self.teacher, "valid-course", "Duplicate")


    def test_assessment_submissions_are_append_only_idempotent_and_human_reviewed(self):
        course = self._course()
        self._publish(course)
        self.store.enroll(self.learner, course["course_id"])
        with self.assertRaises(LearningPermissionError):
            self.store.submit_assessment(
                self.learner, course["course_id"], "submission-1", "lesson-2",
                "wrong-task", {"answer": "x"},
            )
        submitted = self.store.submit_assessment(
            self.learner, course["course_id"], "submission-1", "lesson-2",
            "rotation-check", {"explanation": "A quarter turn maps (x,y) to (-y,x)."},
        )
        self.assertEqual(submitted["status"], "pending_review")
        self.assertFalse(submitted["mastery_updated"])
        self.assertFalse(submitted["proof_qualified"])
        replay = self.store.submit_assessment(
            self.learner, course["course_id"], "submission-1", "lesson-2",
            "rotation-check", {"explanation": "A quarter turn maps (x,y) to (-y,x)."},
        )
        self.assertTrue(replay["duplicate"])
        with self.assertRaises(LearningConflictError):
            self.store.submit_assessment(
                self.learner, course["course_id"], "submission-1", "lesson-2",
                "rotation-check", {"explanation": "Different answer"},
            )
        queue = self.store.list_submissions(self.reviewer, course["course_id"])
        self.assertEqual(queue["count"], 1)
        self.assertEqual(queue["submissions"][0]["response"]["explanation"],
                         "A quarter turn maps (x,y) to (-y,x).")
        with self.assertRaises(LearningPermissionError):
            self.store.review_submission(
                self.teacher, course["course_id"], "submission-1", "accepted", "self-review"
            )
        review = self.store.review_submission(
            self.reviewer, course["course_id"], "submission-1", "accepted",
            "Clear explanation.", {"procedure": 1.0},
        )
        self.assertFalse(review["mastery_updated"])
        self.assertFalse(review["proof_qualified"])
        queue = self.store.list_submissions(self.admin, course["course_id"])
        self.assertEqual(queue["submissions"][0]["status"], "accepted")
        with self.assertRaises(LearningPermissionError):
            self.store.list_submissions(self.learner, course["course_id"])


if __name__ == "__main__":
    unittest.main()
