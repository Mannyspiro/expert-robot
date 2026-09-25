#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/growth/ablation_evidence.hpp"
#include "expert_robot/sha256.hpp"

#include <cassert>
#include <filesystem>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::eval;
    using namespace expert_robot::growth;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-ablation-lineage.sqlite3";
    std::filesystem::remove(db);

    GenerationLineageStore store(db);

    (void)store.record_candidate(
        GenerationCandidate{
            .generation_id = "generation-0000",
            .parent_generation_id = "",
            .source_tree_hash = sha256_hex("source"),
            .model_manifest_hash = sha256_hex("models"),
            .config_hash = sha256_hex("config"),
            .rationale = "baseline candidate"
        });

    VariantSummary baseline;
    baseline.variant = "baseline";
    baseline.cases = 20;
    baseline.verified = 10;
    baseline.total_resource_cost = 20.0;
    baseline.total_duplicate_candidates = 4;

    VariantSummary candidate;
    candidate.variant = "route-planner";
    candidate.cases = 20;
    candidate.verified = 13;
    candidate.total_resource_cost = 21.0;
    candidate.total_duplicate_candidates = 3;

    const auto result =
        compare_variants(
            baseline,
            candidate,
            AblationPolicy{
                .minimum_cases = 10,
                .maximum_verified_rate_regression = 0.0,
                .maximum_cost_multiplier_without_accuracy_gain = 1.10,
                .meaningful_verified_rate_gain = 0.05,
                .maximum_duplicate_rate_increase = 0.10
            });

    assert(result.enough_cases);
    assert(result.verification_ok);
    assert(result.efficiency_ok);
    assert(result.diversity_ok);
    assert(result.recommend_keep);

    const auto hash1 =
        ablation_evidence_hash(result);
    const auto hash2 =
        ablation_evidence_hash(result);
    assert(hash1 == hash2);
    assert(hash1.size() == 64);

    const auto evidence =
        record_ablation_evidence(
            store,
            "generation-0000",
            "math_eval_v1",
            result);

    assert(evidence.recommend_keep);
    assert(evidence.verification_ok);
    assert(evidence.efficiency_ok);
    assert(evidence.diversity_ok);
    assert(evidence.evidence_hash == hash1);

    // Evaluation evidence alone remains insufficient for promotion.
    auto readiness =
        store.readiness(
            "generation-0000");
    assert(readiness.has_positive_evaluation);
    assert(!readiness.externally_approved);
    assert(!readiness.promotable());

    (void)store.record_promotion_decision(
        PromotionDecision{
            .generation_id = "generation-0000",
            .actor = "owner-policy-boundary",
            .approved = true,
            .reason = "explicit external approval",
            .evidence_hash = sha256_hex("approval")
        });

    readiness =
        store.readiness(
            "generation-0000");
    assert(readiness.promotable());

    // Too few cases cannot become positive promotion evidence even if raw
    // point estimates look better.
    VariantSummary tiny_baseline = baseline;
    tiny_baseline.cases = 2;
    tiny_baseline.verified = 1;

    VariantSummary tiny_candidate = candidate;
    tiny_candidate.cases = 2;
    tiny_candidate.verified = 2;

    const auto tiny =
        compare_variants(
            tiny_baseline,
            tiny_candidate);

    const auto tiny_evidence =
        record_ablation_evidence(
            store,
            "generation-0000",
            "tiny_eval",
            tiny);

    assert(!tiny_evidence.recommend_keep);

    std::filesystem::remove(db);
    return 0;
}
