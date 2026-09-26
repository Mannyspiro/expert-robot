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

    VariantSummary validation_baseline;
    validation_baseline.variant = "sequence_memory::validation";
    validation_baseline.cases = 20;
    validation_baseline.verified = 10;
    validation_baseline.total_resource_cost = 20.0;
    validation_baseline.total_ideas_generated = 20;
    validation_baseline.total_duplicate_candidates = 2;

    VariantSummary validation_candidate;
    validation_candidate.variant = "strategy_memory::validation";
    validation_candidate.cases = 20;
    validation_candidate.verified = 14;
    validation_candidate.total_resource_cost = 22.0;
    validation_candidate.total_ideas_generated = 20;
    validation_candidate.total_duplicate_candidates = 2;

    const auto validation =
        compare_variants(
            validation_baseline,
            validation_candidate);
    assert(validation.recommend_keep);

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
            validation,
            credits);

    assert(packet.experience_sufficient);
    assert(packet.validation_sufficient);
    assert(!packet.holdout_sufficient);
    assert(packet.step_evidence_sufficient);
    assert(packet.ready_for_holdout_confirmation);
    assert(!packet.ready_for_external_review);
    assert(!packet.holdout_ablation.has_value());
    assert(packet.requires_explicit_promotion);
    assert(packet.experience_hash.size() == 64);
    assert(packet.validation_hash.size() == 64);
    assert(packet.holdout_hash.empty());
    assert(packet.step_credit_hash.size() == 64);
    assert(packet.packet_hash.size() == 64);

    const auto confirmed =
        confirm_strategy_holdout(
            packet,
            holdout);

    assert(confirmed.holdout_ablation.has_value());
    assert(confirmed.holdout_sufficient);
    assert(confirmed.ready_for_external_review);
    assert(confirmed.holdout_hash.size() == 64);
    assert(
        confirmed.packet_hash !=
        packet.packet_hash);

    const auto packet_again =
        build_strategy_qualification_packet(
            strategy,
            experience,
            validation,
            credits);
    const auto confirmed_again =
        confirm_strategy_holdout(
            packet_again,
            holdout);

    assert(
        confirmed.packet_hash ==
        confirmed_again.packet_hash);

    bool second_holdout_rejected = false;
    try {
        (void)confirm_strategy_holdout(
            confirmed,
            holdout);
    } catch (const std::logic_error&) {
        second_holdout_rejected = true;
    }
    assert(second_holdout_rejected);

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
            validation,
            redundant_credits);

    assert(prune_packet.experience_sufficient);
    assert(prune_packet.validation_sufficient);
    assert(!prune_packet.step_evidence_sufficient);
    assert(!prune_packet.ready_for_holdout_confirmation);
    assert(!prune_packet.ready_for_external_review);
    assert(prune_packet.requires_explicit_promotion);

    bool premature_holdout_rejected = false;
    try {
        (void)confirm_strategy_holdout(
            prune_packet,
            holdout);
    } catch (const std::logic_error&) {
        premature_holdout_rejected = true;
    }
    assert(premature_holdout_rejected);

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
            validation,
            credits);

    assert(!sparse_packet.experience_sufficient);
    assert(!sparse_packet.ready_for_holdout_confirmation);
    assert(!sparse_packet.ready_for_external_review);

    bool sparse_holdout_rejected = false;
    try {
        (void)confirm_strategy_holdout(
            sparse_packet,
            holdout);
    } catch (const std::logic_error&) {
        sparse_holdout_rejected = true;
    }
    assert(sparse_holdout_rejected);

    // Validation failure blocks access to holdout even when history and step
    // evidence are otherwise strong.
    VariantSummary weak_validation_candidate =
        validation_candidate;
    weak_validation_candidate.verified = 8;
    weak_validation_candidate.total_resource_cost = 24.0;

    const auto weak_validation =
        compare_variants(
            validation_baseline,
            weak_validation_candidate);
    assert(!weak_validation.recommend_keep);

    const auto validation_reject_packet =
        build_strategy_qualification_packet(
            strategy,
            experience,
            weak_validation,
            credits);

    assert(!validation_reject_packet.validation_sufficient);
    assert(!validation_reject_packet.ready_for_holdout_confirmation);

    bool validation_holdout_rejected = false;
    try {
        (void)confirm_strategy_holdout(
            validation_reject_packet,
            holdout);
    } catch (const std::logic_error&) {
        validation_holdout_rejected = true;
    }
    assert(validation_holdout_rejected);

    return 0;
}
