#include "expert_robot/growth/cace_evidence.hpp"
#include "expert_robot/growth/generation_lineage.hpp"
#include "expert_robot/sha256.hpp"

#include <cassert>
#include <filesystem>
#include <stdexcept>
#include <string>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::growth;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-cace-evidence.sqlite3";
    std::filesystem::remove(db);

    GenerationLineageStore store(db);

    (void)store.record_candidate(
        GenerationCandidate{
            .generation_id = "generation-cace-0001",
            .parent_generation_id = "",
            .source_tree_hash = sha256_hex("source"),
            .model_manifest_hash = sha256_hex("model"),
            .config_hash = sha256_hex("config"),
            .rationale = "candidate requiring external verification"
        });

    // Independent hidden/ablation evidence and external approval alone would
    // normally make this candidate promotable.
    (void)store.record_evaluation(
        EvaluationRecord{
            .generation_id = "generation-cace-0001",
            .evaluator = "hidden-ablation-v1",
            .evidence_hash = sha256_hex("hidden-ablation"),
            .recommend_keep = true,
            .verification_ok = true,
            .efficiency_ok = true,
            .diversity_ok = true,
            .verified_rate_delta = 0.08,
            .cost_per_verified_ratio = 0.91
        });
    (void)store.record_promotion_decision(
        PromotionDecision{
            .generation_id = "generation-cace-0001",
            .actor = "owner-policy-boundary",
            .approved = true,
            .reason = "independent evaluation accepted",
            .evidence_hash = sha256_hex("external-approval")
        });

    auto readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.promotable());

    // Planning a required formal CACE check immediately blocks promotion,
    // before external execution has produced any result.
    const auto requirement =
        record_cace_verification_requirement(
            store,
            "generation-cace-0001",
            "cace.formal.exact_pin_lean_preflight",
            sha256_hex("admitted-cace-request"));
    assert(requirement.sequence > 0);
    assert(requirement.required_for_promotion);
    assert(!requirement.passed);

    readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.has_required_gate_evidence);
    assert(readiness.blocking_gate_failure);
    assert(!readiness.promotable());

    CaceEvaluationEvidence formal_fail{
        .request_id = "candidate-001-cace",
        .capability_id =
            "cace.formal.exact_pin_lean_preflight",
        .source_commit =
            "ffffffffffffffffffffffffffffffffffffffff",
        .cace_commit =
            "0e7aa229d3bb57174e281b883ee8af5445f15f75",
        .evidence_sha256 = sha256_hex("raw-failed-evidence"),
        .result_sha256 = sha256_hex("failed-result"),
        .evaluation_evidence_hash =
            sha256_hex("failed-broker-envelope"),
        .passed = false,
        .qualification_capability = true,
        .qualification_evidence = false,
        .authority = "qualification-only",
        .promotion_authority = false,
        .monetary_cost = "free",
        .wall_seconds = 18,
        .lean_checks = 2
    };

    const auto failed =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            formal_fail);
    assert(failed.evaluation.sequence > 0);
    assert(!failed.evaluation.recommend_keep);
    assert(!failed.evaluation.verification_ok);
    assert(failed.verification_gate.has_value());
    assert(!failed.verification_gate->passed);

    readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.blocking_gate_failure);
    assert(!readiness.promotable());

    // A later broker-validated pass for the same required gate satisfies it,
    // while remaining unable to recommend the generation.
    auto formal_pass = formal_fail;
    formal_pass.evidence_sha256 =
        sha256_hex("raw-passing-evidence");
    formal_pass.result_sha256 =
        sha256_hex("passing-result");
    formal_pass.evaluation_evidence_hash =
        sha256_hex("passing-broker-envelope");
    formal_pass.passed = true;
    formal_pass.qualification_evidence = true;

    const auto passed =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            formal_pass);
    assert(passed.evaluation.verification_ok);
    assert(!passed.evaluation.recommend_keep);
    assert(!passed.evaluation.efficiency_ok);
    assert(!passed.evaluation.diversity_ok);
    assert(passed.verification_gate.has_value());
    assert(passed.verification_gate->passed);

    readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.has_required_gate_evidence);
    assert(!readiness.blocking_gate_failure);
    assert(readiness.promotable());

    // Latest gate state wins: a later regression blocks promotion again.
    auto later_fail = formal_fail;
    later_fail.request_id = "candidate-001-cace-recheck";
    later_fail.evidence_sha256 =
        sha256_hex("later-failed-evidence");
    later_fail.result_sha256 =
        sha256_hex("later-failed-result");
    later_fail.evaluation_evidence_hash =
        sha256_hex("later-failed-envelope");

    const auto recheck =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            later_fail);
    assert(recheck.verification_gate.has_value());
    assert(!recheck.verification_gate->passed);
    readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.blocking_gate_failure);
    assert(!readiness.promotable());

    // A non-qualifying capability may be logged but never creates or satisfies
    // a promotion verification gate.
    CaceEvaluationEvidence regression_pass = formal_pass;
    regression_pass.request_id = "candidate-001-regression";
    regression_pass.capability_id = "cace.regression.python";
    regression_pass.evaluation_evidence_hash =
        sha256_hex("regression-envelope");
    regression_pass.qualification_capability = false;
    regression_pass.qualification_evidence = false;

    const auto nonqual =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            regression_pass);
    assert(!nonqual.evaluation.verification_ok);
    assert(!nonqual.evaluation.recommend_keep);
    assert(!nonqual.verification_gate.has_value());

    bool rejected = false;
    try {
        auto bad = formal_pass;
        bad.promotion_authority = true;
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        auto bad = formal_pass;
        bad.qualification_evidence = false;
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        (void)record_cace_verification_requirement(
            store,
            "generation-cace-0001",
            "cace.formal.exact_pin_lean_preflight",
            "not-a-hash");
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    std::filesystem::remove(db);
    return 0;
}
