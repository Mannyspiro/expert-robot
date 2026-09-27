#include "expert_robot/research/strategy_ablation.hpp"

#include <cassert>
#include <cmath>

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

    const auto ablations =
        generate_strategy_step_ablations(
            strategy);

    assert(ablations.size() == 3);
    assert(ablations[0].removed_index == 0);
    assert(
        ablations[0].removed_kind ==
        ProofRouteKind::RepresentationSwitch);
    assert(ablations[0].remaining_steps.size() == 2);

    assert(ablations[1].removed_index == 1);
    assert(
        ablations[1].removed_kind ==
        ProofRouteKind::RecursiveDecomposition);
    assert(
        ablations[1].ablated_signature ==
        "representation_switch -> intensify_verification");

    assert(ablations[2].removed_index == 2);
    assert(
        ablations[2].removed_kind ==
        ProofRouteKind::IntensifyVerification);

    VariantSummary full;
    full.variant = "full";
    full.cases = 20;
    full.verified = 16;
    full.total_resource_cost = 20.0;

    VariantSummary redundant = full;
    redundant.variant = "drop-reframe";

    const auto redundant_credit =
        evaluate_strategy_step_ablation(
            ablations[0],
            full,
            redundant);

    assert(redundant_credit.enough_cases);
    assert(!redundant_credit.verification_critical);
    assert(!redundant_credit.efficiency_critical);
    assert(!redundant_credit.important);
    assert(
        std::abs(
            redundant_credit.importance_score) <
        1e-12);

    VariantSummary verification_loss = full;
    verification_loss.variant =
        "drop-decomposition";
    verification_loss.verified = 10;
    verification_loss.total_resource_cost = 18.0;

    const auto critical =
        evaluate_strategy_step_ablation(
            ablations[1],
            full,
            verification_loss);

    assert(critical.enough_cases);
    assert(critical.verification_critical);
    assert(critical.important);
    assert(critical.verified_rate_drop > 0.25);
    assert(critical.importance_score > 0.20);

    VariantSummary expensive = full;
    expensive.variant =
        "drop-verification";
    expensive.total_resource_cost = 32.0;

    const auto efficiency =
        evaluate_strategy_step_ablation(
            ablations[2],
            full,
            expensive);

    assert(efficiency.enough_cases);
    assert(!efficiency.verification_critical);
    assert(efficiency.efficiency_critical);
    assert(efficiency.important);
    assert(efficiency.ablated_cost_ratio > 1.5);
    assert(efficiency.importance_score > 0.05);

    VariantSummary tiny = full;
    tiny.cases = 2;
    tiny.verified = 2;

    const auto insufficient =
        evaluate_strategy_step_ablation(
            ablations[1],
            tiny,
            verification_loss);

    assert(!insufficient.enough_cases);
    assert(!insufficient.important);
    assert(insufficient.importance_score == 0.0);

    ResearchStrategyPlan one_step{
        .strategy_id = "one",
        .signature = "recursive_decomposition",
        .title = "one",
        .steps = {
            ProofRouteKind::RecursiveDecomposition
        }
    };
    assert(
        generate_strategy_step_ablations(
            one_step).empty());

    return 0;
}
