"""Evidence-aware mathematical transfer hypotheses for Merlin subsystems.

This engine proposes where a mathematical result might be useful. It does not
assert theorem validity, applicability, performance improvement, or deployment
authority. Those require independent proof/evaluation and controlled promotion.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Mapping

SCHEMA = "merlin-math-transfer-preview/1"
PROOF_STATES = frozenset({
    "unreviewed", "formal_proof_verified", "numerically_supported",
    "empirically_supported", "refuted", "not_applicable",
})

# Explicit, reviewable mappings. A match is a hypothesis, never a qualification.
TRANSFER_RULES = {
    "optimization": [
        ("hermes_scheduler", "Compare scheduling objective, constraint set and resource utilization.",
         "paired workload replay; makespan, queue time, deadline misses, resource utilization"),
        ("mcfc_resource_allocator", "Compare allocation quality under identical resource budgets.",
         "fixed-budget benchmark; throughput, starvation, utilization, constraint violations"),
    ],
    "graph_theory": [
        ("knowledge_graph", "Test whether the graph structure improves traversal, indexing or relation discovery.",
         "held-out graph queries; recall@k, traversal cost, precision, update cost"),
        ("research_branching", "Test whether graph structure improves evidence-branch selection.",
         "held-out research tasks; evidence coverage, branch usefulness, redundant branches"),
    ],
    "information_theory": [
        ("research_retrieval", "Test retrieval/compression trade-offs without losing evidence provenance.",
         "held-out retrieval set; recall, precision, token/byte cost, provenance retention"),
        ("context_management", "Test whether the result improves context selection under a fixed budget.",
         "fixed-context-budget replay; task success, omitted-critical-fact rate, latency"),
    ],
    "numerical_analysis": [
        ("simulation_engine", "Compare numerical stability, convergence and error against the current solver.",
         "reference problems; convergence order, residual, stability region, runtime"),
        ("engineering_simulation", "Test accuracy and runtime on reproducible engineering cases.",
         "pinned solver suite; error bounds, conservation checks, runtime, reproducibility"),
    ],
    "linear_algebra": [
        ("ml_representation", "Test whether the decomposition or invariant improves representation workloads.",
         "held-out matrices; residual, conditioning, runtime, downstream task score"),
        ("equation_atlas", "Test canonicalization and equivalence checks on known transformations.",
         "verified identity suite; false-equivalence rate, coverage, runtime"),
    ],
    "control_theory": [
        ("agent_orchestration", "Test stability and bounded response under simulated workload disturbances.",
         "reproducible load scenarios; settling time, overshoot, constraint violations"),
        ("resource_governance", "Test resource feedback without changing authority or approval policy.",
         "bounded stress suite; budget violations, oscillation, starvation, recovery time"),
    ],
    "learning_theory": [
        ("learner_model", "Test whether the result improves learning-state estimation or lesson selection.",
         "held-out learner traces; calibration, delayed retention, transfer, learning time"),
        ("math_kung_fu", "Test instructional sequencing against demonstrated learning outcomes.",
         "controlled lesson comparison; delayed retrieval, transfer, misconception recurrence"),
    ],
    "probability_statistics": [
        ("evaluation_engine", "Test calibration, uncertainty and robustness of model/task evaluation.",
         "held-out labelled set; calibration error, confidence intervals, false promotion rate"),
        ("research_ranking", "Test ranking robustness and sensitivity to source/evidence uncertainty.",
         "point-in-time replay; rank stability, calibration, source-quality sensitivity"),
    ],
}

TARGETS = frozenset(target for rows in TRANSFER_RULES.values() for target, _, _ in rows)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def preview_transfers(discovery: Mapping[str, Any],
                      requested_targets: list[str] | None = None) -> dict[str, Any]:
    """Create deterministic, reviewable subsystem-transfer hypotheses."""
    if not isinstance(discovery, Mapping):
        raise ValueError("discovery must be an object")
    discovery_id = discovery.get("discovery_id")
    title = discovery.get("title")
    structures = discovery.get("structure_families")
    proof_state = discovery.get("proof_state", "unreviewed")
    source_refs = discovery.get("source_refs", [])
    assumptions = discovery.get("assumptions", [])
    limitations = discovery.get("limitations", [])
    if not isinstance(discovery_id, str) or not _ID.fullmatch(discovery_id):
        raise ValueError("discovery_id must be an opaque identifier")
    if not isinstance(title, str) or not title.strip() or len(title) > 300:
        raise ValueError("title is required and must be at most 300 characters")
    if not isinstance(structures, list) or not structures or any(
        item not in TRANSFER_RULES for item in structures
    ):
        raise ValueError("structure_families must contain supported structure identifiers")
    if len(set(structures)) != len(structures):
        raise ValueError("structure_families must be unique")
    if proof_state not in PROOF_STATES:
        raise ValueError("unsupported proof_state")
    for field_name, values in (("source_refs", source_refs), ("assumptions", assumptions),
                               ("limitations", limitations)):
        if not isinstance(values, list) or any(not isinstance(x, str) or len(x) > 1000 for x in values):
            raise ValueError(field_name + " must be a list of strings")
    if requested_targets is not None and (
        not isinstance(requested_targets, list) or any(x not in TARGETS for x in requested_targets)
    ):
        raise ValueError("requested_targets contains an unsupported subsystem")

    candidates = []
    for family in structures:
        for target, rationale, measurement in TRANSFER_RULES[family]:
            if requested_targets is not None and target not in requested_targets:
                continue
            candidates.append({
                "candidate_id": f"{discovery_id}:{target}",
                "discovery_id": discovery_id,
                "structure_family": family,
                "target_subsystem": target,
                "rationale": rationale,
                "benchmark_plan": measurement,
                "proof_state": proof_state,
                "qualification_state": "hypothesis_only",
                "required_gates": [
                    "verify source provenance and exact discovery artifact",
                    "verify mathematical claim and assumptions independently",
                    "implement behind an isolated feature flag",
                    "compare against a pinned baseline on held-out workloads",
                    "check regressions, resource limits and rollback",
                    "obtain subsystem owner approval and CACE evidence receipt",
                ],
                "promotion_authorized": False,
            })
    candidates.sort(key=lambda row: (row["target_subsystem"], row["structure_family"]))
    core = {
        "schema": SCHEMA,
        "discovery": {
            "discovery_id": discovery_id, "title": title,
            "structure_families": list(structures), "proof_state": proof_state,
            "source_refs": list(source_refs), "assumptions": list(assumptions),
            "limitations": list(limitations),
        },
        "candidates": candidates,
        "candidate_count": len(candidates),
        "promotion_authorized": False,
        "notice": (
            "These are transfer hypotheses, not proof of applicability or improvement. "
            "A verified theorem may still be irrelevant or slower in a target subsystem."
        ),
    }
    digest = sha256(_canonical(core)).hexdigest()
    return {**core, "preview_sha256": digest}


def compare_measurements(baseline: Mapping[str, Any],
                         candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Conservative numeric comparison; lower/higher direction must be explicit."""
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
        raise ValueError("baseline and candidate measurements must be objects")
    metric = baseline.get("metric")
    if not isinstance(metric, str) or metric != candidate.get("metric"):
        raise ValueError("baseline and candidate must identify the same metric")
    direction = baseline.get("preferred_direction")
    if direction not in {"lower", "higher"} or candidate.get("preferred_direction") != direction:
        raise ValueError("preferred_direction must be lower or higher and match")
    before, after = baseline.get("value"), candidate.get("value")
    for value in (before, after):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("measurement values must be numeric")
    if before == 0:
        improvement = None
    elif direction == "lower":
        improvement = (before - after) / abs(before)
    else:
        improvement = (after - before) / abs(before)
    return {
        "metric": metric, "baseline": before, "candidate": after,
        "preferred_direction": direction,
        "relative_improvement": round(improvement, 8) if improvement is not None else None,
        "numerically_better_on_this_metric": improvement is not None and improvement > 0,
        "qualification_state": "single_metric_observation_only",
        "promotion_authorized": False,
        "notice": "A single metric comparison is not a qualification; use paired held-out trials and regression gates.",
    }
