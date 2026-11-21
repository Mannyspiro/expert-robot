"""Canonical workflow tests with synthetic hosts; no weights or models are used."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dot_ai_os.bridge import canonical, digest
from dot_ai_os.dual_coder import DualCoderWorkflow, WorkflowConflict
from merlin.project_registry import MerlinRegistry
from merlin.weight_binding import WeightBinding


FLAGS = {"qualification": False, "promotion_authority": False,
         "independent_verification": False, "model_quality_assessed": False}


class WeightBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.registry = MerlinRegistry(Path(temporary.name) / "registry")
        self.registry.register_project("test", "Synthetic binding fixture")
        self.allowed = True
        self.authenticated = []
        self.requests = []
        self.calls = {"coder_a": 0, "coder_b": 0, "evaluator": 0}
        self.providers = {name: {"provider_id": "fixture-" + name, "revision": "fixture-v1",
            "prompt_sha256": char * 64, "config_sha256": "c" * 64, "adapter_sha256": "d" * 64}
            for name, char in (("coder_a", "a"), ("coder_b", "b"), ("evaluator", "e"))}
        self.context_ref = self.put("sources/context.txt", b"Synthetic engineering context; no model runtime.")
        self.specification = {"objective": "Exercise exact binding without model execution",
            "source_commit": "a" * 40, "context_refs": [self.context_ref],
            "train_ids": ["development-1"], "holdout_ids": ["held-out-1"],
            "acceptance_criteria": ["Only a correctly bound research result is admitted"], "max_cost_usd": 0}
        self.manifest = {"schema": "merlin-weight-manifest/1", "role": "coder_a",
            "source_commit": "a" * 40, "provider": deepcopy(self.providers["coder_a"]),
            "runtime": {"runtime_id": "synthetic-runtime", "revision": "fixture-runtime-v1",
                        "implementation_sha256": "1" * 64},
            "model": {"architecture_sha256": "2" * 64, "tensor_layout_sha256": "3" * 64,
                "checkpoint_sha256": "4" * 64,
                "shards": [{"name": "fixture-shard", "sha256": "5" * 64, "size_bytes": 16}],
                "tokenizer_sha256": "6" * 64, "model_config_sha256": "7" * 64,
                "inference_config_sha256": "8" * 64, "dtype": "synthetic-float32",
                "quantization_sha256": "9" * 64},
            "transformation": {"program_sha256": "0" * 64, "delta_sha256": None},
            "rollback_ref": self.put("weights/baseline.json", {"role": "synthetic-baseline", **FLAGS}),
            "evaluation_protocol_ref": self.put("weights/protocol.json", {"scope": "software-contract-only", **FLAGS}),
            **FLAGS}
        self.manifest_ref = self.put("weights/candidate.json", self.manifest)
        self.binding = self.make_binding()
        self.workflow = DualCoderWorkflow(self.registry, project_id="test", coder_a_binding=self.binding)

    def put(self, path, body, *, project="test"):
        raw = body if isinstance(body, bytes) else canonical(body)
        self.registry.put_artifact(project, path, raw, "application/json")
        return self.registry.artifact_ref(project, path)

    def read(self, path, *, registry=None):
        registry = registry or self.registry
        ref = registry.artifact_ref("test", path, version=1)
        return json.loads(registry.read_artifact_ref(ref)["content"]), ref

    def authenticate(self, receipt, checksum):
        self.assertEqual(checksum, digest(canonical(receipt)))
        self.authenticated.append(deepcopy(receipt))
        return self.allowed

    def make_binding(self, *, registry=None, manifest_ref=None, authenticate=None):
        return WeightBinding(registry or self.registry, project_id="test",
            manifest_ref=self.manifest_ref if manifest_ref is None else manifest_ref,
            authenticate=self.authenticate if authenticate is None else authenticate)

    def fresh(self, *, authenticate=None, manifest_ref=None):
        registry = MerlinRegistry(self.registry.root)
        return DualCoderWorkflow(registry, project_id="test",
            coder_a_binding=self.make_binding(registry=registry, authenticate=authenticate, manifest_ref=manifest_ref))

    @staticmethod
    def payload():
        return {"candidate": "synthetic candidate A", "rationale": "A software fixture, not model output."}

    def observation(self, request, payload):
        # Intentionally simulated host observation, independently assembled from
        # the contract fields. A real host must measure its loaded state instead.
        context = request["weight_binding"]
        manifest = context["manifest"]
        return {"schema": "merlin-weight-invocation-observation/1",
            "evidence_kind": "host_observed_weight_invocation", "status": "completed",
            "session_id": context["session_id"], "stage": "coder_a", "source_commit": request["source_commit"],
            "manifest_ref": deepcopy(context["manifest_ref"]), "intent_ref": deepcopy(context["intent_ref"]),
            "request_sha256": context["request_sha256"], "input_sha256": context["input_sha256"],
            "callback_request_sha256": digest(canonical(request)), "idempotency_key": request["idempotency_key"],
            "output_sha256": digest(canonical(payload)), "provider": deepcopy(manifest["provider"]),
            "runtime": deepcopy(manifest["runtime"]), "runtime_instance_id": "synthetic-instance",
            "load_session_id": "synthetic-load-session", "loaded_model": deepcopy(manifest["model"]), **FLAGS}

    def coder_a(self, request):
        self.calls["coder_a"] += 1
        self.requests.append(deepcopy(request))
        payload = self.payload()
        return {"payload": payload, "observation": self.observation(request, payload)}

    def coder_b(self, request):
        self.calls["coder_b"] += 1
        self.requests.append(deepcopy(request))
        return {"candidate": "synthetic candidate B", "rationale": "Unbound control fixture."}

    def evaluator(self, request):
        self.calls["evaluator"] += 1
        self.requests.append(deepcopy(request))
        return {"baseline": {"train_passed": 1, "holdout_passed": 0, "regressions": 0},
                "coder_a": {"train_passed": 1, "holdout_passed": 1, "regressions": 0},
                "coder_b": {"train_passed": 1, "holdout_passed": 0, "regressions": 0},
                "notes": "Declared synthetic counts; no model efficacy measured."}

    def run_workflow(self, session="one", *, workflow=None, coder_a=None):
        return (workflow or self.workflow).run(session, specification=self.specification, providers=self.providers,
            coder_a=self.coder_a if coder_a is None else coder_a, coder_b=self.coder_b, evaluator=self.evaluator)

    def assert_pending(self, result, *, stage="coder_a"):
        self.assertEqual(result["status"], "reconciliation_required")
        self.assertEqual(result["stage"], stage)
        self.assertIs(result["automatic_retry"], False)
        self.assertIs(result["qualification"], False)
        self.assertIs(result["promotion_authority"], False)

    def corrupt(self, ref):
        checksum = ref["sha256"]
        (self.registry.blobs / checksum[:2] / checksum[2:]).write_bytes(b"corrupted fixture bytes")

    def test_exact_bound_workflow_stores_manifest_intent_receipt_and_result(self):
        result = self.run_workflow()
        self.assertEqual(result["status"], "completed_research_only")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})
        spec, _ = self.read("dual-coder/one/spec.json")
        intent, intent_ref = self.read("dual-coder/one/stages/coder_a/intent.json")
        receipt, receipt_ref = self.read("dual-coder/one/stages/coder_a/weight-receipt.json")
        stage, stage_ref = self.read("dual-coder/one/stages/coder_a/result.json")
        self.assertEqual(spec["schema"], "dot-dual-coder-spec/2")
        self.assertEqual(intent["schema"], "dot-dual-coder-intent/2")
        self.assertEqual(stage["schema"], "dot-dual-coder-result/2")
        self.assertEqual(result["schema"], "dot-dual-coder-report/2")
        self.assertEqual(stage["weight_receipt_ref"], receipt_ref)
        self.assertEqual(result["coder_a_weight_receipt_ref"], receipt_ref)
        self.assertEqual(result["coder_a_ref"], stage_ref)
        self.assertEqual(receipt["observation"]["intent_ref"], intent_ref)
        self.assertEqual(receipt["observation"]["manifest_ref"], self.manifest_ref)
        self.assertEqual(receipt["payload"], stage["payload"])
        self.assertEqual(receipt["observation"]["output_sha256"], digest(canonical(stage["payload"])))
        self.assertEqual(receipt["observation"]["loaded_model"], self.manifest["model"])
        self.assertEqual(self.read("dual-coder/one/stages/coder_b/result.json")[0]["schema"], "dot-dual-coder-result/1")
        for record in (receipt, receipt["observation"], stage, result):
            for name in FLAGS:
                self.assertIs(record[name], False)

    def test_completed_replay_and_fresh_status_reauthenticate_without_provider_calls(self):
        first = self.run_workflow()
        auth_count = len(self.authenticated)
        fresh = self.fresh()
        status = fresh.status("one")
        self.assertEqual(status["status"], "completed_research_only")
        self.assertEqual(status["weight_receipt_refs"]["coder_a"], first["coder_a_weight_receipt_ref"])
        self.assertEqual(self.run_workflow(workflow=fresh), first)
        self.assertGreater(len(self.authenticated), auth_count)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_each_observed_identity_mismatch_is_fenced_after_one_call(self):
        changes = [("session_id", "another"), ("stage", "coder_b"), ("source_commit", "f" * 40),
            ("manifest_ref", {**self.manifest_ref, "sha256": "f" * 64}),
            ("intent_ref", {**self.manifest_ref, "logical_path": "other/intent.json"}),
            ("request_sha256", "f" * 64), ("input_sha256", "f" * 64),
            ("callback_request_sha256", "f" * 64), ("idempotency_key", "f" * 64),
            ("output_sha256", "f" * 64), ("status", "running"),
            ("evidence_kind", "model_self_report"), ("schema", "unknown/1")]
        for index, (field, value) in enumerate(changes):
            with self.subTest(field=field):
                def wrong(request):
                    generated = self.coder_a(request)
                    generated["observation"][field] = value
                    return generated
                before = self.calls["coder_a"]
                session = "mismatch-" + str(index)
                self.assert_pending(self.run_workflow(session, coder_a=wrong))
                self.assert_pending(self.run_workflow(session, workflow=self.fresh()))
                self.assertEqual(self.calls["coder_a"], before + 1)
        self.assertEqual(self.calls["coder_b"], 0)
        self.assertEqual(self.calls["evaluator"], 0)

    def test_provider_adapter_runtime_and_loaded_model_mismatches_are_rejected(self):
        changes = [("provider", "provider_id", "other-host"), ("provider", "revision", "other-revision"),
            ("provider", "adapter_sha256", "f" * 64), ("provider", "config_sha256", "f" * 64),
            ("provider", "prompt_sha256", "f" * 64), ("runtime", "runtime_id", "other-runtime"),
            ("runtime", "revision", "other-revision"), ("runtime", "implementation_sha256", "f" * 64)]
        changes.extend(("loaded_model", name, "f" * 64) for name in self.manifest["model"] if name not in {"shards", "dtype"})
        changes.extend([("loaded_model", "dtype", "other-dtype"),
                        ("loaded_model", "shards", [{"name": "fixture-shard", "sha256": "f" * 64, "size_bytes": 16}])])
        for index, (group, field, value) in enumerate(changes):
            with self.subTest(group=group, field=field):
                def wrong(request):
                    generated = self.coder_a(request)
                    generated["observation"][group][field] = value
                    return generated
                before = self.calls["coder_a"]
                session = "loaded-" + str(index)
                self.assert_pending(self.run_workflow(session, coder_a=wrong))
                self.assert_pending(self.run_workflow(session, workflow=self.fresh()))
                self.assertEqual(self.calls["coder_a"], before + 1)

    def test_model_and_authority_claims_cannot_be_added_to_observation(self):
        for index, name in enumerate(FLAGS):
            for value in (True, 0):
                with self.subTest(name=name, value=value):
                    def wrong(request):
                        generated = self.coder_a(request)
                        generated["observation"][name] = value
                        return generated
                    self.assert_pending(self.run_workflow(f"authority-{index}-{value}", coder_a=wrong))

    def test_missing_or_extra_observation_fields_do_not_trigger_retry(self):
        for index, change in enumerate(("missing", "extra", "no-observation", "old-payload")):
            with self.subTest(change=change):
                def wrong(request):
                    generated = self.coder_a(request)
                    if change == "missing": generated["observation"].pop("load_session_id")
                    if change == "extra": generated["observation"]["claim"] = "verified"
                    if change == "no-observation": generated.pop("observation")
                    if change == "old-payload": return generated["payload"]
                    return generated
                before = self.calls["coder_a"]
                session = "shape-" + str(index)
                self.assert_pending(self.run_workflow(session, coder_a=wrong))
                self.assert_pending(self.run_workflow(session, workflow=self.fresh()))
                self.assertEqual(self.calls["coder_a"], before + 1)

    def test_other_session_observation_cannot_be_reused(self):
        self.run_workflow("original")
        receipt, _ = self.read("dual-coder/original/stages/coder_a/weight-receipt.json")
        def replay(request):
            self.calls["coder_a"] += 1
            return {"payload": receipt["payload"], "observation": receipt["observation"]}
        self.assert_pending(self.run_workflow("other", coder_a=replay))
        self.assert_pending(self.run_workflow("other", workflow=self.fresh()))
        self.assertEqual(self.calls["coder_a"], 2)

    def test_authenticator_requires_literal_true_and_retry_stays_fenced(self):
        for index, value in enumerate((False, 1, "yes", {"verified": True}, None)):
            with self.subTest(value=value):
                self.allowed = value
                session = "auth-" + str(index)
                before = self.calls["coder_a"]
                self.assert_pending(self.run_workflow(session))
                self.allowed = True
                self.assert_pending(self.run_workflow(session, workflow=self.fresh()))
                self.assertEqual(self.calls["coder_a"], before + 1)

    def test_missing_host_authenticator_is_rejected_before_any_callback(self):
        with self.assertRaises(ValueError):
            WeightBinding(self.registry, project_id="test", manifest_ref=self.manifest_ref, authenticate=None)
        self.assertEqual(sum(self.calls.values()), 0)

    def test_fresh_status_and_run_fail_when_host_authentication_is_revoked(self):
        self.run_workflow()
        self.allowed = False
        fresh = self.fresh()
        with self.assertRaises(PermissionError): fresh.status("one")
        with self.assertRaises(PermissionError): self.run_workflow(workflow=fresh)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_revocation_after_a_result_commit_blocks_coder_b(self):
        original = self.workflow._put_once
        def revoke(path, payload):
            ref = original(path, payload)
            if path == "dual-coder/one/stages/coder_a/result.json": self.allowed = False
            return ref
        with patch.object(self.workflow, "_put_once", side_effect=revoke):
            with self.assertRaises(PermissionError): self.run_workflow()
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 0, "evaluator": 0})
        with self.assertRaises(KeyError): self.read("dual-coder/one/stages/coder_b/intent.json")
        with self.assertRaises(KeyError): self.read("dual-coder/one/report.json")
        self.allowed = True
        self.assertEqual(self.run_workflow(workflow=self.fresh())["status"], "completed_research_only")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_revocation_during_coder_b_blocks_evaluator_without_repeating_completed_calls(self):
        def revoke(request):
            payload = self.coder_b(request)
            self.allowed = False
            return payload
        with self.assertRaises(PermissionError):
            self.workflow.run("one", specification=self.specification, providers=self.providers,
                coder_a=self.coder_a, coder_b=revoke, evaluator=self.evaluator)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 0})
        before = self.read("dual-coder/one/stages/coder_b/result.json")
        with self.assertRaises(KeyError): self.read("dual-coder/one/stages/evaluator/intent.json")
        with self.assertRaises(KeyError): self.read("dual-coder/one/report.json")
        self.allowed = True
        self.assertEqual(self.run_workflow(workflow=self.fresh())["status"], "completed_research_only")
        self.assertEqual(self.read("dual-coder/one/stages/coder_b/result.json"), before)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_revocation_after_downstream_intent_blocks_callback_and_automatic_retry(self):
        original = self.workflow._put_once
        def revoke(path, payload):
            ref = original(path, payload)
            if path == "dual-coder/one/stages/coder_b/intent.json": self.allowed = False
            return ref
        with patch.object(self.workflow, "_put_once", side_effect=revoke):
            self.assert_pending(self.run_workflow(), stage="coder_b")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 0, "evaluator": 0})
        with self.assertRaises(KeyError): self.read("dual-coder/one/stages/coder_b/result.json")
        self.allowed = True
        self.assert_pending(self.run_workflow(workflow=self.fresh()), stage="coder_b")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 0, "evaluator": 0})

    def test_revocation_during_evaluator_blocks_report_without_repeating_completed_calls(self):
        def revoke(request):
            payload = self.evaluator(request)
            self.allowed = False
            return payload
        with self.assertRaises(PermissionError):
            self.workflow.run("one", specification=self.specification, providers=self.providers,
                coder_a=self.coder_a, coder_b=self.coder_b, evaluator=revoke)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})
        before = self.read("dual-coder/one/stages/evaluator/result.json")
        with self.assertRaises(KeyError): self.read("dual-coder/one/report.json")
        self.allowed = True
        self.assertEqual(self.run_workflow(workflow=self.fresh())["status"], "completed_research_only")
        self.assertEqual(self.read("dual-coder/one/stages/evaluator/result.json"), before)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_receipt_corruption_during_coder_b_blocks_evaluator_and_report(self):
        preserved = {}
        def corrupt(request):
            payload = self.coder_b(request)
            receipt, ref = self.read("dual-coder/one/stages/coder_a/weight-receipt.json")
            preserved.update(receipt=receipt, ref=ref)
            self.corrupt(ref)
            return payload
        with self.assertRaises(RuntimeError):
            self.workflow.run("one", specification=self.specification, providers=self.providers,
                coder_a=self.coder_a, coder_b=corrupt, evaluator=self.evaluator)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 0})
        with self.assertRaises(KeyError): self.read("dual-coder/one/report.json")
        checksum = preserved["ref"]["sha256"]
        (self.registry.blobs / checksum[:2] / checksum[2:]).write_bytes(canonical(preserved["receipt"]))
        self.assertEqual(self.run_workflow(workflow=self.fresh())["status"], "completed_research_only")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_orphan_receipt_is_rejected_before_new_intent_or_coder_call(self):
        self.run_workflow("original")
        receipt, _ = self.read("dual-coder/original/stages/coder_a/weight-receipt.json")
        missing = self.workflow.run("orphan", specification=self.specification, providers=self.providers)
        self.assertEqual(missing["status"], "blocked_missing_adapter")
        orphan_ref = self.put("dual-coder/orphan/stages/coder_a/weight-receipt.json", receipt)
        before = dict(self.calls)
        with self.assertRaises(WorkflowConflict): self.fresh().status("orphan")
        with self.assertRaises(WorkflowConflict): self.run_workflow("orphan", workflow=self.fresh())
        self.assertEqual(self.calls, before)
        self.assertEqual(self.read("dual-coder/orphan/stages/coder_a/weight-receipt.json"), (receipt, orphan_ref))
        with self.assertRaises(KeyError): self.read("dual-coder/orphan/stages/coder_a/intent.json")

    def test_bound_status_cannot_be_downgraded_without_matching_binding(self):
        self.run_workflow()
        plain = DualCoderWorkflow(self.registry, project_id="test")
        with self.assertRaises(PermissionError): plain.status("one")
        with self.assertRaises(WorkflowConflict): self.run_workflow(workflow=plain)
        self.assertEqual(self.calls["coder_a"], 1)

    def test_authenticator_receives_detached_receipt_and_hash(self):
        def mutate(receipt, checksum):
            self.assertEqual(checksum, digest(canonical(receipt)))
            receipt["payload"]["candidate"] = "mutated by auth"
            receipt["observation"]["loaded_model"]["checkpoint_sha256"] = "f" * 64
            receipt["qualification"] = True
            return True
        self.run_workflow(workflow=self.fresh(authenticate=mutate))
        receipt, _ = self.read("dual-coder/one/stages/coder_a/weight-receipt.json")
        self.assertEqual(receipt["payload"], self.payload())
        self.assertEqual(receipt["observation"]["loaded_model"], self.manifest["model"])
        self.assertIs(receipt["qualification"], False)

    def test_callback_request_and_caller_inputs_are_detached(self):
        original_spec, original_providers = deepcopy(self.specification), deepcopy(self.providers)
        def mutate(request):
            generated = self.coder_a(request)
            request["context"][0]["text"] = "changed callback copy"
            request["weight_binding"]["manifest"]["model"]["checkpoint_sha256"] = "f" * 64
            request["weight_binding"]["intent_ref"]["sha256"] = "f" * 64
            self.specification["source_commit"] = "f" * 40
            self.providers["coder_a"]["adapter_sha256"] = "f" * 64
            return generated
        result = self.run_workflow(coder_a=mutate)
        self.assertEqual(result["status"], "completed_research_only")
        stored, _ = self.read("dual-coder/one/spec.json")
        self.assertEqual(stored["specification"], original_spec)
        self.assertEqual(stored["providers"], original_providers)
        receipt, _ = self.read("dual-coder/one/stages/coder_a/weight-receipt.json")
        self.assertEqual(receipt["observation"]["loaded_model"], self.manifest["model"])
        self.assertEqual(self.requests[1]["source_commit"], original_spec["source_commit"])

    def test_constructor_and_property_reference_copies_cannot_rebind_manifest(self):
        supplied = deepcopy(self.manifest_ref)
        binding = self.make_binding(manifest_ref=supplied)
        supplied["sha256"] = "f" * 64
        exposed = binding.manifest_ref
        exposed["sha256"] = "e" * 64
        workflow = DualCoderWorkflow(self.registry, project_id="test", coder_a_binding=binding)
        self.assertEqual(self.run_workflow(workflow=workflow)["status"], "completed_research_only")
        self.assertEqual(binding.manifest_ref, self.manifest_ref)

    def test_host_mutation_of_context_after_authentication_is_detected(self):
        def mutate(receipt, checksum):
            self.corrupt(self.context_ref)
            return True
        self.assert_pending(self.run_workflow(workflow=self.fresh(authenticate=mutate)))
        self.assertEqual(self.calls["coder_a"], 1)
        with self.assertRaises(KeyError): self.read("dual-coder/one/stages/coder_a/result.json")

    def test_callback_mutation_of_canonical_manifest_is_detected(self):
        def mutate(request):
            generated = self.coder_a(request)
            self.corrupt(self.manifest_ref)
            return generated
        self.assert_pending(self.run_workflow(coder_a=mutate))
        self.assertEqual(self.calls["coder_a"], 1)
        with self.assertRaises(KeyError): self.read("dual-coder/one/stages/coder_a/weight-receipt.json")

    def test_interrupted_callback_never_runs_automatically_again(self):
        def interrupted(request):
            self.coder_a(request)
            raise SystemExit("synthetic provider interruption")
        with self.assertRaises(SystemExit): self.run_workflow(coder_a=interrupted)
        fresh = self.fresh()
        self.assertEqual(fresh.status("one")["stages"]["coder_a"], "reconciliation_required")
        self.assert_pending(self.run_workflow(workflow=fresh))
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 0, "evaluator": 0})

    def test_failure_retains_error_class_and_original_intent_without_private_message(self):
        def failed(request):
            self.coder_a(request)
            raise RuntimeError("private fixture diagnostic must not be persisted")
        self.assert_pending(self.run_workflow(coder_a=failed))
        failure, _ = self.read("dual-coder/one/stages/coder_a/failure.json")
        intent, intent_ref = self.read("dual-coder/one/stages/coder_a/intent.json")
        self.assertEqual(failure["error_class"], "RuntimeError")
        self.assertEqual(failure["intent_ref"], intent_ref)
        self.assertNotIn("private fixture", canonical(failure).decode())
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(self.calls["coder_a"], 1)

    def test_interruption_after_intent_before_callback_is_conservatively_fenced(self):
        with patch.object(self.binding, "invocation_request", side_effect=SystemExit("before callback")):
            with self.assertRaises(SystemExit): self.run_workflow()
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(sum(self.calls.values()), 0)

    def test_interruption_after_receipt_before_result_preserves_receipt_and_blocks_retry(self):
        original = self.workflow._put_once
        def interrupted(path, payload):
            if path == "dual-coder/one/stages/coder_a/result.json":
                raise SystemExit("after receipt, before result")
            return original(path, payload)
        with patch.object(self.workflow, "_put_once", side_effect=interrupted):
            with self.assertRaises(SystemExit): self.run_workflow()
        receipt, ref = self.read("dual-coder/one/stages/coder_a/weight-receipt.json")
        fresh = self.fresh()
        status = fresh.status("one")
        self.assertEqual(status["status"], "incomplete")
        self.assertEqual(status["weight_receipt_refs"]["coder_a"], ref)
        pending = self.run_workflow(workflow=fresh)
        self.assert_pending(pending)
        self.assertEqual(pending["weight_receipt_ref"], ref)
        self.assertEqual(self.read("dual-coder/one/stages/coder_a/weight-receipt.json"), (receipt, ref))
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 0, "evaluator": 0})

    def test_interruption_at_receipt_commit_is_not_hidden_by_retry(self):
        original = self.workflow._put_once
        def interrupted(path, payload):
            ref = original(path, payload)
            if path.endswith("/weight-receipt.json"):
                raise SystemExit("receipt written, return interrupted")
            return ref
        with patch.object(self.workflow, "_put_once", side_effect=interrupted):
            with self.assertRaises(SystemExit): self.run_workflow()
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(self.calls["coder_a"], 1)

    def test_interruption_after_result_commit_resumes_only_remaining_stages(self):
        original = self.workflow._put_once
        def interrupted(path, payload):
            ref = original(path, payload)
            if path == "dual-coder/one/stages/coder_a/result.json":
                raise SystemExit("result written, return interrupted")
            return ref
        with patch.object(self.workflow, "_put_once", side_effect=interrupted):
            with self.assertRaises(SystemExit): self.run_workflow()
        fresh = self.fresh()
        self.assertEqual(fresh.status("one")["next_stage"], "coder_b")
        self.assertEqual(self.run_workflow(workflow=fresh)["status"], "completed_research_only")
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_corrupted_receipt_fails_fresh_status_and_run(self):
        result = self.run_workflow()
        self.corrupt(result["coder_a_weight_receipt_ref"])
        fresh = self.fresh()
        with self.assertRaises(RuntimeError): fresh.status("one")
        with self.assertRaises(RuntimeError): self.run_workflow(workflow=fresh)
        self.assertEqual(self.calls["coder_a"], 1)

    def test_corrupted_manifest_fails_before_provider_contact(self):
        self.corrupt(self.manifest_ref)
        with self.assertRaises(RuntimeError): self.run_workflow()
        self.assertEqual(sum(self.calls.values()), 0)

    def test_missing_canonical_receipt_cannot_establish_completed_status(self):
        def interrupted(request):
            self.coder_a(request)
            raise SystemExit("interrupted before receipt")
        with self.assertRaises(SystemExit): self.run_workflow(coder_a=interrupted)
        _, intent_ref = self.read("dual-coder/one/stages/coder_a/intent.json")
        # Append a malformed stage publication through the real store. The store
        # correctly forbids deleting history, so a deletion is not a valid fixture.
        self.put("dual-coder/one/stages/coder_a/result.json", {
            "schema": "dot-dual-coder-result/2", "intent_ref": intent_ref, "payload": self.payload(),
            "weight_receipt_ref": {**intent_ref, "logical_path": "dual-coder/one/stages/coder_a/weight-receipt.json"},
            **FLAGS})
        fresh = self.fresh()
        with self.assertRaises(WorkflowConflict): fresh.status("one")
        with self.assertRaises(WorkflowConflict): self.run_workflow(workflow=fresh)
        self.assertEqual(self.calls["coder_a"], 1)

    def test_noncanonical_manifest_and_duplicate_json_fields_are_rejected(self):
        canonical_raw = canonical(self.manifest)
        duplicate = canonical_raw.replace(b'"role":"coder_a"', b'"role":"coder_a","role":"coder_a"')
        for index, raw in enumerate((json.dumps(self.manifest, indent=2).encode(), duplicate)):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.make_binding(manifest_ref=self.put(f"weights/noncanonical-{index}.json", raw))

    def test_changed_manifest_cannot_reuse_a_completed_session(self):
        self.run_workflow()
        changed = deepcopy(self.manifest)
        changed["model"]["checkpoint_sha256"] = "f" * 64
        ref = self.put("weights/other-candidate.json", changed)
        different = self.fresh(manifest_ref=ref)
        with self.assertRaises(WorkflowConflict): different.status("one")
        with self.assertRaises(WorkflowConflict): self.run_workflow(workflow=different)
        self.assertEqual(self.calls["coder_a"], 1)

    def test_new_manifest_version_does_not_silently_upgrade_a_pinned_binding(self):
        first = self.run_workflow()
        changed = deepcopy(self.manifest)
        changed["model"]["checkpoint_sha256"] = "f" * 64
        latest = self.put("weights/candidate.json", changed)
        self.assertEqual(latest["version"], 2)
        self.assertEqual(self.run_workflow(workflow=self.fresh()), first)
        self.assertEqual(self.calls["coder_a"], 1)

    def test_rollback_and_protocol_references_are_exact_and_revalidated(self):
        self.corrupt(self.manifest["rollback_ref"])
        with self.assertRaises(RuntimeError): self.run_workflow()
        self.assertEqual(sum(self.calls.values()), 0)

    def test_malformed_manifests_fail_before_provider_contact(self):
        cases = []
        for name, value in (("role", "evaluator"), ("source_commit", "main"), ("schema", "future/9"),
                            ("qualification", True), ("independent_verification", 0)):
            item = deepcopy(self.manifest); item[name] = value; cases.append(item)
        item = deepcopy(self.manifest); item["extra"] = "unexpected"; cases.append(item)
        item = deepcopy(self.manifest); item.pop("transformation"); cases.append(item)
        item = deepcopy(self.manifest); item["runtime"]["revision"] = "latest"; cases.append(item)
        item = deepcopy(self.manifest); item["model"]["shards"] *= 2; cases.append(item)
        for value in (True, 0, -1, 2**63):
            item = deepcopy(self.manifest); item["model"]["shards"][0]["size_bytes"] = value; cases.append(item)
        item = deepcopy(self.manifest); item["model"]["shards"][0]["name"] = "../weights"; cases.append(item)
        item = deepcopy(self.manifest); item["model"]["shards"] = []; cases.append(item)
        item = deepcopy(self.manifest); item["model"]["dtype"] = "x" * 70000; cases.append(item)
        for index, item in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.make_binding(manifest_ref=self.put(f"weights/invalid-{index}.json", item))
        self.assertEqual(sum(self.calls.values()), 0)

    def test_manifest_provider_and_source_must_match_before_intent(self):
        for index, change in enumerate(("provider", "source")):
            item = deepcopy(self.manifest)
            if change == "provider": item["provider"]["adapter_sha256"] = "f" * 64
            else: item["source_commit"] = "f" * 40
            binding = self.make_binding(manifest_ref=self.put(f"weights/mismatched-{index}.json", item))
            workflow = DualCoderWorkflow(self.registry, project_id="test", coder_a_binding=binding)
            with self.assertRaises(ValueError): self.run_workflow("mismatched", workflow=workflow)
        self.assertEqual(sum(self.calls.values()), 0)
        with self.assertRaises(KeyError): self.read("dual-coder/mismatched/stages/coder_a/intent.json")

    def test_cross_project_manifest_and_lineage_are_rejected(self):
        self.registry.register_project("other", "Other synthetic project")
        foreign = self.put("weights/candidate.json", self.manifest, project="other")
        with self.assertRaises(ValueError): self.make_binding(manifest_ref=foreign)
        item = deepcopy(self.manifest); item["rollback_ref"] = foreign
        with self.assertRaises(ValueError): self.make_binding(manifest_ref=self.put("weights/foreign.json", item))

    def test_binding_cannot_use_a_different_canonical_registry_instance(self):
        with self.assertRaises(ValueError):
            DualCoderWorkflow(MerlinRegistry(self.registry.root), project_id="test", coder_a_binding=self.binding)

    def test_oversized_observation_is_fenced_after_one_call(self):
        def oversized(request):
            generated = self.coder_a(request)
            generated["observation"]["runtime_instance_id"] = "x" * 70000
            return generated
        self.assert_pending(self.run_workflow(coder_a=oversized))
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(self.calls["coder_a"], 1)

    def test_oversized_candidate_is_fenced_after_one_call(self):
        def oversized(request):
            generated = self.coder_a(request)
            generated["payload"]["candidate"] = "x" * (64 * 1024 + 1)
            return generated
        self.assert_pending(self.run_workflow(coder_a=oversized))
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(self.calls["coder_a"], 1)

    def test_callback_request_byte_ceiling_blocks_before_provider(self):
        self.specification["context_refs"] = [self.put("sources/large.txt", b"\0" * (400 * 1024))]
        self.assert_pending(self.run_workflow())
        self.assert_pending(self.run_workflow(workflow=self.fresh()))
        self.assertEqual(sum(self.calls.values()), 0)

    def test_heldout_ids_are_not_added_to_coder_request(self):
        self.run_workflow()
        for request in self.requests[:2]:
            self.assertNotIn("holdout_ids", request)
            self.assertNotIn("held-out-1", canonical(request).decode())
        self.assertEqual(self.requests[2]["specification"]["holdout_ids"], ["held-out-1"])

    def test_unbound_v1_workflow_keeps_original_records_and_replay(self):
        plain = DualCoderWorkflow(self.registry, project_id="test")
        def unbound(request):
            self.calls["coder_a"] += 1
            self.assertNotIn("weight_binding", request)
            return self.payload()
        first = self.run_workflow("legacy", workflow=plain, coder_a=unbound)
        expected = {}
        for path in ("spec.json", "stages/coder_a/intent.json", "stages/coder_a/result.json", "report.json"):
            body, ref = self.read("dual-coder/legacy/" + path)
            self.assertTrue(body["schema"].endswith("/1"))
            expected[path] = (body, ref)
        self.assertEqual(self.run_workflow("legacy", workflow=plain, coder_a=unbound), first)
        # A host with an opt-in binding may inspect a historical unbound record,
        # but cannot silently upgrade/reexecute that same session as bound.
        self.assertEqual(self.workflow.status("legacy")["schema"], "dot-dual-coder-status/1")
        with self.assertRaises(WorkflowConflict): self.run_workflow("legacy")
        for path, value in expected.items():
            self.assertEqual(self.read("dual-coder/legacy/" + path), value)
        self.assertEqual(self.calls, {"coder_a": 1, "coder_b": 1, "evaluator": 1})

    def test_unbound_missing_adapter_and_ambiguous_failure_behavior_is_unchanged(self):
        plain = DualCoderWorkflow(self.registry, project_id="test")
        result = plain.run("missing", specification=self.specification, providers=self.providers)
        self.assertEqual(result["status"], "blocked_missing_adapter")
        def failed(request):
            self.calls["coder_a"] += 1
            raise RuntimeError("synthetic failure")
        self.assert_pending(self.run_workflow("legacy-failure", workflow=plain, coder_a=failed))
        self.assert_pending(self.run_workflow("legacy-failure", workflow=plain, coder_a=failed))
        self.assertEqual(self.calls["coder_a"], 1)


class PostAuthenticationRecordTests(unittest.TestCase):
    """Compose fresh fixtures; callbacks cannot invalidate already-read records."""

    def _fixture(self):
        fixture = WeightBindingTests("runTest")
        fixture.setUp()
        return fixture

    @staticmethod
    def _mutate(fixture, path, mode):
        body, ref = fixture.read(path)
        if mode == "corrupt":
            fixture.corrupt(ref)
        else:
            fixture.put(path, {**body, "regression_fixture_version": "changed"})

    def _completed_mutation(self, operation, relative, mode):
        fixture = self._fixture()
        try:
            fixture.run_workflow()
            before = dict(fixture.calls)
            authentications = []
            target = 1 if operation == "status" else 4
            def authenticate(receipt, checksum):
                authentications.append(checksum)
                if len(authentications) == target:
                    self._mutate(fixture, "dual-coder/one/" + relative, mode)
                return True
            workflow = fixture.fresh(authenticate=authenticate)
            with self.assertRaises((RuntimeError, WorkflowConflict)):
                if operation == "status":
                    workflow.status("one")
                else:
                    fixture.run_workflow(workflow=workflow)
            self.assertEqual(len(authentications), target)
            self.assertEqual(fixture.calls, before)
        finally:
            fixture.doCleanups()

    def test_status_rechecks_receipt_bytes_and_single_version_after_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("status", "stages/coder_a/weight-receipt.json", mode)

    def test_replay_rechecks_receipt_bytes_and_single_version_after_last_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("replay", "stages/coder_a/weight-receipt.json", mode)

    def test_status_rechecks_stage_result_after_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("status", "stages/coder_a/result.json", mode)

    def test_replay_rechecks_stage_result_after_last_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("replay", "stages/coder_a/result.json", mode)

    def test_status_rechecks_specification_after_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("status", "spec.json", mode)

    def test_replay_rechecks_specification_after_last_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("replay", "spec.json", mode)

    def test_status_rechecks_intent_bytes_and_single_version_after_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("status", "stages/coder_a/intent.json", mode)

    def test_replay_rechecks_intent_bytes_and_single_version_after_last_authentication(self):
        for mode in ("corrupt", "append"):
            with self.subTest(mode=mode):
                self._completed_mutation("replay", "stages/coder_a/intent.json", mode)

    def test_replay_rechecks_already_read_downstream_results_and_intents(self):
        for stage in ("coder_b", "evaluator"):
            for record in ("intent", "result"):
                for mode in ("corrupt", "append"):
                    with self.subTest(stage=stage, record=record, mode=mode):
                        self._completed_mutation("replay", "stages/" + stage + "/" + record + ".json", mode)

    def test_authentication_cannot_change_new_downstream_intent_before_provider(self):
        for stage in ("coder_b", "evaluator"):
            for mode in ("corrupt", "append"):
                with self.subTest(stage=stage, mode=mode):
                    fixture = self._fixture()
                    try:
                        changed = []
                        path = "dual-coder/one/stages/" + stage + "/intent.json"
                        def authenticate(receipt, checksum):
                            if not changed and fixture.registry.artifact_history("test", path):
                                self._mutate(fixture, path, mode)
                                changed.append(path)
                            return True
                        result = fixture.run_workflow(workflow=fixture.fresh(authenticate=authenticate))
                        fixture.assert_pending(result, stage=stage)
                        self.assertEqual(changed, [path])
                        self.assertEqual(fixture.calls, {"coder_a": 1,
                            "coder_b": 0 if stage == "coder_b" else 1, "evaluator": 0})
                    finally:
                        fixture.doCleanups()

    def test_unchanged_status_and_replay_keep_existing_authentication_counts(self):
        fixture = self._fixture()
        try:
            first = fixture.run_workflow()
            before = dict(fixture.calls)
            calls = []
            def authenticate(receipt, checksum):
                calls.append(checksum)
                return True
            workflow = fixture.fresh(authenticate=authenticate)
            self.assertEqual(workflow.status("one")["status"], "completed_research_only")
            self.assertEqual(len(calls), 1)
            calls.clear()
            self.assertEqual(fixture.run_workflow(workflow=workflow), first)
            self.assertEqual(len(calls), 4)
            self.assertEqual(fixture.calls, before)
        finally:
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
