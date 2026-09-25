#pragma once

#include "expert_robot/research/route_planner.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::research {

class RouteOutcomeLedger;

struct ResearchStrategyPlannerConfig {
    std::size_t max_output_strategies{6};

    // Bounded empirical adjustment after enough observations.
    double experience_weight{0.14};
    long long minimum_experience_attempts{3};

    // Small optimism bonus keeps untried methods from being permanently
    // starved by early successful strategies.
    double exploration_weight{0.03};
};

struct ResearchStrategyPlan {
    std::string strategy_id;
    std::string signature;
    std::string title;

    std::vector<ProofRouteKind> steps;
    ProofRouteSequence exemplar_sequence;

    double base_score{0.0};
    double experience_adjustment{0.0};
    double exploration_bonus{0.0};
    double final_score{0.0};
};

void validate_research_strategy_planner_config(
    const ResearchStrategyPlannerConfig& config);

[[nodiscard]] std::string research_strategy_signature(
    const ProofRouteSequence& sequence);

[[nodiscard]] std::string research_strategy_id(
    std::string_view signature);

[[nodiscard]] std::string research_strategy_title(
    const std::vector<ProofRouteKind>& steps);

class ResearchStrategyPlanner {
public:
    ResearchStrategyPlanner(
        ResearchStrategyPlannerConfig config = {},
        const RouteOutcomeLedger* memory = nullptr);

    [[nodiscard]] std::vector<ResearchStrategyPlan> plan(
        const std::vector<ProofRouteSequence>& sequences,
        std::string_view target_domain) const;

private:
    ResearchStrategyPlannerConfig config_;
    const RouteOutcomeLedger* memory_{nullptr};
};

} // namespace expert_robot::research
