"""Typed skeptical-scientist records over Merlin's canonical scientific loop.

Python 3.9 standard library only. This adapter enforces structural contracts,
preserves unresolved questions, and records bounded search coverage. It neither
proves factual premises nor executes literature searches, experiments or repairs.
External text remains untrusted source data. No result grants signing, merge,
deployment, paid-compute or capability-promotion authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations, islice
import math
import re
from typing import Any, Mapping

from merlin.artifact_ref import ArtifactRef
from merlin.project_registry import MerlinRegistry
from merlin.scientific_loop import (
    Observation, Prediction, compare_observation, decompose_by_analogy,
    enumerate_useful_combinations, update_plan_from_observations,
)
from .bridge import canonical, digest

MODES = frozenset({"deductive", "inductive", "abductive", "analogical"})
REPRESENTATION_LENSES = frozenset({"simplex", "n_ality", "continuum", "fuzzy_logic"})
MAX_RECORD_BYTES = 128000


def _text(value: Any, label: str, maximum: int = 3000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(label + " requires nonempty bounded text")
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,99}", value) is None:
        raise ValueError("safe bounded identifier required")
    return value


def _texts(values: Any, label: str, *, minimum: int = 1, maximum: int = 30) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or not minimum <= len(values) <= maximum:
        raise ValueError(label + " requires an explicit bounded sequence")
    return tuple(_text(value, label) for value in values)


def _hash(value: Any, length: int = 64) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{%d}" % length, value) is None:
        raise ValueError("full lowercase digest required")
    return value


def _number(value: Any, label: str, minimum: float = 0, maximum: float = 1e9) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(label + " must be finite and within declared bounds")
    return value


def _refs(values: Any, known: set[str], label: str) -> tuple[str, ...]:
    refs = _texts(values, label)
    if len(set(refs)) != len(refs) or not set(refs) <= known:
        raise ValueError(label + " must name unique declared sources")
    return refs


def _sealed(value: dict[str, Any]) -> dict[str, Any]:
    result = {**value, "record_sha256": digest(canonical(value))}
    if len(canonical(result)) > MAX_RECORD_BYTES:
        raise ValueError("research record exceeds bounded payload ceiling")
    return result


def _check_seal(value: Any, schema: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != schema or len(canonical(value)) > MAX_RECORD_BYTES:
        raise ValueError("invalid bounded research record")
    payload = {key: item for key, item in value.items() if key != "record_sha256"}
    if value.get("record_sha256") != digest(canonical(payload)):
        raise ValueError("research record digest mismatch")
    if value.get("promotion_authority") is not False or value.get("qualification") is not False:
        raise ValueError("research records cannot promote or qualify")
    return value


@dataclass(frozen=True)
class ProvenanceRef:
    source_id: str
    locator: str
    content_sha256: str
    kind: str
    epistemic_status: str


@dataclass(frozen=True)
class FirstPrinciplesFrame:
    question: str
    intended_outcome: str
    scope: str
    first_principles_model: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    essential_invariants: tuple[str, ...]
    unknowns: tuple[str, ...]
    unknowns_resolution_plan: str
    baseline: str
    falsifier: str
    sources: tuple[ProvenanceRef, ...]


@dataclass(frozen=True)
class MeasurementPlan:
    measurement_id: str
    metric: str
    unit: str
    expected: float
    tolerance: float
    method: str
    uncertainty_plan: str
    conditions_and_controls: tuple[str, ...]
    sampling_plan: str
    raw_artifact_plan: str
    falsifier: str


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    assumptions: tuple[str, ...]
    falsifier: str
    measurement_ids: tuple[str, ...]
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReasoningStep:
    mode: str
    premises: tuple[str, ...]
    inference: str
    consequence: str
    scope_limit: str
    source_ids: tuple[str, ...]
    sample_description: str = ""
    competing_hypothesis_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextCheck:
    kind: str
    concern: str
    context: str
    assessment: str
    rationale: str
    mitigation_or_test: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class AnalogyPlan:
    analogue: str
    mapping_extent: str
    invariant_mapping: dict[str, str]
    unmapped_invariants: tuple[str, ...]
    loss_or_boundary_note: str
    reverse_mapping_test: str
    original_acceptance_tests: tuple[str, ...]


@dataclass(frozen=True)
class RepresentationCheck:
    decision: str
    reason: str
    invariant_or_test: str
    unknowns: tuple[str, ...]


@dataclass(frozen=True)
class Primitive:
    primitive_id: str
    domain: str
    mechanism: str
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    falsifier: str
    measurement_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    estimated_cost: float = 0
    status: str = "candidate"


@dataclass(frozen=True)
class Compatibility:
    left: str
    right: str
    rationale: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class DefectClass:
    defect_id: str
    minimal_reproducer: str
    violated_invariant: str
    root_cause_status: str
    root_cause_or_unknown: str
    sibling_search_scope: tuple[str, ...]
    regression_test: str
    preventive_guard: str
    verification_plan: str
    rollback: str
    authorization_status: str
    sources: tuple[ProvenanceRef, ...]


def _provenance(sources: Any) -> set[str]:
    if not isinstance(sources, (tuple, list)) or not 1 <= len(sources) <= 50:
        raise ValueError("explicit bounded provenance required")
    ids = []
    for source in sources:
        if not isinstance(source, ProvenanceRef):
            raise ValueError("typed ProvenanceRef records required")
        ids.append(_id(source.source_id))
        _text(source.locator, "source locator", 2000)
        _hash(source.content_sha256)
        if source.kind not in {"user_input", "local_artifact", "measurement", "external_source", "model_output", "declared_assumption"}:
            raise ValueError("unsupported provenance kind")
        if source.epistemic_status not in {"reported", "observed", "simulated", "assumed", "hypothesis"}:
            raise ValueError("unsupported source epistemic status")
    if len(set(ids)) != len(ids):
        raise ValueError("source IDs must be unique")
    return set(ids)


def _checks(checks: Any, sources: set[str]) -> list[dict[str, Any]]:
    if not isinstance(checks, (tuple, list)) or not 1 <= len(checks) <= 30:
        raise ValueError("at least one contextual bias/fallacy/measurement check required")
    result = []
    for check in checks:
        if not isinstance(check, ContextCheck) or check.kind not in {"bias", "fallacy", "measurement_confound", "source_quality"}:
            raise ValueError("typed contextual check required")
        if check.assessment not in {"not_assessed", "possible", "supported_concern", "tested_not_supported", "not_applicable"}:
            raise ValueError("unsupported contextual assessment")
        for name in ("concern", "context", "rationale", "mitigation_or_test"):
            _text(getattr(check, name), name)
        _refs(check.source_ids, sources, "check sources")
        result.append(asdict(check))
    return result


def build_research_plan(plan_id: str, frame: FirstPrinciplesFrame,
                        hypotheses: tuple[Hypothesis, ...], measurements: tuple[MeasurementPlan, ...],
                        reasoning_steps: tuple[ReasoningStep, ...], contextual_checks: tuple[ContextCheck, ...],
                        *, source_commit: str, subproblems: tuple[str, ...], alternatives_review: str,
                        representation_checks: Mapping[str, RepresentationCheck],
                        analogy: AnalogyPlan | None = None, version: int = 1,
                        parent_plan_ref: dict[str, Any] | None = None) -> dict[str, Any]:
    _id(plan_id); _hash(source_commit, 40)
    if type(version) is not int or not 1 <= version <= 1000000:
        raise ValueError("positive bounded plan version required")
    if (version == 1) != (parent_plan_ref is None):
        raise ValueError("revised plans need an exact parent; initial plans have none")
    if parent_plan_ref is not None:
        ArtifactRef.from_mapping(parent_plan_ref)
    if not isinstance(frame, FirstPrinciplesFrame):
        raise ValueError("typed first-principles framing required before literature")
    for field in ("question", "intended_outcome", "scope", "first_principles_model",
                  "unknowns_resolution_plan", "baseline", "falsifier"):
        _text(getattr(frame, field), field)
    for field in ("assumptions", "constraints", "essential_invariants", "unknowns"):
        _texts(getattr(frame, field), field)
    sources = _provenance(frame.sources)
    _texts(subproblems, "smaller subproblems")
    _text(alternatives_review, "competing-explanation review")
    if not isinstance(measurements, tuple) or not 1 <= len(measurements) <= 30:
        raise ValueError("bounded measurement plans required")
    measurement_ids = set()
    for measurement in measurements:
        if not isinstance(measurement, MeasurementPlan):
            raise ValueError("typed measurement plans required")
        identity = _id(measurement.measurement_id)
        if identity in measurement_ids:
            raise ValueError("measurement IDs must be unique")
        measurement_ids.add(identity)
        for field in ("metric", "unit", "method", "uncertainty_plan", "sampling_plan", "raw_artifact_plan", "falsifier"):
            _text(getattr(measurement, field), field)
        _number(measurement.expected, "prediction", -1e9)
        _number(measurement.tolerance, "tolerance")
        _texts(measurement.conditions_and_controls, "conditions and controls")
    if not isinstance(hypotheses, tuple) or not 1 <= len(hypotheses) <= 30:
        raise ValueError("bounded testable hypotheses required")
    hypothesis_ids = set()
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, Hypothesis):
            raise ValueError("typed hypotheses required")
        identity = _id(hypothesis.hypothesis_id)
        if identity in hypothesis_ids:
            raise ValueError("hypothesis IDs must be unique")
        hypothesis_ids.add(identity)
        _text(hypothesis.statement, "hypothesis statement"); _text(hypothesis.falsifier, "hypothesis falsifier")
        _texts(hypothesis.assumptions, "hypothesis assumptions")
        _refs(hypothesis.source_ids, sources, "hypothesis sources")
        _refs(hypothesis.measurement_ids, measurement_ids, "hypothesis measurement plans")
    if not isinstance(reasoning_steps, tuple) or not 1 <= len(reasoning_steps) <= 50:
        raise ValueError("bounded explicit reasoning steps required")
    for step in reasoning_steps:
        if not isinstance(step, ReasoningStep) or step.mode not in MODES:
            raise ValueError("typed, distinguished reasoning modes required")
        _texts(step.premises, "reasoning premises")
        for field in ("inference", "consequence", "scope_limit"):
            _text(getattr(step, field), field)
        _refs(step.source_ids, sources, "reasoning sources")
        if step.mode == "inductive":
            _text(step.sample_description, "induction sample and population limits")
        if step.mode == "abductive" and (len(step.competing_hypothesis_ids) < 2
                or not set(step.competing_hypothesis_ids) <= hypothesis_ids
                or len(set(step.competing_hypothesis_ids)) != len(step.competing_hypothesis_ids)):
            raise ValueError("abduction must retain at least two distinct competing hypotheses")
    checks = _checks(contextual_checks, sources)
    if not isinstance(representation_checks, Mapping) or set(representation_checks) != REPRESENTATION_LENSES:
        raise ValueError("explicit simplex, n_ality, continuum and fuzzy_logic assessments required")
    representation_payload = {}
    for lens in sorted(REPRESENTATION_LENSES):
        check = representation_checks[lens]
        if not isinstance(check, RepresentationCheck) or check.decision not in {"applied", "not_applicable", "deferred"}:
            raise ValueError("typed representation decision required")
        _text(check.reason, "representation applicability reason")
        _text(check.invariant_or_test, "representation invariant/test")
        _texts(check.unknowns, "representation unknowns")
        representation_payload[lens] = asdict(check)
    analogy_payload = None
    if analogy is not None:
        if not isinstance(analogy, AnalogyPlan) or analogy.mapping_extent not in {"exact", "partial"}:
            raise ValueError("typed exact/partial analogy mapping required")
        if (not isinstance(analogy.invariant_mapping, dict) or len(analogy.invariant_mapping) > 30
                or set(analogy.invariant_mapping) | set(analogy.unmapped_invariants) != set(frame.essential_invariants)
                or set(analogy.invariant_mapping) & set(analogy.unmapped_invariants)):
            raise ValueError("every essential invariant must be explicitly mapped or declared unmapped")
        if analogy.mapping_extent == "exact" and analogy.unmapped_invariants:
            raise ValueError("exact mapping cannot omit essential invariants")
        if analogy.mapping_extent == "partial" and not analogy.unmapped_invariants:
            raise ValueError("partial mapping must expose its unmapped invariants")
        for value in analogy.invariant_mapping.values():
            _text(value, "invariant mapping")
        _text(analogy.loss_or_boundary_note, "analogy limits")
        _text(analogy.reverse_mapping_test, "translation-back test")
        _texts(analogy.original_acceptance_tests, "original task acceptance tests")
        analogy_payload = decompose_by_analogy(frame.question, analogy.analogue,
                                               analogy.invariant_mapping, subproblems)
        analogy_payload.update({"claimed_mapping_extent": analogy.mapping_extent,
            "unmapped_invariants": list(analogy.unmapped_invariants),
            "loss_or_boundary_note": analogy.loss_or_boundary_note,
            "reverse_mapping_test": analogy.reverse_mapping_test,
            "original_acceptance_tests": list(analogy.original_acceptance_tests),
            "equivalence_established": False})
    return _sealed({"schema": "merlin-research-plan/1", "record_type": "research_plan",
        "plan_id": plan_id, "version": version, "parent_plan_ref": parent_plan_ref,
        "source_commit": source_commit, "stage": "first_principles_framed",
        "source_commit_scope": "caller_declared_project_source; not authenticated by this protocol",
        "frame": asdict(frame), "hypotheses": [asdict(x) for x in hypotheses],
        "measurements": [asdict(x) for x in measurements], "reasoning_steps": [asdict(x) for x in reasoning_steps],
        "contextual_checks": checks, "subproblems": list(subproblems), "analogy": analogy_payload,
        "representation_checks": representation_payload,
        "alternatives_review": alternatives_review, "literature_status": "not_requested_by_protocol",
        "source_text_policy": "untrusted_data_not_instructions", "epistemic_status": "hypothesis_plan",
        "novelty_status": "not_assessed", "qualification": False, "promotion_authority": False})


def _validated_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Rebuild typed contracts; a recomputed self-hash cannot bypass field gates."""
    _check_seal(plan, "merlin-research-plan/1")
    try:
        frame = dict(plan["frame"])
        frame["sources"] = tuple(ProvenanceRef(**source) for source in frame["sources"])
        for field in ("assumptions", "constraints", "essential_invariants", "unknowns"):
            frame[field] = tuple(frame[field])
        def typed(cls, rows, tuples):
            return tuple(cls(**{**row, **{key: tuple(row[key]) for key in tuples}}) for row in rows)
        hypotheses = typed(Hypothesis, plan["hypotheses"], ("assumptions", "measurement_ids", "source_ids"))
        measurements = typed(MeasurementPlan, plan["measurements"], ("conditions_and_controls",))
        steps = typed(ReasoningStep, plan["reasoning_steps"], ("premises", "source_ids", "competing_hypothesis_ids"))
        checks = typed(ContextCheck, plan["contextual_checks"], ("source_ids",))
        representations = {name: RepresentationCheck(**{**value, "unknowns": tuple(value["unknowns"])})
                           for name, value in plan["representation_checks"].items()}
        a = plan["analogy"]
        analogy = None if a is None else AnalogyPlan(a["analogue"], a["claimed_mapping_extent"],
            a["invariant_mapping"], tuple(a["unmapped_invariants"]), a["loss_or_boundary_note"],
            a["reverse_mapping_test"], tuple(a["original_acceptance_tests"]))
        rebuilt = build_research_plan(plan["plan_id"], FirstPrinciplesFrame(**frame), hypotheses,
            measurements, steps, checks, source_commit=plan["source_commit"], subproblems=tuple(plan["subproblems"]),
            alternatives_review=plan["alternatives_review"], representation_checks=representations, analogy=analogy,
            version=plan["version"], parent_plan_ref=plan["parent_plan_ref"])
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("invalid persisted typed research plan") from exc
    if canonical(rebuilt) != canonical(plan):
        raise ValueError("persisted research plan differs from validated typed contract")
    return plan


