"""Real full-app startup/restart with explicitly synthetic host authentication.

No app method, seed, store, listener or dependency is mocked. The evidence-only
opt-in uses the normal environment composition in app.serve; the resolver is a
fixed synthetic host fixture, not institutional SSO or signature verification.
The CLI negative controls use the actual module entry point. No public listener,
network provider, real student, lab execution or deployment is involved.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
from http import client
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from dot_ai_os.bridge import canonical
from merlin.learning_evidence_eval import _setup_demo, grade_evidence_response


SOURCE = "d" * 40  # Synthetic course metadata, not an attested checkout commit.
REPO = Path(__file__).resolve().parents[1]
STARTUP_SECONDS = 30
STOP_SECONDS = 10

_HOST = r'''import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from merlin.learning_platform import Actor
from merlin.app import serve
context=json.loads(Path(sys.argv[2]).read_text())
actors={name:Actor(**value) for name,value in context['actors'].items()}
def synthetic_host_resolver(headers):
    # Explicit test-only credential table; never an OIDC/JWT verification claim.
    authorization=headers.get('Authorization','')
    return actors.get(authorization[7:]) if authorization.startswith('Bearer ') else None
serve(port=int(sys.argv[3]),db_path=sys.argv[4],learning_identity_resolver=synthetic_host_resolver)
'''

_CLI = r'''import runpy,sys
sys.path.insert(0,sys.argv[1])
sys.argv=['merlin.app','--port',sys.argv[2],'--db',sys.argv[3]]
runpy.run_module('merlin.app',run_name='__main__')
'''


class LearningHostStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.fixture, self.platform, self.registry, self.context, self.service, self.teacher,
         self.learner, self.scope, self.pins, self.frozen) = _setup_demo(self.root, SOURCE)
        actors = {"startup-learner": self.learner, "startup-teacher": self.teacher}
        self.host_context = self.root / "synthetic-host-context.json"
        self.host_context.write_text(json.dumps({"fixture_class": "synthetic_host_identity",
            "actors": {name: {"tenant_id": actor.tenant_id, "actor_id": actor.actor_id, "role": actor.role}
                       for name, actor in actors.items()}}))
        self.base = "/api/learning/courses/" + self.scope["course_id"] + "/research/"
        self.body = {key: self.scope[key] for key in ("course_version", "manifest_sha256")}
        self.expected_binding = {"tenant_id": self.learner.tenant_id, "project_id": "synthetic-learning-evidence", **self.scope}
        self.environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8",
            "MERLIN_DB_PATH": str(self.root / "events.sqlite3"),
            "MERLIN_LEARNING_DB_PATH": str(self.root / "learning.sqlite3"),
            "MERLIN_LEARNER_DB_PATH": str(self.root / "learning.sqlite3"),
            "MERLIN_MEMORY_DB_PATH": str(self.root / "memory.sqlite3"),
            "MERLIN_REGISTRY_ROOT": str(self.root / "registry")}

    def port(self):
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                return listener.getsockname()[1]
        except OSError as exc:
            if exc.errno == errno.EPERM:
                self.skipTest("sandbox denies loopback bind with EPERM; full startup must run on the validation host")
            raise

    def request(self, port, method, path, body=None, *, token="startup-learner", headers=None):
        raw = None if body is None else canonical(body)
        supplied = {} if raw is None else {"Content-Type": "application/json", "Content-Length": str(len(raw))}
        if token is not None:
            supplied["Authorization"] = "Bearer " + token
        supplied.update(headers or {})
        connection = client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request(method, path, body=raw, headers=supplied)
            response = connection.getresponse(); data = response.read(262145)
            self.assertLessEqual(len(data), 262144)
            return response.status, json.loads(data)
        finally:
            connection.close()

    @staticmethod
    def logs(path):
        return path.read_bytes()[-12000:].decode("utf-8", "replace")

    @contextmanager
    def running(self, *, port=None, configured=True, cli=False):
        port = self.port() if port is None else port
        environment = dict(self.environment)
        if configured:
            environment["MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS"] = json.dumps(
                {self.learner.tenant_id: "synthetic-learning-evidence"})
        script = _CLI if cli else _HOST
        args = ([str(REPO / "python"), str(port), str(self.root / "events.sqlite3")] if cli else
                [str(REPO / "python"), str(self.host_context), str(port), str(self.root / "events.sqlite3")])
        log_path = self.root / ("app-" + str(time.time_ns()) + ".log")
        with log_path.open("wb") as log:
            process = subprocess.Popen([sys.executable, "-I", "-B", "-u", "-c", script, *args],
                cwd=self.root, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + STARTUP_SECONDS
                while True:
                    if process.poll() is not None:
                        self.fail("real app exited before readiness: " + self.logs(log_path))
                    try:
                        status, health = self.request(port, "GET", "/health", token=None)
                        if status == 200 and health.get("ok") is True and health.get("service") == "merlin":
                            break
                    except (OSError, client.HTTPException, ValueError):
                        pass
                    if time.monotonic() >= deadline:
                        self.fail("real app readiness deadline exceeded: " + self.logs(log_path))
                    time.sleep(0.05)
                yield port
            finally:
                if process.poll() is None:
                    process.terminate()  # Real serve SIGTERM handler shuts the listener down.
                    try:
                        process.wait(timeout=STOP_SECONDS)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
                        self.fail("real app did not stop after SIGTERM: " + self.logs(log_path))
            self.assertEqual(process.returncode, 0, self.logs(log_path))

    def evaluate_http(self, port):
        responses = []
        for case in self.fixture["cases"]:
            status, response = self.request(port, "POST", self.base + "evidence", {**self.body, "query": case["query"]})
            self.assertEqual(status, 200)
            grade = grade_evidence_response(case["case_id"], response, pinned_sources=self.pins,
                expected_binding=self.expected_binding, expected_source_manifest_ref=self.frozen["source_manifest_ref"])
            self.assertTrue(grade["passed"], grade)
            responses.append(response)
        return responses

    def assert_no_learning_promotion(self):
        with sqlite3.connect(self.root / "learning.sqlite3") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_courses").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_enrollments").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learning_submissions").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM learner_attempts").fetchone()[0], 0)
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='learning_lab_runs'").fetchone())
        self.assertFalse((self.root / "hypotheses.sqlite3").exists())

    def test_real_serve_opt_in_seed_http_sigterm_and_restart_preserve_pinned_evidence(self):
        port = self.port()
        with self.running(port=port) as live:
            first = self.evaluate_http(live)
            curation = {**self.body, "sources": [{"resource_id": source["resource_id"], **self.pins[source["resource_id"]],
                "review_note": "Original synthetic CC0 text; fixture scope and source metadata reviewed."}
                for source in self.fixture["sources"]], "conflicts": self.fixture["conflicts"]}
            status, frozen = self.request(live, "POST", self.base + "sources", curation, token="startup-teacher")
            self.assertEqual(status, 200); self.assertEqual(frozen["source_manifest_ref"], self.frozen["source_manifest_ref"])
            status, forge = self.request(live, "GET", "/api/forge/status", token=None)
            self.assertEqual(status, 200); self.assertGreater(forge["source_snapshot"]["file_count"], 0)
            self.assertGreater(forge["source_snapshot"]["total_bytes"], 0)
            self.assertFalse(forge["source_snapshot"]["source_commit_verified"])
            self.assertFalse(forge["source_snapshot"]["sensitive_files_included"])
            for body, token, headers, expected in (
                ({**self.body, "query": "placeholder"}, "unknown-synthetic-identity", {}, 401),
                ({**self.body, "query": "placeholder", "actor": {"role": "tenant_admin"}}, "startup-learner", {}, 400),
                ({**self.body, "query": "placeholder"}, "startup-learner", {"Origin": "https://foreign.example"}, 403)):
                status, error = self.request(live, "POST", self.base + "evidence", body, token=token, headers=headers)
                self.assertEqual(status, expected); self.assertNotIn("detail", error)
            status, error = self.request(live, "POST", self.base + "lab", {**self.body, "lesson_id": "titan-structural-lab",
                "run_id": "must-not-execute", "prediction": "Known structural fixture only"})
            self.assertEqual(status, 503); self.assertNotIn("artifact_ref", error)
        for name in ("events.sqlite3", "memory.sqlite3", "merlin-forge.sqlite3"):
            self.assertGreater((self.root / name).stat().st_size, 0)
        self.assert_no_learning_promotion()
        # The latest context pointer advances while the service is stopped.
        # The next real process must still retrieve the frozen historical pair.
        source = self.fixture["sources"][0]
        self.context.ingest(namespace=source["namespace"], source_id=source["source_id"], title="Later unreviewed acquisition",
            content=b"Later synthetic source text must not replace reviewed course evidence", source_url=source["source_url"],
            source_version="startup-later-version", epistemic=source["epistemic"], captured_at="2026-11-18T01:00:00Z")
        with self.running(port=port) as live:
            self.assertEqual(self.evaluate_http(live), first)
            status, restarted_forge = self.request(live, "GET", "/api/forge/status", token=None)
            self.assertEqual(status, 200); self.assertEqual(restarted_forge["source_snapshot"], forge["source_snapshot"])
        self.assert_no_learning_promotion()
        ref = self.frozen["source_manifest_ref"]
        self.assertEqual(len(self.registry.artifact_history(ref["project_id"], ref["logical_path"])), 1)
        for source in self.fixture["sources"]:
            self.assertEqual(self.registry.read_artifact_ref(self.pins[source["resource_id"]]["source_ref"])["content"], source["content"].encode())

    def test_real_module_entry_without_opt_in_keeps_research_disabled(self):
        with self.running(configured=False, cli=True) as live:
            status, result = self.request(live, "POST", self.base + "evidence", {**self.body, "query": "placeholder"}, token=None)
            self.assertEqual(status, 503); self.assertEqual(result["error"], "research_service_unavailable")
        self.assert_no_learning_promotion()

    def test_real_module_entry_opt_in_without_host_identity_fails_before_listener(self):
        port = self.port(); environment = dict(self.environment)
        environment["MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS"] = json.dumps(
            {self.learner.tenant_id: "synthetic-learning-evidence"})
        result = subprocess.run([sys.executable, "-I", "-B", "-u", "-c", _CLI,
            str(REPO / "python"), str(port), str(self.root / "events.sqlite3")],
            cwd=self.root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=STARTUP_SECONDS)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"requires an authenticated host resolver", result.stdout)
        self.assertNotIn(b"API listening", result.stdout)
        with self.assertRaises((OSError, client.HTTPException)):
            self.request(port, "GET", "/health", token=None)

    def test_missing_lms_alias_cannot_be_created_by_learner_store_before_gate(self):
        for existing_unrelated in (False, True):
            with self.subTest(existing_unrelated=existing_unrelated):
                port = self.port(); environment = dict(self.environment)
                target = self.root / ("unrelated.sqlite3" if existing_unrelated else "missing-lms.sqlite3")
                self.assertFalse(target.exists())
                before = None
                if existing_unrelated:
                    with sqlite3.connect(target) as db:
                        db.execute("CREATE TABLE unrelated(value TEXT)")
                        db.execute("INSERT INTO unrelated VALUES('preserve existing unrelated data')")
                    before = target.read_bytes()
                environment.update(MERLIN_LEARNING_DB_PATH=str(target), MERLIN_LEARNER_DB_PATH=str(target),
                    MERLIN_LEARNING_RESEARCH_TENANT_PROJECTS=json.dumps({self.learner.tenant_id: "synthetic-learning-evidence"}))
                result = subprocess.run([sys.executable, "-I", "-B", "-u", "-c", _HOST,
                    str(REPO / "python"), str(self.host_context), str(port), str(self.root / "events.sqlite3")],
                    cwd=self.root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=STARTUP_SECONDS)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"requires an existing LMS database", result.stdout)
                self.assertNotIn(b"API listening", result.stdout)
                if existing_unrelated:
                    self.assertEqual(target.read_bytes(), before, "preflight must not migrate an unrelated SQLite file")
                else:
                    self.assertFalse(target.exists(), "a constructor must not manufacture preexisting LMS state")
                with self.assertRaises((OSError, client.HTTPException)):
                    self.request(port, "GET", "/health", token=None)


if __name__ == "__main__": unittest.main()
