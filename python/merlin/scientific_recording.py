"""Canonical scientific records and an opt-in Hermes recording handler.

This is a typed persistence/gating adapter over MerlinRegistry and the existing
HermesStageJournal, not a second registry or an experiment executor. A record is
unverified reported data. Plan revisions are proposals, including explicit forks.
No caller-controlled status can grant CACE verification or execution authority.
"""
from __future__ import annotations

from dataclasses import asdict
from copy import deepcopy
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping

from .artifact_ref import ArtifactRef
from .hermes_stage_journal import HermesStageJournal, StageJournalConflict
from .project_registry import MerlinRegistry
from .scientific_loop import Observation, Prediction, compare_observation, update_plan_from_observations

SCHEMA = "merlin-scientific-record/1"
STAGE = "scientific_recording"
PREFIX = "scientific-loop/records/"
MEDIA_TYPE = "application/vnd.merlin.scientific-record+json"
MAX_RECORD_BYTES = 262144
MAX_SOURCE_BYTES = 1048576
MAX_REFS = 16
MAX_LINEAGE_RECORDS = 128
OPERATIONS = frozenset({"observation", "plan", "prediction_set", "outcome", "plan_revision"})
_FIELDS = {"schema", "operation", "scope", "source_repository", "source_commit", "data",
           "input_refs", "payload", "verification_status", "qualification", "promotion_authority"}


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _text(value: Any, label: str, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(label + " must be non-empty bounded text")
    return value


def _texts(value: Any, label: str, minimum: int = 1) -> list[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= 32:
        raise ValueError(label + " must be a bounded non-empty list")
    return [_text(item, label) for item in value]


def _fields(value: Any, names: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("record data must contain exactly: " + ", ".join(sorted(names)))
    return value


def _observation(value: Any, refs: list[dict[str, Any]]) -> Observation:
    _fields(value, {"observation_id", "question", "method", "measurements", "units",
                    "uncertainty", "conditions", "source_refs", "observed_at", "artifact_sha256"})
    for name in ("measurements", "units", "uncertainty", "conditions"):
        if not isinstance(value[name], dict) or not 1 <= len(value[name]) <= 32:
            raise ValueError(name + " must be a non-empty bounded mapping")
    if set(value["measurements"]) != set(value["units"]) or set(value["measurements"]) != set(value["uncertainty"]):
        raise ValueError("measurement, unit and uncertainty keys must match")
    for key, item in value["conditions"].items():
        _text(key, "condition key"); _text(item, "condition value")
    labels = ["sha256:" + ref["sha256"] for ref in refs]
    if value["source_refs"] != list(dict.fromkeys(labels)) or value["artifact_sha256"] not in {ref["sha256"] for ref in refs}:
        raise ValueError("observation must bind its exact input artifact digests")
    observation = Observation(**{**value, "source_refs": tuple(value["source_refs"])})
    observation.validate()
    for metric, measured in observation.measurements.items():
        sigma = observation.uncertainty[metric]
        if not math.isfinite(measured - sigma) or not math.isfinite(measured + sigma):
            raise ValueError("observation interval overflow")
    return observation


def _predictions(values: Any) -> list[Prediction]:
    if not isinstance(values, list) or not 1 <= len(values) <= 32:
        raise ValueError("predictions must be non-empty and bounded")
    predictions = []
    for value in values:
        _fields(value, {"metric", "expected", "tolerance", "unit"})
        prediction = Prediction(**value)
        prediction.validate()
        predictions.append(prediction)
    if len({p.metric for p in predictions}) != len(predictions):
        raise ValueError("prediction metrics must be unique")
    return predictions


class ScientificRecordingStore:
    """Reuse canonical artifacts; never overwrite a plan or select an implicit latest."""

    def __init__(self, registry: MerlinRegistry, *, project_id: str, hypothesis_id: str,
                 episode_id: str, repository: str, commit_sha: str, max_input_bytes: int = 16 * 1048576):
        if not isinstance(registry, MerlinRegistry):
            raise ValueError("the canonical MerlinRegistry is required")
        if isinstance(max_input_bytes, bool) or not isinstance(max_input_bytes, int) or not 1 <= max_input_bytes <= 16 * 1048576:
            raise ValueError("scientific aggregate input limit is invalid")
        self.max_input_bytes = max_input_bytes
        self.registry = registry
        self.scope = {key: _text(value, key, 200) for key, value in (
            ("project_id", project_id), ("hypothesis_id", hypothesis_id), ("episode_id", episode_id))}
        if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("repository must be owner/name")
        if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            raise ValueError("an exact source commit is required")
        self.repository, self.commit_sha = repository, commit_sha

    def _refs(self, values: Any) -> list[dict[str, Any]]:
        if not isinstance(values, list) or not 1 <= len(values) <= MAX_REFS:
            raise ValueError("one to sixteen exact input ArtifactRefs are required")
        refs = [ArtifactRef.from_mapping(value).to_dict() for value in values]
        if any(ref["project_id"] != self.scope["project_id"] for ref in refs):
            raise ValueError("cross-project scientific inputs are not admitted")
        if len({_json(ref) for ref in refs}) != len(refs):
            raise ValueError("duplicate input ArtifactRefs")
        return refs

    @staticmethod
    def _provenance(record: Mapping[str, Any], digest: str) -> dict[str, Any]:
        return {"schema": "merlin-artifact-provenance/1", "source_repo": record["source_repository"],
                "source_commit": record["source_commit"], "artifact_id": digest,
                "artifact_kind": "scientific-record", "artifact_schema": SCHEMA}

    def _load(self, ref: dict[str, Any], cache: dict[bytes, Any], remaining: list[int], depth: int = 0) -> dict[str, Any] | None:
        key = _json(ref)
        if key in cache:
            if cache[key] is False:
                raise ValueError("cyclic scientific lineage")
            return cache[key]
        if depth > 48 or len(cache) >= MAX_LINEAGE_RECORDS:
            raise ValueError("scientific lineage inspection budget exceeded")
        cache[key] = False
        # Cheap admission before the registry's current whole-blob integrity read.
        # These checks are not protection against hostile concurrent filesystem writes.
        path = self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]
        if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("source is symlinked or exceeds the scientific input ceiling")
        remaining[0] -= path.stat().st_size
        if remaining[0] < 0:
            raise ValueError("scientific aggregate input byte budget exceeded")
        inspected = self.registry.read_artifact_ref(ref, max_bytes=MAX_SOURCE_BYTES)
        content, resolution = inspected["content"], inspected["resolution"]
        if not ref["logical_path"].startswith(PREFIX):
            if resolution["media_type"] == MEDIA_TYPE:
                raise ValueError("scientific record has a noncanonical path")
            cache[key] = None
            return None
        if len(content) > MAX_RECORD_BYTES or ref["version"] != 1 or resolution["media_type"] != MEDIA_TYPE:
            raise ValueError("invalid scientific record envelope")
        record = json.loads(content)
        if not isinstance(record, dict) or set(record) != _FIELDS or record["schema"] != SCHEMA:
            raise ValueError("unsupported scientific record schema")
        if record["operation"] not in OPERATIONS or record["scope"] != self.scope:
            raise ValueError("scientific operation/episode scope mismatch")
        if record["source_repository"] != self.repository or not isinstance(record["source_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", record["source_commit"]):
            raise ValueError("scientific source identity mismatch")
        if record["verification_status"] != "unverified" or record["qualification"] is not False or record["promotion_authority"] is not False:
            raise ValueError("scientific records cannot promote verification or authority")
        digest = hashlib.sha256(content).hexdigest()
        if content != _json(record) or ref["logical_path"] != PREFIX + digest + ".json":
            raise ValueError("scientific record canonical identity mismatch")
        if resolution.get("provenance") != self._provenance(record, digest):
            raise ValueError("scientific record provenance mismatch")
        refs = self._refs(record["input_refs"])
        inputs = [self._load(item, cache, remaining, depth + 1) for item in refs]
        payload = self._derive(record["operation"], record["data"], refs, inputs, cache)
        if _json(payload) != _json(record["payload"]):
            raise ValueError("scientific record derived payload mismatch")
        cache[key] = record
        return record

    def read(self, value: Mapping[str, Any]) -> dict[str, Any]:
        ref = self._refs([value])[0]
        record = self._load(ref, {}, [self.max_input_bytes])
        if record is None:
            raise ValueError("expected a canonical scientific record")
        return record

    def prepare(self, operation: str, data: Mapping[str, Any], input_refs: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ValueError("unsupported scientific operation")
        encoded = _json(data)
        if len(encoded) > MAX_RECORD_BYTES:
            raise ValueError("scientific command exceeds its byte budget")
        data = json.loads(encoded)  # Snapshot caller-owned mutable inputs.
        refs = self._refs(input_refs)
        cache: dict[bytes, Any] = {}
        remaining = [self.max_input_bytes]
        inputs = [self._load(ref, cache, remaining) for ref in refs]
        record = {"schema": SCHEMA, "operation": operation, "scope": dict(self.scope),
                  "source_repository": self.repository, "source_commit": self.commit_sha,
                  "data": data, "input_refs": refs, "payload": self._derive(operation, data, refs, inputs, cache),
                  "verification_status": "unverified", "qualification": False, "promotion_authority": False}
        if len(_json(record)) > MAX_RECORD_BYTES:
            raise ValueError("scientific record exceeds its byte budget")
        return record

    def _derive(self, operation: str, data: Any, refs: list[dict[str, Any]], inputs: list[Any], cache: dict[bytes, Any]) -> dict[str, Any]:
        def require(index: int, kinds: set[str]) -> dict[str, Any]:
            if index >= len(inputs) or inputs[index] is None or inputs[index]["operation"] not in kinds:
                raise ValueError("required predecessor scientific record is missing or wrong-kind")
            return inputs[index]["payload"]

        if operation == "observation":
            if any(item is not None for item in inputs):
                raise ValueError("observation inputs must be raw source artifacts")
            return asdict(_observation(data, refs))
        if operation == "plan":
            _fields(data, {"plan_id", "objective", "assumptions", "alternatives", "acceptance_criteria", "falsifiers", "next_actions"})
            for name in ("plan_id", "objective"):
                _text(data[name], name)
            for name in ("assumptions", "acceptance_criteria", "falsifiers", "next_actions"):
                _texts(data[name], name)
            _texts(data["alternatives"], "alternatives", minimum=2)
            for index in range(len(refs)):
                require(index, {"observation"})
            return {**data, "version": 1, "parent_plan_ref": None, "observation_refs": refs,
                    "requires_review": True, "authority_effect": "none"}
        if operation == "prediction_set":
            _fields(data, {"experiment_id", "predictions", "falsifiers"})
            _text(data["experiment_id"], "experiment_id", 200)
            if len(refs) != 1:
                raise ValueError("a prediction set requires exactly one parent plan")
            require(0, {"plan", "plan_revision"})
            predictions = _predictions(data["predictions"])
            if not isinstance(data["falsifiers"], dict) or set(data["falsifiers"]) != {p.metric for p in predictions}:
                raise ValueError("every prediction requires an explicit falsifier")
            for value in data["falsifiers"].values():
                _text(value, "falsifier")
            return {**data, "plan_ref": refs[0], "registration_scope": "recorded_before_this_outcome_only"}
        if operation == "outcome":
            _fields(data, {"run_id", "status", "reason", "observation_count"})
            _text(data["run_id"], "run_id", 200)
            if not isinstance(data["status"], str) or data["status"] not in {"completed", "failed", "inconclusive", "not_run"}:
                raise ValueError("invalid experiment outcome status")
            _text(data["reason"], "outcome reason")
            count = data["observation_count"]
            if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 8 or len(refs) < count + 2:
                raise ValueError("outcome requires a prediction set, observations and at least one raw log")
            predicted = require(0, {"prediction_set"})
            if data["status"] in {"completed", "inconclusive"} and count == 0:
                raise ValueError("completed/inconclusive outcomes require measurements")
            if data["status"] == "not_run" and count:
                raise ValueError("not_run cannot claim experiment measurements")
            if any(item is not None for item in inputs[1 + count:]):
                raise ValueError("outcome logs must be raw artifacts")
            assessments = []
            for index in range(1, count + 1):
                measured = require(index, {"observation"})
                observation = Observation(**{**measured, "source_refs": tuple(measured["source_refs"])})
                assessments.append(compare_observation(observation, _predictions(predicted["predictions"])))
            return {**data, "plan_ref": predicted["plan_ref"], "prediction_ref": refs[0],
                    "observation_refs": refs[1:1 + count], "execution_log_refs": refs[1 + count:],
                    "assessments": assessments, "independent_verification": "not_established"}
        _fields(data, {"changes", "next_actions"})
        _texts(data["changes"], "changes"); _texts(data["next_actions"], "next_actions")
        parent = require(0, {"plan", "plan_revision"})
        if len(refs) < 2:
            raise ValueError("a plan revision requires outcome evidence")
        observations, observation_refs = [], []
        for index in range(1, len(refs)):
            outcome = require(index, {"outcome"})
            if outcome["plan_ref"] != refs[0]:
                raise ValueError("outcome evidence belongs to a different parent plan")
            for ref in outcome["observation_refs"]:
                if ref not in observation_refs:
                    observation_refs.append(ref)
                    measured = cache[_json(ref)]["payload"]
                    observations.append(Observation(**{**measured, "source_refs": tuple(measured["source_refs"])}))
        if not observations:
            raise ValueError("a measured observation is required before proposing a plan revision")
        update = update_plan_from_observations(parent, observations, next_actions=data["next_actions"])
        result = {key: parent[key] for key in ("plan_id", "objective", "assumptions", "alternatives", "acceptance_criteria", "falsifiers")}
        return {**result, "version": parent["version"] + 1, "parent_plan_ref": refs[0],
                "observation_refs": observation_refs, "outcome_refs": refs[1:],
                "changes": data["changes"], "next_actions": data["next_actions"], "update": update,
                "requires_review": True, "authority_effect": "none"}

    def persist(self, record: Mapping[str, Any]) -> dict[str, Any]:
        # Re-derive at the write boundary; a prepared checkpoint is not trusted evidence.
        expected = self.prepare(record["operation"], record["data"], record["input_refs"])
        if _json(record) != _json(expected):
            raise ValueError("prepared scientific record changed or has the wrong source/scope")
        content = _json(expected)
        digest = hashlib.sha256(content).hexdigest()
        path = PREFIX + digest + ".json"
        # Reuse the existing journal to reserve semantic identities across task IDs.
        # New roots/experiments/observations/runs cannot silently replace old content.
        identity_fields = {"observation": "observation_id", "plan": "plan_id",
                           "prediction_set": "experiment_id", "outcome": "run_id"}
        identity_journal = None
        identity_key = None
        if expected["operation"] in identity_fields:
            identity = {"scope": self.scope, "operation": expected["operation"],
                        "id": expected["payload"][identity_fields[expected["operation"]]]}
            identity_digest = hashlib.sha256(_json(identity)).hexdigest()
            identity_key = "scientific-identity:" + identity_digest
            identity_journal = HermesStageJournal(self.registry.root / "hermes-stage-journal.sqlite3")
            reserved = identity_journal.begin(idempotency_key=identity_key,
                stage="scientific_record_identity", task_id=identity_digest,
                hypothesis_id=self.scope["hypothesis_id"], request=expected)
            if reserved["candidate_set"] is not None and _json(reserved["candidate_set"]) != _json(expected):
                raise StageJournalConflict("scientific identity checkpoint changed")
            if reserved["state"] == "completed" and reserved["candidate_set"] is None:
                raise StageJournalConflict("scientific identity lost its checkpoint")
            if reserved["candidate_set"] is None:
                identity_journal.save_generated(identity_key, expected)
        self.registry.put_artifact(self.scope["project_id"], path, content, MEDIA_TYPE,
                                   provenance=self._provenance(expected, digest))
        ref = self.registry.artifact_ref(self.scope["project_id"], path, version=1)
        if ref["sha256"] != digest:
            raise ValueError("scientific content-addressed path collision")
        self.read(ref)
        if identity_journal is not None:
            identity_journal.complete(identity_key, {"artifact_ref": ref})
        return ref


def build_scientific_recording_handler(*, registry: MerlinRegistry, project_id: str,
        repository: str, commit_sha: str,
        admission_validator: Callable[[Mapping[str, Any], Any], bool]) -> Callable[..., Mapping[str, Any]]:
    """Inject under handlers['scientific_recording']; no automatic public API enablement.

    The runtime-owned admission callback must validate policy/approval/lease and
    hypothesis existence. HermesWorker admission remains independently required.
    """
    if not isinstance(registry, MerlinRegistry) or not callable(admission_validator):
        raise ValueError("canonical registry and independent admission validator are required")
    journal = HermesStageJournal(registry.root / "hermes-stage-journal.sqlite3")

    def handle(task: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
        if not isinstance(task, Mapping):
            raise ValueError("scientific task must be an object")
        encoded_task = _json(dict(task))
        if len(encoded_task) > 2 * MAX_RECORD_BYTES:
            raise ValueError("scientific task envelope exceeds byte budget")
        task = json.loads(encoded_task)
        if task.get("stage") != STAGE:
            raise ValueError("scientific recording stage mismatch")
        if task.get("task_id") != context.task_id or task.get("hypothesis_id") != context.hypothesis_id:
            raise ValueError("scientific task/context identity mismatch")
        if task.get("promotion_authority") is not False or task.get("authority") != "bounded_execution_only":
            raise PermissionError("scientific recording cannot expand authority")
        for field in ("approval_ref", "lease_ref"):
            _text(task.get(field), field, 256)
            if task[field] != getattr(context, field, None):
                raise ValueError("scientific task/context approval or lease mismatch")
        if task.get("resource_budget") != dict(context.resource_budget) or task.get("artifact_refs") != list(context.artifact_refs):
            raise ValueError("scientific task/context inputs or budget mismatch")
        def require_admission() -> None:
            context.check_cancelled()
            if admission_validator(deepcopy(task), context) is not True:
                raise PermissionError("scientific recording admission was not independently approved")
            context.check_cancelled()

        require_admission()
        budget = task.get("resource_budget")
        if not isinstance(budget, dict) or set(budget) != {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}:
            raise ValueError("canonical scientific resource budget required")
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in budget.values()):
            raise ValueError("scientific budget values must be positive integers")
        spec = _fields(task.get("experiment_spec"), {"episode_id", "operation", "data"})
        store = ScientificRecordingStore(registry, project_id=project_id, hypothesis_id=context.hypothesis_id,
            episode_id=spec["episode_id"], repository=repository, commit_sha=commit_sha,
            max_input_bytes=max(1, min(16 * 1048576, budget["memory_bytes"] // 8)))
        if len(_json(spec)) > min(MAX_RECORD_BYTES, budget["memory_bytes"] // 16):
            raise ValueError("scientific command exceeds admission budget")
        prepared = store.prepare(spec["operation"], spec["data"], task.get("artifact_refs"))
        request = {"task": task, "record": prepared}
        require_admission()
        checkpoint = journal.begin(idempotency_key=context.idempotency_key, stage=STAGE,
            task_id=context.task_id, hypothesis_id=context.hypothesis_id, request=request)
        if checkpoint["candidate_set"] is not None and _json(checkpoint["candidate_set"]) != _json(prepared):
            raise StageJournalConflict("scientific checkpoint changed")
        if checkpoint["state"] == "completed" and checkpoint["candidate_set"] is None:
            raise StageJournalConflict("completed scientific stage lost its checkpoint")
        if checkpoint["state"] != "completed" and checkpoint["candidate_set"] is None:
            journal.save_generated(context.idempotency_key, prepared)
        require_admission()
        ref = store.persist(prepared)
        require_admission()
        result = {"schema": "merlin-hermes-scientific-recording-result/1", "stage": STAGE,
                  "operation": spec["operation"], "artifact_refs": [ref], "evidence_refs": [],
                  "verification_status": "unverified", "qualification": False,
                  "authority": "scientific_recording_only", "promotion_authority": False}
        if checkpoint["state"] == "completed":
            if checkpoint["result"] != result:
                raise StageJournalConflict("scientific completed result changed")
            return result
        require_admission()
        return journal.complete(context.idempotency_key, result)

    return handle


def register_scientific_recording(
    handlers: Mapping[str, Callable[..., Mapping[str, Any]]], *,
    enabled: bool, registry: MerlinRegistry, ledger: Any, project_id: str,
    repository: str, commit_sha: str,
    approval_validator: Callable[[str, Mapping[str, Any]], bool],
    lease_validator: Callable[[str, Mapping[str, int]], bool],
) -> dict[str, Callable[..., Mapping[str, Any]]]:
    """Opt into the existing worker map using the runtime's actual policy hooks.

    This grants no approval or lease. Deployed validators must independently
    authorize the complete task, including episode/operation/input scope. A test
    callback is not a production authorization service. Refuted hypotheses may
    still receive negative observations; recording never changes ledger status.
    """
    from .hypothesis_ledger import HypothesisLedger

    if type(enabled) is not bool or not isinstance(handlers, Mapping):
        raise ValueError("recording enablement must be explicit boolean and handlers a mapping")
    registered = dict(handlers)
    if not enabled:
        return registered
    if STAGE in registered:
        raise ValueError("scientific recording handler is already registered")
    if not isinstance(registry, MerlinRegistry) or not isinstance(ledger, HypothesisLedger):
        raise ValueError("canonical registry and hypothesis ledger are required")
    if not callable(approval_validator) or not callable(lease_validator):
        raise ValueError("independent approval and MCFC lease validators are required")
    registry.inventory(project_id)  # Require an existing canonical project.

    def admit(task: Mapping[str, Any], context: Any) -> bool:
        context.check_cancelled()
        if task.get("stage") != STAGE or task.get("hypothesis_id") != context.hypothesis_id:
            return False
        try:
            hypothesis = ledger.get(context.hypothesis_id)
        except KeyError:
            return False
        if hypothesis.hypothesis_id != context.hypothesis_id:
            return False
        refs = task.get("artifact_refs")
        if not isinstance(refs, list) or not refs:
            return False
        if any(ArtifactRef.from_mapping(ref).project_id != project_id for ref in refs):
            return False
        if approval_validator(task["approval_ref"], deepcopy(task)) is not True:
            return False
        if lease_validator(task["lease_ref"], dict(task["resource_budget"])) is not True:
            return False
        context.check_cancelled()
        return True

    registered[STAGE] = build_scientific_recording_handler(
        registry=registry, project_id=project_id, repository=repository,
        commit_sha=commit_sha, admission_validator=admit,
    )
    return registered