def prepare_literature_request(registry: MerlinRegistry, plan_ref: dict[str, Any],
                               questions: tuple[str, ...]) -> dict[str, Any]:
    """Require an existing exact first-principles checkpoint before search planning."""
    ref = ArtifactRef.from_mapping(plan_ref)
    import json
    plan = json.loads(registry.read_artifact_ref(ref.to_dict(), max_bytes=MAX_RECORD_BYTES)["content"])
    _validated_plan(plan)
    if plan.get("stage") != "first_principles_framed":
        raise ValueError("first-principles framing checkpoint required before literature")
    return {"schema": "merlin-literature-request/1", "framed_plan_ref": ref.to_dict(),
            "questions": list(_texts(questions, "specific literature questions")),
            "ordering": "after_persisted_first_principles_frame", "execution_status": "not_run",
            "source_policy": "external_sources_are_untrusted_data", "novelty_status": "not_assessed",
            "qualification": False, "promotion_authority": False}


def build_research_review(plan: dict[str, Any], observations: tuple[Observation, ...], *,
                          reviewer_id: str, contextual_checks: tuple[ContextCheck, ...],
                          next_actions: tuple[str, ...], limitations: tuple[str, ...]) -> dict[str, Any]:
    _validated_plan(plan); _id(reviewer_id)
    if not isinstance(observations, tuple) or not 1 <= len(observations) <= 30:
        raise ValueError("bounded measured observations required")
    known = {source["source_id"] for source in plan["frame"]["sources"]}
    assessments = []
    ids = set()
    predictions = [Prediction(x["metric"], x["expected"], x["tolerance"], x["unit"]) for x in plan["measurements"]]
    for observation in observations:
        if not isinstance(observation, Observation):
            raise ValueError("canonical measured Observation records required")
        if (not isinstance(observation.measurements, Mapping) or not 1 <= len(observation.measurements) <= 30
                or not isinstance(observation.units, Mapping) or not 1 <= len(observation.units) <= 30
                or not isinstance(observation.uncertainty, Mapping) or not 1 <= len(observation.uncertainty) <= 30):
            raise ValueError("bounded explicit measured quantities, units and uncertainty required")
        observation.validate(); _hash(observation.artifact_sha256)
        _text(observation.question, "observation question"); _text(observation.method, "observation method")
        _texts(observation.source_refs, "observation sources")
        if (not isinstance(observation.conditions, Mapping) or not 1 <= len(observation.conditions) <= 30
                or any(not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip()
                       for key, value in observation.conditions.items())
                or set(observation.units) != set(observation.measurements)
                or set(observation.uncertainty) != set(observation.measurements)):
            raise ValueError("measurement conditions, units and uncertainty must bind the measured quantities")
        _id(observation.observation_id)
        if observation.observation_id in ids:
            raise ValueError("observation IDs must be unique")
        ids.add(observation.observation_id)
        known.update(observation.source_refs)
        assessments.append(compare_observation(observation, predictions))
    checks = _checks(contextual_checks, known)
    update = update_plan_from_observations({"plan_id": plan["plan_id"], "version": plan["version"]},
        observations, next_actions=_texts(next_actions, "concrete next actions"))
    return _sealed({"schema": "merlin-research-review/1", "record_type": "research_review",
        "plan_id": plan["plan_id"], "plan_version": plan["version"], "plan_record_sha256": plan["record_sha256"],
        "reviewer_id": reviewer_id, "observations": [asdict(x) for x in observations],
        "deductive_assessments": assessments, "inductive_plan_update": update,
        "contextual_checks": checks, "limitations": list(_texts(limitations, "review limitations")),
        "negative_or_inconclusive_results_retained": True, "independence": "not_established_by_reviewer_name",
        "epistemic_status": "review_recorded_not_independent_verification",
        "qualification": False, "promotion_authority": False})


