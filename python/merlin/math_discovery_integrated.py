"""Integrated, fail-closed adapters for Merlin mathematical discovery.

This module composes existing Ideonomy, Lean, local numerical/counterexample
backends and CACE with the canonical Hermes evidence path. Optional compute
backends are injected explicitly; absence is reported, never simulated.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence

from merlin.ideonomy_invention_lab import (
    IDEONOMY_PRIMITIVES, enumerate_simplex_combinations,
)
from merlin.math_discovery_atlas import atlas_candidates, validate_candidate
from merlin.math_discovery_engine import (
    MathematicalDiscoveryEngine, ResearchAdapters,
)
from merlin.hermes_stage_handlers import build_hermes_stage_handlers
from merlin.research_evidence import ResearchEvidenceRecorder

INTEGRATION_SCHEMA = "merlin-math-discovery-integrated/1"
PLACEHOLDER_RE = re.compile(
    r"\bsorry\b|\badmit\b|\baxiom\s+TODO\b|"
    r"TODO\s*[:(]|REPLACE_WITH|\?\?\?",
    re.IGNORECASE,
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be a non-empty string")
    return value.strip()


def _validate_hypothesis(item: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(item)
    assumptions = result.get("assumptions")
    statement = result.get("falsifiable_statement")
    if not isinstance(assumptions, list) or not assumptions or any(
        not isinstance(x, str) or not x.strip() for x in assumptions
    ):
        raise ValueError("Ideonomy output requires explicit non-empty assumptions")
    _required_text(statement, "falsifiable_statement")
    formal_statement = _required_text(result.get("formal_statement"), "formal_statement")
    lean_source = _required_text(result.get("lean_source"), "lean_source")
    source_identity = result.get("source_identity")
    if not isinstance(source_identity, Mapping):
        raise ValueError("Ideonomy output requires explicit source_identity metadata")
    source_ids = result.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or set(source_ids) != set(source_identity.get("primitive_ids", [])):
        raise ValueError("claim source identity must exactly match its Ideonomy primitive IDs")
    if formal_statement not in lean_source:
        raise ValueError("Lean source must contain the exact declared formal statement")
    if PLACEHOLDER_RE.search(lean_source):
        raise ValueError("Lean source contains a placeholder and is not eligible")
    result["epistemic_status"] = "proposed_unproved_conjecture"
    result["lean_translation_eligible"] = True
    result["promotion_authority"] = False
    return result


class IdeonomyConjectureAdapter:
    """Use actual primitive/simplex IDs; a factory must supply precise claims.

    Without a claim_factory, outputs remain research prompts and cannot be
    translated to Lean. The existing invention-candidate catalogue is not
    silently reinterpreted as mathematical theorems.
    """
    def __init__(self, claim_factory: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None):
        self.claim_factory = claim_factory
        self.primitive_by_id = {p["id"]: dict(p) for p in IDEONOMY_PRIMITIVES}

    def __call__(self, payload: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        candidate = payload["candidate"]
        seeds = payload["seeds"]
        combinations = enumerate_simplex_combinations(3)
        output = []
        for simplex in combinations:
            source_ids = list(simplex["primitive_ids"])
            source_primitives = [self.primitive_by_id[x] for x in source_ids]
            proposal = {
                "conjecture_id": candidate["candidate_id"] + "-" + simplex["simplex_id"],
                "parent_candidate_id": candidate["candidate_id"],
                "source_ids": source_ids,
                "simplex_id": simplex["simplex_id"],
                "source_domains": list(simplex["domains"]),
                "source_functions": list(simplex["functions"]),
                "source_primitives": source_primitives,
                "atlas_seed_ids": [s["conjecture_id"] for s in seeds],
                "assumptions": [],
                "falsifiable_statement": "",
                "formal_statement": "",
                "epistemic_status": "ideonomy_proposal_unformalized",
                "lean_translation_eligible": False,
                "promotion_authority": False,
            }
            if self.claim_factory is not None:
                generated = self.claim_factory(proposal)
                if not isinstance(generated, Mapping):
                    raise TypeError("Ideonomy claim_factory must return one mapping per proposal")
                if generated is None:
                    # A simplex without a defensible mathematical bridge is
                    # retained as Ideonomy provenance, not promoted into a claim.
                    proposal["epistemic_status"] = "ideonomy_proposal_no_grounded_claim"
                    output.append(proposal)
                    continue
                proposal.update(dict(generated))
                proposal = _validate_hypothesis(proposal)
            output.append(proposal)
        return output


@dataclass(frozen=True)
class LeanProject:
    root: Path
    toolchain: str
    manifest_sha256: str
    lakefile_sha256: str


def discover_lean_project(root: str | Path) -> LeanProject:
    base = Path(root).resolve()
    candidates = [base] if (base / "lean-toolchain").is_file() else [
        p.parent for p in base.rglob("lean-toolchain")
        if ".lake" not in p.parts and "node_modules" not in p.parts
    ]
    if len(candidates) != 1:
        raise FileNotFoundError("expected exactly one Lean project root with lean-toolchain")
    project = candidates[0]
    toolchain_file = project / "lean-toolchain"
    manifest = project / "lake-manifest.json"
    lakefile = project / "lakefile.toml"
    if not manifest.is_file() or not lakefile.is_file():
        raise FileNotFoundError("Lean project must contain lake-manifest.json and lakefile.toml")
    return LeanProject(
        project, toolchain_file.read_text().strip(),
        sha256(manifest.read_bytes()), sha256(lakefile.read_bytes()),
    )


class LeanCompilerAdapter:
    """Run the pinned Lake/Lean project and retain raw compiler receipts."""
    def __init__(self, project: LeanProject, *, timeout_seconds: int = 90):
        if not 1 <= timeout_seconds <= 600:
            raise ValueError("Lean timeout must be between 1 and 600 seconds")
        self.project = project
        self.timeout_seconds = timeout_seconds

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        conjecture = payload["conjecture"]
        source = _required_text(conjecture.get("lean_source") or payload.get("source"), "Lean source")
        eligible = conjecture.get("lean_translation_eligible") is True
        if not eligible:
            return {"status": "blocked_missing_formal_statement",
                    "proof_verified": False, "reason": "hypothesis lacks validated assumptions and falsifiable statement"}
        if PLACEHOLDER_RE.search(source):
            return {"status": "rejected_placeholder", "proof_verified": False,
                    "source_sha256": sha256(source.encode("utf-8"))}
        target = conjecture.get("formal_statement")
        if not isinstance(target, str) or not target.strip():
            return {"status": "rejected_missing_target", "proof_verified": False}
        started = time.monotonic()
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".lean",
            prefix="MerlinDiscovery_", dir=self.project.root, delete=False
        ) as handle:
            handle.write(source)
            source_path = Path(handle.name)
        try:
            command = ["lake", "env", "lean", source_path.name]
            try:
                completed = subprocess.run(
                    command, cwd=self.project.root, capture_output=True,
                    text=True, timeout=self.timeout_seconds, check=False,
                    env={**os.environ, "LAKE_NO_UPDATE": "1"},
                )
                exit_status = completed.returncode
                stdout, stderr = completed.stdout, completed.stderr
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                exit_status, timed_out = None, True
                stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        finally:
            source_path.unlink(missing_ok=True)
        has_placeholder = bool(PLACEHOLDER_RE.search(source))
        verified = exit_status == 0 and not timed_out and not has_placeholder
        return {
            "status": "compiled_unverified" if verified else ("timeout" if timed_out else "compile_failed"),
            "proof_verified": False,
            "compiler_exit_status": exit_status,
            "stdout": stdout, "stderr": stderr,
            "toolchain": self.project.toolchain,
            "lake_manifest_sha256": self.project.manifest_sha256,
            "lakefile_sha256": self.project.lakefile_sha256,
            "source_sha256": sha256(source.encode("utf-8")),
            "target_declaration": target,
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "contains_placeholder": has_placeholder,
            "kernel_checked": False,
            "note": "Compilation is not an independent proof receipt; CACE kernel and axiom verification remains required.",
        }


class ReproducibleNumericalAdapter:
    """Bounded deterministic local runner around an explicitly supplied solver."""
    def __init__(self, solver: Callable[[Mapping[str, Any]], Any], *,
                 engine: str, engine_version: str, tool_version: str,
                 environment: Mapping[str, str], max_runtime_seconds: float = 10.0):
        if not callable(solver):
            raise ValueError("a real numerical solver callable is required")
        if not 0 < max_runtime_seconds <= 60:
            raise ValueError("local numerical runtime limit must be in (0, 60]")
        self.solver, self.engine = solver, _required_text(engine, "engine")
        self.engine_version, self.tool_version = engine_version, tool_version
        self.environment = dict(environment)
        self.max_runtime_seconds = max_runtime_seconds

    def __call__(self, spec: Mapping[str, Any]) -> Mapping[str, Any]:
        seed = spec.get("seed")
        precision = _required_text(spec.get("precision"), "precision")
        parameters = spec.get("parameters")
        if seed is None or not isinstance(parameters, Mapping):
            raise ValueError("numerical spec requires seed and parameters object")
        request = {**dict(spec), "parameters": dict(parameters)}
        start = time.monotonic()
        first_result = self.solver(request)
        first_raw = canonical_bytes(first_result)
        first_elapsed = time.monotonic() - start
        if first_elapsed > self.max_runtime_seconds:
            raise TimeoutError("numerical solver exceeded configured runtime limit")
        second_result = self.solver(request)
        elapsed = time.monotonic() - start
        if elapsed > self.max_runtime_seconds:
            raise TimeoutError("numerical reproducibility replay exceeded configured runtime limit")
        raw = canonical_bytes(second_result)
        reproducible = first_raw == raw
        environment_digest = sha256(canonical_bytes(self.environment))
        record = {
            "schema": "merlin-numerical-run/1", "status": "completed" if reproducible else "completed_non_reproducible",
            "engine": self.engine, "engine_version": self.engine_version,
            "tool_version": self.tool_version, "precision": precision,
            "seed": seed, "parameters": dict(parameters),
            "environment": self.environment, "environment_digest": environment_digest,
            "runtime_limit_seconds": self.max_runtime_seconds,
            "elapsed_seconds": round(elapsed, 6),
            "raw_output_bytes_base64": __import__("base64").b64encode(raw).decode("ascii"),
            "first_output_sha256": sha256(first_raw), "raw_output_sha256": sha256(raw), "reproducible": reproducible,
            "promotion_authority": False,
        }
        record["artifact_sha256"] = sha256(canonical_bytes(record))
        return record


class BoundedCounterexampleAdapter:
    """Require a real bounded search backend and explicit completion semantics."""
    def __init__(self, searcher: Callable[[Mapping[str, Any]], Mapping[str, Any]], *,
                 engine: str, engine_version: str, tool_version: str,
                 max_runtime_seconds: float = 10.0):
        if not callable(searcher) or not 0 < max_runtime_seconds <= 60:
            raise ValueError("counterexample backend and bounded runtime are required")
        self.searcher, self.engine = searcher, engine
        self.engine_version, self.tool_version = engine_version, tool_version
        self.max_runtime_seconds = max_runtime_seconds

    def __call__(self, spec: Mapping[str, Any]) -> Mapping[str, Any]:
        domain = _required_text(spec.get("search_domain"), "search_domain")
        bounds = spec.get("bounds")
        method = _required_text(spec.get("method"), "method")
        seed = spec.get("seed")
        if not isinstance(bounds, Mapping) or seed is None:
            raise ValueError("counterexample spec requires bounds and seed")
        start = time.monotonic()
        result = self.searcher(dict(spec))
        elapsed = time.monotonic() - start
        if elapsed > self.max_runtime_seconds:
            raise TimeoutError("counterexample search exceeded configured runtime limit")
        if not isinstance(result, Mapping):
            raise TypeError("counterexample searcher must return a mapping")
        status = result.get("termination_status")
        if status not in {"complete", "counterexample_found", "timeout", "incomplete", "error"}:
            raise ValueError("counterexample backend must declare termination_status")
        completed = status in {"complete", "counterexample_found"}
        counterexample = result.get("counterexample")
        if status == "counterexample_found" and counterexample is None:
            raise ValueError("counterexample_found requires an explicit counterexample")
        raw = canonical_bytes(dict(result))
        record = {
            "schema": "merlin-counterexample-search/1",
            "status": "completed" if completed else "incomplete",
            "search_domain": domain, "bounds": dict(bounds), "method": method,
            "seed": seed, "engine": self.engine, "engine_version": self.engine_version,
            "tool_version": self.tool_version, "precision": str(spec.get("precision", "exact-or-backend-defined")),
            "runtime_limit_seconds": self.max_runtime_seconds,
            "elapsed_seconds": round(elapsed, 6),
            "termination_status": status, "counterexample": counterexample,
            "raw_output_sha256": sha256(raw),
            "raw_output_bytes_base64": __import__("base64").b64encode(raw).decode("ascii"),
            "search_scope": {"domain": domain, "bounds": dict(bounds), "method": method},
            "promotion_authority": False,
        }
        record["artifact_sha256"] = sha256(canonical_bytes(record))
        return record


def build_integrated_math_discovery_handlers(
    *, repository_root: str | Path, evidence_recorder: ResearchEvidenceRecorder,
    project_id: str, repository: str, commit_sha: str, requester_id: str,
    cace_adapter: Any, numerical_solver: Callable[[Mapping[str, Any]], Any],
    counterexample_searcher: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ideonomy_claim_factory: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None,
    numerical_environment: Mapping[str, str] | None = None,
    numerical_engine_version: str = "injected",
    numerical_tool_version: str = "injected",
    counterexample_engine_version: str = "injected",
    counterexample_tool_version: str = "injected",
) -> dict[str, Callable[..., Mapping[str, Any]]]:
    """Construct the complete adapter stack and register one canonical Hermes path."""
    lean_project = discover_lean_project(repository_root)
    from merlin.cace_adapter import CaceVerificationAdapter
    if not isinstance(cace_adapter, CaceVerificationAdapter):
        raise TypeError("a real CaceVerificationAdapter is required")
    if cace_adapter.verify_transport is None:
        raise RuntimeError("CACE independent verification transport is not configured; refusing to register Hermes handlers")
    ideonomy = IdeonomyConjectureAdapter(ideonomy_claim_factory)
    lean = LeanCompilerAdapter(lean_project)
    numerical = ReproducibleNumericalAdapter(
        numerical_solver, engine="merlin-local-numerical",
        engine_version=numerical_engine_version, tool_version=numerical_tool_version,
        environment=numerical_environment or {"platform": os.name},
    )
    counterexample = BoundedCounterexampleAdapter(
        counterexample_searcher, engine="merlin-bounded-counterexample",
        engine_version=counterexample_engine_version,
        tool_version=counterexample_tool_version,
    )

    # CACE runs in the Hermes handler only after the recorder stores and
    # re-hashes the exact artifact bytes.
    adapters = ResearchAdapters(
        ideonomy=ideonomy, lean=lean, numerical=numerical,
        counterexample=counterexample, cace=None,
    )
    engine = MathematicalDiscoveryEngine(adapters)
    candidates = {item["candidate_id"]: item for item in atlas_candidates()}

    def executor(task: Mapping[str, Any], context: Any) -> Mapping[str, Any]:
        requested = task.get("candidate_id")
        selected = [candidates[requested]] if requested in candidates else list(candidates.values())
        if requested is not None and requested not in candidates:
            raise ValueError("unknown mathematical atlas candidate_id")
        results = []
        for candidate in selected:
            if validate_candidate(candidate):
                raise ValueError("atlas candidate failed validation")
            conjectures = engine.ideonomy_expand(candidate)
            eligible = [c for c in conjectures if c.get("lean_translation_eligible") is True]
            # Compile only the exact Lean source supplied by the validated claim.
            # Do not call engine.lean_scaffold(): that method deliberately emits
            # an incomplete sorry scaffold and is never a proof input.
            lean_results = [
                dict(lean({"conjecture": dict(claim)}))
                for claim in eligible
            ]
            for claim, lean_result in zip(eligible, lean_results):
                lean_result["conjecture_id"] = claim["conjecture_id"]
                lean_result["formal_statement"] = claim["formal_statement"]
                lean_result["source_identity"] = dict(claim["source_identity"])
                lean_result["proof_verified"] = False
                if lean_result.get("status") == "compiled_unverified":
                    lean_result["compilation_status"] = "compiled"
                    lean_result["verification_status"] = "not_independently_verified"
            # Compilation and independent proof verification remain separate.
            experiments = [engine.run_numerical(s) for s in task.get("experiment_specs", [])]
            searches = [engine.search_counterexamples(s) for s in task.get("counterexample_specs", [])]
            results.append({
                "candidate_id": candidate["candidate_id"],
                "conjectures": conjectures, "lean_results": lean_results,
                "experiments": experiments, "counterexample_searches": searches,
                "promotion_authority": False, "cryptographic_status": "not_eligible",
            })
        payload = canonical_bytes({
            "schema": INTEGRATION_SCHEMA, "task_id": context.task_id,
            "hypothesis_id": context.hypothesis_id, "results": results,
            "lean_project": {"root": str(lean_project.root),
                             "toolchain": lean_project.toolchain,
                             "manifest_sha256": lean_project.manifest_sha256,
                             "lakefile_sha256": lean_project.lakefile_sha256},
            "notices": [
                "Proposals are not established conjectures.",
                "Lean compilation is not independent proof verification.",
                "Numerical agreement is not proof.",
                "Counterexample search claims are bounded by their declared scope.",
                "Titan is unchanged; automatic promotion is disabled.",
            ],
            "promotion_authority": False,
        })
        return {
            "artifact_bytes": payload,
            "media_type": "application/vnd.merlin.math-discovery-integrated+json",
            "summary": "Integrated mathematical discovery run recorded as research-only evidence.",
            "metadata": {"artifact_schema": INTEGRATION_SCHEMA,
                         "artifact_sha256": sha256(payload),
                         "candidate_count": len(results),
                         "promotion_authority": False},
        }

    return build_hermes_stage_handlers(
        evidence_recorder=evidence_recorder, project_id=project_id,
        research_executor=executor,
        numerical_experiment_executor=executor,
        proof_search_executor=executor,
        artifact_verifier=cace_adapter.verify_artifact,
        repository=repository, commit_sha=commit_sha,
        requester_id=requester_id,
    )


def build_default_local_math_discovery_handlers(
    *, repository_root: str | Path, evidence_recorder: ResearchEvidenceRecorder,
    project_id: str, repository: str, commit_sha: str, requester_id: str,
    cace_adapter: Any,
) -> dict[str, Callable[..., Mapping[str, Any]]]:
    """Wire the repository's actual RK4 and finite cyclic search implementations."""
    from merlin.math_discovery_backends import (
        COUNTEREXAMPLE_ENGINE, COUNTEREXAMPLE_ENGINE_VERSION,
        RK4_ENGINE, RK4_ENGINE_VERSION, default_runtime_environment,
        finite_cyclic_translation_search, rk4_solver, round_robin_ideonomy_claim,
    )
    return build_integrated_math_discovery_handlers(
        repository_root=repository_root,
        evidence_recorder=evidence_recorder,
        project_id=project_id,
        repository=repository,
        commit_sha=commit_sha,
        requester_id=requester_id,
        cace_adapter=cace_adapter,
        numerical_solver=rk4_solver,
        counterexample_searcher=finite_cyclic_translation_search,
        ideonomy_claim_factory=round_robin_ideonomy_claim,
        numerical_environment=default_runtime_environment(),
        numerical_engine_version=RK4_ENGINE_VERSION,
        numerical_tool_version="python-standard-library",
        counterexample_engine_version=COUNTEREXAMPLE_ENGINE_VERSION,
        counterexample_tool_version="python-integer-enumeration/1",
    )


__all__ = [
    "INTEGRATION_SCHEMA", "IdeonomyConjectureAdapter", "LeanProject",
    "discover_lean_project", "LeanCompilerAdapter",
    "ReproducibleNumericalAdapter", "BoundedCounterexampleAdapter",
    "build_integrated_math_discovery_handlers",
    "build_default_local_math_discovery_handlers",
]
