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
from python.merlin.learner_model import LearnerStore, learner_subject_id


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
            "Bearer admin": Actor("tenant-a", "admin-1", "tenant_admin"),
            "Bearer learner": Actor("tenant-a", "student-1", "learner"),
            "Bearer learner-course-authoring": Actor("tenant-a", "student-course-authoring", "learner"),
            "Bearer learner-profile": Actor("tenant-a", "student-profile", "learner"),
            "Bearer learner-foundations": Actor("tenant-a", "student-foundations", "learner"),
            "Bearer learner-logic": Actor("tenant-a", "student-logic", "learner"),
            "Bearer learner-algebra": Actor("tenant-a", "student-algebra", "learner"),
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
        learner_ref = learner_subject_id("tenant-a", "student-course-authoring")
        status, course = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "physics-foundations", "title": "Physics Foundations",
            "description": "A first course.",
            "role": "tenant_admin", "tenant_id": "tenant-b",
        })
        self.assertEqual(status, 201)
        cid = course["course_id"]
        status, faculty_catalog = self.request("GET", "/api/learning/courses", "Bearer faculty")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(faculty_catalog["count"], 1)
        created = next((item for item in faculty_catalog["courses"]
                        if item["course_id"] == cid), None)
        self.assertIsNotNone(created)
        self.assertEqual(created["status"], "draft")
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
             "body": "Acceleration is the rate of change of velocity.",
             "interest_tags": ["physics"],
             "exercise": {"task_id": "acceleration-explain",
                          "prompt": "Explain acceleration in your own words."}},
        ]
        manifest["assessments"] = [{
            "id": "assessment-phy-2", "title": "Acceleration explanation",
            "objective_id": "PHY-2", "high_stakes": False,
            "human_review_required": True,
            "rubric": [{"dimension": "conceptual_explanation",
                        "description": "Explains change in velocity.", "points": 2}],
        }]
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
        status, learner_catalog = self.request("GET", "/api/learning/courses", "Bearer learner-course-authoring")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(learner_catalog["count"], 1)
        learner_course = next((item for item in learner_catalog["courses"]
                               if item["course_id"] == cid), None)
        self.assertIsNotNone(learner_course)
        self.assertIsNone(learner_course["enrollment_status"])
        status, enrollment = self.request("POST", f"/api/learning/courses/{cid}/enroll",
                                          "Bearer learner-course-authoring", {})
        self.assertEqual(status, 200)
        self.assertEqual(enrollment["learner_id"], "student-course-authoring")
        status, submission = self.request(
            "POST", f"/api/learning/courses/{cid}/submissions", "Bearer learner-course-authoring", {
                "submission_id": "physics-submission-1",
                "lesson_id": "lesson-2",
                "task_id": "acceleration-explain",
                "response": {"explanation": "Acceleration measures how velocity changes over time."},
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(submission["status"], "pending_review")
        self.assertTrue(submission["rubric_sha256"])
        self.assertFalse(submission["mastery_updated"])
        with self.assertRaises(HTTPError) as unqualified:
            self.request(
                "GET", f"/api/learning/courses/{cid}/submissions", "Bearer reviewer"
            )
        self.assertEqual(unqualified.exception.code, 403)
        status, calibration = self.request(
            "POST", "/api/learning/reviewers/reviewer-1/calibration", "Bearer admin", {
                "calibration_sha256": "a" * 64,
                "case_count": 10,
                "agreement_score": 0.95,
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(calibration["status"], "qualified")
        status, queue = self.request(
            "GET", f"/api/learning/courses/{cid}/submissions", "Bearer reviewer"
        )
        self.assertEqual(status, 200)
        self.assertEqual(queue["count"], 1)
        self.assertEqual(
            queue["submissions"][0]["assessment_rubric"][0]["dimension"],
            "conceptual_explanation",
        )
        self.assertTrue(queue["submissions"][0]["assessment_title"])
        status, review_result = self.request(
            "POST", f"/api/learning/courses/{cid}/submissions/physics-submission-1/review",
            "Bearer reviewer", {
                "decision": "accepted",
                "feedback": "The explanation correctly identifies change in velocity.",
                "rubric_scores": {"conceptual_explanation": 1.0},
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(review_result["decision"], "accepted")
        self.assertEqual(review_result["rubric_sha256"], submission["rubric_sha256"])
        self.assertFalse(review_result["mastery_updated"])
        with self.assertRaises(HTTPError) as duplicate_review:
            self.request(
                "POST", f"/api/learning/courses/{cid}/submissions/physics-submission-1/review",
                "Bearer reviewer", {"decision": "needs_revision", "feedback": "A second final decision must not overwrite the first."},
            )
        self.assertEqual(duplicate_review.exception.code, 400)
        status, my_work = self.request(
            "GET", f"/api/learning/courses/{cid}/submissions/mine", "Bearer learner-course-authoring"
        )
        self.assertEqual(status, 200)
        self.assertEqual(my_work["submissions"][0]["reviews"][0]["feedback"],
                         "The explanation correctly identifies change in velocity.")
        self.assertEqual(
            my_work["submissions"][0]["reviews"][0]["rubric_sha256"],
            submission["rubric_sha256"],
        )
        self.assertEqual(
            my_work["submissions"][0]["reviews"][0]["rubric_scores"],
            {"conceptual_explanation": 1.0},
        )
        self.assertFalse(my_work["mastery_updated"])
        status, enrolled_catalog = self.request("GET", "/api/learning/courses", "Bearer learner-course-authoring")
        self.assertEqual(status, 200)
        enrolled_course = next((item for item in enrolled_catalog["courses"]
                                 if item["course_id"] == cid), None)
        self.assertIsNotNone(enrolled_course)
        self.assertEqual(enrolled_course["enrollment_status"], "active")
        status, learner_view = self.request("GET", f"/api/learning/courses/{cid}",
                                            "Bearer learner-course-authoring")
        self.assertEqual(status, 200)
        self.assertEqual(learner_view["manifest"]["objectives"][0]["id"], "PHY-1")
        for attempt_id, session_id in (("phy-attempt-1", "phy-session-a"),
                                       ("phy-attempt-2", "phy-session-b")):
            self.learner_store.record_attempt({
                "learner_id": learner_ref, "attempt_id": attempt_id,
                "idea_id": "PHY-1", "problem_id": "motion-explain",
                "problem_version": "1", "dimension": "conceptual_explanation",
                "score": 1.0, "session_id": session_id,
                "response": {"explanation": "Position changes over time."},
                "rubric_version": "motion-r1", "delayed": True, "transfer": True,
            })
        status, recommendation = self.request(
            "GET", f"/api/learning/courses/{cid}/recommendation", "Bearer learner-course-authoring")
        self.assertEqual(status, 200)
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["lesson_id"], "lesson-2")
        self.assertEqual(recommendation["authority"], "recommendation_only")

        # Two independent delayed/transfer demonstrations unlock the prerequisite.
        for dimension in ["recognition", "conceptual_explanation", "representation_translation", "transfer"]:
            for session_number in (1, 2):
                self.learner_store.record_attempt({
                    "learner_id": learner_ref,
                    "attempt_id": f"math-foundations-{dimension}-{session_number}",
                    "idea_id": "MATH-NT-001",
                    "problem_id": "math-foundations-whole-number-diagnostic",
                    "problem_version": "1",
                    "dimension": dimension,
                    "score": 1.0,
                    "session_id": f"math-foundations-session-{session_number}",
                    "response": {"fixture": "independent-transfer"},
                    "rubric_version": "foundation-test-v1",
                    "delayed": True,
                    "transfer": True,
                })

        status, preferences = self.request("POST", "/api/learning/profile", "Bearer learner-course-authoring", {
            "pathway_weights": {
                "mathematician": 0.0,
                "mathematics_programmer": 1.0,
                "computational_hacker": 0.0,
            },
            "interests": ["physics"],
            "pace": "standard",
        })
        self.assertEqual(status, 200)
        self.assertEqual(preferences["max_minutes"], 35)
        status, personalized = self.request(
            "GET", f"/api/learning/courses/{course['course_id']}/recommendation",
            "Bearer learner-course-authoring",
        )
        self.assertEqual(status, 200)
        self.assertEqual(personalized["lesson_id"], "lesson-2")
        self.assertIn("matches_learner_interests", personalized["reason_codes"])

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


    def test_math_foundations_template_is_instructor_only_and_uses_normal_review_flow(self):
        status, preview = self.request(
            "GET", "/api/learning/templates/math-foundations", "Bearer faculty"
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["curriculum_id"], "math-foundations-v1")
        self.assertEqual(preview["objective_count"], 7)
        self.assertEqual(preview["lesson_count"], 7)

        with self.assertRaises(HTTPError) as denied:
            self.request("GET", "/api/learning/templates/math-foundations", "Bearer learner-foundations")
        self.assertEqual(denied.exception.code, 403)

        status, draft = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "math-foundations",
            "title": preview["title"],
            "description": "First-principles mathematics across proof, programming, and computational problem solving.",
        })
        self.assertEqual(status, 201)
        course_id = draft["course_id"]

        status, applied = self.request(
            "POST",
            f"/api/learning/courses/{course_id}/templates/math-foundations",
            "Bearer faculty",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(applied["manifest"]["curriculum_id"], "math-foundations-v1")
        self.assertEqual(len(applied["manifest"]["objectives"]), 7)
        self.assertEqual(len(applied["manifest"]["lessons"]), 7)
        self.assertTrue(applied["manifest_sha256"])

        status, review = self.request(
            "POST", f"/api/learning/courses/{course_id}/review", "Bearer reviewer",
            {"version": 1, "decision": "approved", "notes": "Reviewed low-stakes foundations template."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(review["decision"], "approved")
        status, published = self.request(
            "POST", f"/api/learning/courses/{course_id}/publish", "Bearer faculty", {}
        )
        self.assertEqual(status, 200)
        self.assertEqual(published["status"], "published")
        status, enrollment = self.request(
            "POST", f"/api/learning/courses/{course_id}/enroll", "Bearer learner-foundations", {}
        )
        self.assertEqual(status, 200)
        status, recommendation = self.request(
            "GET", f"/api/learning/courses/{course_id}/recommendation", "Bearer learner-foundations"
        )
        self.assertEqual(status, 200)
        self.assertEqual(recommendation["state"], "recommended")
        self.assertEqual(recommendation["lesson_id"], "math-foundations-counting-v1")
        self.assertEqual(recommendation["authority"], "recommendation_only")

    def test_learner_profile_is_identity_scoped_and_persisted(self):
        status, default = self.request("GET", "/api/learning/profile", "Bearer learner-profile")
        self.assertEqual(status, 200)
        self.assertAlmostEqual(sum(default["pathway_weights"].values()), 1.0)
        self.assertEqual(default["interests"], [])

        status, updated = self.request("POST", "/api/learning/profile", "Bearer learner-profile", {
            "pathway_weights": {
                "mathematician": 0.0,
                "mathematics_programmer": 1.0,
                "computational_hacker": 0.0,
            },
            "interests": ["Number Theory", "python"],
            "pace": "gentle",
        })
        self.assertEqual(status, 200)
        self.assertEqual(updated["interests"], ["number_theory", "python"])
        self.assertEqual(updated["max_minutes"], 20)

        status, persisted = self.request("GET", "/api/learning/profile", "Bearer learner-profile")
        self.assertEqual(status, 200)
        self.assertEqual(persisted["pathway_weights"], updated["pathway_weights"])
        self.assertEqual(persisted["interests"], updated["interests"])

        with self.assertRaises(HTTPError) as instructor_denied:
            self.request("POST", "/api/learning/profile", "Bearer faculty", {"interests": ["proof"]})
        self.assertEqual(instructor_denied.exception.code, 403)

        with self.assertRaises(HTTPError) as identity_denied:
            self.request("POST", "/api/learning/profile", "Bearer learner-profile", {
                "learner_id": "another-learner", "interests": ["proof"]
            })
        self.assertEqual(identity_denied.exception.code, 400)


    def test_legacy_learner_endpoints_are_identity_scoped(self):
        with self.assertRaises(HTTPError) as unauthenticated:
            self.request("GET", "/api/learning/recommendation?learner_id=student-1")
        self.assertEqual(unauthenticated.exception.code, 503)

        status, recommendation = self.request(
            "GET", "/api/learning/recommendation?learner_id=student-1", "Bearer learner"
        )
        self.assertEqual(status, 200)
        self.assertEqual(recommendation["learner_id"], "student-1")

        with self.assertRaises(HTTPError) as mismatched_recommendation:
            self.request(
                "GET", "/api/learning/recommendation?learner_id=another-learner", "Bearer learner"
            )
        self.assertEqual(mismatched_recommendation.exception.code, 403)

        status, state = self.request(
            "GET", "/api/learning/learner?learner_id=student-1", "Bearer learner"
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["learner_id"], "student-1")
        with self.assertRaises(HTTPError) as mismatched_state:
            self.request(
                "GET", "/api/learning/learner?learner_id=another-learner", "Bearer learner"
            )
        self.assertEqual(mismatched_state.exception.code, 403)


    def test_logic_discrete_template_publish_enroll_and_submit(self):
        status, preview = self.request(
            "GET", "/api/learning/templates/math-logic-discrete", "Bearer faculty"
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["curriculum_id"], "math-logic-discrete-v1")
        self.assertEqual(preview["objective_count"], 3)
        with self.assertRaises(HTTPError) as denied:
            self.request("GET", "/api/learning/templates/math-logic-discrete", "Bearer learner-logic")
        self.assertEqual(denied.exception.code, 403)

        status, draft = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "math-logic-discrete-bridge",
            "title": preview["title"],
            "description": "Logic, sets, relations and graph structures.",
        })
        self.assertEqual(status, 201)
        course_id = draft["course_id"]
        status, applied = self.request(
            "POST", f"/api/learning/courses/{course_id}/templates/math-logic-discrete",
            "Bearer faculty", {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(applied["manifest"]["lessons"]), 3)

        status, review = self.request(
            "POST", f"/api/learning/courses/{course_id}/review", "Bearer reviewer",
            {"version": 1, "decision": "approved", "notes": "Reviewed concrete-first sequence."},
        )
        self.assertEqual(status, 200)
        status, published = self.request(
            "POST", f"/api/learning/courses/{course_id}/publish", "Bearer faculty", {}
        )
        self.assertEqual(status, 200)
        self.assertEqual(published["status"], "published")
        status, enrollment = self.request(
            "POST", f"/api/learning/courses/{course_id}/enroll", "Bearer learner-logic", {}
        )
        self.assertEqual(status, 200)

        status, submitted = self.request(
            "POST", f"/api/learning/courses/{course_id}/submissions", "Bearer learner-logic", {
                "submission_id": "logic-bridge-submission-1",
                "lesson_id": "math-logic-quantifiers-v1",
                "task_id": "logic-quantifier-scope",
                "response": "Some elements satisfy the predicate; the universal claim is false.",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(submitted["status"], "pending_review")
        self.assertFalse(submitted["mastery_updated"])


    def test_algebra_functions_template_lifecycle_and_exercise_submission(self):
        status, preview = self.request(
            "GET", "/api/learning/templates/math-algebra-functions", "Bearer faculty"
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["curriculum_id"], "math-algebra-functions-v1")
        self.assertEqual(preview["objective_count"], 5)
        status, draft = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "math-algebra-functions-bridge",
            "title": preview["title"],
            "description": "From patterns and variables to equations and mappings.",
        })
        self.assertEqual(status, 201)
        course_id = draft["course_id"]
        status, applied = self.request(
            "POST", f"/api/learning/courses/{course_id}/templates/math-algebra-functions",
            "Bearer faculty", {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(applied["manifest"]["objectives"]), 5)
        status, review = self.request(
            "POST", f"/api/learning/courses/{course_id}/review", "Bearer reviewer",
            {"version": 1, "decision": "approved", "notes": "Reviewed algebra bridge."},
        )
        self.assertEqual(status, 200)
        status, published = self.request(
            "POST", f"/api/learning/courses/{course_id}/publish", "Bearer faculty", {}
        )
        self.assertEqual(status, 200)
        status, enrollment = self.request(
            "POST", f"/api/learning/courses/{course_id}/enroll", "Bearer learner-algebra", {}
        )
        self.assertEqual(status, 200)
        status, submitted = self.request(
            "POST", f"/api/learning/courses/{course_id}/submissions", "Bearer learner-algebra", {
                "submission_id": "algebra-bridge-submission-1",
                "lesson_id": "math-equations-inequalities-v1",
                "task_id": "solve-equations-preserve-solutions",
                "response": "3x + 5 = 20 gives x = 5; the inequality solution is x >= -3.",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(submitted["status"], "pending_review")
        self.assertFalse(submitted["proof_qualified"])


    def test_calculus_probability_template_is_instructor_only_and_applies(self):
        status, preview = self.request(
            "GET", "/api/learning/templates/math-calculus-probability", "Bearer faculty"
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["curriculum_id"], "math-calculus-probability-v1")
        self.assertEqual(preview["lesson_count"], 5)
        with self.assertRaises(HTTPError) as denied:
            self.request(
                "GET", "/api/learning/templates/math-calculus-probability", "Bearer learner"
            )
        self.assertEqual(denied.exception.code, 403)

        status, draft = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "math-calculus-probability",
            "title": preview["title"],
            "description": "Calculus, probability and statistical reasoning.",
        })
        self.assertEqual(status, 201)
        course_id = draft["course_id"]
        status, applied = self.request(
            "POST", f"/api/learning/courses/{course_id}/templates/math-calculus-probability",
            "Bearer faculty", {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(applied["manifest"]["lessons"]), 5)
        calc = next(
            item for item in applied["manifest"]["objectives"]
            if item["id"] == "MATH-CALC-001"
        )
        self.assertEqual(calc["external_prerequisites"], ["MATH-FUNC-001"])


    def test_numerical_methods_template_declares_external_prerequisites(self):
        status, preview = self.request(
            "GET", "/api/learning/templates/math-numerical-scientific-computing", "Bearer faculty"
        )
        self.assertEqual(status, 200)
        self.assertEqual(preview["curriculum_id"], "math-numerical-scientific-computing-v1")
        self.assertEqual(preview["lesson_count"], 4)
        status, draft = self.request("POST", "/api/learning/courses", "Bearer faculty", {
            "slug": "math-numerical-scientific-computing",
            "title": preview["title"],
            "description": "Numerical methods and scientific computing.",
        })
        self.assertEqual(status, 201)
        status, applied = self.request(
            "POST",
            f"/api/learning/courses/{draft['course_id']}/templates/math-numerical-scientific-computing",
            "Bearer faculty",
            {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(applied["manifest"]["lessons"]), 4)
        ode = next(
            item for item in applied["manifest"]["objectives"]
            if item["id"] == "MATH-ODE-001"
        )
        self.assertEqual(
            ode["external_prerequisites"], ["MATH-CALC-002", "MATH-CALC-003"]
        )


if __name__ == "__main__":
    unittest.main()