def bounded_ideonomy(plan: dict[str, Any], primitives: tuple[Primitive, ...],
                     compatibility: tuple[Compatibility, ...], *, trigger: str,
                     max_size: int = 3, max_cost: float = 0, examine_limit: int = 256,
                     result_limit: int = 16) -> dict[str, Any]:
    _validated_plan(plan); _text(trigger, "concrete blockage, lacuna or trade-off")
    if type(max_size) is not int or not 2 <= max_size <= 3:
        raise ValueError("combination size must be 2 or 3")
    if type(examine_limit) is not int or not 1 <= examine_limit <= 4096 or type(result_limit) is not int or not 1 <= result_limit <= 64:
        raise ValueError("bounded examination and output ceilings required")
    _number(max_cost, "estimated-cost ceiling")
    if not isinstance(primitives, tuple) or not 2 <= len(primitives) <= 24:
        raise ValueError("2..24 typed primitives required")
    sources = {source["source_id"] for source in plan["frame"]["sources"]}
    measures = {row["measurement_id"] for row in plan["measurements"]}
    primitive_by_id = {}
    for primitive in primitives:
        if not isinstance(primitive, Primitive):
            raise ValueError("typed Primitive required")
        identity = _id(primitive.primitive_id)
        if identity in primitive_by_id:
            raise ValueError("primitive IDs must be unique")
        primitive_by_id[identity] = primitive
        _text(primitive.domain, "primitive domain", 100); _text(primitive.mechanism, "mechanism")
        _texts(primitive.assumptions, "primitive assumptions"); _texts(primitive.unknowns, "primitive unknowns")
        _text(primitive.falsifier, "primitive falsifier")
        _refs(primitive.source_ids, sources, "primitive sources")
        _refs(primitive.measurement_ids, measures, "primitive measurement plans")
        _number(primitive.estimated_cost, "estimated primitive cost")
        if primitive.status not in {"candidate", "supported", "refuted", "rejected", "disabled"}:
            raise ValueError("primitive status is a declaration, never proof or novelty")
    if not isinstance(compatibility, tuple) or len(compatibility) > 276:
        raise ValueError("bounded explicit pair compatibility required")
    pairs = set()
    for pair in compatibility:
        if not isinstance(pair, Compatibility) or pair.left == pair.right or {pair.left, pair.right} - set(primitive_by_id):
            raise ValueError("compatibility must reference two distinct known primitives")
        identity = frozenset((pair.left, pair.right))
        if identity in pairs:
            raise ValueError("duplicate compatibility declaration")
        pairs.add(identity)
        _text(pair.rationale, "compatibility rationale"); _refs(pair.source_ids, sources, "compatibility sources")
    if len(canonical({"primitives": [asdict(p) for p in primitives],
                      "compatibility": [asdict(pair) for pair in compatibility]})) > MAX_RECORD_BYTES:
        raise ValueError("primitive catalogue exceeds bounded input ceiling")
    ordered = [primitive_by_id[key] for key in sorted(primitive_by_id)]
    total = sum(math.comb(len(ordered), size) for size in range(2, max_size + 1))
    groups = (group for size in range(2, max_size + 1) for group in combinations(ordered, size))
    output = []; examined = 0
    for group in islice(groups, examine_limit):
        examined += 1
        rows = [{"id": p.primitive_id, "domain": p.domain, "estimated_cost": p.estimated_cost, "status": p.status} for p in group]
        eligible = enumerate_useful_combinations(rows, pairs, trigger=trigger,
            problem=plan["frame"]["question"], max_size=len(group), max_cost=max_cost, limit=8)
        match = next((item for item in eligible if len(item["primitive_ids"]) == len(group)), None)
        if match is None:
            continue
        group_ids = {p.primitive_id for p in group}
        identity = {"plan_record_sha256": plan["record_sha256"], "trigger": trigger,
            "primitives": [asdict(p) for p in group],
            "compatibility": sorted((asdict(pair) for pair in compatibility
                if {pair.left, pair.right} <= group_ids), key=lambda pair: sorted((pair["left"], pair["right"])))}
        output.append({**match, "canonical_helper_label": match["combination_id"],
            "combination_id": "ideonomy-" + digest(canonical(identity)),
            "mechanism_proposals": [p.mechanism for p in group],
            "assumptions": sorted({x for p in group for x in p.assumptions}),
            "unknowns": sorted({x for p in group for x in p.unknowns}),
            "falsifiers": [p.falsifier for p in group],
            "measurement_ids": sorted({x for p in group for x in p.measurement_ids}),
            "source_ids": sorted({x for p in group for x in p.source_ids}),
            "novelty_status": "not_assessed", "physical_feasibility": "not_established"})
    output.sort(key=lambda item: (item["estimated_cost"], item["combination_id"]))
    result = {"schema": "merlin-bounded-ideonomy/1", "plan_record_sha256": plan["record_sha256"],
        "candidates": output[:result_limit], "coverage": {"total_catalog_combinations": total,
            "examined_combinations": examined, "filtered_examined_combinations": examined - len(output),
            "eligible_examined_combinations": len(output), "eligible_output_omitted": max(0, len(output) - result_limit),
            "unexamined_combinations": total - examined, "enumeration_complete": total == examined,
            "catalog_scope": "supplied primitives only; not all possible ideas", "ranking_scope": "examined eligible combinations only"},
        "claim_boundary": "A local lacuna or alternative glyph/alien-science analogy is a research hypothesis, not novelty, physical feasibility or proof.",
        "compatibility_status": "caller_declared_not_independently_verified",
        "epistemic_status": "hypothesis_combinations", "qualification": False, "promotion_authority": False}
    if len(canonical(result)) > MAX_RECORD_BYTES:
        raise ValueError("enumeration result exceeds record ceiling; request a smaller result limit")
    return result


