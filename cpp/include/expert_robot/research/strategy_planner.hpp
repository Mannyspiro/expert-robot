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

    // Number of completed executions at which empirical evidence reaches
    // roughly half of its maximum influence.
    double evidence_half_saturation_attempts{6.0};

    // Soft retirement suppresses persistently poor, expensive methods without
    // deleting them. Improved future evidence can automatically restore them.
    long long soft_retirement_min_attempts{8};
    double soft_retirement_verified_rate_ceiling{0.25};
    double soft_retirement_cost_floor{0.50};
    double soft_retirement_penalty{0.18};

    // Context-specific evidence is deliberately weaker than the broad domain
    // prior until repeated matching proof states accumulate.
    double context_experience_weight{0.10};
    long long minimum_context_attempts{3};
    double context_half_saturation_attempts{4.0};

    // Small optimism bonus keeps untried methods from being permanently
    // starved by early successful strategies.
    double exploration_weight{0.03};
};

struct ResearchStrategyContext {
    std::string domain;
    double theorem_graph_coverage{0.0};
    double uncertainty{0.0};
    double route_repetition{0.0};
    long long consecutive_failures{0};

    double decomposition_value{0.0};
    double counterexample_value{0.0};
    double abstraction_value{0.0};
    double compression_value{0.0};
    double representation_switch_value{0.0};
};

[[nodiscard]] std::string research_strategy_context_key(
    const ResearchStrategyContext& context);

struct ResearchStrategyPlan {
    std::string strategy_id;
    std::string signature;
    std::string title;

    std::vector<ProofRouteKind> steps;
    ProofRouteSequence exemplar_sequence;

    double base_score{0.0};
    double evidence_confidence{0.0};
    double experience_adjustment{0.0};
    std::string context_key;
    double context_evidence_confidence{0.0};
    double context_adjustment{0.0};
    bool soft_retired{false};
    double soft_retirement_penalty{0.0};
    double exploration_bonus{0.0};
    double final_score{0.0};
};

void validate_research_strategy_planner_config(
    const ResearchStrategyPlannerConfig& config);

[[nodiscard]] std::string research_strategy_signature(
    const std::vector<ProofRouteKind>& steps);

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
        std::string_view target_domain,
        const ResearchStrategyContext* context = nullptr) const;

private:
    ResearchStrategyPlannerConfig config_;
    const RouteOutcomeLedger* memory_{nullptr};
};

} // namespace expert_robot::research
