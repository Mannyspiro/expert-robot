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
from merlin.glyph_normalizer import GlyphNormalizer, RewriteRule
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
        "observatory_benchmarks": inspect.getmodule(run_core_benchmarks),
    }
    source_hashes = {name: _module_sha256(module) for name, module in sorted(modules.items())}
    domains = {
        "geometry": geometry_result,
        "xmg": xmg_result,
        "equation_atlas": equation_result,
        "cad": cad_result,
    }
    negative_controls = run_negative_controls()
    payload = {
        "schema": "merlin-cross-domain-benchmark-receipt-v1",
        "source_commit": commit_sha,
        "source_sha256": source_hashes,
        "domains": domains,
        "negative_controls": negative_controls,
        "all_passed": all(item["passed"] for item in domains.values()) and negative_controls["all_detected"],
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


def run_negative_controls() -> dict[str, Any]:
    """Prove that each domain fixture detects one deliberately invalid case."""
    # Geometry: singular frame matrices must be rejected at construction.
    try:
        geometry.RepresentationGraph([
            geometry.Frame("valid", geometry.identity(2)),
            geometry.Frame("singular", geometry.matrix([[1, 2], [2, 4]])),
        ])
        geometry_detected = False
    except ValueError:
        geometry_detected = True

    # XMG: inject a deliberately wrong double-negation rewrite and check a
    # finite integer holdout; the incorrect rewrite must be distinguished.
    registry = glyph_foundry.build_default_registry()
    negate = registry.primitive_expr("NEGATE_INT")
    expression = registry.compose(negate, negate)
    bad_rule = RewriteRule(
        "NEGATIVE_CONTROL_WRONG_DOUBLE_NEGATION",
        "deliberately incorrect replacement used only by this test",
        lambda e: (
            e.op == "compose"
            and e.args[0].op == "primitive" and e.args[0].args == ("NEGATE_INT",)
            and e.args[1].op == "primitive" and e.args[1].args == ("NEGATE_INT",)
        ),
        lambda e, r: r.primitive_expr("NEGATE_INT"),
    )
    bad_normalized = GlyphNormalizer(registry, rules=(bad_rule,)).normalize(expression)
    xmg_detected = any(
        expression.evaluate(x, registry) != bad_normalized.expression.evaluate(x, registry)
        for x in (-7, -1, 1, 7)
    )

    # Equation Atlas: a length/time equality is dimensionally inconsistent.
    try:
        dimensions.require_same(dimensions.LENGTH, dimensions.TIME, "negative_control_length_equals_time")
        equation_detected = False
    except ValueError:
        equation_detected = True

    # CAD: overlapping world AABBs must be reported by the existing validator.
    overlap = cad_assembly.CADAssembly(
        "observatory-overlap-negative-control",
        (
            cad_assembly.AssemblyComponent("A1"),
            cad_assembly.AssemblyComponent("B1"),
        ),
    )
    overlap_issues = cad_assembly.validate_assembly(project_fixture(), overlap)
    cad_detected = any(issue.code == "AABB_INTERFERENCE" for issue in overlap_issues)

    return {
        "geometry_singular_frame_rejected": geometry_detected,
        "xmg_wrong_rewrite_rejected_by_holdout": xmg_detected,
        "equation_dimension_mismatch_rejected": equation_detected,
        "cad_overlap_reported": cad_detected,
        "all_detected": all((geometry_detected, xmg_detected, equation_detected, cad_detected)),
        "claim_scope": "controlled software negative controls; not adversarial validation of all input space",
    }


def project_fixture() -> engineering_ir.EngineeringProject:
    """Return the same canonical CAD fixture used by the positive benchmark."""
    return engineering_ir.EngineeringProject(
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


def run_repeated_benchmarks(commit_sha: str, repeats: int = 3) -> dict[str, Any]:
    """Repeat the complete suite and report deterministic domain-level stability."""
    if repeats < 2 or repeats > 25:
        raise ValueError("repeats must be between 2 and 25")
    receipts = [run_core_benchmarks(commit_sha) for _ in range(repeats)]
    domain_hashes: dict[str, list[str]] = {}
    for domain in ("geometry", "xmg", "equation_atlas", "cad"):
        domain_hashes[domain] = [
            _sha256(_canonical(receipt["domains"][domain]).encode("utf-8"))
            for receipt in receipts
        ]
    stable = {domain: len(set(hashes)) == 1 for domain, hashes in domain_hashes.items()}
    return {
        "schema": "merlin-repeated-benchmark-receipt-v1",
        "source_commit": commit_sha,
        "repeats": repeats,
        "run_receipt_sha256": [receipt["receipt_sha256"] for receipt in receipts],
        "domain_receipt_sha256": domain_hashes,
        "domain_stable": stable,
        "all_passed": all(receipt["all_passed"] for receipt in receipts) and all(stable.values()),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Merlin cross-domain benchmark receipts")
    parser.add_argument("--commit", required=True, help="40-character source Git commit")
    parser.add_argument("--output", required=True, help="Path for canonical JSON receipt")
    args = parser.parse_args()
    receipt = write_benchmark_receipt(args.output, args.commit)
    repeated = run_repeated_benchmarks(args.commit, repeats=3)
    repeat_path = Path(args.output).with_name("merlin-cross-domain-repeatability.json")
    repeat_path.write_text(_canonical(repeated) + "\\n", encoding="utf-8")
    print(json.dumps({
        "receipt_sha256": receipt["receipt_sha256"],
        "all_passed": receipt["all_passed"],
        "negative_controls_detected": receipt["negative_controls"]["all_detected"],
        "repeatability": repeated["all_passed"],
        "domains": {name: value["passed"] for name, value in receipt["domains"].items()},
    }, sort_keys=True))
    if not receipt["all_passed"] or not repeated["all_passed"]:
        raise SystemExit(1)

