#pragma once

#include "expert_robot/eval/math_eval.hpp"
#include "expert_robot/research/strategy_planner.hpp"

#include <cstddef>
#include <string>
#include <vector>

namespace expert_robot::research {

struct StrategyStepAblation {
    std::string parent_strategy_id;
    std::string parent_signature;

    std::size_t removed_index{0};
    ProofRouteKind removed_kind{
        ProofRouteKind::ReuseVerifiedTheorem};

    std::vector<ProofRouteKind> remaining_steps;
    std::string ablated_signature;
    std::string ablated_strategy_id;
};

struct StrategyStepCreditPolicy {
    long long minimum_cases{10};

    // Removing a step must reduce verified rate by at least this much before
    // the step is called verification-critical.
    double meaningful_verified_drop{0.05};

    // If verification rate is unchanged, a step can still earn bounded credit
    // when removing it makes verified work materially more expensive.
    double meaningful_cost_ratio{1.10};

    double verification_weight{0.80};
    double efficiency_weight{0.20};
};

struct StrategyStepCredit {
    StrategyStepAblation ablation;

    double verified_rate_drop{0.0};
    double ablated_cost_ratio{1.0};
    double importance_score{0.0};

    bool enough_cases{false};
    bool verification_critical{false};
    bool efficiency_critical{false};
    bool important{false};
};

void validate_strategy_step_credit_policy(
    const StrategyStepCreditPolicy& policy);

[[nodiscard]] std::vector<StrategyStepAblation>
generate_strategy_step_ablations(
    const ResearchStrategyPlan& strategy);

[[nodiscard]] StrategyStepCredit evaluate_strategy_step_ablation(
    const StrategyStepAblation& ablation,
    const eval::VariantSummary& full_strategy,
    const eval::VariantSummary& ablated_strategy,
    const StrategyStepCreditPolicy& policy = {});

} // namespace expert_robot::research
