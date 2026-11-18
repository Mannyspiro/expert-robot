"""Exercise the host-authenticated Titan lab routes with synthetic learner state."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from merlin.app import EventStore, make_handler
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.learning_lab_bridge import LearningLabBridge
from merlin.learning_platform import Actor, LearningPlatform
from merlin.learning_titan_course import LAB_LESSON_ID, create_titan_course
from merlin.project_registry import MerlinRegistry
from merlin.research_evidence import ResearchEvidenceRecorder


class TitanHttpTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.store = EventStore(root / "events.sqlite3")
        self.platform = LearningPlatform(root / "learning.sqlite3")
        self.learner = Actor("college", "learner", "learner")
        teacher = Actor("college", "instructor", "instructor")
        reviewer = Actor("college", "reviewer", "reviewer")
        revision = "b" * 40
        draft = create_titan_course(self.platform, teacher, revision)
        cid = draft["course_id"]
        self.platform.review_course(reviewer, cid, 1, "approved", "Synthetic fixture review.")
        course = self.platform.publish_course(teacher, cid)
        self.platform.enroll(self.learner, cid)
        registry = MerlinRegistry(root / "registry")
        registry.register_project("learning", "Synthetic lab evidence")
        recorder = ResearchEvidenceRecorder(registry, HypothesisLedger(root / "ledger.sqlite3"),
                                            MerlinKnowledgeGraph(root / "graph.sqlite3"))
        self.bridge = LearningLabBridge(self.platform, recorder, tenant_projects={"college": "learning"},
                                        source_commit=revision)
        self.route = f"/api/learning/courses/{cid}/titan-lab/"
        self.binding = dict(course_version=1, manifest_sha256=course["manifest_sha256"],
                            lesson_id=LAB_LESSON_ID, run_id="http-fixture")

    def start(self, bridge):
        actors = {"Bearer fixture": self.learner, "Bearer outsider": Actor("other", "learner", "learner")}
        handler = make_handler(self.store, learning_platform=self.platform, learning_lab_bridge=bridge,
                               learning_identity_resolver=lambda headers: actors.get(headers.get("Authorization")))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}" + self.route

    def post(self, action, payload, token="Bearer fixture"):
        request = Request(self.url + action, data=json.dumps(payload).encode(),
                          headers={"Authorization": token, "Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_session_bound_run_and_submission_replay(self):
        self.start(self.bridge)
        run = dict(self.binding, prediction="The five fixed structural vector results should reproduce.")
        self.assertEqual(self.post("run", run, token="")[0], 503)
        self.assertEqual(self.post("run", run, token="Bearer outsider")[0], 403)
        self.assertEqual(self.post("run", dict(run, tenant_id="college"))[0], 400)
        self.assertEqual(self.post("run", dict(run, manifest_sha256="0" * 64))[0], 409)
        status, receipt = self.post("run", run)
        self.assertEqual(status, 200, receipt)
        self.assertEqual(receipt["binding"]["learner_id"], self.learner.actor_id)
        self.assertEqual(self.post("run", run), (200, receipt))
        submit = dict(self.binding, submission_id="http-submission",
                      reflection="The public fixture reproduces structure; independent review is pending.")
        status, result = self.post("submit", submit)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "pending_review")
        self.assertFalse(result["mastery_updated"])
        self.assertTrue(self.post("submit", submit)[1]["duplicate"])

    def test_unconfigured_host(self):
        self.start(None)
        self.assertEqual(self.post("run", self.binding), (503, {"error": "learning_lab_not_configured"}))