def prepare_jit_repair(defect: DefectClass, dependency_graph: dict[str, tuple[str, ...]],
                       changed_nodes: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(defect, DefectClass):
        raise ValueError("typed defect-class record required")
    _id(defect.defect_id); _provenance(defect.sources)
    if defect.root_cause_status not in {"known", "hypothesis", "unknown"}:
        raise ValueError("root cause must retain its evidence status")
    if defect.authorization_status not in {"routine_fix_authorized", "additional_scope_required", "not_authorized"}:
        raise ValueError("explicit existing authorization status required")
    for field in ("minimal_reproducer", "violated_invariant", "root_cause_or_unknown", "regression_test",
                  "preventive_guard", "verification_plan", "rollback"):
        _text(getattr(defect, field), field)
    _texts(defect.sibling_search_scope, "sibling defect-class search scope")
    if not isinstance(dependency_graph, dict) or not 1 <= len(dependency_graph) <= 256:
        raise ValueError("bounded explicit dependency graph required")
    reverse = {node: set() for node in dependency_graph}
    for node, dependencies in dependency_graph.items():
        _id(node)
        if not isinstance(dependencies, tuple) or len(dependencies) > 64 or len(set(dependencies)) != len(dependencies):
            raise ValueError("bounded unique dependency tuples required")
        if set(dependencies) - set(dependency_graph):
            raise ValueError("unknown dependency blocks targeted invalidation")
        for dependency in dependencies:
            _id(dependency); reverse[dependency].add(node)
    changed = set(_texts(changed_nodes, "changed nodes", maximum=256))
    if not changed <= set(dependency_graph):
        raise ValueError("changed node absent from dependency map")
    invalidated = set(changed); pending = sorted(changed)
    while pending:
        node = pending.pop(0)
        for dependent in sorted(reverse[node]):
            if dependent not in invalidated:
                invalidated.add(dependent); pending.append(dependent)
    return _sealed({"schema": "merlin-jit-repair-plan/1", "record_type": "defect_repair_plan",
        "defect": asdict(defect), "dependency_graph": dependency_graph,
        "dependency_graph_sha256": digest(canonical(dependency_graph)),
        "changed_nodes": sorted(changed), "invalidated_nodes": sorted(invalidated),
        "preserved_nodes": sorted(set(dependency_graph) - invalidated),
        "recompute_policy": "changed_nodes_and_transitive_dependents_only",
        "unknown_dependency_policy": "stop_targeted_recompute_until_map_is_reconciled",
        "execution_status": "not_run", "repair_verified": False, "verification_evidence": [],
        "sibling_search_status": "not_run",
        "verification_gate": "Retain actual reproducer/regression/guard results and exact artifacts before claiming repair verified.",
        "authorization_status": defect.authorization_status,
        "authorization_note": "Existing routine-fix authorization is preserved; additional authority-sensitive scope remains separate.",
        "qualification": False, "promotion_authority": False})


def store_research_record(registry: MerlinRegistry, project_id: str,
                          record: dict[str, Any]) -> dict[str, Any]:
    """Append only through canonical artifact history; no shadow database.

    Plan revisions require the exact current parent. Reviews must bind an already
    persisted plan version/digest. The caller supplies its authorized registry;
    this routine grants no additional filesystem or application authority.
    """
    # One cooperative host: serialize this adapter's check/append sequence.
    # This does not defend against unrelated code bypassing the writer protocol.
    import fcntl
    import os
    descriptor = os.open(registry.root / "dot-research-protocol.lock",
                         os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("research writer busy; retry the identical record after reconciliation") from exc
        return _store_record_unlocked(registry, project_id, record)
    finally:
        os.close(descriptor)


def _store_record_unlocked(registry: MerlinRegistry, project_id: str,
                           record: dict[str, Any]) -> dict[str, Any]:
    schema = record.get("schema") if isinstance(record, dict) else None
    if schema not in {"merlin-research-plan/1", "merlin-research-review/1", "merlin-jit-repair-plan/1"}:
        raise ValueError("unsupported typed research record")
    _check_seal(record, schema)
    if schema == "merlin-research-plan/1":
        _validated_plan(record)
        path = "research/" + _id(record["plan_id"]) + "/plan.json"
        history = registry.artifact_history(project_id, path)
        if history:
            current = registry.artifact_ref(project_id, path)
            if registry.read_artifact_ref(current, max_bytes=MAX_RECORD_BYTES)["content"] == canonical(record):
                return {"artifact_ref": current, "record_type": "research_plan", "replayed": True}
            if record["parent_plan_ref"] != current or record["version"] != current["version"] + 1:
                raise ValueError("plan revision must bind exact current parent and next version")
        elif record["version"] != 1 or record["parent_plan_ref"] is not None:
            raise ValueError("initial plan must start at version one without parent")
    elif schema == "merlin-research-review/1":
        path = "research/" + _id(record["plan_id"]) + "/plan.json"
        ref = registry.artifact_ref(project_id, path, version=record["plan_version"])
        import json
        plan = json.loads(registry.read_artifact_ref(ref, max_bytes=MAX_RECORD_BYTES)["content"])
        _validated_plan(plan)
        if plan["record_sha256"] != record["plan_record_sha256"]:
            raise ValueError("review does not match the persisted exact plan")
        try:
            observations = tuple(Observation(**{**value, "source_refs": tuple(value["source_refs"])})
                                 for value in record["observations"])
            if any(not registry.verify_artifact(observation.artifact_sha256) for observation in observations):
                raise ValueError("persist raw observation artifacts before recording their research review")
            checks = tuple(ContextCheck(**{**value, "source_ids": tuple(value["source_ids"])})
                           for value in record["contextual_checks"])
            rebuilt = build_research_review(plan, observations, reviewer_id=record["reviewer_id"],
                contextual_checks=checks, next_actions=tuple(record["inductive_plan_update"]["next_actions"]),
                limitations=tuple(record["limitations"]))
        except (TypeError, KeyError, AttributeError) as exc:
            raise ValueError("invalid persisted typed research review") from exc
        if canonical(rebuilt) != canonical(record):
            raise ValueError("research review differs from actual typed observation assessment")
        path = "research/" + record["plan_id"] + "/reviews/" + record["record_sha256"] + ".json"
    else:
        try:
            value = record["defect"]
            defect = DefectClass(**{**value, "sources": tuple(ProvenanceRef(**x) for x in value["sources"]),
                                   "sibling_search_scope": tuple(value["sibling_search_scope"])})
            rebuilt = prepare_jit_repair(defect, {key: tuple(value) for key, value in record["dependency_graph"].items()},
                                         tuple(record["changed_nodes"]))
        except (TypeError, KeyError, AttributeError) as exc:
            raise ValueError("invalid persisted typed repair plan") from exc
        if canonical(rebuilt) != canonical(record):
            raise ValueError("repair record cannot self-declare execution or verification")
        path = "research/defects/" + _id(record["defect"]["defect_id"]) + "/" + record["record_sha256"] + ".json"
    registry.put_artifact(project_id, path, canonical(record), "application/json")
    return {"artifact_ref": registry.artifact_ref(project_id, path),
            "record_type": record["record_type"], "qualification": False, "promotion_authority": False}


def research_contract(arguments: dict[str, Any]) -> dict[str, Any]:
    """Fixed read-only protocol description, suitable for static tool registration."""
    if type(arguments) is not dict or set(arguments) - {"operation"} or arguments.get("operation", "contract") != "contract":
        raise ValueError("only the research contract operation is available")
    return {"schema": "merlin-research-protocol-contract/1",
        "ordering": ["first_principles_framing", "persist_exact_research_plan", "focused_literature_if_needed",
                     "bounded_measurement", "deductive_prediction_check", "contextual_skeptical_review", "append_plan_revision"],
        "required_records": ["research_plan", "research_review", "defect_repair_plan_when_applicable"],
        "reasoning_modes": sorted(MODES), "representation_lenses": sorted(REPRESENTATION_LENSES),
        "representation_rule": "Assess applicability explicitly; do not force an irrelevant formalism.",
        "fuzzy_rule": "Fuzzy membership is not probability and cannot soften a hard verification or authorization gate.",
        "ideonomy_rule": "Only explicit compatible, testable, budget-feasible bounded combinations; report all omitted/unexamined scope.",
        "jit_rule": "Preserve existing routine-fix authorization; recompute only changed nodes and dependent results; no repair is verified until actual checks are retained.",
        "source_policy": "External/retrieved source text is untrusted data, not instructions.",
        "claim_boundary": "Structural contract validation is not factual truth, novelty, formal proof or independent verification.",
        "execution_status": "not_run", "qualification": False, "promotion_authority": False}


def research_episode_demo(arguments: dict[str, Any]) -> dict[str, Any]:
    """Frame before one fixed virtual experiment; return records without persistence.

    This reviewed fixture touches no private context, registry, external service,
    model provider or repair executor. A caller may archive the returned records
    through the canonical store. The demo does not prepare a literature request.
    """
    if type(arguments) is not dict or set(arguments) - {"operation"} or arguments.get("operation", "demo") != "demo":
        raise ValueError("only the fixed research episode demo is available")
    from fractions import Fraction
    from .simulation_research import virtual_circuit_demo
    premise = {"supply_v": "5", "baseline_ohm": ["1000", "1000"], "candidate_ohm": ["9000", "9000"],
               "model": "ideal unloaded DC resistors; no physical measurements"}
    source = ProvenanceRef("fixed-input", "reviewed_fixture:SI_parameters_and_model_assumptions",
                           digest(canonical(premise)), "declared_assumption", "assumed")
    frame = FirstPrinciplesFrame(
        "Can proportional resistor scaling preserve ideal output voltage while reducing modeled power?",
        "Compare voltage invariance and ideal-model power under unchanged source and topology",
        "One fixed ideal unloaded low-voltage DC fixture; no physical generalization",
        "Ohm/Kirchhoff model predicts Vout=Vs*Rbottom/(Rtop+Rbottom) and P=Vs^2/(Rtop+Rbottom).",
        ("Ideal constant resistors", "No load or parasitics", "Exact SI parameter declarations"),
        ("No hardware or external execution", "No new authority"),
        ("same source and topology", "correct units and output", "unchanged authority"),
        ("Physical-model adequacy is unmeasured", "Implementation could violate the stated ideal model"),
        "Check the exact fixture against closed-form predictions; keep physical adequacy unresolved",
        "Two 1000-ohm resistors at 5 V", "Output differs from 2.5 V or candidate dissipation differs from 1/720 W", (source,))
    measurements = (
        MeasurementPlan("output-voltage", "output_v", "V", 2.5, 1e-12, "Exact-rational nodal simulation",
            "Zero conversion error for 2.5; no physical uncertainty has been measured", ("Same ideal source/topology",),
            "One deterministic fixture only", "Hash the complete simulation report", "Output interval excludes 2.5 V"),
        MeasurementPlan("candidate-power", "power_w", "W", float(Fraction(1, 720)), 1e-12,
            "Exact rational power converted to float for interval adapter",
            "1e-12 W adapter-rounding bound only; no physical/model uncertainty bound", ("Ideal constant resistors",),
            "One deterministic fixture only", "Retain exact rational and float-adapter values",
            "Power interval excludes 1/720 W"),)
    hypotheses = (
        Hypothesis("ideal-scaling", "Proportional scaling preserves the ratio and reduces ideal dissipation",
            ("The declared ideal model holds",), "The fixture contradicts the closed-form predictions",
            ("output-voltage", "candidate-power"), ("fixed-input",)),
        Hypothesis("implementation-mismatch", "An implementation/unit/connectivity mismatch changes the predicted values",
            ("A mismatch exists",), "Independent fixture checks reproduce both predictions under the stated model",
            ("output-voltage", "candidate-power"), ("fixed-input",)),)
    steps = (
        ReasoningStep("deductive", ("Ohm/Kirchhoff equations", "Fixed source and resistance ratio"),
            "Substitute 1000/1000 and 9000/9000 ohms in the same ideal equations",
            "Predict 2.5 V and candidate power 1/720 W", "Only the stated ideal model", ("fixed-input",)),
        ReasoningStep("abductive", ("Model or implementation might explain an observed discrepancy",),
            "Retain ideal-scaling and implementation-mismatch alternatives", "A discrepancy needs diagnosis, not a novelty claim",
            "No discrepancy has yet been observed by this plan", ("fixed-input",),
            competing_hypothesis_ids=("ideal-scaling", "implementation-mismatch")),)
    check = ContextCheck("measurement_confound", "Single-fixture and model-validity limits", "Ideal DC demonstration",
        "supported_concern", "A deterministic fixture does not sample physical devices or general task behavior",
        "Preserve the limitation; use separate matched-load/tolerance studies before generalizing", ("fixed-input",))
    representations = {
        "simplex": RepresentationCheck("not_applicable", "No barycentric geometry or normalized mixture model is needed",
            "Do not treat positive voltages as probabilities or simplex coordinates without a defined map", ("Utility for later design mixtures",)),
        "n_ality": RepresentationCheck("not_applicable", "Three named circuit nets do not establish a threefold algebraic symmetry",
            "Require a typed operation and explicit invariant before adding an n-ality model", ("Future symmetry model",)),
        "continuum": RepresentationCheck("deferred", "Lumped scalar DC nodes do not resolve a spatial continuum field",
            "Retain SI units and model scope; require boundary/regularity assumptions for field claims", ("Spatial, thermal and material behavior",)),
        "fuzzy_logic": RepresentationCheck("not_applicable", "This fixture uses explicit rational equations and hard interval checks",
            "Fuzzy membership is not probability and cannot replace exact residual or authority gates", ("Whether later qualitative evidence warrants a separate fuzzy model",)),}
    # The first-principles frame and prediction plan must exist before execution.
    plan = build_research_plan("fixed-dc-research", frame, hypotheses, measurements, steps, (check,),
        source_commit="d074cab60ea61411373098cb86562109813b3a3a",
        subproblems=("Derive the ratio prediction", "Derive ideal power", "Compare exact simulated outputs", "Retain model limitations"),
        alternatives_review="Distinguish model prediction from an implementation/unit mismatch; physical adequacy remains unknown",
        representation_checks=representations)
    simulation = virtual_circuit_demo({})
    candidate = next(row for row in simulation["results"] if row["candidate_id"] == "lower_power")
    observation = Observation("fixed-simulation", frame.question,
        "Exact-rational ideal DC calculation; canonical interval adapter uses converted floats",
        {"output_v": float(Fraction(candidate["node_voltage_v"]["OUT"])),
         "power_w": float(Fraction(candidate["total_resistor_power_w"]))},
        {"output_v": "V", "power_w": "W"}, {"output_v": 0.0, "power_w": 1e-12},
        {"mode": "simulated_only", "physical_measurements": "none", "sampling": "one fixed fixture"},
        ("simulation-report",), "2026-11-17T00:00:00Z", digest(canonical(simulation)))
    review = build_research_review(plan, (observation,), reviewer_id="deterministic-fixture-review",
        contextual_checks=(check,), next_actions=("Retain the fixture as a regression", "Review model adequacy separately before physical use"),
        limitations=("This is deterministic review code, not an independently authenticated evaluator",
                     "Known-fixture reproduction: prior expected results were already known; this is not a new confirmatory discovery",
                     "The fixed timestamp is fixture metadata, not a claim about a physical measurement time"))
    primitives = (
        Primitive("ratio-scaling", "circuit_model", "Preserve resistance ratio while scaling total resistance", ("Ideal model",),
            ("Loaded behavior",), "Output ratio changes", ("output-voltage",), ("fixed-input",)),
        Primitive("shared-ir", "representation", "Derive wiring, SPICE and CAD previews from one typed revision", ("Explicit parameter values",),
            ("Native CAD fidelity",), "Exports disagree on connectivity", ("output-voltage",), ("fixed-input",)),
        Primitive("reference-check", "verification_method", "Compare nodal output against a separate closed-form fixture", ("Same assumptions",),
            ("Generalization beyond this fixture",), "Reference and solver differ", ("candidate-power",), ("fixed-input",)),)
    pairs = tuple(Compatibility(a.primitive_id, b.primitive_id, "Compatible declared fixture contracts", ("fixed-input",))
                  for a, b in combinations(primitives, 2))
    ideas = bounded_ideonomy(plan, primitives, pairs, trigger="Find a small testable bridge between parameter scaling, shared exports and reference checks",
                             result_limit=4, examine_limit=10)
    defect = DefectClass("parameter-response-guard", "Change one resistor alone and require output to change",
        "Inputs must affect the computed model; constants/placeholders cannot masquerade as a solver", "hypothesis",
        "A placeholder or stale cache could ignore changed inputs; no such defect is claimed observed in this episode",
        ("Parameter transforms", "Netlist generation", "Candidate comparison", "Cached result identities"),
        "Perturb one resistor and compare independent closed-form and nodal results", "Bind every electrical parameter to request/result identity",
        "Run perturbation and sibling regressions and retain exact outputs", "Restore prior reviewed solver/adapter",
        "routine_fix_authorized", (source,))
    repair = prepare_jit_repair(defect, {"candidate_values": (), "spice": ("candidate_values",),
        "simulation": ("candidate_values",), "measurement": ("simulation",), "review": ("measurement",),
        "master_plan_update": ("review",), "uid_scope": (), "base_geometry": ()}, ("candidate_values",))
    result = {"schema": "merlin-research-episode-demo/1", "research_plan": plan, "simulation": simulation,
        "research_review": review, "lacuna_proposals": ideas, "jit_repair_plan": repair,
        "ordering": ["research_plan", "fixed_virtual_experiment", "research_review", "bounded_lacuna_proposals", "nonexecuting_repair_plan"],
        "persistence": "not_written_by_demo; caller may archive through canonical registry",
        "experiment_class": "known_fixture_reproduction", "prior_result_known": True,
        "confirmatory_discovery": False,
        "literature_execution": "not_run", "private_context_access": False,
        "qualification": False, "promotion_authority": False}
    if len(canonical(result)) > 48000:
        raise RuntimeError("fixed research episode exceeds reviewed private transport ceiling")
    return result
