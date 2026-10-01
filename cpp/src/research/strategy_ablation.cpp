#include "expert_robot/research/strategy_ablation.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace expert_robot::research {
namespace {

double clamp01(double value) {
    return std::clamp(value, 0.0, 1.0);
}

} // namespace

void validate_strategy_step_credit_policy(
    const StrategyStepCreditPolicy& p) {
    if (p.minimum_cases <= 0) {
        throw std::invalid_argument(
            "step-credit minimum_cases must be positive");
    }

    for (const double value : {
             p.meaningful_verified_drop,
             p.verification_weight,
             p.efficiency_weight}) {
        if (!std::isfinite(value) ||
            value < 0.0 ||
            value > 1.0) {
            throw std::invalid_argument(
                "step-credit rates/weights must be in [0,1]");
        }
    }

    if (!std::isfinite(
            p.meaningful_cost_ratio) ||
        p.meaningful_cost_ratio < 1.0) {
        throw std::invalid_argument(
            "step-credit meaningful_cost_ratio must be >= 1");
    }

    if (p.verification_weight +
            p.efficiency_weight <= 0.0) {
        throw std::invalid_argument(
            "step-credit weights must have positive total mass");
    }
}

std::vector<StrategyStepAblation>
generate_strategy_step_ablations(
    const ResearchStrategyPlan& strategy) {
    if (strategy.strategy_id.empty() ||
        strategy.signature.empty()) {
        throw std::invalid_argument(
            "step ablation requires a named parent strategy");
    }

    if (strategy.steps.size() < 2U) {
        return {};
    }

    std::vector<StrategyStepAblation> result;
    result.reserve(strategy.steps.size());

    for (std::size_t removed = 0U;
         removed < strategy.steps.size();
         ++removed) {
        std::vector<ProofRouteKind> remaining;
        remaining.reserve(
            strategy.steps.size() - 1U);

        for (std::size_t i = 0U;
             i < strategy.steps.size();
             ++i) {
            if (i != removed) {
                remaining.push_back(
                    strategy.steps[i]);
            }
        }

        const std::string signature =
            research_strategy_signature(
                remaining);

        result.push_back(
            StrategyStepAblation{
                .parent_strategy_id =
                    strategy.strategy_id,
                .parent_signature =
                    strategy.signature,
                .removed_index =
                    removed,
                .removed_kind =
                    strategy.steps[removed],
                .remaining_steps =
                    std::move(remaining),
                .ablated_signature =
                    signature,
                .ablated_strategy_id =
                    research_strategy_id(
                        signature),
            });
    }

    return result;
}

StrategyStepCredit evaluate_strategy_step_ablation(
    const StrategyStepAblation& ablation,
    const eval::VariantSummary& full_strategy,
    const eval::VariantSummary& ablated_strategy,
    const StrategyStepCreditPolicy& policy) {
    validate_strategy_step_credit_policy(
        policy);

    if (full_strategy.cases < 0 ||
        ablated_strategy.cases < 0) {
        throw std::invalid_argument(
            "step ablation case counts must be nonnegative");
    }

    StrategyStepCredit credit;
    credit.ablation = ablation;

    credit.enough_cases =
        full_strategy.cases >=
            policy.minimum_cases &&
        ablated_strategy.cases >=
            policy.minimum_cases;

    credit.verified_rate_drop =
        full_strategy.verified_rate() -
        ablated_strategy.verified_rate();

    const double full_cost =
        full_strategy.resource_cost_per_verified();
    const double ablated_cost =
        ablated_strategy.resource_cost_per_verified();

    if (std::isfinite(full_cost) &&
        full_cost > 0.0) {
        credit.ablated_cost_ratio =
            ablated_cost / full_cost;
    } else if (std::isfinite(ablated_cost)) {
        credit.ablated_cost_ratio = 1.0;
    } else {
        credit.ablated_cost_ratio =
            std::numeric_limits<double>::infinity();
    }

    credit.verification_critical =
        credit.enough_cases &&
        credit.verified_rate_drop >=
            policy.meaningful_verified_drop;

    credit.efficiency_critical =
        credit.enough_cases &&
        credit.verified_rate_drop >= 0.0 &&
        credit.ablated_cost_ratio >=
            policy.meaningful_cost_ratio;

    const double verification_component =
        clamp01(
            std::max(
                0.0,
                credit.verified_rate_drop));

    double efficiency_component = 0.0;
    if (std::isfinite(
            credit.ablated_cost_ratio) &&
        credit.ablated_cost_ratio > 1.0) {
        efficiency_component =
            clamp01(
                credit.ablated_cost_ratio -
                1.0);
    } else if (
        !std::isfinite(
            credit.ablated_cost_ratio)) {
        efficiency_component = 1.0;
    }

    const double weight_sum =
        policy.verification_weight +
        policy.efficiency_weight;

    credit.importance_score =
        credit.enough_cases
            ? clamp01(
                  (policy.verification_weight *
                       verification_component +
                   policy.efficiency_weight *
                       efficiency_component) /
                  weight_sum)
            : 0.0;

    credit.important =
        credit.verification_critical ||
        credit.efficiency_critical;

    return credit;
}

} // namespace expert_robot::research
