#!/usr/bin/env python3
"""Static production-readiness gate for the Expert Robot RSI release."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message, failures):
    if not condition:
        failures.append(message)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    failures = []
    collar = json.loads((ROOT / "config/collar_policy.json").read_text())
    experiment = json.loads((ROOT / "config/experiment_policy.json").read_text())
    compute = json.loads((ROOT / "config/compute_policy.json").read_text())
    math_wf = (ROOT / ".github/workflows/math-benchmark.yml").read_text()
    ci_wf = (ROOT / ".github/workflows/ci.yml").read_text()
    production_wf = (ROOT / ".github/workflows/production-rsi-qualification.yml").read_text()
    collar_wf = (ROOT / ".github/workflows/collared-rsi-generation.yml").read_text()
    candidate_wf = (ROOT / ".github/workflows/rsi-candidate-qualification.yml").read_text()

    required_files = [
        "config/formal_dependency_lock.json",
        "config/telemetry_contract.json",
        "scripts/run_collared.sh",
        "scripts/collar_vault.sh",
        "scripts/validate_cace_return.py",
        "scripts/estimate_generation_budget.py",
        "scripts/evaluate_promotion.py",
        "scripts/compare_benchmark_to_baseline.py",
        "scripts/compare_progression_to_reference.py",
        "scripts/prepare_collared_generation.sh",
        "config/benchmarks/g0_baseline.json",
        "config/benchmarks/progression_math_v2.json",
        "config/benchmarks/g2_progression_v2_baseline.json",
        "tests/collar_runtime_contract_smoke.py",
        "tests/benchmark_baseline_smoke.py",
        "tests/progression_benchmark_smoke.py",
        "tests/progression_baseline_integrity_smoke.py",
        "tests/lean/hard_math_v2_witnesses.lean",
        "config/auto_promotion_scope.json",
        "config/blind_evaluation_policy.json",
        "scripts/validate_candidate_scope.py",
        "scripts/validate_collar_evidence.py",
        "scripts/build_generation_view.py",
        "scripts/validate_blind_candidate.py",
        "tests/candidate_scope_smoke.py",
        "tests/collar_evidence_smoke.py",
        "tests/blind_generation_view_smoke.py",
        "tests/blind_candidate_smoke.py",
        ".github/workflows/rsi-candidate-qualification.yml",
        ".github/workflows/auto-promote-qualified.yml",
        "cpp/src/research_cli_main.cpp",
        "tests/promotion_workflow_smoke.py",
        "tests/research_cli_contract_smoke.py",
        "tests/collar_policy_smoke.py",
        "tests/formal_dependency_lock_smoke.py",
        ".github/workflows/cace-return-pr.yml",
    ]
    for rel in required_files:
        require((ROOT / rel).exists(), f"missing required file: {rel}", failures)

    hard = experiment["hard_limits"]
    require(hard["max_total_vcpu"] <= 30, "compute ceiling exceeds 30 vCPU", failures)
    require(
        hard["worker_vcpu"] * hard["max_parallel_workers"] <= hard["max_total_vcpu"],
        "parallel worker policy exceeds total vCPU ceiling",
        failures,
    )
    require(hard["holdout_may_tune_search"] is False, "holdout may tune search", failures)
    require("max-parallel: 1" in math_wf, "standalone benchmark is not capped at 1 worker", failures)
    require("avrea-ubuntu-latest-32-vcpu" not in math_wf, "32-vCPU runner exceeds approved ceiling", failures)
    require("name: aggregate-benchmark" in math_wf and "runs-on: avrea-ubuntu-latest-8-vcpu" in math_wf,
            "benchmark aggregation is not on Avrea", failures)
    require('branches: ["feat/**", "fix/**"]' in math_wf,
            "standalone benchmark trigger drifted", failures)
    require('branches: ["release/**"]' in production_wf,
            "production release workflow trigger drifted", failures)
    require("max-parallel: 1" in production_wf,
            "release benchmark is not capped at 1 worker", failures)
    require("release-benchmark-" in production_wf and "Require demonstrated merit" in production_wf,
            "production release does not integrate benchmark merit gating", failures)
    require("runs-on: avrea-ubuntu-latest-8-vcpu" in ci_wf, "CI is not on Avrea", failures)
    heavy_group = "group: expert-robot-avrea-heavy-v2"
    promotion_group = "group: expert-robot-avrea-rsi-promotion-v2"
    require(heavy_group in math_wf, "benchmark lacks current heavy Avrea concurrency group", failures)
    require(heavy_group in production_wf, "production qualification lacks current heavy Avrea concurrency group", failures)
    require(promotion_group in collar_wf, "collared RSI generation lacks current promotion concurrency group", failures)
    require(promotion_group in candidate_wf, "candidate qualification lacks current promotion concurrency group", failures)
    require("cancel-in-progress: false" in math_wf, "benchmark may cancel serialized heavy work", failures)
    require("cancel-in-progress: false" in production_wf, "production qualification may cancel serialized heavy work", failures)
    for label, workflow in (
        ("standalone benchmark", math_wf),
        ("production qualification", production_wf),
        ("candidate qualification", candidate_wf),
    ):
        require("progression_math_v2.json" in workflow,
                f"{label} is not using the post-G2 progression suite", failures)
        require("g2_progression_v2_baseline.json" in workflow,
                f"{label} is not bound to the frozen G2 progression baseline", failures)
    require(hard["worker_vcpu"] * 3 <= hard["max_total_vcpu"],
            "CI + heavy + promotion lanes can exceed total vCPU ceiling", failures)

    require(collar["rsi_start_allowed"] is True, "RSI start is disabled", failures)
    require(collar["user_passkey_required"] is False, "unexpected passkey dependency", failures)
    require(collar["promotion"]["automatic"] is True, "automatic merit promotion disabled", failures)
    require(collar["promotion"]["forbidden_after_trip"] is True, "trip does not forbid promotion", failures)
    require(collar["recursive_self_modification"]["authority_change"] == "same_or_less",
            "recursive modification may expand authority", failures)
    require(collar["sandbox"]["network_default"] == "none", "sandbox network is not fail-closed", failures)
    require(collar["encryption"]["key_destruction_on_trip"] is True, "trip does not destroy key", failures)

    required_gates = set(experiment["promotion"]["required_gates"])
    for gate in (
        "generation_budget_estimated", "collared_execution", "merit_demonstrated",
        "qualification_passed", "validation_improved", "blind_holdout_non_regression",
        "formal_verification_passed", "rollback_verified", "lineage_verified",
        "authority_same_or_less", "core_integrity_verified", "collar_not_tripped",
    ):
        require(gate in required_gates, f"missing promotion gate: {gate}", failures)

    # Preserve zero-spend compute policy as a release invariant.
    compute_text = json.dumps(compute)
    require("free" in compute_text.lower() or "zero" in compute_text.lower(),
            "compute policy does not encode free/zero-spend operation", failures)

    result = {
        "schema_version": 1,
        "ready": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "max_total_vcpu": hard["max_total_vcpu"],
        "max_parallel_vcpu": hard["worker_vcpu"] * hard["max_parallel_workers"],
        "worst_case_with_ci_vcpu": hard.get("worst_case_with_ci_vcpu"),
        "automatic_promotion": collar["promotion"]["automatic"],
        "authority_invariant": collar["authority_invariant"],
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
