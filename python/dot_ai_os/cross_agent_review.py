"""Host-side review of agent changes using dot's durable two-coder workflow.

A trusted host supplies identities, case labels, and any adapters. Exact-match
scores describe those captured outputs on this corpus. The reviewer only stores
research artifacts; it never executes proposed code or changes an agent.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry

from .bridge import canonical, digest, text_value
from .dual_coder import DualCoderWorkflow, Provider

DEFAULT_ROSTER = ("merlin", "dot", "coder_a", "coder_b", "evaluator", "rsi_reviewer")
ARMS = ("baseline", "coder_a", "coder_b")
METRIC = "Gain at least one exact held-out match with no newly failed case on either split."


def _labels(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not 1 <= len(value) <= 200:
        raise ValueError(f"{field} requires 1 through 200 case labels")
    labels = {}
    for key, label in value.items():
        text_value(key, "case ID", 120)
        labels[key] = text_value(label, "case label", 256)
    return labels


def _measure(protocol, outputs):
    expected = {**protocol["train_labels"], **protocol["holdout_labels"]}
    if not isinstance(outputs, Mapping) or set(outputs) != set(ARMS):
        raise ValueError("capture baseline and both candidate predictions")
    predictions = {}
    matches = {}
    for arm in ARMS:
        if not isinstance(outputs[arm], Mapping) or set(outputs[arm]) != expected.keys():
            raise ValueError("capture every frozen case exactly once per arm")
        predictions[arm] = {key: text_value(outputs[arm][key], "prediction", 256) for key in expected}
        matches[arm] = {key for key in expected if predictions[arm][key] == expected[key]}
    regressed = {arm: sorted(matches["baseline"] - matches[arm]) for arm in ARMS}
    scores = {arm: {"train_passed": len(matches[arm] & protocol["train_labels"].keys()),
                    "holdout_passed": len(matches[arm] & protocol["holdout_labels"].keys()),
                    "regressions": len(regressed[arm])} for arm in ARMS}
    return predictions, scores, regressed


class CrossAgentReviewer:
    """Operate against explicit host-owned target identities in a Merlin registry."""

    def __init__(self, registry: MerlinRegistry, *, roster: Mapping[str, str] | None = None,
                 project_id: str = "dot-ai-os"):
        self.workflow = DualCoderWorkflow(registry, project_id=project_id)
        self.registry = registry
        self.project_id = self.workflow.project_id
        self.roster = dict(roster) if roster is not None else {name: name for name in DEFAULT_ROSTER}
        if not 1 <= len(self.roster) <= 100:
            raise ValueError("require an explicit bounded target roster")
        for name, identity in self.roster.items():
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,59}", name):
                raise ValueError("invalid target role")
            text_value(identity, "target identity", 200)

    def _store(self, target, kind, value):
        raw = canonical(value)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("review artifact exceeds two MiB")
        path = f"cross-agent/{target}/{kind}/{digest(raw)}.json"
        self.registry.put_artifact(self.project_id, path, raw, "application/json")
        ref = self.registry.artifact_ref(self.project_id, path, version=1)
        if ref["sha256"] != digest(raw):
            raise ValueError("immutable review artifact conflict")
        return ref

    def _load(self, value, kind):
        ref = ArtifactRef.from_mapping(value)
        parts = ref.logical_path.split("/")
        if (ref.project_id != self.project_id or ref.version != 1 or len(parts) != 4
                or parts[0] != "cross-agent" or parts[1] not in self.roster
                or parts[2] != kind or parts[3] != f"{ref.sha256}.json"):
            raise ValueError("review reference outside configured target or research scope")
        raw = self.registry.read_artifact_ref(ref.to_dict(), max_bytes=2 * 1024 * 1024)["content"]
        payload = json.loads(raw)
        if payload.get("target") != parts[1] or canonical(payload) != raw:
            raise ValueError("invalid review record binding")
        return payload

    def _manifest(self, *, target, baseline_ref, context_refs, objective, source_commit,
                  providers, train_labels, holdout_labels):
        if not isinstance(target, str) or target not in self.roster:
            raise ValueError("target outside configured roster")
        train = _labels(train_labels, "train")
        holdout = _labels(holdout_labels, "holdout")
        if train.keys() & holdout.keys():
            raise ValueError("training and held-out IDs overlap")
        if not isinstance(context_refs, list):
            raise ValueError("context_refs must be a list of additional exact refs")
        spec = {"objective": objective, "source_commit": source_commit,
                "context_refs": [baseline_ref, *context_refs], "train_ids": sorted(train),
                "holdout_ids": sorted(holdout), "acceptance_criteria": [METRIC], "max_cost_usd": 0}
        # Validate through the same bounded contract used by the two-coder runner.
        for source in spec["context_refs"]:
            path = ArtifactRef.from_mapping(source).logical_path
            if path.startswith("cross-agent/") or (path.startswith("dual-coder/")
                    and not path.endswith(("/stages/coder_a/result.json", "/stages/coder_b/result.json"))):
                raise ValueError("evaluator records are outside coder context scope")
        envelope, _ = self.workflow._spec(spec, providers)
        target_identity = self.roster[target]
        identities = {stage: info["provider_id"].strip().casefold() for stage, info in envelope["providers"].items()}
        if len(set(identities.values())) != len(identities):
            raise ValueError("each coder and evaluator requires a distinct declared identity")
        if identities["evaluator"] == target_identity.strip().casefold():
            raise ValueError("a target requires a separately declared evaluator identity")
        return {"schema": "dot-cross-agent-protocol/1",
            "target": target, "target_identity": target_identity, "workflow": envelope,
            "train_labels": train, "holdout_labels": holdout}

    def prepare(self, *, target, baseline_ref, context_refs, objective, source_commit,
                providers, train_labels, holdout_labels) -> dict[str, Any]:
        """Freeze cases, expected labels, host identities and exact artifact revisions."""
        protocol = self._manifest(target=target, baseline_ref=baseline_ref, context_refs=context_refs,
            objective=objective, source_commit=source_commit, providers=providers,
            train_labels=train_labels, holdout_labels=holdout_labels)
        return self._store(target, "protocols", protocol)

    def _protocol(self, ref):
        value = self._load(ref, "protocols")
        if (value.get("schema") != "dot-cross-agent-protocol/1"
                or value.get("target_identity") != self.roster[value["target"]]):
            raise ValueError("target identity differs from the frozen protocol")
        # Recheck the complete protocol and its historical artifact bindings on resume.
        workflow = value["workflow"]
        spec = workflow["specification"]
        expected = self._manifest(target=value["target"], baseline_ref=spec["context_refs"][0],
            context_refs=spec["context_refs"][1:], objective=spec["objective"],
            source_commit=spec["source_commit"], providers=workflow["providers"],
            train_labels=value["train_labels"], holdout_labels=value["holdout_labels"])
        if value != expected:
            raise ValueError("invalid frozen protocol")
        return value

    def run(self, protocol_ref, *, coder_a: Provider | None = None,
            coder_b: Provider | None = None, observe: Provider | None = None):
        """Resume dot's existing research stages; absent adapters leave the run pending."""
        protocol_ref = deepcopy(protocol_ref)
        protocol = self._protocol(protocol_ref)
        target = protocol["target"]
        workflow = protocol["workflow"]
        spec = workflow["specification"]

        def evaluate(request):
            # The observer receives exact revisions, the two proposals and test IDs.
            # Expected labels remain in the host and never enter provider requests.
            outputs = observe(deepcopy({**request, "target": target, "baseline_ref": spec["context_refs"][0]}))
            predictions, scores, regressed = _measure(protocol, outputs)
            receipt = self._store(target, "observations", {"schema": "dot-cross-agent-observation/1",
                "target": target, "protocol_ref": protocol_ref, "candidate_refs": request["candidate_refs"],
                "predictions": predictions, "scores": scores,
                "regressed_cases": regressed})
            return {**scores, "notes": receipt["sha256"]}

        self.workflow.run(protocol_ref["sha256"], specification=spec, providers=workflow["providers"],
                          coder_a=coder_a, coder_b=coder_b, evaluator=evaluate if observe is not None else None)
        return self.status(protocol_ref)

    def status(self, protocol_ref):
        """Recover the pending stage, or the selected candidate and reproducible observations."""
        protocol = self._protocol(protocol_ref)
        session = self.workflow.status(protocol_ref["sha256"])
        if "spec_ref" in session:
            saved = self.registry.read_artifact_ref(session["spec_ref"], max_bytes=2 * 1024 * 1024)["content"]
            if saved != canonical(protocol["workflow"]):
                raise ValueError("workflow specification differs from the frozen protocol")
        result = {"target": protocol["target"], "protocol_ref": protocol_ref, "workflow": session,
                  "qualification": False, "promotion_authority": False}
        if session["status"] != "completed_research_only":
            return result
        report = json.loads(self.registry.read_artifact_ref(session["report_ref"])["content"])
        evaluation = json.loads(self.registry.read_artifact_ref(report["evaluation_ref"])["content"])["payload"]
        path = f"cross-agent/{protocol['target']}/observations/{evaluation['notes']}.json"
        observation_ref = self.registry.artifact_ref(self.project_id, path, version=1)
        obs = self._load(observation_ref, "observations")
        candidate_refs = {arm: report[f"{arm}_ref"] for arm in ARMS[1:]}
        if (obs.get("schema") != "dot-cross-agent-observation/1" or obs["protocol_ref"] != protocol_ref
                or obs["candidate_refs"] != candidate_refs or obs["scores"] != {a: evaluation[a] for a in ARMS}):
            raise ValueError("completed workflow conflicts with captured observations")
        _, measured, regressed = _measure(protocol, obs["predictions"])
        if measured != obs["scores"] or regressed != obs["regressed_cases"]:
            raise ValueError("stored scores differ from frozen-case replay")
        outcomes = {}
        baseline = obs["scores"]["baseline"]
        for arm in ARMS[1:]:
            scores = obs["scores"][arm]
            if scores["regressions"]:
                outcomes[arm] = "regression"
            elif scores["holdout_passed"] > baseline["holdout_passed"]:
                outcomes[arm] = "heldout_gain"
            elif scores["train_passed"] > baseline["train_passed"]:
                outcomes[arm] = "training_only_gain"
            else:
                outcomes[arm] = "no_case_match_change"
        eligible = [arm for arm in ARMS[1:] if outcomes[arm] == "heldout_gain"]
        eligible.sort(key=lambda arm: (-measured[arm]["holdout_passed"], -measured[arm]["train_passed"], arm))
        expected_choice = eligible[0] if eligible else "retain_parent"
        if report.get("recommendation") != expected_choice:
            raise ValueError("workflow recommendation differs from replay")
        result.update(observation_ref=observation_ref, outcomes=outcomes, scores=obs["scores"],
                      regressed_cases=obs["regressed_cases"],
                      recommendation=report["recommendation"], evidence_scope="host_supplied_outputs_on_frozen_cases")
        return result

    def coverage(self):
        """List registered trials, including roles that have never been reviewed."""
        trials = {name: [] for name in self.roster}
        for item in self.registry.inventory(self.project_id)["artifacts"]:
            path = item["logical_path"]
            parts = path.split("/")
            if len(parts) == 4 and parts[0] == "cross-agent" and parts[1] in trials and parts[2] == "protocols":
                ref = self.registry.artifact_ref(self.project_id, path, version=1)
                self._load(ref, "protocols")
                trials[parts[1]].append(ref)
        return trials
