from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from merlin.app import EventStore, make_handler
from merlin.rsi import EvalCase, SkillProcedure, suite_digest


def payload():
    baseline = SkillProcedure(
        skill_id="math.error-triage", version=1,
        purpose="Diagnose an invalid algebra transformation.",
        trigger_conditions=("learner submits an invalid equality",),
        steps=("locate the first invalid step", "show a counterexample", "ask for a retry"),
        guardrails=("do not reveal the full solution", "do not award mastery from hints"),
        source_failure_ids=("failure-001",),
    )
    candidate = SkillProcedure(
        skill_id="math.error-triage", version=2,
        purpose="Diagnose an invalid algebra transformation.",
        trigger_conditions=("learner submits an invalid equality",),
        steps=("locate the first invalid step", "show a counterexample", "ask for a retry"),
        guardrails=("do not reveal the full solution", "do not award mastery from hints"),
        source_failure_ids=("failure-001",),
    )
    cases = [
        {"case_id": "train-1", "split": "train", "input_sha256": "a" * 64},
        {"case_id": "held-1", "split": "heldout", "input_sha256": "b" * 64},
        {"case_id": "held-2", "split": "heldout", "input_sha256": "c" * 64},
    ]
    common = {
        "suite_sha256": suite_digest(EvalCase(**row) for row in cases),
        "evaluator_sha256": "d" * 64,
        "runner_id": "loopback-test-runner",
        "runner_revision": "test-1",
    }
    return {
        "baseline_skill": skill_payload(1),
        "candidate_skill": skill_payload(2),
        "cases": cases,
        "baseline_evaluation": {
            **common, "skill_sha256": baseline.sha256,
            "outcomes": [
                {"case_id": "train-1", "passed": False, "resource_units": 1},
                {"case_id": "held-1", "passed": True, "resource_units": 1},
                {"case_id": "held-2", "passed": False, "resource_units": 1},
            ],
        },
        "candidate_evaluation": {
            **common, "skill_sha256": candidate.sha256,
            "outcomes": [
                {"case_id": "train-1", "passed": True, "resource_units": 1},
                {"case_id": "held-1", "passed": True, "resource_units": 1},
                {"case_id": "held-2", "passed": True, "resource_units": 1},
            ],
        },
        "max_resource_units": 10,
    }


class RSIApiTests(unittest.TestCase):
    def test_compare_route_returns_review_only_and_records_event(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "events.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/rsi/compare",
                    data=json.dumps(payload()).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    result = json.loads(response.read())
                self.assertEqual(result["status"], "ELIGIBLE_FOR_REVIEW")
                self.assertFalse(result["automatic_promotion"])
                self.assertTrue(result["human_review_required"])
                self.assertEqual(store.recent(1)[0]["kind"], "/api/rsi/compare")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_induce_route_returns_non_executable_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "events.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = {
                    "skill_id": "math.error-triage", "version": 1,
                    "purpose": "Repair invalid equality transformations.",
                    "guardrails": ["do not award mastery from hints"],
                    "trajectories": [
                        {"failure_id": "f-1", "failure_signature": "invalid-equality",
                         "trigger_condition": "learner submits invalid equality",
                         "corrective_steps": ["locate invalid step", "construct counterexample"],
                         "source_commit_sha": "1" * 40, "source_artifact_sha256": "a" * 64},
                        {"failure_id": "f-2", "failure_signature": "invalid-equality",
                         "trigger_condition": "learner equality is invalid",
                         "corrective_steps": ["locate invalid step", "construct counterexample"],
                         "source_commit_sha": "2" * 40, "source_artifact_sha256": "b" * 64},
                    ],
                }
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/rsi/induce",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urlopen(request, timeout=5) as response:
                    result = json.loads(response.read())
                self.assertEqual(result["status"], "PROPOSAL_ONLY")
                self.assertFalse(result["executable"])
                self.assertEqual(result["source_failure_ids"], ["f-1", "f-2"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_invalid_evaluation_is_a_client_error(self):
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "events.sqlite3")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/api/rsi/compare",
                    data=b'{"cases":[]}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(HTTPError) as raised:
                    urlopen(request, timeout=5)
                self.assertEqual(raised.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
