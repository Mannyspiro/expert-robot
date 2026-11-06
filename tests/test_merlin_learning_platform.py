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

    def test_publish_enroll_and_learner_scope(self):
        course = self._course()
        self.assertEqual(course["status"], "draft")
        published = self.store.publish_course(self.teacher, course["course_id"])
        self.assertEqual(published["status"], "published")
        enrollment = self.store.enroll(self.learner, course["course_id"])
        self.assertEqual(enrollment["status"], "active")
        view = self.store.get_course(self.learner, course["course_id"])
        self.assertEqual(view["manifest"]["objectives"][1]["prerequisites"], ["OBJ-1"])
        with self.assertRaises(LearningPermissionError):
            self.store.get_course(Actor("college-a", "other-student", "learner"),
                                  course["course_id"])

    def test_published_version_is_immutable_and_revision_is_new_version(self):
        course = self._course()
        self.store.publish_course(self.teacher, course["course_id"])
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
        self.store.publish_course(self.teacher, course["course_id"])
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


if __name__ == "__main__":
    unittest.main()
