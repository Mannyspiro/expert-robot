"""Synthetic engineering controls; no model, native isolation or quality claim.

Only trusted test programs run in ordinary local child processes. The actual
Systemd boundary is replaced in these fixtures and must be checked on its host.
"""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from dot_ai_os import local_research as research
from dot_ai_os.bridge import DotContextBridge, canonical, digest
from dot_ai_os.dual_coder import DualCoderWorkflow, WorkflowConflict
from merlin.hermes_systemd import SystemdFixedPythonProcess
from merlin.hermes_worker import TaskExecutionContext
from merlin.project_registry import MerlinRegistry


REVISION = "gguf:" + "1" * 64 + ";llama:" + "2" * 40 + ";bin:" + "3" * 64
WRONG = "def _solve(matrix, right):\n    return [Fraction(0) for _ in right]\n"


def fixture_oracle():
    cases = []
    for split in ("train", "holdout", "final"):
        for number, size in enumerate((0, 1, 2, 3, 4, 12)):
            solution = [Fraction(index + 2, 3) for index in range(size)]
            matrix = [[Fraction(2 if row == col else 0) for col in range(size)] for row in range(size)]
            right = [2 * value for value in solution]
            pair = lambda value: [value.numerator, value.denominator]
            cases.append({"case_id": split + "-independent-" + str(number), "split": split,
                "matrix": [[pair(value) for value in row] for row in matrix],
                "right": [pair(value) for value in right],
                "expected": {"status": "solved", "solution": [pair(value) for value in solution]}})
        singular = cases[-3]
        singular["matrix"][-1] = list(singular["matrix"][0])
        singular["right"][-1] = list(singular["right"][0])
        singular["expected"] = {"status": "error", "error_class": "ValueError",
                               "message": "floating or unconstrained resistor-network component"}
    return {"schema": "merlin-solver-oracle/1", "baseline_source_commit": "b" * 40,
            "baseline_function_sha256": digest(research._function_source().encode()), "cases": cases}


def worker_observation(raw, sha):
    """Execute trusted fixture source locally; synthetic kernel fields below."""
    completed = subprocess.run([sys.executable, "-I", str(research.WORKER_PATH)], input=raw,
                               capture_output=True, timeout=4, check=False)
    return {"schema": "merlin-systemd-process-result/1",
        "status": "completed" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode, "program_sha256": sha, "input_sha256": digest(raw),
        "kernel_setup": {"uid": 1000, "program_sha256": sha, "fixture_only": True},
        "stdout": completed.stdout.decode(), "stderr": completed.stderr.decode(),
        "qualification": False, "promotion_authority": False, "fixture_only": True}


class LocalResearchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.registry = MerlinRegistry(Path(self.directory.name) / "registry")
        self.registry.register_project("research", "synthetic engineering fixture")
        self.baseline = research._function_source()
        bridge = DotContextBridge(self.registry, project_id="research", namespaces=("merlin",))
        def source(name, content):
            return bridge.ingest(namespace="merlin", source_id=name, title=name, content=content,
                source_url="https://example.invalid/" + name, source_version="fixture-1",
                epistemic="local_observation", captured_at="2026-11-21T00:00:00Z")["source_ref"]
        self.context_refs = [source("current-solver", self.baseline.encode()),
            source("source-notes", canonical({"schema": "merlin-research-source-notes/1", "sources": [
                {"url": "https://docs.python.org/3/library/fractions.html",
                 "notes": "Use exact Fraction pairs; this fixture is not a model result."}]}))]
        self.oracle = fixture_oracle()
        self.oracle_ref = self.put("fixture/oracle.json", self.oracle)
        bootstrap = {"schema": "merlin-local-model-bootstrap-receipt/1", "status": "ready",
                     "smoke": {"passed": True, "inference_requests": 1,
                               "oracle_id": "restricted-ast-numeric-clamp/1"}, "fixture_only": True}
        self.bootstrap_ref = self.put("fixture/bootstrap.json", bootstrap)
        self.config = {"endpoint": "http://127.0.0.1:8080/v1/chat/completions",
                       "model": "synthetic-fixture", "revision": REVISION, "client_timeout_seconds": 180}
        self.manifest = {"schema": "merlin-local-model-provider/1", "status": "ready",
            **{key: self.config[key] for key in ("endpoint", "model", "revision")},
            "bootstrap_receipt_sha256": self.bootstrap_ref["sha256"],
            "model_artifact": {"sha256": "1" * 64},
            "runtime": {"source_commit": "2" * 40, "binary_sha256": "3" * 64},
            "limits": {"context_tokens": 4096}, "qualification": False, "promotion_authority": False}
        self.manifest_ref = self.put("fixture/manifest.json", self.manifest)
        self.provider_refs = {"manifest_ref": self.manifest_ref, "bootstrap_ref": self.bootstrap_ref}
        self.context = TaskExecutionContext(task_id="fixture-task", hypothesis_id="fixture-hypothesis",
            resource_budget={"cpu_cores": 2, "memory_bytes": 4 * 1024**3, "max_wall_seconds": 540,
                             "compute_budget_units": 1},
            approval_ref="synthetic-approval", lease_ref="synthetic-lease",
            artifact_refs=tuple(self.context_refs + [self.oracle_ref, self.manifest_ref, self.bootstrap_ref]),
            idempotency_key="fixture-task-key", deadline_epoch=time.time() + 540,
            emit_progress=lambda *args: None, emit_tool_event=lambda *args: None,
            heartbeat=lambda: None, check_cancelled=lambda: None)
        self.process = SystemdFixedPythonProcess(research.WORKER_PATH, digest(research.WORKER_PATH.read_bytes()))
        self.model_calls = []
        self.native_calls = []
        self.policies = []
        self.candidates = [self.baseline, self.baseline]

    def put(self, path, value):
        self.registry.put_artifact("research", path, canonical(value), "application/json")
        return self.registry.artifact_ref("research", path)

    def read(self, ref):
        return json.loads(self.registry.read_artifact_ref(ref)["content"])

    def authorize(self, policy):
        self.policies.append(deepcopy(policy))
        return True

    def inference(self, call, config, context):
        self.model_calls.append(deepcopy(call))
        source = self.candidates[len(self.model_calls) - 1]
        content = canonical({"candidate": source, "rationale": "Synthetic bounded engineering fixture."}).decode()
        response = {"choices": [{"message": {"content": content}}],
                    "usage": {"prompt_tokens": 500, "completion_tokens": 500, "total_tokens": 1000}}
        raw = canonical(response)
        token_raw = canonical({"object": "response.input_tokens", "input_tokens": 500})
        return {"response": response, "response_utf8": raw.decode(), "response_sha256": digest(raw),
                "accepted": True, "inference_attempted": True, "inference_requests": 1,
                "tokenization_utf8": token_raw.decode(), "tokenization_sha256": digest(token_raw),
                "metadata_requests": 1, "measured_prompt_tokens": 500, "fixture_only": True}, 0.01

    def native(self, instance, raw, *, limits, context, authorize):
        self.native_calls.append(json.loads(raw))
        self.assertEqual(limits, research.WORKER_LIMITS)
        self.assertIs(authorize({"program_sha256": instance.sha256, "fixture_only": True}), True)
        return worker_observation(raw, instance.sha256)

    def arguments(self, **changes):
        result = dict(project_id="research", session_id="episode", source_commit="a" * 40,
            context_refs=self.context_refs, oracle_ref=self.oracle_ref, provider_config=self.config,
            provider_evidence_refs=self.provider_refs, process=self.process,
            execution_context=self.context, authorize=self.authorize)
        result.update(changes)
        return result

    def run_phase(self, phase, **changes):
        with patch.object(research, "_request_child", side_effect=self.inference), \
                patch.object(SystemdFixedPythonProcess, "run", autospec=True, side_effect=self.native):
            return research.run_episode(self.registry, phase=phase, **self.arguments(**changes))

    def file_bytes(self):
        return {str(path.relative_to(self.registry.root)): path.read_bytes()
                for path in self.registry.root.rglob("*") if path.is_file()}

    def test_three_phases_resume_and_read_only_replay(self):
        first = self.run_phase("coder_a")
        self.assertEqual(first["status"], "blocked_missing_adapter")
        self.assertEqual(first["workflow_result"]["stage"], "coder_b")
        self.assertEqual(first["effects_this_call"], {"inference_attempts": 1, "inference_responses": 1,
                                                      "native_process_launches": 0})
        self.assertFalse(self.registry.artifact_history("research", "dual-coder/episode/stages/coder_b/intent.json"))
        completed = self.run_phase("complete", execution_context=replace(self.context, lease_ref="fresh-lease"))
        self.assertEqual(completed["status"], "completed_research_only")
        self.assertEqual(completed["workflow_result"]["recommendation"], "retain_parent")
        self.assertEqual(completed["effects_this_call"], {"inference_attempts": 1, "inference_responses": 1,
                                                          "native_process_launches": 6})
        self.assertEqual(len(completed["process_receipt_refs"]), 6)
        self.assertEqual(len(completed["provider_observation_refs"]), 2)
        before = self.file_bytes()
        replayed = self.run_phase("replay")
        self.assertEqual(self.file_bytes(), before)
        self.assertEqual(replayed["report_ref"], completed["report_ref"])
        self.assertEqual(replayed["new_artifact_refs"], [])
        self.assertEqual(list(replayed["effects_this_call"].values()), [0, 0, 0])
        self.assertEqual((len(self.model_calls), len(self.native_calls)), (2, 6))

    def test_original_task_observations_and_negative_candidate_are_retained(self):
        self.candidates[1] = WRONG
        result = self.run_phase("complete")
        selection = self.read(result["selection_ref"])
        final = self.read(result["final_ref"])
        self.assertTrue(all(row["passed"] for row in selection["variants"]["baseline"]["cases"]))
        self.assertTrue(all(row["passed"] for row in final["variants"]["baseline"]["cases"]))
        self.assertTrue(any(not row["passed"] for row in selection["variants"]["coder_b"]["cases"]))
        self.assertEqual(result["workflow_result"]["recommendation"], "retain_parent")
        self.assertIs(result["qualification"], False)
        self.assertEqual({case["case_id"] for call in self.native_calls[:3] for case in call["cases"]},
                         {case["case_id"] for case in self.oracle["cases"] if case["split"] != "final"})
        self.assertTrue(all("expected" not in case for call in self.native_calls for case in call["cases"]))

    def test_exact_sources_and_prior_candidate_enter_prompts_without_checker_data(self):
        self.run_phase("complete")
        prompts = [json.loads(call["messages"][1]["content"]) for call in self.model_calls]
        self.assertIn(self.baseline, prompts[0]["sources"][0]["text"])
        self.assertIn("https://docs.python.org/3/library/fractions.html", prompts[0]["sources"][1]["text"])
        self.assertEqual(prompts[1]["coder_a_candidate"]["candidate"], self.baseline)
        for call in self.model_calls:
            raw = canonical(call)
            for case in self.oracle["cases"]:
                self.assertNotIn(case["case_id"].encode(), raw)
            self.assertNotIn(b'"expected"', raw)
        self.assertEqual(self.read(self.registry.artifact_ref("research", "local-solver/episode/host.json"))
                         ["baseline_source_commit"], "b" * 40)

    def test_invalid_model_output_keeps_observation_and_never_retries(self):
        def invalid(call, config, context):
            observation, elapsed = self.inference(call, config, context)
            observation["response"]["choices"][0]["message"]["content"] = "not JSON"
            return observation, elapsed
        with patch.object(research, "_request_child", side_effect=invalid):
            first = research.run_episode(self.registry, phase="complete", **self.arguments())
        self.assertEqual(first["status"], "reconciliation_required")
        self.assertEqual(len(first["provider_observation_refs"]), 1)
        again = self.run_phase("complete")
        self.assertEqual(again["status"], "reconciliation_required")
        self.assertEqual(len(self.model_calls), 1)
        self.assertEqual(list(again["effects_this_call"].values()), [0, 0, 0])

    def test_interrupted_client_reports_unknown_effect_and_fences_retry(self):
        with patch.object(research, "_request_child", side_effect=TimeoutError("fixture")):
            result = research.run_episode(self.registry, phase="coder_a", **self.arguments())
        self.assertEqual(result["status"], "reconciliation_required")
        self.assertIsNone(result["effects_this_call"]["inference_attempts"])
        self.assertIsNone(result["effects_this_call"]["inference_responses"])
        again = self.run_phase("complete")
        self.assertEqual(again["status"], "reconciliation_required")
        self.assertEqual(self.model_calls, [])

    def test_final_interruption_does_not_repeat_completed_effects(self):
        original = self.native
        def interrupted(*args, **kwargs):
            if len(self.native_calls) == 3:
                raise RuntimeError("synthetic final boundary interruption")
            return original(*args, **kwargs)
        with patch.object(research, "_request_child", side_effect=self.inference), \
                patch.object(SystemdFixedPythonProcess, "run", autospec=True, side_effect=interrupted):
            first = research.run_episode(self.registry, phase="complete", **self.arguments())
        self.assertEqual(first["status"], "reconciliation_required")
        self.assertIsNone(first["effects_this_call"]["native_process_launches"])
        again = self.run_phase("complete")
        self.assertEqual(again["status"], "reconciliation_required")
        self.assertEqual((len(self.model_calls), len(self.native_calls)), (2, 3))
        self.assertIsNone(again["report_ref"])

    def test_nonboolean_authorization_and_mutated_context_prevent_effects(self):
        with self.assertRaises(PermissionError):
            self.run_phase("coder_a", authorize=lambda policy: 1)
        def mutate(policy):
            self.context.resource_budget["cpu_cores"] = 1
            return True
        with self.assertRaises(PermissionError):
            self.run_phase("coder_a", authorize=mutate)
        self.assertEqual(self.model_calls, [])
        self.assertFalse(self.registry.artifact_paths("research", prefix="dual-coder/")["paths"])

    def test_canonical_result_mutation_in_authorizer_blocks_dependent_model(self):
        self.run_phase("coder_a")
        def mutate(policy):
            if policy["action"] == "local_model_inference":
                path = "dual-coder/episode/stages/coder_a/result.json"
                ref = self.registry.artifact_ref("research", path)
                changed = self.read(ref)
                changed["payload"]["rationale"] = "Different synthetic result after authorization."
                self.registry.put_artifact("research", path, canonical(changed), "application/json")
            return True
        with self.assertRaises(WorkflowConflict):
            self.run_phase("complete", authorize=mutate)
        self.assertEqual(len(self.model_calls), 1)

    def test_missing_admission_and_wrong_provider_identity_reject_before_writes(self):
        with self.assertRaises(PermissionError):
            self.run_phase("coder_a", execution_context=replace(self.context, artifact_refs=tuple(self.context_refs)))
        wrong = dict(self.config, revision="gguf:" + "4" * 64 + ";llama:" + "2" * 40 + ";bin:" + "3" * 64)
        with self.assertRaises(PermissionError):
            self.run_phase("coder_a", provider_config=wrong)
        self.assertEqual(self.model_calls, [])

    def test_orphan_model_observation_prevents_new_intent_and_call(self):
        episode = research._Episode(self.registry, phase="coder_a", **self.arguments())
        episode._put("host.json", episode.host_record)
        episode._put("coder_a/observation.json", {"schema": "synthetic-orphan"})
        with self.assertRaises(WorkflowConflict):
            self.run_phase("coder_a")
        self.assertEqual(self.model_calls, [])
        self.assertFalse(self.registry.artifact_history("research", "dual-coder/episode/stages/coder_a/intent.json"))

    def test_oracle_equation_failure_and_wrong_worker_identity_fail_closed(self):
        broken = deepcopy(self.oracle)
        broken["cases"][1]["expected"]["solution"] = [[99, 1]]
        with self.assertRaises(ValueError):
            research._oracle(broken)
        self.process.tasks_max = 9
        with self.assertRaises(ValueError):
            self.run_phase("coder_a")
        self.assertEqual(self.model_calls, [])

    def test_fixed_worker_exact_cases_output_budget_and_input_mutation(self):
        for split in ("selection", "final"):
            cases = [case for case in self.oracle["cases"] if (case["split"] == "final") == (split == "final")]
            payload = {"schema": "merlin-solver-worker-input/1", "program": self.baseline,
                       "cases": [{key: case[key] for key in ("case_id", "matrix", "right")} for case in cases]}
            receipt = worker_observation(canonical(payload), self.process.sha256)
            self.assertLess(len(receipt["stdout"].encode()), 7000)
            self.assertTrue(all(row["passed"] for row in research._checked_outcomes(receipt, cases)))
        payload["program"] = "def _solve(matrix, right):\n    right.clear()\n    return []\n"
        receipt = worker_observation(canonical(payload), self.process.sha256)
        self.assertTrue(any(not row["passed"] for row in research._checked_outcomes(receipt, cases)))
        output = json.loads(receipt["stdout"])
        output["cases"].append(output["cases"][0])
        receipt["stdout"] = canonical(output).decode()
        self.assertFalse(any(row["passed"] for row in research._checked_outcomes(receipt, cases)))

    def inference_request(self):
        return {"config": self.config, "messages": [{"role": "system", "content": "Fixture only"},
                                                   {"role": "user", "content": "Fixture only"}]}

    def test_exact_token_preflight_and_inference_body_with_distinct_socket_timeouts(self):
        calls = []
        result = {"choices": [{"message": {"content": "{}"}}],
                  "usage": {"prompt_tokens": 100, "completion_tokens": 2, "total_tokens": 102}}
        def post(host, port, target, payload, **kwargs):
            calls.append((target, deepcopy(payload), kwargs))
            value = {"object": "response.input_tokens", "input_tokens": 100} if len(calls) == 1 else result
            return value, canonical(value)
        with patch.object(research, "_post", side_effect=post):
            observation = research._inference(self.inference_request())
        self.assertIs(observation["accepted"], True)
        self.assertEqual(calls[0][0], "/v1/chat/completions/input_tokens")
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertEqual(calls[0][2], {})
        self.assertEqual(calls[1][2], {"timeout": 180})
        self.assertEqual(set(calls[1][1]), {"model", "messages", "temperature", "max_tokens", "stream"})

    def test_token_overflow_has_no_inference_and_usage_mismatch_retains_response(self):
        overflow = {"object": "response.input_tokens", "input_tokens": 3197}
        trace = {}
        with patch.object(research, "_post", return_value=(overflow, canonical(overflow))) as post:
            with self.assertRaises(ValueError):
                research._inference(self.inference_request(), trace)
        self.assertEqual(post.call_count, 1)
        self.assertIs(trace["inference_attempted"], False)
        tokens = {"object": "response.input_tokens", "input_tokens": 100}
        bad = {"usage": {"prompt_tokens": 101, "completion_tokens": 1, "total_tokens": 102}}
        with patch.object(research, "_post", side_effect=[(tokens, canonical(tokens)), (bad, canonical(bad))]):
            with self.assertRaises(ValueError):
                research._inference(self.inference_request(), trace)
        self.assertEqual(trace["response_utf8"], canonical(bad).decode())
        self.assertEqual(trace["inference_requests"], 1)

    def test_direct_transport_rejects_redirect_and_closes_without_followup(self):
        connections = []
        class Response:
            status = 302
            closed = False
            def close(self): self.closed = True
        class Connection:
            def __init__(self, host, port, timeout):
                self.response, self.closed, self.requests = Response(), False, []
                connections.append(self)
            def request(self, *args, **kwargs): self.requests.append((args, kwargs))
            def getresponse(self): return self.response
            def close(self): self.closed = True
        with patch.object(research, "HTTPConnection", Connection):
            with self.assertRaises(OSError):
                research._post("127.0.0.1", 8080, "/v1/chat/completions", {})
        self.assertEqual(len(connections), 1)
        self.assertEqual(len(connections[0].requests), 1)
        self.assertTrue(connections[0].closed and connections[0].response.closed)


if __name__ == "__main__":
    unittest.main()
