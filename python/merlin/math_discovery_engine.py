"""Evidence-gated Mathematical Discovery Engine.

All substantive engines are injected adapters. This module never fabricates
proofs, experiments, counterexample searches, Ideonomy outputs or CACE receipts.
It orchestrates immutable records and ranks evidence quality, reproducibility
and mathematical significance. It has no promotion authority.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence

from merlin.math_discovery_atlas import atlas_candidates, validate_candidate

ENGINE_SCHEMA = "merlin-mathematical-discovery-engine/1"

def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")

def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _safe_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not result or result[0].isdigit():
        result = "c_" + result
    return result[:80]

@dataclass(frozen=True)
class ResearchAdapters:
    """Real adapters supplied by deployment; None means stage unavailable."""
    ideonomy: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None
    numerical: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None
    counterexample: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None
    lean: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None
    cace: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None

def generate_conjecture_seeds(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Produce transparent seed prompts for Ideonomy; these are not discoveries."""
    errors = validate_candidate(candidate)
    if errors:
        raise ValueError("invalid atlas candidate: " + "; ".join(errors))
    cid = str(candidate["candidate_id"])
    seeds = []
    for index, obligation in enumerate(candidate["lean_obligations"]):
        seeds.append({
            "conjecture_id": cid + "-obligation-" + str(index + 1),
            "parent_candidate_id": cid,
            "source": "atlas_obligation_seed",
            "statement_prompt": str(obligation),
            "assumptions": list(candidate["domain_and_assumptions"]),
            "status": "hypothesis_seed_not_conjecture",
            "ideonomy_review_required": True,
        })
    for index, experiment in enumerate(candidate["numerical_experiments"]):
        seeds.append({
            "conjecture_id": cid + "-experiment-" + str(index + 1),
            "parent_candidate_id": cid,
            "source": "atlas_experiment_seed",
            "statement_prompt": "Formulate a quantitative, falsifiable prediction for: " + str(experiment),
            "assumptions": list(candidate["domain_and_assumptions"]),
            "status": "hypothesis_seed_not_conjecture",
            "ideonomy_review_required": True,
        })
    return seeds

def generate_lean_skeleton(conjecture: Mapping[str, Any]) -> str:
    """Generate a visibly incomplete Lean scaffold, never a claimed proof."""
    name = _safe_id(str(conjecture.get("conjecture_id", "unnamed_obligation")))
    statement = str(conjecture.get("formal_statement", "")).strip()
    if not statement:
        statement = "TODO: replace with a precise proposition and explicit assumptions"
    assumptions = conjecture.get("assumptions", [])
    comment = "\n".join("-- Assumption: " + str(item).replace("\n", " ")
                         for item in assumptions)
    return (
        "-- GENERATED SCAFFOLD ONLY: not a theorem statement or verified proof.\n"
        "-- Replace the TODO proposition with a mathematically precise statement.\n"
        "import Mathlib\n\nnamespace MerlinDiscovery\n\n"
        + comment + "\n"
        + "-- Conjecture: " + str(conjecture.get("statement_prompt", "unspecified")).replace("\n", " ")
        + "\n theorem " + name + " : (" + statement + ") := by\n"
        + "  sorry -- TODO: proof obligation; this placeholder is not verification\n\n"
        + "end MerlinDiscovery\n"
    )

def _validate_run_record(record: Mapping[str, Any], stage: str) -> None:
    for key in ("engine", "engine_version", "tool_version", "precision", "seed"):
        if key not in record:
            raise ValueError(stage + " result missing reproducibility field: " + key)
    if not isinstance(record["seed"], (int, str)):
        raise ValueError(stage + " seed must be an integer or string")
    if not isinstance(record["precision"], str) or not record["precision"].strip():
        raise ValueError(stage + " precision must be explicit")

def compare_experiment_to_claim(claim: Mapping[str, Any],
                                experiment: Mapping[str, Any]) -> dict[str, Any]:
    """Require an explicit comparator result; never infer proof from numerical fit."""
    comparison = experiment.get("formal_comparison")
    if not isinstance(comparison, Mapping):
        return {"status": "not_compared", "reason": "engine supplied no formal_comparison"}
    status = comparison.get("status")
    if status not in {"consistent_with_claim", "contradicts_claim", "inconclusive"}:
        raise ValueError("formal_comparison.status is invalid")
    return {
        "status": status,
        "method": str(comparison.get("method", "unspecified")),
        "tolerance": comparison.get("tolerance"),
        "scope": str(comparison.get("scope", "unspecified")),
        "warning": "Numerical consistency is not a formal proof.",
    }

