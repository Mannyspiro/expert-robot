"""Deterministic cross-domain benchmark receipts for Merlin's existing math systems.

These are regression/consistency observations, not empirical validation or
fabrication certification. Every receipt is pinned to a caller-supplied source
commit and hashes the imported implementation files.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
from pathlib import Path
from typing import Any

from merlin import representation_graph as geometry
from merlin import glyph_foundry, glyph_normalizer
from merlin.equation_atlas import dimensions, symbolic_checks
from merlin.equation_atlas.experiments import baseline
from merlin import cad_assembly, engineering_ir, engineering_project_store


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False, default=str)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _module_sha256(module: object) -> str:
    source = inspect.getsourcefile(module)
    if not source:
        raise ValueError(f"cannot locate source file for {module!r}")
    return _sha256(Path(source).read_bytes())


def run_core_benchmarks(commit_sha: str) -> dict[str, Any]:
    """Run one deterministic smoke benchmark in geometry, XMG, equations and CAD."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("commit_sha must be a lowercase 40-character Git SHA")

    # Geometry: exact rational frame transitions and basis-invariant spectrum.
    frames = geometry.RepresentationGraph([
        geometry.Frame("cartesian", geometry.identity(2)),
        geometry.Frame("sheared", geometry.matrix([[1, 1], [0, 1]])),
        geometry.Frame("rotated", geometry.matrix([[0, -1], [1, 0]])),
    ])
    path_audit = frames.audit_path(["cartesian", "sheared", "rotated"])
    operator = geometry.matrix([[2, 1], [0, 3]])
    signatures = {
        frame_id: [str(x) for x in frames.spectral_signature(operator, frame_id)]
        for frame_id in sorted(frames.frames)
    }
    geometry_pass = path_audit.consistent and len(set(tuple(v) for v in signatures.values())) == 1
    geometry_result = {
        "passed": geometry_pass,
        "checks": {
            "composed_transition_equals_direct": path_audit.consistent,
            "trace_determinant_invariant_across_frames": len(set(tuple(v) for v in signatures.values())) == 1,
        },
        "spectral_signatures": signatures,
        "dimension": frames.dimension,
    }

    # XMG: typed expression evaluation and candidate rewrite normalization.
    registry = glyph_foundry.build_default_registry()
    negate = registry.primitive_expr("NEGATE_INT")
    double_negation = registry.compose(negate, negate)
    normalizer = glyph_normalizer.GlyphNormalizer(registry)
    normalized = normalizer.normalize(double_negation)
    rewrite_pass = (
        normalized.complete
        and normalized.expression == registry.identity(glyph_foundry.TypeRef("Int"))
        and all(double_negation.evaluate(x, registry) == normalized.expression.evaluate(x, registry)
                for x in range(-32, 33))
    )
    xmg_result = {
        "passed": rewrite_pass,
        "checks": {
            "normalization_complete": normalized.complete,
            "double_negation_matches_identity_on_integer_holdout": rewrite_pass,
            "rewrite_trace_nonempty": bool(normalized.steps),
        },
        "expression_fingerprint": double_negation.fingerprint(),
        "normal_form_fingerprint": normalized.expression.fingerprint(),
        "rewrite_rule_ids": [step.rule_id for step in normalized.steps],
        "claim_scope": "candidate rewrite equivalence on finite holdout; not a formal proof",
    }
    xmg_result["passed"] = all(xmg_result["checks"].values())

    # Equation Atlas: dimensional, symbolic and deterministic numerical checks.
    dimension_results = dimensions.core_dimension_checks()
    symbolic_results = symbolic_checks.run_symbolic_checks()
    baseline_a = baseline.run()
    baseline_b = baseline.run()
    equation_pass = baseline_a == baseline_b and bool(dimension_results) and bool(symbolic_results)
    equation_result = {
        "passed": equation_pass,
        "checks": {
            "dimension_checks_nonempty": bool(dimension_results),
            "symbolic_checks_nonempty": bool(symbolic_results),
            "numerical_baseline_reproducible": baseline_a == baseline_b,
        },
        "dimension_check_count": len(dimension_results),
        "symbolic_check_ids": sorted(symbolic_results),
        "baseline_sha256": _sha256(_canonical(baseline_a).encode("utf-8")),
        "claim_scope": "model consistency and deterministic regression checks; not empirical validation",
    }

    # CAD: valid typed Engineering IR, proper rigid transform, deterministic export.
    project = engineering_ir.EngineeringProject(
        name="merlin-observatory-cad-fixture",
        units="mm",
        parts=(
            engineering_ir.Part("A1", "housing", (engineering_ir.Pin("1", "mount"),),
                                size_mm=(20.0, 20.0, 10.0)),
            engineering_ir.Part("B1", "board", (engineering_ir.Pin("1", "io"),),
                                size_mm=(10.0, 10.0, 2.0)),
        ),
        nets=(),
        metadata={"fixture": "deterministic-observatory-v1"},
    )
    assembly = cad_assembly.CADAssembly(
        "observatory-separated-fixture",
        (
            cad_assembly.AssemblyComponent("A1"),
            cad_assembly.AssemblyComponent(
                "B1", cad_assembly.Transform3D(translation_mm=(40.0, 0.0, 0.0))
            ),
        ),
    )
    issues = cad_assembly.validate_assembly(project, assembly)
    export_a = cad_assembly.export_assembly_openscad(project, assembly)
    export_b = cad_assembly.export_assembly_openscad(project, assembly)
    cad_pass = (
        not any(issue.severity == "error" for issue in issues)
        and not any(issue.code == "AABB_INTERFERENCE" for issue in issues)
        and export_a == export_b
    )
    cad_result = {
        "passed": cad_pass,
        "checks": {
            "engineering_ir_valid": not any(issue.severity == "error" for issue in issues),
            "separated_fixture_has_no_aabb_interference": not any(
                issue.code == "AABB_INTERFERENCE" for issue in issues
            ),
            "openscad_export_reproducible": export_a == export_b,
        },
        "engineering_project_sha256": engineering_project_store.project_hash(project),
        "openscad_export_sha256": _sha256(export_a.encode("utf-8")),
        "issue_codes": [issue.code for issue in issues],
        "claim_scope": "typed IR and conservative AABB checks; not exact B-rep collision or fabrication sign-off",
    }

    modules = {
        "geometry": geometry,
        "xmg_foundry": glyph_foundry,
        "xmg_normalizer": glyph_normalizer,
        "equation_dimensions": dimensions,
        "equation_symbolic_checks": symbolic_checks,
        "equation_baseline": baseline,
        "cad_assembly": cad_assembly,
        "engineering_ir": engineering_ir,
        "engineering_project_store": engineering_project_store,
    }
    source_hashes = {name: _module_sha256(module) for name, module in sorted(modules.items())}
    domains = {
        "geometry": geometry_result,
        "xmg": xmg_result,
        "equation_atlas": equation_result,
        "cad": cad_result,
    }
    payload = {
        "schema": "merlin-cross-domain-benchmark-receipt-v1",
        "source_commit": commit_sha,
        "source_sha256": source_hashes,
        "domains": domains,
        "all_passed": all(item["passed"] for item in domains.values()),
    }
    payload["receipt_sha256"] = _sha256(_canonical(payload).encode("utf-8"))
    return payload


def write_benchmark_receipt(path: str | Path, commit_sha: str) -> dict[str, Any]:
    """Write a canonical JSON receipt and return the exact object written."""
    receipt = run_core_benchmarks(commit_sha)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_canonical(receipt) + "\n", encoding="utf-8")
    return receipt
