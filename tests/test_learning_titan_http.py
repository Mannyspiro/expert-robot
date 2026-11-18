"""Exercise the host-authenticated Titan lab routes with synthetic learner state."""
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from merlin.app import EventStore, make_handler
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.identity import SQLiteTokenRevocationStore, learning_identity_resolver_from_environment
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

    def start(self, bridge, resolver=None):
        actors = {"Bearer fixture": self.learner, "Bearer outsider": Actor("other", "learner", "learner")}
        handler = make_handler(self.store, learning_platform=self.platform, learning_lab_bridge=bridge,
                               learning_identity_resolver=resolver or (lambda headers: actors.get(headers.get("Authorization"))))
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

    def test_signed_session_key_rotation_and_revocation(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        published = {}
        fetches = []

        class KeyEndpoint(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/keys":
                    self.send_error(404)
                    return
                fetches.append(published["kid"])
                body = json.dumps({"keys": [published]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass

        issuer_server = ThreadingHTTPServer(("127.0.0.1", 0), KeyEndpoint)
        thread = threading.Thread(target=issuer_server.serve_forever)
        thread.start()
        self.addCleanup(issuer_server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(issuer_server.shutdown)
        issuer = f"http://127.0.0.1:{issuer_server.server_port}"
        audience = "synthetic-learning"
        revocations = Path(self.store.path).with_name("revocations.sqlite3")
        settings = {"MERLIN_OIDC_ISSUER": issuer, "MERLIN_OIDC_AUDIENCE": audience,
                    "MERLIN_OIDC_JWKS_URL": issuer + "/keys",
                    "MERLIN_OIDC_REVOCATION_DB": str(revocations),
                    "MERLIN_OIDC_TENANT_CLAIM": "campus", "MERLIN_OIDC_ROLE_CLAIM": "campus_role"}
        with patch.dict(os.environ, settings, clear=True):
            resolver = learning_identity_resolver_from_environment()
        self.assertIsNotNone(resolver)
        self.start(self.bridge, resolver)

        def rotate_and_issue(kid):
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            published.clear()
            published.update(json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())),
                             kid=kid, alg="RS256", use="sig")
            now = int(time.time())
            claims = dict(iss=issuer, aud=audience, sub=self.learner.actor_id, campus="college",
                          campus_role="learner", iat=now, exp=now + 300, jti="fixture-" + kid)
            return "Bearer " + jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})

        first = rotate_and_issue("first")
        run = dict(self.binding, prediction="The structural test vectors should reproduce.")
        status, receipt = self.post("run", run, first)
        self.assertEqual(status, 200, receipt)
        self.assertEqual(receipt["binding"]["learner_id"], self.learner.actor_id)
        second = rotate_and_issue("second")
        self.assertEqual(self.post("run", run, second), (200, receipt))
        self.assertEqual(fetches, ["first", "second"])
        submit = dict(self.binding, submission_id="signed-session-submission",
                      reflection="The structural fixture still requires independent review.")
        status, result = self.post("submit", submit, second)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "pending_review")
        SQLiteTokenRevocationStore(revocations).revoke(issuer, "fixture-second")
        self.assertEqual(self.post("submit", submit, second)[0], 503)
        self.assertEqual(fetches, ["first", "second"])

    def test_unconfigured_host(self):
        self.start(None)
        self.assertEqual(self.post("run", self.binding), (503, {"error": "learning_lab_not_configured"}))