def evidence_score(record: Mapping[str, Any]) -> dict[str, float]:
    """Transparent 0..1 dimensions; missing evidence receives zero, not a guess."""
    proof = record.get("proof", {})
    experiment = record.get("experiment", {})
    counter = record.get("counterexample", {})
    independent = record.get("cace", {})
    proof_score = 1.0 if proof.get("status") == "verified" else 0.0
    exp_score = 1.0 if experiment.get("status") == "completed" and experiment.get("reproducible") is True else 0.0
    counter_score = 1.0 if counter.get("status") == "completed" and counter.get("search_scope") else 0.0
    cace_score = 1.0 if independent.get("verification_status") == "verified" else 0.0
    source_score = 1.0 if record.get("evidence_sources_reviewed") is True else 0.0
    quality = 0.30 * proof_score + 0.20 * exp_score + 0.15 * counter_score + 0.25 * cace_score + 0.10 * source_score
    reproducibility = 1.0 if exp_score and experiment.get("environment_digest") and experiment.get("seed") is not None and experiment.get("tool_version") else 0.0
    significance = record.get("mathematical_significance", 0.0)
    if isinstance(significance, bool) or not isinstance(significance, (int, float)) or not math.isfinite(significance):
        significance = 0.0
    significance = min(1.0, max(0.0, float(significance)))
    return {
        "evidence_quality": round(quality, 4),
        "reproducibility": round(reproducibility, 4),
        "mathematical_significance": round(significance, 4),
        "composite": round(0.50 * quality + 0.30 * reproducibility + 0.20 * significance, 4),
    }

