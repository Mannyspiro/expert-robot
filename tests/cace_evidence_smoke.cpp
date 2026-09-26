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

    const CaceEvaluationEvidence formal_pass{
        .request_id = "candidate-001-cace",
        .capability_id =
            "cace.formal.exact_pin_lean_preflight",
        .source_commit =
            "ffffffffffffffffffffffffffffffffffffffff",
        .cace_commit =
            "0e7aa229d3bb57174e281b883ee8af5445f15f75",
        .evidence_sha256 = sha256_hex("raw-evidence"),
        .result_sha256 = sha256_hex("result"),
        .evaluation_evidence_hash =
            sha256_hex("broker-validated-envelope"),
        .passed = true,
        .qualification_evidence = true,
        .authority = "qualification-only",
        .promotion_authority = false,
        .monetary_cost = "free",
        .wall_seconds = 18,
        .lean_checks = 2
    };

    const auto recorded =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            formal_pass);

    assert(recorded.sequence > 0);
    assert(
        recorded.evaluator ==
        "cace_tool_broker:cace.formal.exact_pin_lean_preflight");
    assert(
        recorded.evidence_hash ==
        formal_pass.evaluation_evidence_hash);
    assert(recorded.verification_ok);
    assert(!recorded.recommend_keep);
    assert(!recorded.efficiency_ok);
    assert(!recorded.diversity_ok);

    // Verifier evidence is recorded, but it cannot make the candidate a
    // positive evaluation or promotion-ready by itself.
    auto readiness =
        store.readiness("generation-cace-0001");
    assert(!readiness.has_positive_evaluation);
    assert(!readiness.verification_ok);
    assert(!readiness.promotable());

    // Even an external approval cannot compensate for missing independent
    // positive ablation/hidden-evaluation evidence.
    (void)store.record_promotion_decision(
        PromotionDecision{
            .generation_id = "generation-cace-0001",
            .actor = "owner-policy-boundary",
            .approved = true,
            .reason = "premature approval for guardrail test",
            .evidence_hash = sha256_hex("external-approval")
        });

    readiness =
        store.readiness("generation-cace-0001");
    assert(readiness.externally_approved);
    assert(!readiness.has_positive_evaluation);
    assert(!readiness.promotable());

    // Non-qualifying CACE capabilities may be logged as evaluation evidence,
    // but their pass must not be marked verification_ok.
    CaceEvaluationEvidence regression_pass = formal_pass;
    regression_pass.request_id = "candidate-001-regression";
    regression_pass.capability_id = "cace.regression.python";
    regression_pass.evaluation_evidence_hash =
        sha256_hex("regression-envelope");
    regression_pass.qualification_evidence = false;

    const auto nonqual =
        record_cace_evaluation_evidence(
            store,
            "generation-cace-0001",
            regression_pass);
    assert(!nonqual.verification_ok);
    assert(!nonqual.recommend_keep);

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
        bad.authority = "promotion";
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        auto bad = formal_pass;
        bad.monetary_cost = "paid";
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        auto bad = formal_pass;
        bad.passed = false;
        bad.qualification_evidence = true;
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    rejected = false;
    try {
        auto bad = formal_pass;
        bad.evaluation_evidence_hash = "not-a-hash";
        (void)record_cace_evaluation_evidence(
            store, "generation-cace-0001", bad);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    std::filesystem::remove(db);
    return 0;
}
