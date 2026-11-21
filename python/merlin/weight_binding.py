"""Opt-in, host-authenticated identity binding for one research coder invocation.

This module reads bounded canonical metadata. It does not load weights, invoke a
model, grant resources, assess model quality, or establish independent verification.
The manifest describes intended identity; the observation describes one completed
invocation. A separately configured host authenticator must admit the complete
receipt. A digest or a fixture returning True is not real runtime authentication.

The host must verify loaded bytes and bind its observation to the actual invocation,
not merely query a mutable model name before calling it. Authentication is repeated
on replay/status reads; it must not itself invoke the model. Persistence and the
no-automatic-retry boundary belong to the existing DualCoderWorkflow.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Callable, Mapping

from dot_ai_os.bridge import canonical, digest, integer, text_value
from .artifact_ref import ArtifactRef
from .project_registry import MerlinRegistry

MANIFEST_SCHEMA = "merlin-weight-manifest/1"
REQUEST_SCHEMA = "merlin-weight-invocation-request/1"
OBSERVATION_SCHEMA = "merlin-weight-invocation-observation/1"
RECEIPT_SCHEMA = "merlin-weight-invocation-receipt/1"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_OBSERVATION_BYTES = 64 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_CONTEXT_BYTES = 512 * 1024
FLAGS = {"qualification": False, "promotion_authority": False,
         "independent_verification": False, "model_quality_assessed": False}


def _sha(value: Any, field: str, length: int = 64) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{%d}" % length, value) is None:
        raise ValueError(f"{field} requires a full lowercase digest")
    return value


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} requires the exact declared field set")
    return deepcopy(dict(value))


def _bounded(value: Any, maximum: int, label: str) -> bytes:
    raw = canonical(value)
    if len(raw) > maximum:
        raise ValueError(f"{label} exceeds its byte ceiling")
    return raw


def provider_identity(value: Any) -> dict[str, str]:
    """The existing v1 host declaration; it is not an authentication mechanism."""
    identity = _object(value, {"provider_id", "revision", "prompt_sha256",
                              "config_sha256", "adapter_sha256"}, "provider identity")
    text_value(identity["provider_id"], "provider_id", 200)
    revision = text_value(identity["revision"], "revision", 200)
    if revision.casefold() in {"latest", "main", "master", "head", "default"}:
        raise ValueError("an immutable provider revision declaration is required")
    for field in ("prompt_sha256", "config_sha256", "adapter_sha256"):
        _sha(identity[field], field)
    return identity


def _runtime(value: Any) -> dict[str, str]:
    runtime = _object(value, {"runtime_id", "revision", "implementation_sha256"}, "runtime identity")
    text_value(runtime["runtime_id"], "runtime_id", 200)
    revision = text_value(runtime["revision"], "runtime revision", 200)
    if revision.casefold() in {"latest", "stable", "main", "master", "head", "current", "default"}:
        raise ValueError("an immutable runtime revision is required")
    _sha(runtime["implementation_sha256"], "runtime implementation")
    return runtime


def _model(value: Any) -> dict[str, Any]:
    model = _object(value, {"architecture_sha256", "tensor_layout_sha256", "checkpoint_sha256",
                           "shards", "tokenizer_sha256", "model_config_sha256",
                           "inference_config_sha256", "dtype", "quantization_sha256"}, "model identity")
    for name in set(model) - {"shards", "dtype"}:
        _sha(model[name], name)
    # Dtype is an identity label, not a claim that a runtime supports that dtype.
    text_value(model["dtype"], "dtype", 80)
    shards = model["shards"]
    if not isinstance(shards, list) or not 1 <= len(shards) <= 128:
        raise ValueError("model requires 1 through 128 shard identities")
    names = set()
    for shard in shards:
        row = _object(shard, {"name", "sha256", "size_bytes"}, "weight shard")
        name = row["name"]
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", name) is None:
            raise ValueError("shard name must be a bounded identity, not a filesystem path")
        if name in names:
            raise ValueError("duplicate shard identity")
        names.add(name)
        _sha(row["sha256"], "shard sha256")
        integer(row["size_bytes"], "shard size_bytes", 1, 2**63 - 1)
    return model


class WeightBinding:
    """Host-provisioned manifest and authenticator, initially for coder A only.

    Constructor inputs are detached. Exact artifact versions remain pinned even
    if a newer version appears. Every use rechecks their bytes. The authenticator
    receives a detached complete receipt and its canonical SHA-256, and must
    return the Boolean True. The surrounding trusted host owns its provisioning.
    """

    def __init__(self, registry: MerlinRegistry, *, project_id: str,
                 manifest_ref: Mapping[str, Any], authenticate: Callable):
        if not callable(authenticate):
            raise ValueError("a separately configured host authenticator is required")
        self.registry = registry
        self.project_id = text_value(project_id, "project_id", 120)
        self._manifest_ref_bytes = canonical(self._ref(manifest_ref))
        self._authenticate = authenticate
        self._manifest()

    @property
    def manifest_ref(self) -> dict[str, Any]:
        return json.loads(self._manifest_ref_bytes)

    def _ref(self, value: Any) -> dict[str, Any]:
        ref = ArtifactRef.from_mapping(value).to_dict()
        if ref["project_id"] != self.project_id:
            raise ValueError("cross-project weight evidence is outside workflow scope")
        return ref

    def _read(self, value: Any, *, maximum: int = MAX_MANIFEST_BYTES) -> bytes:
        return self.registry.read_artifact_ref(self._ref(value), max_bytes=maximum)["content"]

    def _manifest(self) -> dict[str, Any]:
        raw = self._read(self.manifest_ref)
        body = json.loads(raw)
        fields = {"schema", "role", "source_commit", "provider", "runtime", "model",
                  "transformation", "rollback_ref", "evaluation_protocol_ref", *FLAGS}
        body = _object(body, fields, "weight manifest")
        if canonical(body) != raw or body["schema"] != MANIFEST_SCHEMA or body["role"] != "coder_a":
            raise ValueError("canonical coder_a weight manifest required")
        if any(body[name] is not False for name in FLAGS):
            raise ValueError("weight manifest cannot confer authority or model-quality evidence")
        _sha(body["source_commit"], "source_commit", 40)
        provider_identity(body["provider"])
        _runtime(body["runtime"])
        _model(body["model"])
        transform = _object(body["transformation"], {"program_sha256", "delta_sha256"}, "transformation")
        _sha(transform["program_sha256"], "transformation program")
        if transform["delta_sha256"] is not None:
            _sha(transform["delta_sha256"], "transformation delta")
        # These exact artifacts preserve rollback/protocol lineage only. Their
        # existence does not establish an approved deployment or sound experiment.
        for name in ("rollback_ref", "evaluation_protocol_ref"):
            self._read(body[name])
        return body

    def validate_for(self, provider: Mapping[str, Any], source_commit: str) -> dict[str, Any]:
        body = self._manifest()
        if body["provider"] != provider_identity(provider) or body["source_commit"] != source_commit:
            raise ValueError("weight manifest differs from pinned provider/source identity")
        return body

    def _inputs(self, inputs: Mapping[str, Any]) -> None:
        contexts = inputs.get("context")
        if not isinstance(contexts, list) or not 1 <= len(contexts) <= 50:
            raise ValueError("weight invocation requires the selected canonical context")
        size = 0
        seen = set()
        for value in contexts:
            item = _object(value, {"artifact_ref", "text"}, "context item")
            ref = self._ref(item["artifact_ref"])
            key = canonical(ref)
            if key in seen:
                raise ValueError("duplicate weight invocation context")
            seen.add(key)
            raw = self._read(ref, maximum=MAX_CONTEXT_BYTES)
            size += len(raw)
            if size > MAX_CONTEXT_BYTES or raw.decode("utf-8") != item["text"]:
                raise ValueError("weight invocation context differs from its canonical bytes")

    def invocation_request(self, *, session_id: str, intent_ref: Mapping[str, Any],
                           identity: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Revalidate current canonical inputs and construct a detached host request."""
        if not isinstance(session_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,100}", session_id) is None:
            raise ValueError("bounded workflow session required")
        fields = {"schema", "stage", "session_id", "request_sha256", "input_sha256",
                  "provider", "weight_manifest_ref", "idempotency_key"}
        identity = _object(identity, fields, "weight invocation intent")
        ref = self._ref(intent_ref)
        if (identity["schema"] != "dot-dual-coder-intent/2" or identity["stage"] != "coder_a"
                or identity["session_id"] != session_id
                or identity["weight_manifest_ref"] != self.manifest_ref
                or ref["logical_path"] != f"dual-coder/{session_id}/stages/coder_a/intent.json"
                or ref["version"] != 1 or self._read(ref) != canonical(identity)):
            raise ValueError("weight invocation requires the exact canonical session intent")
        _sha(identity["request_sha256"], "request_sha256")
        _sha(identity["input_sha256"], "input_sha256")
        key = identity.pop("idempotency_key")
        if key != digest(canonical(identity)) or identity["input_sha256"] != digest(canonical(inputs)):
            raise ValueError("weight invocation input/idempotency binding differs")
        manifest = self.validate_for(identity["provider"], inputs.get("source_commit"))
        self._inputs(inputs)
        request = deepcopy({**dict(inputs), "stage": "coder_a", "idempotency_key": key,
            "weight_binding": {"schema": REQUEST_SCHEMA, "session_id": session_id,
                "manifest_ref": self.manifest_ref, "manifest": manifest, "intent_ref": ref,
                "request_sha256": identity["request_sha256"], "input_sha256": identity["input_sha256"]}})
        _bounded(request, MAX_REQUEST_BYTES, "weight invocation request")
        return request

    def _revalidate_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        snapshot = deepcopy(dict(request))
        context = _object(snapshot.pop("weight_binding", None),
            {"schema", "session_id", "manifest_ref", "manifest", "intent_ref", "request_sha256", "input_sha256"},
            "weight invocation context")
        if context["schema"] != REQUEST_SCHEMA:
            raise ValueError("unsupported weight invocation request")
        snapshot.pop("stage", None)
        snapshot.pop("idempotency_key", None)
        identity = json.loads(self._read(context["intent_ref"]))
        rebuilt = self.invocation_request(session_id=context["session_id"], intent_ref=context["intent_ref"],
                                           identity=identity, inputs=snapshot)
        if canonical(rebuilt) != canonical(request):
            raise ValueError("weight invocation request changed after admission")
        return rebuilt["weight_binding"]

    def admit(self, *, payload: Mapping[str, Any], observation: Mapping[str, Any],
              request: Mapping[str, Any]) -> dict[str, Any]:
        """Authenticate one completed observation; no persistence or model call."""
        context = self._revalidate_request(request)
        manifest = context["manifest"]
        payload = deepcopy(dict(payload))
        fields = {"schema", "evidence_kind", "status", "session_id", "stage", "source_commit",
                  "manifest_ref", "intent_ref", "request_sha256", "input_sha256", "callback_request_sha256",
                  "idempotency_key", "output_sha256", "provider", "runtime", "runtime_instance_id",
                  "load_session_id", "loaded_model", *FLAGS}
        observed = _object(observation, fields, "weight invocation observation")
        _bounded(observed, MAX_OBSERVATION_BYTES, "weight invocation observation")
        expected = {"schema": OBSERVATION_SCHEMA, "evidence_kind": "host_observed_weight_invocation",
            "status": "completed", "session_id": context["session_id"], "stage": "coder_a",
            "source_commit": request["source_commit"], "manifest_ref": context["manifest_ref"],
            "intent_ref": context["intent_ref"], "request_sha256": context["request_sha256"],
            "input_sha256": context["input_sha256"], "callback_request_sha256": digest(canonical(request)),
            "idempotency_key": request["idempotency_key"], "output_sha256": digest(canonical(payload)),
            "provider": manifest["provider"], "runtime": manifest["runtime"], "loaded_model": manifest["model"]}
        if any(canonical(observed[name]) != canonical(value) for name, value in expected.items()):
            raise ValueError("observed weight invocation differs from its exact intended identity")
        if any(observed[name] is not False for name in FLAGS):
            raise ValueError("weight observation cannot confer authority or model-quality evidence")
        text_value(observed["runtime_instance_id"], "runtime instance", 200)
        text_value(observed["load_session_id"], "load session", 200)
        receipt = {"schema": RECEIPT_SCHEMA, "observation": observed, "payload": payload,
                   "authentication_scope": "configured_host_callback", **FLAGS}
        raw = _bounded(receipt, MAX_RECEIPT_BYTES, "weight invocation receipt")
        if self._authenticate(deepcopy(receipt), digest(raw)) is not True:
            raise PermissionError("weight invocation evidence not authenticated by configured host")
        # A callback may revoke/change evidence while it runs. Check canonical
        # bytes again, and never persist modifications made to its detached input.
        self._revalidate_request(request)
        return receipt

    def validate_receipt(self, value: Mapping[str, Any], *, payload: Mapping[str, Any],
                         request: Mapping[str, Any]) -> dict[str, Any]:
        body = _object(value, {"schema", "observation", "payload", "authentication_scope", *FLAGS}, "weight receipt")
        _bounded(body, MAX_RECEIPT_BYTES, "weight invocation receipt")
        if (body["schema"] != RECEIPT_SCHEMA or body["authentication_scope"] != "configured_host_callback"
                or any(body[name] is not False for name in FLAGS)
                or canonical(body["payload"]) != canonical(payload)):
            raise ValueError("persisted weight receipt differs from the stage payload or authority boundary")
        admitted = self.admit(payload=payload, observation=body["observation"], request=request)
        if canonical(admitted) != canonical(body):
            raise ValueError("persisted weight receipt is not the exact admitted observation")
        return admitted


__all__ = ["WeightBinding", "provider_identity"]
