#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/research/strategy_ablation.hpp"
#include "expert_robot/research/strategy_qualification.hpp"

#include <cassert>

int main() {
    using namespace expert_robot::eval;
    using namespace expert_robot::research;

    const std::vector<ProofRouteKind> steps{
        ProofRouteKind::RepresentationSwitch,
        ProofRouteKind::RecursiveDecomposition,
        ProofRouteKind::IntensifyVerification
    };

    const std::string signature =
        research_strategy_signature(
            steps);

    ResearchStrategyPlan strategy{
        .strategy_id =
            research_strategy_id(
                signature),
        .signature =
            signature,
        .title =
            research_strategy_title(
                steps),
        .steps =
            steps,
        .base_score = 0.80,
        .final_score = 0.80
    };

    ResearchStrategyExperience experience{
        .strategy_id =
            strategy.strategy_id,
        .signature =
            strategy.signature,
        .domain = "geometry",
        .attempts = 12,
        .verified_progresses = 9,
        .target_verifications = 9,
        .dead_end_escapes = 8,
        .total_resource_cost = 3.0
    };

    VariantSummary baseline;
    baseline.variant = "sequence_memory::holdout";
    baseline.cases = 20;
    baseline.verified = 10;
    baseline.total_resource_cost = 20.0;
    baseline.total_ideas_generated = 20;
    baseline.total_duplicate_candidates = 2;

    VariantSummary candidate;
    candidate.variant = "strategy_memory::holdout";
    candidate.cases = 20;
    candidate.verified = 14;
    candidate.total_resource_cost = 22.0;
    candidate.total_ideas_generated = 20;
    candidate.total_duplicate_candidates = 2;

    const auto holdout =
        compare_variants(
            baseline,
            candidate);
    assert(holdout.recommend_keep);

    const auto ablations =
        generate_strategy_step_ablations(
            strategy);
    assert(ablations.size() == 3);

    VariantSummary full;
    full.variant = "full-strategy";
    full.cases = 20;
    full.verified = 16;
    full.total_resource_cost = 20.0;

    VariantSummary drop_reframe = full;
    drop_reframe.variant = "drop-reframe";
    drop_reframe.verified = 12;
    drop_reframe.total_resource_cost = 20.0;

    VariantSummary drop_decompose = full;
    drop_decompose.variant = "drop-decompose";
    drop_decompose.verified = 10;
    drop_decompose.total_resource_cost = 18.0;

    VariantSummary drop_verify = full;
    drop_verify.variant = "drop-verify";
    drop_verify.total_resource_cost = 32.0;

    std::vector<StrategyStepCredit> credits{
        evaluate_strategy_step_ablation(
            ablations[0],
            full,
            drop_reframe),
        evaluate_strategy_step_ablation(
            ablations[1],
            full,
            drop_decompose),
        evaluate_strategy_step_ablation(
            ablations[2],
            full,
            drop_verify)
    };

    for (const auto& credit : credits) {
        assert(credit.enough_cases);
        assert(credit.important);
    }

    const auto packet =
        build_strategy_qualification_packet(
            strategy,
            experience,
            holdout,
            credits);

    assert(packet.experience_sufficient);
    assert(packet.holdout_sufficient);
    assert(packet.step_evidence_sufficient);
    assert(packet.ready_for_external_review);
    assert(packet.requires_explicit_promotion);
    assert(packet.experience_hash.size() == 64);
    assert(packet.holdout_hash.size() == 64);
    assert(packet.step_credit_hash.size() == 64);
    assert(packet.packet_hash.size() == 64);

    const auto packet_again =
        build_strategy_qualification_packet(
            strategy,
            experience,
            holdout,
            credits);

    assert(
        packet.packet_hash ==
        packet_again.packet_hash);

    // If one step can be removed with no verified or efficiency loss, the
    // over-complex strategy is not qualification-ready.
    VariantSummary redundant = full;
    redundant.variant = "drop-redundant";

    auto redundant_credits = credits;
    redundant_credits[0] =
        evaluate_strategy_step_ablation(
            ablations[0],
            full,
            redundant);

    assert(
        !redundant_credits[0].important);

    const auto prune_packet =
        build_strategy_qualification_packet(
            strategy,
            experience,
            holdout,
            redundant_credits);

    assert(prune_packet.experience_sufficient);
    assert(prune_packet.holdout_sufficient);
    assert(!prune_packet.step_evidence_sufficient);
    assert(!prune_packet.ready_for_external_review);
    assert(prune_packet.requires_explicit_promotion);

    // Strong holdout evidence is not enough when completed execution history
    // itself is too sparse.
    auto sparse_experience =
        experience;
    sparse_experience.attempts = 2;
    sparse_experience.verified_progresses = 2;
    sparse_experience.target_verifications = 2;
    sparse_experience.total_resource_cost = 0.4;

    const auto sparse_packet =
        build_strategy_qualification_packet(
            strategy,
            sparse_experience,
            holdout,
            credits);

    assert(!sparse_packet.experience_sufficient);
    assert(!sparse_packet.ready_for_external_review);

    return 0;
}