class MathematicalDiscoveryEngine:
    def __init__(self, adapters: ResearchAdapters):
        self.adapters = adapters

    def ideonomy_expand(self, candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
        seeds = generate_conjecture_seeds(candidate)
        if self.adapters.ideonomy is None:
            return seeds
        expanded = self.adapters.ideonomy({"candidate": dict(candidate), "seeds": seeds})
        if not isinstance(expanded, Sequence) or isinstance(expanded, (str, bytes)):
            raise TypeError("Ideonomy adapter must return a sequence of conjecture records")
        result = []
        for item in expanded:
            if not isinstance(item, Mapping):
                raise TypeError("Ideonomy conjectures must be objects")
            entry = dict(item)
            entry.setdefault("parent_candidate_id", candidate["candidate_id"])
            entry.setdefault("status", "proposed_unreviewed")
            entry["promotion_authority"] = False
            result.append(entry)
        return result

    def lean_scaffold(self, conjecture: Mapping[str, Any]) -> dict[str, Any]:
        source = generate_lean_skeleton(conjecture)
        if self.adapters.lean is None:
            return {"status": "scaffold_generated_not_checked", "source": source,
                    "toolchain": None, "proof_verified": False}
        result = dict(self.adapters.lean({"conjecture": dict(conjecture), "source": source}))
        result.setdefault("proof_verified", False)
        if result.get("proof_verified") is True and result.get("status") != "verified":
            raise ValueError("Lean adapter cannot claim proof_verified without status=verified")
        return result

    def run_numerical(self, experiment_spec: Mapping[str, Any]) -> dict[str, Any]:
        if self.adapters.numerical is None:
            return {"status": "not_dispatched", "reason": "no numerical adapter configured"}
        result = dict(self.adapters.numerical(dict(experiment_spec)))
        _validate_run_record(result, "numerical")
        result["status"] = result.get("status", "completed")
        result["artifact_sha256"] = _digest(_canonical(result))
        return result

    def search_counterexamples(self, search_spec: Mapping[str, Any]) -> dict[str, Any]:
        if self.adapters.counterexample is None:
            return {"status": "not_dispatched", "reason": "no counterexample adapter configured"}
        result = dict(self.adapters.counterexample(dict(search_spec)))
        _validate_run_record(result, "counterexample")
        if not result.get("search_scope"):
            raise ValueError("counterexample result must declare search_scope")
        result["artifact_sha256"] = _digest(_canonical(result))
        return result

    def verify_with_cace(self, artifact: Mapping[str, Any]) -> dict[str, Any]:
        if self.adapters.cace is None:
            return {"verification_status": "not_requested", "reason": "no CACE adapter configured"}
        result = dict(self.adapters.cace(dict(artifact)))
        if result.get("artifact_sha256") != artifact.get("artifact_sha256"):
            raise ValueError("CACE receipt does not bind the exact submitted artifact digest")
        if result.get("verification_status") not in {"verified", "rejected", "inconclusive"}:
            raise ValueError("CACE must return a recognized verification status")
        return result

    def rank(self, records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        ranked = []
        for record in records:
            ranked.append({
                "candidate_id": record["candidate_id"],
                "scores": evidence_score(record),
                "promotion_authority": False,
                "status": record.get("status", "research_only"),
            })
        return sorted(ranked, key=lambda item: (
            item["scores"]["composite"], item["candidate_id"]), reverse=True)

    def run_candidate(self, candidate: Mapping[str, Any], *,
                      experiment_specs: Sequence[Mapping[str, Any]] = (),
                      counterexample_specs: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        errors = validate_candidate(candidate)
        if errors:
            raise ValueError("invalid atlas candidate: " + "; ".join(errors))
        conjectures = self.ideonomy_expand(candidate)
        lean = [self.lean_scaffold(item) for item in conjectures]
        # Counterexample search is deliberately run before any promotion decision.
        counterexamples = [self.search_counterexamples(spec) for spec in counterexample_specs]
        experiments = [self.run_numerical(spec) for spec in experiment_specs]
        comparisons = [
            compare_experiment_to_claim({"candidate_id": candidate["candidate_id"]}, result)
            for result in experiments
        ]
        proof_records = [{"artifact_sha256": _digest(item["source"].encode("utf-8")),
                          "source": item["source"], "status": item["status"]}
                         for item in lean]
        cace_receipts = []
        for item in proof_records:
            cace_receipts.append(self.verify_with_cace(item))
        for item in experiments:
            if item.get("artifact_sha256"):
                cace_receipts.append(self.verify_with_cace(item))
        result = {
            "schema": ENGINE_SCHEMA,
            "candidate_id": candidate["candidate_id"],
            "conjectures": conjectures,
            "lean_scaffolds": lean,
            "counterexample_searches": counterexamples,
            "experiments": experiments,
            "formal_comparisons": comparisons,
            "cace_receipts": cace_receipts,
            "status": "research_only",
            "promotion_authority": False,
            "cryptographic_status": "not_eligible",
        }
        result["artifact_sha256"] = _digest(_canonical(result))
        return result

def hermes_math_discovery_executor(task: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Hermes research-stage adapter; emits atlas-derived conjecture seeds only."""
    from merlin.math_discovery_atlas import atlas_candidates
    if task.get("stage") != "research":
        raise ValueError("Mathematical Discovery Engine entrypoint requires research stage")
    requested = task.get("candidate_id")
    candidates = [c for c in atlas_candidates() if requested is None or c["candidate_id"] == requested]
    if not candidates:
        raise ValueError("requested atlas candidate was not found")
    engine = MathematicalDiscoveryEngine(ResearchAdapters())
    outputs = []
    for candidate in candidates:
        outputs.append({
            "candidate_id": candidate["candidate_id"],
            "conjecture_seeds": engine.ideonomy_expand(candidate),
            "lean_scaffolds": [],
            "numerical_status": "not_dispatched",
            "counterexample_status": "not_dispatched",
            "cace_status": "not_requested",
        })
    payload = _canonical({
        "schema": ENGINE_SCHEMA,
        "task_id": context.task_id,
        "hypothesis_id": context.hypothesis_id,
        "objective": str(task.get("objective", "")),
        "candidates": outputs,
        "notice": "No Ideonomy model, Lean checker, numerical engine, counterexample search or CACE service was invoked by this seed-only handler.",
        "promotion_authority": False,
    })
    return {
        "artifact_bytes": payload,
        "media_type": "application/vnd.merlin.discovery-engine+json",
        "summary": "Generated atlas-derived conjecture seeds; external engines remain explicitly unconfigured.",
        "metadata": {"artifact_schema": ENGINE_SCHEMA, "promotion_authority": False,
                     "candidate_count": len(outputs)},
    }

__all__ = ["ENGINE_SCHEMA", "ResearchAdapters", "MathematicalDiscoveryEngine",
           "generate_conjecture_seeds", "generate_lean_skeleton",
           "compare_experiment_to_claim", "evidence_score",
           "hermes_math_discovery_executor"]
