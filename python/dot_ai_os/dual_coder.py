"""Durable, bounded two-coder research workflow over MerlinRegistry.

Runtime-supplied coder A authors a candidate; coder B separately reviews it and
authors an alternative from the same pinned context. A separate evaluator
reports baseline/candidate case counts. The recommendation is research only:
this module neither executes candidate code nor establishes CACE verification,
changes skills, grants capabilities, signs, merges, deploys or promotes.

Every external callback receives a deterministic idempotency key. Intent is
persisted before invoking it. A crash/failure after intent but before a valid
result requires explicit external reconciliation; resume NEVER repeats that
call automatically. This is at-most-once automatic invocation, not exactly-once
provider execution. Completed stages replay from immutable ArtifactRefs.

Providers are injected by a trusted host, with host-owned identity/revision and
prompt/config/adapter digests. These declarations do not authenticate providers
or prove independence. The host must enforce resource/isolation limits; the
zero-cost declaration is not billing enforcement. Coders receive no held-out
IDs or evaluator outcomes. Case-ID separation is not semantic dataset secrecy.

An optional host-provisioned coder_a WeightBinding uses explicit v2 records to
admit exact invocation evidence. It supplies no loader or model endpoint, and
neither host authentication nor declared case counts assess model quality.
Historical unbound v1 records retain their existing research-only semantics.

Use one cooperative host per registry. Linux advisory locks serialize this
workflow, but do not defend against arbitrary code bypassing the lock or a
compromised registry host. No second journal/database is created.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
import re
from typing import Any, Callable, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry
from merlin.weight_binding import WeightBinding, provider_identity

from .bridge import canonical, digest, text_value

MAX_CONTEXT_BYTES = 512 * 1024
MAX_CANDIDATE_BYTES = 64 * 1024
STAGES = ("coder_a", "coder_b", "evaluator")
Provider = Callable[[dict[str, Any]], Mapping[str, Any]]


class WorkflowConflict(ValueError):
    """A session or stage identity was reused with different immutable inputs."""


def _sha(value: Any, field: str, length: int = 64) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{%d}" % length, value) is None:
        raise ValueError(f"{field} requires a full lowercase digest")
    return value


def _case_ids(values: Any, field: str) -> list[str]:
    if not isinstance(values, list) or not 1 <= len(values) <= 1000:
        raise ValueError(f"{field} needs 1 through 1000 case IDs")
    for item in values:
        text_value(item, field, 200)
    if len(set(values)) != len(values):
        raise ValueError(f"duplicate {field}")
    return list(values)


def _provider_identity(value: Any) -> dict[str, str]:
    return provider_identity(value)


class DualCoderWorkflow:
    def __init__(self, registry: MerlinRegistry, *, project_id: str = "dot-ai-os",
                 coder_a_binding: WeightBinding | None = None):
        self.registry = registry
        self.project_id = text_value(project_id, "project_id", 120)
        if coder_a_binding is not None and (not isinstance(coder_a_binding, WeightBinding)
                or coder_a_binding.registry is not registry or coder_a_binding.project_id != self.project_id):
            raise ValueError("coder_a binding must use this exact canonical registry and project")
        self.coder_a_binding = coder_a_binding

    def _base(self, session_id: str) -> str:
        if not isinstance(session_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id) is None:
            raise ValueError("session_id must be a safe bounded identifier")
        return f"dual-coder/{session_id}"

    @contextmanager
    def _locked(self, session_id: str):
        # The filename contains only a validated identifier; never follow a symlink.
        self._base(session_id)
        # Serialize all sessions using the same registry: upstream blob writes
        # share a temporary pathname when two sessions store identical bytes.
        path = self.registry.root / "dot-dual-coder.lock"
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open(path, flags, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkflowConflict("session is already running; do not dispatch a second host") from exc
            yield
        finally:
            os.close(descriptor)

    def _load_once(self, path: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        history = self.registry.artifact_history(self.project_id, path)
        if not history:
            return None
        if len(history) != 1:
            raise WorkflowConflict("immutable workflow path has multiple versions")
        ref = self.registry.artifact_ref(self.project_id, path, version=1)
        raw = self.registry.read_artifact_ref(ref, max_bytes=2 * 1024 * 1024)["content"]
        value = json.loads(raw)
        if not isinstance(value, dict) or canonical(value) != raw:
            raise WorkflowConflict("workflow record is not a canonical object")
        return value, ref

    def _put_once(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        old = self._load_once(path)
        if old is not None:
            if canonical(old[0]) != canonical(payload):
                raise WorkflowConflict("immutable workflow identity conflicts with new input")
            return old[1]
        self.registry.put_artifact(self.project_id, path, canonical(payload), "application/json")
        return self.registry.artifact_ref(self.project_id, path, version=1)

    def _spec(self, specification: Mapping[str, Any],
              providers: Mapping[str, Mapping[str, Any]], *, bind: bool = True
              ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fields = {"objective", "source_commit", "context_refs", "train_ids", "holdout_ids",
                  "acceptance_criteria", "max_cost_usd"}
        if not isinstance(specification, Mapping) or set(specification) != fields:
            raise ValueError("specification requires the exact declared field set")
        spec = deepcopy(dict(specification))
        text_value(spec["objective"], "objective", 3000)
        _sha(spec["source_commit"], "source_commit", 40)
        spec["train_ids"] = _case_ids(spec["train_ids"], "train_ids")
        spec["holdout_ids"] = _case_ids(spec["holdout_ids"], "holdout_ids")
        if set(spec["train_ids"]) & set(spec["holdout_ids"]):
            raise ValueError("training and held-out case IDs overlap")
        if type(spec["max_cost_usd"]) is not int or spec["max_cost_usd"] != 0:
            raise ValueError("only zero-cost workflow specifications are admitted")
        criteria = spec["acceptance_criteria"]
        if not isinstance(criteria, list) or not 1 <= len(criteria) <= 20:
            raise ValueError("1 through 20 acceptance criteria required")
        for item in criteria:
            text_value(item, "acceptance criterion", 1000)
        if not isinstance(providers, Mapping) or set(providers) != set(STAGES):
            raise ValueError("all three runtime-owned provider identities required")
        identities = {name: _provider_identity(providers[name]) for name in STAGES}
        if len({x["provider_id"] for x in identities.values()}) != 3:
            raise ValueError("coder and evaluator identities must be distinct")
        refs = spec["context_refs"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 50:
            raise ValueError("1 through 50 exact context references required")
        contexts = []
        size = 0
        seen = set()
        for value in refs:
            ref = ArtifactRef.from_mapping(value)
            if ref.project_id != self.project_id:
                raise ValueError("cross-project context is outside workflow scope")
            encoded = canonical(ref.to_dict())
            if encoded in seen:
                raise ValueError("duplicate context reference")
            seen.add(encoded)
            raw = self.registry.read_artifact_ref(ref.to_dict(), max_bytes=MAX_CONTEXT_BYTES)["content"]
            size += len(raw)
            if size > MAX_CONTEXT_BYTES:
                raise ValueError("context exceeds bounded shard; select a smaller pinned packet")
            contexts.append({"artifact_ref": ref.to_dict(), "text": raw.decode("utf-8")})
        envelope = {"schema": "dot-dual-coder-spec/1", "specification": spec, "providers": identities}
        if bind and self.coder_a_binding is not None:
            self.coder_a_binding.validate_for(identities["coder_a"], spec["source_commit"])
            envelope.update(schema="dot-dual-coder-spec/2",
                            coder_a_weight_manifest_ref=self.coder_a_binding.manifest_ref)
        return envelope, contexts

    @staticmethod
    def _candidate(value: Any) -> dict[str, str]:
        if not isinstance(value, Mapping) or set(value) != {"candidate", "rationale"}:
            raise ValueError("coder output must contain only candidate and rationale")
        candidate = text_value(value["candidate"], "candidate", MAX_CANDIDATE_BYTES)
        if len(candidate.encode("utf-8")) > MAX_CANDIDATE_BYTES:
            raise ValueError("candidate exceeds UTF-8 byte ceiling")
        rationale = text_value(value["rationale"], "rationale", 8000)
        return {"candidate": candidate, "rationale": rationale}

    @staticmethod
    def _evaluation(value: Any, spec: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, Mapping) or set(value) != {"baseline", "coder_a", "coder_b", "notes"}:
            raise ValueError("evaluator requires baseline and both candidate case counts")
        result = {}
        for name in ("baseline", "coder_a", "coder_b"):
            counts = value[name]
            if not isinstance(counts, Mapping) or set(counts) != {"train_passed", "holdout_passed", "regressions"}:
                raise ValueError("case counts must use the exact declared schema")
            counts = dict(counts)
            bounds = {"train_passed": len(spec["train_ids"]),
                      "holdout_passed": len(spec["holdout_ids"]), "regressions": 1000}
            for field, maximum in bounds.items():
                if type(counts[field]) is not int or not 0 <= counts[field] <= maximum:
                    raise ValueError("invalid evaluator case counts")
            result[name] = counts
        result["notes"] = text_value(value["notes"], "evaluation notes", 8000)
        return result

    @staticmethod
    def _coder_inputs(spec: dict[str, Any], contexts: list[dict[str, Any]]) -> dict[str, Any]:
        return {"objective": spec["objective"], "source_commit": spec["source_commit"],
                "context": contexts, "train_ids": spec["train_ids"],
                "holdout_manifest_sha256": digest(canonical(spec["holdout_ids"])),
                "acceptance_criteria": spec["acceptance_criteria"],
                "max_cost_usd": 0, "qualification": False, "promotion_authority": False}

    def _weight_receipt(self, *, stage_path: str, session_id: str, identity: dict[str, Any],
                        intent_ref: dict[str, Any], inputs: dict[str, Any],
                        payload: dict[str, Any] | None = None,
                        expected_ref: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if self.coder_a_binding is None:
            raise PermissionError("weight-bound evidence requires the configured host binding")
        saved = self._load_once(stage_path + "/weight-receipt.json")
        if saved is None:
            if expected_ref is not None:
                raise WorkflowConflict("weight-bound result has no canonical invocation receipt")
            return None
        if expected_ref is not None and saved[1] != expected_ref:
            raise WorkflowConflict("weight-bound result points to a different invocation receipt")
        stored_payload = self._candidate(saved[0].get("payload"))
        if payload is not None and canonical(stored_payload) != canonical(payload):
            raise WorkflowConflict("weight receipt and stage output differ")
        request = self.coder_a_binding.invocation_request(session_id=session_id, intent_ref=intent_ref,
                                                          identity=identity, inputs=inputs)
        self.coder_a_binding.validate_receipt(saved[0], payload=stored_payload, request=request)
        return saved[1]

    def _stage(self, *, base: str, name: str, request_sha: str,
               provider: dict[str, str], inputs: dict[str, Any], callback: Provider | None,
               validator: Callable[[Any], dict[str, Any]], session_id: str | None = None,
               before_callback: Callable[[], None] | None = None) -> dict[str, Any]:
        stage_path = f"{base}/stages/{name}"
        input_sha = digest(canonical(inputs))
        identity = {"schema": "dot-dual-coder-intent/1", "stage": name,
                    "request_sha256": request_sha, "input_sha256": input_sha,
                    "provider": provider}
        binding = self.coder_a_binding if name == "coder_a" else None
        if binding is not None:
            identity.update(schema="dot-dual-coder-intent/2", session_id=session_id,
                            weight_manifest_ref=binding.manifest_ref)
        identity["idempotency_key"] = digest(canonical(identity))
        intent = self._load_once(stage_path + "/intent.json")
        saved = self._load_once(stage_path + "/result.json")
        if (name == "coder_a" and intent is None
                and self._load_once(stage_path + "/weight-receipt.json") is not None):
            raise WorkflowConflict("weight receipt has no durable invocation intent")
        if intent is not None and canonical(intent[0]) != canonical(identity):
            raise WorkflowConflict("stage identity conflicts with pinned input/provider")
        if saved is not None:
            if intent is None:
                raise WorkflowConflict("stage result has no durable invocation intent")
            result, ref = saved
            fields = {"schema", "intent_ref", "payload", "qualification", "promotion_authority"}
            if binding is not None:
                fields |= {"weight_receipt_ref", "independent_verification", "model_quality_assessed"}
            if set(result) != fields:
                raise WorkflowConflict("invalid persisted stage envelope")
            schema = "dot-dual-coder-result/2" if binding is not None else "dot-dual-coder-result/1"
            if (result["schema"] != schema or result["intent_ref"] != intent[1]
                    or result["qualification"] is not False or result["promotion_authority"] is not False):
                raise WorkflowConflict("persisted stage envelope cannot confer authority")
            payload = validator(result["payload"])
            if binding is not None:
                if result["independent_verification"] is not False or result["model_quality_assessed"] is not False:
                    raise WorkflowConflict("weight binding cannot establish independent verification or model quality")
                self._weight_receipt(stage_path=stage_path, session_id=session_id, identity=identity,
                    intent_ref=intent[1], inputs=inputs, payload=payload,
                    expected_ref=ArtifactRef.from_mapping(result["weight_receipt_ref"]).to_dict())
            completed = {"status": "completed", "payload": payload, "result_ref": ref}
            if binding is not None:
                completed["weight_receipt_ref"] = result["weight_receipt_ref"]
            return completed
        if intent is not None:
            pending = {"status": "reconciliation_required", "stage": name,
                    "intent_ref": intent[1], "reason": "intent_without_committed_result",
                    "automatic_retry": False}
            if binding is not None:
                receipt_ref = self._weight_receipt(stage_path=stage_path, session_id=session_id, identity=identity,
                    intent_ref=intent[1], inputs=inputs)
                if receipt_ref is not None:
                    pending["weight_receipt_ref"] = receipt_ref
            return pending
        if callback is None:
            return {"status": "blocked_missing_adapter", "stage": name,
                    "provider_id": provider["provider_id"]}
        intent_ref = self._put_once(stage_path + "/intent.json", identity)
        request = deepcopy({**inputs, "stage": name,
                            "idempotency_key": identity["idempotency_key"]})
        try:
            if binding is not None:
                request = binding.invocation_request(session_id=session_id, intent_ref=intent_ref,
                                                     identity=identity, inputs=inputs)
            if before_callback is not None:
                before_callback()
            generated = callback(deepcopy(request))
            if binding is not None:
                if not isinstance(generated, Mapping) or set(generated) != {"payload", "observation"}:
                    raise ValueError("weight-bound coder must return payload and invocation observation")
                payload = validator(generated["payload"])
                receipt = binding.admit(payload=payload, observation=generated["observation"], request=request)
                receipt_ref = self._put_once(stage_path + "/weight-receipt.json", receipt)
            else:
                payload = validator(generated)
        except Exception as exc:
            # Never persist messages/tracebacks: providers may include private data.
            self._put_once(stage_path + "/failure.json", {
                "schema": "dot-dual-coder-callback-failure/1", "intent_ref": intent_ref,
                "error_class": type(exc).__name__, "automatic_retry": False})
            return {"status": "reconciliation_required", "stage": name,
                    "intent_ref": intent_ref, "reason": "callback_failed_or_returned_invalid_output",
                    "automatic_retry": False}
        result = {"schema": "dot-dual-coder-result/1", "intent_ref": intent_ref,
                  "payload": payload, "qualification": False, "promotion_authority": False}
        if binding is not None:
            result.update(schema="dot-dual-coder-result/2", weight_receipt_ref=receipt_ref,
                          independent_verification=False, model_quality_assessed=False)
        ref = self._put_once(stage_path + "/result.json", result)
        completed = {"status": "completed", "payload": payload, "result_ref": ref}
        if binding is not None:
            completed["weight_receipt_ref"] = receipt_ref
        return completed

    def run(self, session_id: str, *, specification: Mapping[str, Any],
            providers: Mapping[str, Mapping[str, Any]], coder_a: Provider | None = None,
            coder_b: Provider | None = None, evaluator: Provider | None = None) -> dict[str, Any]:
        """Run or resume up to three callbacks, leaving ambiguity for reconciliation."""
        base = self._base(session_id)
        envelope, contexts = self._spec(specification, providers)
        with self._locked(session_id):
            spec_ref = self._put_once(base + "/spec.json", envelope)
            request_sha = digest(canonical(envelope))
            spec = envelope["specification"]
            coder_input = self._coder_inputs(spec, contexts)
            a = self._stage(base=base, name="coder_a", request_sha=request_sha,
                            provider=envelope["providers"]["coder_a"], inputs=coder_input,
                            callback=coder_a, validator=self._candidate, session_id=session_id)
            if a["status"] != "completed":
                return self._blocked(session_id, spec_ref, a)
            def current_bound_a():
                # Authenticate the exact committed dependency at each effect
                # boundary. This only replays A's records; it cannot call A.
                if envelope["schema"] == "dot-dual-coder-spec/2":
                    current = self._stage(base=base, name="coder_a", request_sha=request_sha,
                        provider=envelope["providers"]["coder_a"], inputs=coder_input,
                        callback=None, validator=self._candidate, session_id=session_id)
                    if canonical(current) != canonical(a):
                        raise WorkflowConflict("admitted coder A result changed before a dependent effect")
            current_bound_a()
            b_input = {**coder_input, "coder_a_result_ref": a["result_ref"],
                       "coder_a_candidate": a["payload"],
                       "assignment": "Independently review coder A and propose an alternative; retain dissent."}
            b = self._stage(base=base, name="coder_b", request_sha=request_sha,
                            provider=envelope["providers"]["coder_b"], inputs=b_input,
                            callback=coder_b, validator=self._candidate, before_callback=current_bound_a)
            if b["status"] != "completed":
                return self._blocked(session_id, spec_ref, b)
            current_bound_a()
            evaluation_input = {"specification": spec, "context": contexts,
                                "candidates": {"coder_a": a["payload"], "coder_b": b["payload"]},
                                "candidate_refs": {"coder_a": a["result_ref"], "coder_b": b["result_ref"]},
                                "qualification": False, "promotion_authority": False}
            evaluation = self._stage(base=base, name="evaluator", request_sha=request_sha,
                                     provider=envelope["providers"]["evaluator"], inputs=evaluation_input,
                                     callback=evaluator, validator=lambda x: self._evaluation(x, spec),
                                     before_callback=current_bound_a)
            if evaluation["status"] != "completed":
                return self._blocked(session_id, spec_ref, evaluation)
            counts = evaluation["payload"]
            baseline = counts["baseline"]
            eligible = [name for name in ("coder_a", "coder_b")
                        if counts[name]["regressions"] == 0
                        and counts[name]["train_passed"] >= baseline["train_passed"]
                        and counts[name]["holdout_passed"] > baseline["holdout_passed"]]
            eligible.sort(key=lambda name: (-counts[name]["holdout_passed"],
                                            -counts[name]["train_passed"], name))
            recommendation = eligible[0] if eligible else "retain_parent"
            report = {"schema": "dot-dual-coder-report/1", "session_id": session_id,
                      "status": "completed_research_only", "spec_ref": spec_ref,
                      "coder_a_ref": a["result_ref"], "coder_b_ref": b["result_ref"],
                      "evaluation_ref": evaluation["result_ref"], "recommendation": recommendation,
                      "selection_scope": "declared_evaluator_case_counts_only",
                      "qualification": False, "promotion_authority": False,
                      "next_gate": "canonical_Hermes_MCFC_and_independent_CACE_policy",
                      "limitations": ["runtime identities are declarations, not authenticated attestations",
                                      "callback reports are not independent CACE receipts",
                                      "no live dot/model/OCI adapter is configured by this module"]}
            if self.coder_a_binding is not None:
                report.update(schema="dot-dual-coder-report/2", coder_a_weight_receipt_ref=a["weight_receipt_ref"],
                              independent_verification=False, model_quality_assessed=False)
                report["limitations"][0] = ("coder A weight evidence is admitted only by the configured host callback; "
                                            "other provider identities remain declarations")
            current_bound_a()
            ref = self._put_once(base + "/report.json", report)
            return {**report, "report_ref": ref}

    @staticmethod
    def _blocked(session_id: str, spec_ref: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
        return {"schema": "dot-dual-coder-blocked/1", "session_id": session_id,
                "spec_ref": spec_ref, **stage, "qualification": False,
                "promotion_authority": False}

    def status(self, session_id: str) -> dict[str, Any]:
        """Read stored stage state so a fresh dot session can find its next gate."""
        base = self._base(session_id)
        spec = self._load_once(base + "/spec.json")
        if spec is None:
            return {"session_id": session_id, "status": "not_started", "next_stage": "coder_a"}
        spec_payload = spec[0]
        bound = spec_payload.get("schema") == "dot-dual-coder-spec/2"
        fields = {"schema", "specification", "providers"}
        if bound:
            fields.add("coder_a_weight_manifest_ref")
            if self.coder_a_binding is None:
                raise PermissionError("weight-bound status requires the matching host binding")
        if set(spec_payload) != fields or spec_payload["schema"] not in {"dot-dual-coder-spec/1", "dot-dual-coder-spec/2"}:
            raise WorkflowConflict("invalid persisted specification envelope")
        rebuilt, contexts = self._spec(spec_payload["specification"], spec_payload["providers"], bind=bound)
        if canonical(rebuilt) != canonical(spec_payload):
            raise WorkflowConflict("persisted specification differs from the configured weight binding")
        coder_inputs = self._coder_inputs(spec_payload["specification"], contexts)
        request_sha = digest(canonical(spec_payload))
        stages = {}
        result_refs = {}
        receipt_refs = {}
        for name in STAGES:
            stage_path = f"{base}/stages/{name}"
            result = self._load_once(stage_path + "/result.json")
            intent = self._load_once(stage_path + "/intent.json")
            weight_stage = bound and name == "coder_a"
            if (name == "coder_a" and intent is None
                    and self._load_once(stage_path + "/weight-receipt.json") is not None):
                raise WorkflowConflict("weight receipt has no durable invocation intent")
            if intent is not None:
                identity = dict(intent[0])
                key = identity.pop("idempotency_key", None)
                fields = {"schema", "stage", "request_sha256", "input_sha256", "provider"}
                if weight_stage:
                    fields |= {"session_id", "weight_manifest_ref"}
                schema = "dot-dual-coder-intent/2" if weight_stage else "dot-dual-coder-intent/1"
                if (set(identity) != fields or identity["schema"] != schema or identity["stage"] != name
                        or identity["request_sha256"] != request_sha
                        or identity["provider"] != spec_payload["providers"][name]
                        or key != digest(canonical(identity))):
                    raise WorkflowConflict("persisted invocation identity mismatch")
                if weight_stage and (identity["session_id"] != session_id
                        or identity["weight_manifest_ref"] != spec_payload["coder_a_weight_manifest_ref"]
                        or identity["input_sha256"] != digest(canonical(coder_inputs))):
                    raise WorkflowConflict("persisted weight intent differs from current session/input binding")
            if weight_stage:
                if intent is not None:
                    ref = self._weight_receipt(stage_path=stage_path, session_id=session_id, identity=intent[0],
                        intent_ref=intent[1], inputs=coder_inputs,
                        payload=self._candidate(result[0].get("payload")) if result is not None else None,
                        expected_ref=ArtifactRef.from_mapping(result[0].get("weight_receipt_ref")).to_dict()
                            if result is not None else None)
                    if ref is not None:
                        receipt_refs[name] = ref
            if result is not None:
                envelope = result[0]
                fields = {"schema", "intent_ref", "payload", "qualification", "promotion_authority"}
                if weight_stage:
                    fields |= {"weight_receipt_ref", "independent_verification", "model_quality_assessed"}
                schema = "dot-dual-coder-result/2" if weight_stage else "dot-dual-coder-result/1"
                if (intent is None or set(envelope) != fields or envelope["schema"] != schema
                        or envelope["intent_ref"] != intent[1]
                        or envelope["qualification"] is not False
                        or envelope["promotion_authority"] is not False):
                    raise WorkflowConflict("invalid persisted stage envelope")
                if weight_stage and (envelope["independent_verification"] is not False
                                      or envelope["model_quality_assessed"] is not False):
                    raise WorkflowConflict("weight binding cannot establish independent verification or model quality")
                if name == "evaluator":
                    self._evaluation(envelope["payload"], spec_payload["specification"])
                else:
                    self._candidate(envelope["payload"])
                result_refs[name] = result[1]
            stages[name] = "completed" if result else "reconciliation_required" if intent else "not_started"
        report = self._load_once(base + "/report.json")
        if report is not None:
            payload = report[0]
            schema = "dot-dual-coder-report/2" if bound else "dot-dual-coder-report/1"
            if (set(result_refs) != set(STAGES) or payload.get("schema") != schema
                    or payload.get("session_id") != session_id or payload.get("spec_ref") != spec[1]
                    or payload.get("qualification") is not False or payload.get("promotion_authority") is not False
                    or payload.get("coder_a_ref") != result_refs["coder_a"]
                    or payload.get("coder_b_ref") != result_refs["coder_b"]
                    or payload.get("evaluation_ref") != result_refs["evaluator"]):
                raise WorkflowConflict("invalid persisted report bindings")
            if bound and (payload.get("coder_a_weight_receipt_ref") != receipt_refs.get("coder_a")
                    or payload.get("independent_verification") is not False
                    or payload.get("model_quality_assessed") is not False):
                raise WorkflowConflict("invalid persisted weight report bindings")
        status = {"schema": "dot-dual-coder-status/1", "session_id": session_id,
                "spec_ref": spec[1], "stages": stages,
                "status": "completed_research_only" if report else "incomplete",
                "next_stage": next((name for name in STAGES if stages[name] != "completed"), None),
                "report_ref": report[1] if report else None,
                "qualification": False, "promotion_authority": False}
        if bound:
            status.update(schema="dot-dual-coder-status/2", weight_receipt_refs=receipt_refs,
                          independent_verification=False, model_quality_assessed=False)
        return status
