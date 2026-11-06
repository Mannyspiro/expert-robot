import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from python.merlin.app import EventStore, make_handler
from python.merlin.learning_platform import Actor, LearningPlatform
from python.merlin.learner_model import LearnerStore


class MerlinLearningHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.store = EventStore(root / "events.sqlite3")
        cls.platform = LearningPlatform(root / "learning.sqlite3")
        cls.learner_store = LearnerStore(root / "learner.sqlite3")
        cls.actors = {
            "Bearer faculty": Actor("tenant-a", "faculty-1", "instructor"),
            "Bearer reviewer": Actor("tenant-a", "reviewer-1", "reviewer"),
            "Bearer learner": Actor("tenant-a", "student-1", "learner"),
            "Bearer outsider": Actor("tenant-b", "student-2", "learner"),
        }

        def resolve(headers):
            # Test-only stand-in for a verified OIDC/session resolver.
            return cls.actors.get(headers.get("Authorization"))

        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            make_handler(cls.store, learner_store=cls.learner_store,
                         learning_platform=cls.platform, learning_identity_resolver=resolve),
        )
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def request(self, method, path, token=None, payload=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = token
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base + path, data=body, headers=headers, method=method)
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_course_authoring_review_publish_enroll_and_read_flow(self):
        status, course = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "physics-foundations", "title": "Physics Foundations",
            "description": "A first course.",
            "role": "tenant_admin", "tenant_id": "tenant-b",
        })
        self.assertEqual(status, 201)
        cid = course["course_id"]
        status, faculty_catalog = self.request("GET", "/api/learning/courses", "Bearer faculty")
        self.assertEqual(status, 200)
        self.assertEqual(faculty_catalog["count"], 1)
        self.assertEqual(faculty_catalog["courses"][0]["course_id"], cid)
        self.assertEqual(faculty_catalog["courses"][0]["status"], "draft")
        manifest = course["manifest"]
        manifest["objectives"] = [{"id": "PHY-1", "title": "Describe motion", "prerequisites": [],
                                  "dimensions": ["conceptual_explanation"]},
                                 {"id": "PHY-2", "title": "Model acceleration",
                                  "prerequisites": ["PHY-1"],
                                  "dimensions": ["conceptual_explanation"]}]
        manifest["lessons"] = [
            {"id": "lesson-1", "title": "Motion", "objective_id": "PHY-1",
             "body": "Position changes over time."},
            {"id": "lesson-2", "title": "Acceleration", "objective_id": "PHY-2",
             "body": "Acceleration is the rate of change of velocity."},
        ]
        manifest["resources"] = [{"id": "resource-1", "title": "Open resource",
                                  "source_uri": "https://example.org/physics",
                                  "license": "CC-BY-4.0", "creator": "Faculty"}]
        self.request("POST", f"/api/learning/courses/{cid}/manifest", "Bearer faculty",
                     {"manifest": manifest})
        status, review = self.request("POST", f"/api/learning/courses/{cid}/review",
                                      "Bearer reviewer",
                                      {"version": 1, "decision": "approved", "notes": "Reviewed."})
        self.assertEqual(status, 200)
        self.assertEqual(review["decision"], "approved")
        status, published = self.request("POST", f"/api/learning/courses/{cid}/publish",
                                          "Bearer faculty", {})
        self.assertEqual(status, 200)
        self.assertEqual(published["status"], "published")
        status, learner_catalog = self.request("GET", "/api/learning/courses", "Bearer learner")
        self.assertEqual(status, 200)
        self.assertEqual(learner_catalog["count"], 1)
        self.assertIsNone(learner_catalog["courses"][0]["enrollment_status"])
        status, enrollment = self.request("POST", f"/api/learning/courses/{cid}/enroll",
                                          "Bearer learner", {})
        self.assertEqual(status, 200)
        self.assertEqual(enrollment["learner_id"], "student-1")
        status, enrolled_catalog = self.request("GET", "/api/learning/courses", "Bearer learner")
        self.assertEqual(status, 200)
        self.assertEqual(enrolled_catalog["courses"][0]["enrollment_status"], "active")
        status, learner_view = self.request("GET", f"/api/learning/courses/{cid}",
                                            "Bearer learner")
        self.assertEqual(status, 200)
        self.assertEqual(learner_view["manifest"]["objectives"][0]["id"], "PHY-1")
        for attempt_id, session_id in (("phy-attempt-1", "phy-session-a"),
                                       ("phy-attempt-2", "phy-session-b")):
            self.learner_store.record_attempt({
                "learner_id": "student-1", "attempt_id": attempt_id,
                "idea_id": "PHY-1", "problem_id": "motion-explain",
                "problem_version": "1", "dimension": "conceptual_explanation",
                "score": 1.0, "session_id": session_id,
                "response": {"explanation": "Position changes over time."},
                "rubric_version": "motion-r1", "delayed": True, "transfer": True,
            })
        status, recommendation = self.request(
            "GET", f"/api/learning/courses/{cid}/recommendation", "Bearer learner")
        self.assertEqual(status, 200)
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["lesson_id"], "lesson-2")
        self.assertEqual(recommendation["authority"], "recommendation_only")

    def test_unauthenticated_and_cross_tenant_access_fail_closed(self):
        request = Request(self.base + "/api/learning/courses", data=b'{"slug":"x","title":"X"}',
                          headers={"Content-Type": "application/json"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 503)
        self.assertEqual(json.loads(caught.exception.read())["error"],
                         "learning_identity_provider_not_configured")

        _, course = self.request("POST", "/api/learning/courses", "Bearer faculty",
                                 {"slug": "tenant-course", "title": "Tenant Course"})
        with self.assertRaises(HTTPError) as denied:
            self.request("GET", f"/api/learning/courses/{course['course_id']}", "Bearer outsider")
        self.assertEqual(denied.exception.code, 404)
        self.assertEqual(json.loads(denied.exception.read())["error"], "course_not_found")

    def test_learner_cannot_create_or_publish_courses(self):
        request = Request(self.base + "/api/learning/courses",
                          data=b'{"slug":"blocked-course","title":"Blocked"}',
                          headers={"Content-Type": "application/json",
                                   "Authorization": "Bearer learner"})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
