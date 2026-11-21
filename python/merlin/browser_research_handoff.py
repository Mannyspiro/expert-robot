"""Fixed retained-source intake over Merlin's existing canonical research APIs.

The host supplies pinned imports, an authorized registry and a live authorization
callback. This library is not an authorization boundary or a browser/model runner.
It only writes in the fixed browser research project, and never retries an intent
without a final result. Source integrity and coverage are the only measured claims.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import Observation
from dot_ai_os.bridge import canonical, digest
from dot_ai_os.research_protocol import (
    ContextCheck, FirstPrinciplesFrame, Hypothesis, MeasurementPlan, ProvenanceRef,
    ReasoningStep, RepresentationCheck, _validated_plan, build_research_plan,
    build_research_review, store_research_record,
)

PROJECT = "merlin-browser-research"
REGISTRY_ROOT = "/var/lib/merlin-public-browser/registry"
PROGRAM_ID = "MERLIN-CONTINUOUS-RESEARCH-20261121"
TRACK = "research-runtime-integration"
MAX_JSON = 262144
MAX_EVIDENCE = 12 * 1024 * 1024
MAX_REQUEST = 16384
MAX_FILES = 320
MAX_CAPTURES = 8
SCHEMA = "merlin-browser-research-handoff-request/1"


class HandoffError(ValueError):
    """Invalid retained identity or bounded intake contract."""


def require(condition, message):
    if not condition:
        raise HandoffError(message)


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(HandoffError("nonfinite JSON")))


def request_identity(value):
    require(type(value) is dict and set(value) == {
        "schema", "request_id", "episode_id", "publication_ref"}, "exact handoff request fields required")
    require(value["schema"] == SCHEMA and len(canonical(value)) <= MAX_REQUEST, "bounded handoff request required")
    identity = value["request_id"]
    require(isinstance(identity, str) and str(uuid.UUID(identity)) == identity, "canonical request UUID required")
    episode = value["episode_id"]
    require(isinstance(episode, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", episode),
            "safe episode identifier required")
    ref = exact_ref(value["publication_ref"], "browser/episodes/" + episode + "/publication.json")
    return {**value, "publication_ref": ref}


def exact_ref(value, path=None):
    ref = ArtifactRef.from_mapping(value).to_dict()
    require(ref["project_id"] == PROJECT, "cross-project reference rejected")
    require(ref["version"] == 1, "immutable version-one intake reference required")
    if path is not None:
        require(ref["logical_path"] == path, "artifact logical path differs")
    return ref


def timestamp(value):
    require(isinstance(value, str) and len(value) <= 80, "bounded timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "offset-aware timestamp required")
    return value


def source_only(value):
    require(value.get("qualification") is False and value.get("promotion_authority") is False,
            "source intake cannot qualify or promote")
    require(type(value.get("model_calls")) is int and value["model_calls"] == 0,
            "retained browser record must declare zero model calls")


def _plan(identity, binding, program_ref):
    """Persisted before reading capture bodies; acquisition already predates this plan."""
    plan_id = "browser-intake-" + identity["request_id"]
    sources = (
        ProvenanceRef("retained-publication", canonical(identity["publication_ref"]).decode(),
                      identity["publication_ref"]["sha256"], "local_artifact", "reported"),
        ProvenanceRef("research-program", canonical(program_ref).decode(), program_ref["sha256"],
                      "local_artifact", "reported"),
    )
    frame = FirstPrinciplesFrame(
        "Can the declared retained browser evidence support an auditable source-intake checkpoint?",
        "Record exact retained-byte integrity and capture coverage for subsequent typed research planning.",
        "One saved browser episode in merlin-browser-research; no website truth, domain experiment or model improvement.",
        "An exact ArtifactRef resolves one project, logical path, version and SHA-256; complete bindings are necessary for later review.",
        ("The host independently admits the original browser operation and pins the imported source modules.",
         "The saved publication predates this new plan; this is retrospective source intake, not preregistered acquisition."),
        ("No browser, network, provider or model invocation; external-model spend remains zero.",
         "Retain HTTP/query URLs exactly; never infer truth or authority from a hash."),
        ("Same-project exact artifact identity", "Append-only request and evidence", "No automatic interrupted retry"),
        ("Whether all declared bytes remain readable", "Whether any successful nonempty capture is retained",
         "Scientific content, novelty and external-source correctness remain unassessed"),
        "Resolve declared canonical bytes and count observable coverage; frame a separate domain experiment later.",
        "Existing saved publication without a typed measured intake review.",
        "A missing or changed byte, contradictory binding, or no usable capture prevents the corresponding source-intake claim.",
        sources,
    )
    measures = (
        MeasurementPlan("integrity", "retained_integrity_ratio", "fraction", 1, 0,
                        "Resolve and re-hash every declared saved file plus publication, manifest and browser handoff.",
                        "Exact finite byte comparison; zero arithmetic uncertainty, source truth unassessed.",
                        ("Pinned canonical registry APIs", "No external acquisition"), "Complete one-episode inventory",
                        "Retain measurement.json with every exact ArtifactRef, byte length and coverage count.",
                        "Any unreadable, changed or inconsistent retained input."),
        MeasurementPlan("usable", "has_usable_capture", "boolean", 1, 0,
                        "Count captures whose own action succeeded, document status is 2xx, and rendered UTF-8 text is nonempty.",
                        "Exact local count; usability here makes no semantic truth claim.",
                        ("HTTP/query sources are not excluded", "Failed captures remain in coverage"), "All declared captures",
                        "Retain exact URLs, action/status identities and text/DOM/response/screenshot references.",
                        "No capture meets the stated local conditions."),
    )
    refs = ("retained-publication", "research-program")
    hypotheses = (Hypothesis("retained-intake", "The retained episode has complete byte identity and at least one locally usable capture.",
                             ("Canonical publication is an input identity, not independent attestation.",),
                             frame.falsifier, ("integrity", "usable"), refs),)
    reasoning = (ReasoningStep("deductive", ("Exact bytes and explicit lineage are prerequisites for audit.",),
                              "Check every declared input before recording its reuse as context.",
                              "A complete local intake checkpoint can seed a later domain plan.",
                              "No content truth, independent verification or domain result follows.", refs),)
    checks = (ContextCheck("source_quality", "Artifact integrity may be mistaken for source truth.",
                           "Reusing rendered public text", "possible", "Hashes attest byte identity only.",
                           "Keep domain execution not_run and require a separately framed experiment.", refs),)
    representations = {
        "simplex": RepresentationCheck("not_applicable", "This operation is an exact inventory, not a convex mixture.",
                                       "Every reference must match without weighting.", ("Future domain applicability is unassessed.",)),
        "n_ality": RepresentationCheck("not_applicable", "No geometric/state/channel/temporal model is executed.",
                                       "Retain independent identity fields without conflating dimensions.", ("Future domain dimensions are unassessed.",)),
        "continuum": RepresentationCheck("not_applicable", "Finite byte and capture counts need no continuum approximation.",
                                         "Use exact integer counts and exact hashes.", ("No PDE or continuum claim is evaluated.",)),
        "fuzzy_logic": RepresentationCheck("not_applicable", "Integrity and authority are Boolean boundaries.",
                                          "No membership score can admit mismatched bytes.", ("Semantic source quality is unassessed.",)),
    }
    return build_research_plan(plan_id, frame, hypotheses, measures, reasoning, checks,
        source_commit=binding["source_commit"], subproblems=("Resolve exact retained identities", "Measure capture coverage",
        "Persist typed review and next checkpoint"), alternatives_review="Missing bytes, failed captures, and semantic error remain distinct alternatives.",
        representation_checks=representations)


class BrowserResearchHandoff:
    """Host-owned fixed writer; authorization and import pins come from its coordinator."""

    def __init__(self, registry, *, source_commit, program_bytes, authorize):
        require(isinstance(registry, MerlinRegistry), "canonical registry required")
        require(isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit), "exact source commit required")
        require(isinstance(program_bytes, bytes) and len(program_bytes) <= 128000, "bounded exact program bytes required")
        program = decode(program_bytes)
        require(program.get("schema") == "merlin-research-program/1" and program.get("program_id") == PROGRAM_ID
                and type(program.get("version")) is int and program["version"] >= 1
                and any(row.get("id") == TRACK for row in program.get("tracks", []))
                and program.get("qualification") is False and program.get("promotion_authority") is False,
                "fixed continuous research program required")
        require(callable(authorize), "host authorization callback required")
        self.registry, self.program_bytes, self.authorize = registry, program_bytes, authorize
        self.binding = {"source_commit": source_commit, "program_id": PROGRAM_ID, "program_version": program["version"],
                        "program_sha256": digest(program_bytes), "track_id": TRACK,
                        "executor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        # Do not create another project, import cross-project records or initialize private service state.
        registry.artifact_history(PROJECT, "research-handoffs/project-presence-check")

    def _gate(self, operation):
        if self.authorize(operation, dict(self.binding)) is not True:
            raise PermissionError("host authorization is not current")

    @contextmanager
    def _locked(self):
        descriptor = os.open(self.registry.root / "dot-browser-research-handoff.lock",
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "regular single-link handoff lock required")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(descriptor)

    def _read(self, ref, maximum=MAX_JSON):
        return self.registry.read_artifact_ref(exact_ref(ref), max_bytes=maximum)["content"]

    def _get(self, path):
        history = self.registry.artifact_history(PROJECT, path)
        if not history:
            return None
        require(len(history) == 1, "immutable handoff record has multiple versions")
        ref = self.registry.artifact_ref(PROJECT, path, version=1)
        raw = self._read(ref); value = decode(raw)
        require(canonical(value) == raw, "canonical retained record required")
        return value, ref

    def _put(self, path, raw):
        self._gate("write")
        require(isinstance(raw, bytes) and len(raw) <= MAX_JSON, "bounded handoff record required")
        history = self.registry.artifact_history(PROJECT, path)
        if history:
            require(len(history) == 1, "immutable output has multiple versions")
            ref = self.registry.artifact_ref(PROJECT, path, version=1)
            require(self._read(ref) == raw, "immutable output differs")
            return ref
        self.registry.put_artifact(PROJECT, path, raw, "application/json")
        return exact_ref(self.registry.artifact_ref(PROJECT, path))

    def _typed_put(self, record):
        self._gate("write")
        answer = store_research_record(self.registry, PROJECT, record)
        ref = exact_ref(answer["artifact_ref"])
        require(self._read(ref) == canonical(record), "typed record readback differs")
        return ref

    def _measure(self, identity, observed_at):
        """Read the complete declared inventory; do not acquire or interpret its text."""
        base = "browser/episodes/" + identity["episode_id"] + "/"
        input_rows = []

        def read(ref, maximum=MAX_JSON, expected_bytes=None):
            raw = self._read(ref, maximum)
            require(expected_bytes is None or len(raw) == expected_bytes, "declared retained byte length differs")
            input_rows.append({"artifact_ref": ref, "bytes": len(raw)})
            require(len(input_rows) <= MAX_FILES + 3
                    and sum(row["bytes"] for row in input_rows) <= MAX_EVIDENCE + 3 * MAX_JSON,
                    "retained evidence budget exceeded")
            return raw

        publication = decode(read(identity["publication_ref"]))
        require(set(publication) == {"schema", "episode_id", "manifest_sha256", "manifest_ref", "handoff_ref",
                "context_handoff_ref", "artifacts", "sources", "status", "qualification", "promotion_authority", "model_calls"}
                and publication["schema"] == "merlin-browser-publication/1"
                and publication["episode_id"] == identity["episode_id"], "saved publication identity differs")
        source_only(publication)
        manifest_ref = exact_ref(publication["manifest_ref"], base + "episode.json")
        require(publication["manifest_sha256"] == manifest_ref["sha256"], "manifest digest differs")
        manifest = decode(read(manifest_ref, 131072))
        require(manifest.get("schema") == "merlin-public-browser-episode/1"
                and manifest.get("episode_id") == identity["episode_id"]
                and manifest.get("status") == publication["status"]
                and manifest["status"] in ("completed", "completed_with_failures", "failed"), "saved episode binding differs")
        source_only(manifest)
        require(type(manifest.get("external_model_cost_usd")) is int and manifest["external_model_cost_usd"] == 0,
                "retained episode model cost differs")
        timestamp(manifest["started_at"]); timestamp(manifest["completed_at"])
        handoff_ref = exact_ref(publication["handoff_ref"], base + "handoff.json")
        handoff = decode(read(handoff_ref))
        require(handoff.get("schema") == "merlin-browser-handoff/1" and handoff.get("episode_id") == identity["episode_id"]
                and handoff.get("manifest_ref") == manifest_ref and handoff.get("manifest_sha256") == manifest_ref["sha256"]
                and handoff.get("sources") == publication["sources"] and handoff.get("status") == publication["status"],
                "saved browser handoff differs")
        source_only(handoff)
        require(isinstance(manifest.get("files"), list) and len(manifest["files"]) <= MAX_FILES
                and type(publication["artifacts"]) is dict, "bounded saved inventory required")
        inventory = {}; contents = {}
        for row in manifest["files"]:
            require(type(row) is dict and set(row) == {"path", "bytes", "sha256", "media_type"}, "saved file fields differ")
            path = row["path"]
            require(isinstance(path, str) and len(path) <= 200 and path not in inventory
                    and re.fullmatch(r"(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+", path)
                    and not ({".", ".."} & set(PurePosixPath(path).parts)) and path != "episode.json", "saved inventory path differs")
            require(type(row["bytes"]) is int and 0 <= row["bytes"] <= MAX_EVIDENCE, "bounded saved file length required")
            ref = exact_ref(publication["artifacts"].get(path), base + path)
            require(ref["sha256"] == row["sha256"], "publication file digest differs")
            contents[path] = read(ref, MAX_EVIDENCE, row["bytes"]); inventory[path] = row
        require(set(publication["artifacts"]) == set(inventory), "saved inventory coverage differs")
        require(sum(row["bytes"] for row in inventory.values()) + len(self._read(manifest_ref, 131072)) <= MAX_EVIDENCE,
                "episode evidence ceiling exceeded")
        require(isinstance(manifest.get("observations"), list) and isinstance(publication["sources"], list)
                and len(manifest["observations"]) == len(publication["sources"]) <= MAX_CAPTURES,
                "capture coverage differs")
        require(isinstance(manifest.get("actions"), list) and len(manifest["actions"]) <= MAX_CAPTURES, "bounded saved actions required")
        for number, action in enumerate(manifest["actions"], 1):
            require(type(action) is dict and action.get("id") == "a%04d" % number
                    and action.get("status") in ("succeeded", "failed"), "saved action identity/status differs")
        actions = {row["id"]: row for row in manifest["actions"]}
        require(len(actions) == len(manifest["actions"]), "duplicate action identity")
        sources = {row["observation_id"]: row for row in publication["sources"]}
        require(len(sources) == len(publication["sources"]), "duplicate capture identity")
        captures = []; seen_actions = set()
        for number, index in enumerate(manifest["observations"], 1):
            require(type(index) is dict and set(index) == {"id", "action_id", "event_ref"}
                    and index["id"] == "o%04d" % number, "capture index differs")
            source = sources.get(index["id"]); require(type(source) is dict, "capture publication missing")
            event_descriptor = index["event_ref"]
            require(inventory.get(event_descriptor.get("path")) == event_descriptor, "capture event inventory differs")
            event_ref = exact_ref(source["capture_event_ref"], base + event_descriptor["path"])
            require(event_ref == publication["artifacts"][event_descriptor["path"]], "capture event reference differs")
            envelope = decode(contents[event_descriptor["path"]]); event = envelope["event"]
            require(event.get("kind") == "observation", "capture event kind differs")
            observation = event["observation"]
            action = actions.get(index["action_id"])
            require(observation["id"] == index["id"] and observation["action_id"] == index["action_id"]
                    and type(action) is dict and action["id"] not in seen_actions
                    and action["status"] in ("succeeded", "failed")
                    and (action["status"] != "succeeded" or action["observation_id"] == observation["id"]),
                    "capture action lineage differs")
            seen_actions.add(action["id"])
            url = source["acquisition_url"]
            require(isinstance(url, str) and 1 <= len(url) <= 8192 and url == observation["url"] == observation["document_url"],
                    "exact acquisition URL differs")
            require(source["qualification"] is False and observation["qualification"] is False
                    and observation["epistemic"] == "source_snapshot", "capture evidence class differs")
            refs = source["artifacts"]
            require(type(refs) is dict and set(refs) == set(observation["artifacts"]) == {"text", "dom", "screenshot", "response_body"},
                    "capture artifact coverage differs")
            for kind, descriptor in observation["artifacts"].items():
                require(inventory.get(descriptor.get("path")) == descriptor, "capture file inventory differs")
                require(exact_ref(refs[kind], base + descriptor["path"]) == publication["artifacts"][descriptor["path"]],
                        "capture file reference differs")
            text = contents[observation["artifacts"]["text"]["path"]].decode("utf-8")
            require(type(observation["document_status"]) is int and 100 <= observation["document_status"] <= 599,
                    "document status differs")
            usable = action["status"] == "succeeded" and 200 <= observation["document_status"] < 300 and bool(text.strip())
            captures.append({"observation_id": observation["id"], "action_id": action["id"], "action_status": action["status"],
                             "acquisition_url": url, "document_status": observation["document_status"],
                             "captured_at": timestamp(observation["captured_at"]), "context_intake": source["context_intake"],
                             "capture_event_ref": event_ref, "artifacts": refs, "usable_for_source_intake": usable,
                             "text_bytes": len(text.encode("utf-8")), "semantic_quality": "not_assessed"})
        require({row["id"] for row in manifest["observations"]} == set(sources), "unindexed published capture")
        require(all(row["status"] != "succeeded" or row["id"] in seen_actions for row in actions.values()),
                "successful action has no indexed capture")
        return {"schema": "merlin-browser-retained-source-measurement/1", "episode_id": identity["episode_id"],
                "observed_at": observed_at, "method": "Exact canonical ArtifactRef readback and complete declared-inventory/capture binding checks",
                "input_artifacts": input_rows, "captures": captures,
                "counts": {"verified_input_artifacts": len(input_rows), "verified_input_bytes": sum(row["bytes"] for row in input_rows),
                           "captures": len(captures), "usable_captures": sum(row["usable_for_source_intake"] for row in captures),
                           "failed_actions": sum(row["status"] == "failed" for row in actions.values()),
                           "reported_bridge_source_snapshots": sum(row["context_intake"] == "source_snapshot" for row in captures)},
                "measurements": {"retained_integrity_ratio": 1, "has_usable_capture": int(any(row["usable_for_source_intake"] for row in captures))},
                "original_acquisition_predates_plan": True, "original_browser_status": publication["status"],
                "source_truth": "not_assessed", "native_execution_attestation": "host_coordinator_responsibility",
                "optional_bridge_records": "reported_intake_only_not_resolved_by_this_measurement",
                "domain_execution": "not_run", "new_browser_calls": 0, "model_calls": 0, "external_model_cost_usd": 0,
                "qualification": False, "promotion_authority": False}

    def _review(self, plan, measurement, measurement_ref):
        observation = Observation("retained-source-integrity", plan["frame"]["question"], measurement["method"],
            measurement["measurements"], {"retained_integrity_ratio": "fraction", "has_usable_capture": "boolean"},
            {"retained_integrity_ratio": 0, "has_usable_capture": 0},
            {"scope": "retained canonical bytes only", "acquisition_order": "original capture predates this intake plan",
             "semantic_quality": "not_assessed", "domain_execution": "not_run"},
            ("retained-publication", "research-program", "retained-source-measurement"), measurement["observed_at"], measurement_ref["sha256"])
        check = ContextCheck("source_quality", "Correct byte identity does not validate scientific content.", "Saved public browser capture",
                             "possible", "No scientific experiment or independent content validation ran.",
                             "Create a separate falsifiable domain plan using these exact source refs.", ("retained-source-measurement",))
        return build_research_review(plan, (observation,), reviewer_id="fixed-source-intake-review",
            contextual_checks=(check,), next_actions=("Review the exact retained sources as untrusted context.",
            "Select a ready research track and persist a separate domain frame before any admitted experiment.",
            "Preserve the missing Parallax specification and proposed broader Xenomaths/XMG engines as unresolved."),
            limitations=("This is deterministic source-integrity/coverage review, not independent scientific verification.",
            "No model was invoked or trained, no domain experiment ran, and no improved research capability is claimed.",
            "HTTP/query URLs are preserved; bridge eligibility does not decide source-intake usability.",
            "Native browser admission and module-source authentication belong to the fixed host coordinator."))

    def _validate_intent(self, value, request_id):
        require(type(value) is dict and set(value) == {"schema", "request", "binding", "observed_at",
                "effect_policy", "qualification", "promotion_authority"}
                and value["schema"] == "merlin-browser-research-handoff-intent/1"
                and value["effect_policy"] == "no_automatic_retry_after_intent"
                and value["qualification"] is False and value["promotion_authority"] is False,
                "retained intent contract differs")
        request = request_identity(value["request"])
        require(request["request_id"] == request_id, "retained intent request/path identity differs")
        require(value["binding"] == self.binding, "retained host/source binding differs")
        timestamp(value["observed_at"])

    def _result(self, intent_ref, program_ref, plan_ref, measurement_ref, review_ref, measurement):
        return {"schema": "merlin-browser-research-handoff-result/1", "intent_ref": intent_ref,
                "binding": self.binding, "program_ref": program_ref, "plan_ref": plan_ref,
                "measurement_ref": measurement_ref, "review_ref": review_ref,
                "decision": "source_intake_available" if measurement["measurements"]["has_usable_capture"] else "no_usable_capture",
                "claim_scope": "retained_source_integrity_and_coverage_only", "domain_execution": "not_run",
                "independent_verification": "not_established", "new_browser_calls": 0, "model_calls": 0,
                "external_model_cost_usd": 0, "qualification": False, "promotion_authority": False}

    def _completed(self, base, intent, result):
        value, result_ref = result
        require(value.get("schema") == "merlin-browser-research-handoff-result/1" and value.get("intent_ref") == intent[1]
                and value.get("binding") == self.binding, "completed receipt binding differs")
        source_only(value)
        expected = {"program_ref": base + "program.json", "measurement_ref": base + "measurement.json",
                    "plan_ref": "research/browser-intake-" + intent[0]["request"]["request_id"] + "/plan.json"}
        for key, path in expected.items():
            exact_ref(value[key], path)
        require(value["program_ref"]["sha256"] == self.binding["program_sha256"], "retained program pin differs")
        require(self._read(value["program_ref"]) == self.program_bytes, "retained program bytes differ")
        plan = decode(self._read(value["plan_ref"])); _validated_plan(plan)
        require(canonical(plan) == canonical(_plan(intent[0]["request"], self.binding, value["program_ref"])),
                "retained fixed plan differs")
        measurement = decode(self._read(value["measurement_ref"]))
        require(measurement.get("observed_at") == intent[0]["observed_at"], "retained observation time differs")
        for row in measurement["input_artifacts"]:
            raw = self._read(row["artifact_ref"], MAX_EVIDENCE)
            require(len(raw) == row["bytes"], "retained measurement source length differs")
        review = self._review(plan, measurement, value["measurement_ref"])
        exact_ref(value["review_ref"], "research/" + plan["plan_id"] + "/reviews/" + review["record_sha256"] + ".json")
        require(self._read(value["review_ref"]) == canonical(review), "retained typed review differs")
        require(canonical(value) == canonical(self._result(intent[1], value["program_ref"], value["plan_ref"],
                value["measurement_ref"], value["review_ref"], measurement)), "retained result contract or decision differs")
        return {"status": "recorded", "result_ref": result_ref, "result": value, "replayed": True, "execution_retried": False}

    def status(self, request_id):
        self._gate("read")
        require(isinstance(request_id, str) and str(uuid.UUID(request_id)) == request_id, "canonical request UUID required")
        base = "research-handoffs/" + request_id + "/"
        intent, result = self._get(base + "intent.json"), self._get(base + "result.json")
        require(intent is not None or result is None, "orphan handoff result")
        if intent is None:
            partial = any(self.registry.artifact_history(PROJECT, path) for path in (
                base + "program.json", base + "measurement.json", base + "failure.json",
                "research/browser-intake-" + request_id + "/plan.json"))
            if partial:
                return {"status": "reconciliation_needed", "intent_ref": None,
                        "reason": "orphan retained partial records", "execution_retried": False,
                        "new_browser_calls": 0, "model_calls": 0}
            return {"status": "not_found", "execution_retried": False}
        self._validate_intent(intent[0], request_id)
        if result:
            return self._completed(base, intent, result)
        failure = self._get(base + "failure.json")
        return {"status": "reconciliation_needed", "intent_ref": intent[1], "intent": intent[0],
                "failure_ref": failure[1] if failure else None, "failure": failure[0] if failure else None,
                "execution_retried": False, "new_browser_calls": 0, "model_calls": 0}

    def submit(self, request):
        self._gate("write")
        identity = request_identity(request)
        base = "research-handoffs/" + identity["request_id"] + "/"
        with self._locked():
            prior = self._get(base + "intent.json")
            if prior:
                self._validate_intent(prior[0], identity["request_id"])
                require(prior[0].get("request") == identity and prior[0].get("binding") == self.binding,
                        "request identity reused with different inputs or host binding")
                return self.status(identity["request_id"])
            require(self._get(base + "result.json") is None and self._get(base + "failure.json") is None,
                    "orphan handoff outputs")
            require(not any(self.registry.artifact_history(PROJECT, path) for path in (
                base + "program.json", base + "measurement.json",
                "research/browser-intake-" + identity["request_id"] + "/plan.json")), "orphan handoff partial records")
            intent = {"schema": "merlin-browser-research-handoff-intent/1", "request": identity, "binding": self.binding,
                      "observed_at": datetime.now(timezone.utc).isoformat(),
                      "effect_policy": "no_automatic_retry_after_intent", "qualification": False, "promotion_authority": False}
            intent_ref = self._put(base + "intent.json", canonical(intent))
            stage = "program"
            try:
                program_ref = self._put(base + "program.json", self.program_bytes)
                stage = "plan"
                plan = _plan(identity, self.binding, program_ref)
                plan_ref = self._typed_put(plan)
                stage = "measurement"
                self._gate("read")
                measurement = self._measure(identity, intent["observed_at"])
                measurement_ref = self._put(base + "measurement.json", canonical(measurement))
                # Resolve in this exact project before the protocol's global raw-blob check.
                require(self._read(measurement_ref) == canonical(measurement), "measurement readback differs")
                stage = "review"
                review_ref = self._typed_put(self._review(plan, measurement, measurement_ref))
                stage = "result"
                result = self._result(intent_ref, program_ref, plan_ref, measurement_ref, review_ref, measurement)
                result_ref = self._put(base + "result.json", canonical(result))
                return {"status": "recorded", "result_ref": result_ref, "result": result,
                        "replayed": False, "execution_retried": False}
            except Exception as error:
                failure = {"schema": "merlin-browser-research-handoff-failure/1", "intent_ref": intent_ref,
                           "stage": stage, "error_type": type(error).__name__,
                           "reason": str(error)[:500] if isinstance(error, HandoffError) else "retained operation failed",
                           "status": "reconciliation_needed", "new_browser_calls": 0, "model_calls": 0,
                           "domain_execution": "not_run", "qualification": False, "promotion_authority": False}
                self._put(base + "failure.json", canonical(failure))
                return self.status(identity["request_id"])
